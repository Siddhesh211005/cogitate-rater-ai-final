import queue
import threading
import time
from pathlib import Path
from typing import Any

try:
    import pythoncom
    import win32com.client
except ImportError:  # pragma: no cover - exercised only on non-Windows/dev boxes
    pythoncom = None
    win32com = None


def coerce_by_type(value: Any, value_type: str) -> Any:
    if value is None:
        return None
    if value_type != "number":
        return value
    if isinstance(value, (int, float)):
        return value
    text = str(value).strip()
    if text == "":
        return None
    try:
        return float(text) if "." in text else int(text)
    except ValueError:
        return value


class ComWorksheetAdapter:
    def __init__(self, ws):
        self.ws = ws

    def __setitem__(self, key: str, value: Any) -> None:
        self.ws.Range(key).Value = value


def write_schedule_inputs(ws, config: dict[str, Any], input_data: dict[str, Any]) -> set[str]:
    schedule_defs = config.get("schedules") or []
    if not schedule_defs:
        return set()

    schedule_payload = input_data.get("schedules") or input_data.get("_schedules")
    if not isinstance(schedule_payload, dict):
        return set()

    write_rules = config.get("writeRules") or {}
    clear_unused = bool(write_rules.get("clearUnusedRows", True))
    controlled_cells: set[str] = set()

    for sched in schedule_defs:
        key = sched.get("key")
        row_start = sched.get("rowStart")
        row_end = sched.get("rowEnd")
        columns = sched.get("columns") or []
        if not key or not isinstance(row_start, int) or not isinstance(row_end, int):
            continue
        if row_end < row_start:
            continue

        rows_data = schedule_payload.get(key) or []
        if not isinstance(rows_data, list):
            rows_data = []

        for idx, row_num in enumerate(range(row_start, row_end + 1)):
            row_data = rows_data[idx] if idx < len(rows_data) and isinstance(rows_data[idx], dict) else {}
            row_active = any(v not in (None, "") for v in row_data.values())

            for col_def in columns:
                col = col_def.get("column")
                field = col_def.get("field")
                if not col or not field:
                    continue

                cell_ref = f"{col}{row_num}"
                controlled_cells.add(cell_ref)

                if row_active and field in row_data:
                    ws[cell_ref] = coerce_by_type(row_data.get(field), col_def.get("type", "text"))
                elif clear_unused:
                    ws[cell_ref] = None

    return controlled_cells


class ExcelWorker(threading.Thread):
    def __init__(self, worker_id: str, workbook_path: Path, config: dict[str, Any]):
        super().__init__(name=f"ExcelWorker-{worker_id}")
        self.worker_id = worker_id
        self.workbook_path = str(Path(workbook_path).resolve()).replace("/", "\\")
        self.config = config
        self.request_queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self.response_queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self.daemon = True
        self.is_ready = False
        self.error: str | None = None

    def run(self) -> None:
        if pythoncom is None or win32com is None:
            self.error = "pywin32 is not installed or Microsoft Excel COM is unavailable."
            self.response_queue.put({"status": "error", "error": self.error})
            return

        try:
            pythoncom.CoInitialize()
            self.app = win32com.client.DispatchEx("Excel.Application")
            self.app.Visible = False
            self.app.DisplayAlerts = False

            self.wb = self.app.Workbooks.Open(
                self.workbook_path,
                UpdateLinks=0,
                ReadOnly=True,
                IgnoreReadOnlyRecommended=True,
                CorruptLoad=1,
            )
            # -4135 = xlCalculationManual. We explicitly calculate on each request.
            self.app.Calculation = -4135

            self.sheet_name = self.config.get("sheet") or self._first_visible_sheet_name()
            self.input_map = {
                item["field"]: item["cell"]
                for item in self.config.get("inputs", [])
                if item.get("field") and item.get("cell")
            }
            self.input_type_map = {
                item["field"]: item.get("type", "text")
                for item in self.config.get("inputs", [])
                if item.get("field")
            }
            self.output_map = {
                item["field"]: item["cell"]
                for item in self.config.get("outputs", [])
                if item.get("field") and item.get("cell")
            }

            self.is_ready = True

            while True:
                msg = self.request_queue.get()
                if msg["type"] == "shutdown":
                    break
                if msg["type"] != "calculate":
                    continue

                try:
                    outputs, timings, out_file = self._do_calculation(
                        msg.get("inputs") or {},
                        keep_file=bool(msg.get("keep_file", False)),
                    )
                    self.response_queue.put(
                        {
                            "status": "success",
                            "outputs": outputs,
                            "timings": timings,
                            "out_file": out_file,
                        }
                    )
                except Exception as exc:
                    self.response_queue.put({"status": "error", "error": str(exc)})

        except Exception as exc:
            self.error = str(exc)
            self.response_queue.put({"status": "error", "error": self.error})
        finally:
            try:
                if hasattr(self, "wb"):
                    self.wb.Close(SaveChanges=False)
                if hasattr(self, "app"):
                    self.app.Quit()
            except Exception:
                pass
            if pythoncom is not None:
                pythoncom.CoUninitialize()

    def _first_visible_sheet_name(self) -> str:
        return self.wb.Worksheets(1).Name

    def _write_cell(self, default_sheet_name: str, cell_ref: str, value: Any) -> None:
        if "!" in cell_ref:
            sheet_part, coord = cell_ref.split("!", 1)
            self.wb.Sheets(sheet_part.strip("'\"")).Range(coord).Value = value
        else:
            self.wb.Sheets(default_sheet_name).Range(cell_ref).Value = value

    def _read_cell(self, default_sheet_name: str, cell_ref: str) -> Any:
        if "!" in cell_ref:
            sheet_part, coord = cell_ref.split("!", 1)
            return self.wb.Sheets(sheet_part.strip("'\"")).Range(coord).Value
        return self.wb.Sheets(default_sheet_name).Range(cell_ref).Value

    def _do_calculation(
        self,
        input_data: dict[str, Any],
        keep_file: bool = False,
    ) -> tuple[dict[str, Any], dict[str, float], str]:
        total_start = time.perf_counter()
        timings = {
            "write_ms": 0.0,
            "calc_ms": 0.0,
            "read_ms": 0.0,
            "total_ms": 0.0,
        }
        out_file = ""

        write_start = time.perf_counter()
        ws_adapter = ComWorksheetAdapter(self.wb.Sheets(self.sheet_name))
        schedule_cells = write_schedule_inputs(ws_adapter, self.config, input_data)

        for field, value in input_data.items():
            if field in {"schedules", "_schedules"}:
                continue
            cell_ref = self.input_map.get(field)
            if cell_ref and cell_ref not in schedule_cells:
                self._write_cell(
                    self.sheet_name,
                    cell_ref,
                    coerce_by_type(value, self.input_type_map.get(field, "text")),
                )
        timings["write_ms"] = round((time.perf_counter() - write_start) * 1000, 3)

        calc_start = time.perf_counter()
        self.app.Calculate()
        timings["calc_ms"] = round((time.perf_counter() - calc_start) * 1000, 3)

        read_start = time.perf_counter()
        outputs: dict[str, Any] = {}
        for field, cell_ref in self.output_map.items():
            value = self._read_cell(self.sheet_name, cell_ref)
            if isinstance(value, float):
                value = round(value, 4)
            outputs[field] = value
        timings["read_ms"] = round((time.perf_counter() - read_start) * 1000, 3)

        if keep_file:
            import tempfile
            import uuid

            output_dir = Path(tempfile.gettempdir()) / "cogitate_rater_sessions" / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"{uuid.uuid4()}.xlsx"
            self.wb.SaveCopyAs(str(output_path.resolve()))
            out_file = str(output_path)
            outputs["_output_file"] = out_file

        timings["total_ms"] = round((time.perf_counter() - total_start) * 1000, 3)
        return outputs, timings, out_file

    def calculate_sync(
        self,
        input_data: dict[str, Any],
        keep_file: bool = False,
        timeout: float = 60.0,
    ) -> tuple[dict[str, Any], dict[str, float]]:
        if not self.is_ready:
            if self.error:
                raise RuntimeError(f"Excel worker failed to start: {self.error}")
            raise RuntimeError("Excel worker is not ready yet")

        self.request_queue.put(
            {
                "type": "calculate",
                "inputs": input_data,
                "keep_file": keep_file,
            }
        )

        try:
            response = self.response_queue.get(timeout=timeout)
        except queue.Empty as exc:
            raise TimeoutError("Excel calculation timed out") from exc

        if response.get("status") == "error":
            raise RuntimeError(response.get("error") or "Excel calculation failed")

        return response["outputs"], response["timings"]

    def shutdown(self) -> None:
        self.request_queue.put({"type": "shutdown"})
        self.join(timeout=5.0)
