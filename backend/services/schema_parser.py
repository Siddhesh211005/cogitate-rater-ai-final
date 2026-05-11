import re
from pathlib import Path
from typing import Any

import openpyxl


SCHEMA_SHEET_NAME = "_Schema"


def check_schema_sheet(filepath: str | Path) -> bool:
    try:
        wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
        found = SCHEMA_SHEET_NAME in wb.sheetnames
        wb.close()
        return found
    except Exception:
        return False


def parse_schema(filepath: str | Path, *, require_schema_sheet: bool = False) -> dict[str, Any]:
    wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    try:
        has_schema_sheet = SCHEMA_SHEET_NAME in wb.sheetnames
        if has_schema_sheet:
            config = _parse_from_schema_sheet(wb)
        else:
            if require_schema_sheet:
                raise ValueError(
                    "No '_Schema' sheet found in this workbook. The Excel engine requires a _Schema sheet."
                )
            config = _infer_from_workbook(wb)

        config["has_schema_sheet"] = has_schema_sheet
        config["sheets"] = wb.sheetnames
        return config
    finally:
        wb.close()


def _parse_options(options_raw: Any) -> list[Any]:
    if options_raw is None or str(options_raw).strip() == "":
        return []

    parsed = []
    for part in str(options_raw).split(";"):
        text = part.strip()
        if not text:
            continue
        try:
            parsed.append(int(text))
            continue
        except ValueError:
            pass
        try:
            parsed.append(float(text))
            continue
        except ValueError:
            pass
        parsed.append(text)
    return parsed


def _parse_default(default_raw: Any, field_type: str) -> Any:
    if default_raw is None or str(default_raw).strip() == "":
        return None
    if field_type != "number":
        return default_raw

    text = str(default_raw).strip()
    try:
        return float(text) if "." in text else int(text)
    except ValueError:
        return default_raw


def _parse_from_schema_sheet(wb) -> dict[str, Any]:
    ws = wb[SCHEMA_SHEET_NAME]
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        raise ValueError("_Schema sheet is empty.")

    headers = [str(header).strip().lower() if header else "" for header in rows[0]]
    inputs: list[dict[str, Any]] = []
    outputs: list[dict[str, Any]] = []

    for row in rows[1:]:
        if not any(row):
            continue

        entry = {}
        for index, header in enumerate(headers):
            if not header:
                continue
            entry[header] = row[index] if index < len(row) else None

        field = entry.get("field")
        cell = entry.get("cell")
        if not field or not cell:
            continue

        field = str(field).strip()
        cell = str(cell).strip()
        field_type = str(entry.get("type") or "text").strip()
        direction = str(entry.get("direction") or "input").strip().lower()
        label = str(entry.get("label") or field).strip()
        group = str(entry.get("group") or "General").strip()
        options = _parse_options(entry.get("options"))
        default = _parse_default(entry.get("default"), field_type)

        item: dict[str, Any] = {
            "field": field,
            "cell": cell,
            "type": field_type,
            "label": label,
            "group": group,
        }

        if direction == "output":
            item["primary"] = _coerce_bool(entry.get("primary")) or field == "premium"
            outputs.append(item)
        else:
            if options:
                item["options"] = options
                item["type"] = "dropdown"
            if default is not None:
                item["default"] = default
            inputs.append(item)

    if not inputs and not outputs:
        raise ValueError("_Schema sheet has no usable field definitions.")

    if outputs and not any(output.get("primary") for output in outputs):
        outputs[0]["primary"] = True

    rater_sheet = next((name for name in wb.sheetnames if name != SCHEMA_SHEET_NAME), "Sheet1")
    config = {
        "sheet": rater_sheet,
        "inputs": inputs,
        "outputs": outputs,
    }
    _inject_schedule_mode(config)
    return config


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _infer_from_workbook(wb) -> dict[str, Any]:
    rater_sheet = next((name for name in wb.sheetnames if not name.startswith("_")), None)
    return {
        "inputs": [],
        "outputs": [],
        "sheet": rater_sheet,
        "inferred": True,
        "note": "No _Schema sheet found. Schema inference is not production-ready for Excel COM raters.",
    }


def auto_generate_schema(filepath: str | Path) -> dict[str, Any]:
    wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    try:
        rater_sheet = next(
            (name for name in wb.sheetnames if not name.startswith("_") and name.lower() != "application"),
            None,
        )
        if not rater_sheet:
            return {"inputs": [], "outputs": [], "auto_generated": True}

        ws = wb[rater_sheet]
        inputs = []

        for row in ws.iter_rows():
            for cell in row:
                if cell.value is None:
                    continue
                col = openpyxl.utils.get_column_letter(cell.column)
                if col != "B":
                    continue
                ref = f"{col}{cell.row}"
                value = cell.value
                inputs.append(
                    {
                        "field": f"field_{ref.lower()}",
                        "cell": ref,
                        "type": "number" if isinstance(value, (int, float)) else "text",
                        "label": f"Field {ref}",
                        "group": "Auto-Generated",
                        "default": value,
                    }
                )

        return {
            "inputs": inputs,
            "outputs": [],
            "sheet": rater_sheet,
            "auto_generated": True,
            "has_schema_sheet": False,
            "note": "Auto-generated schema. Review and edit field labels and outputs before saving.",
        }
    finally:
        wb.close()


def _inject_schedule_mode(config: dict[str, Any]) -> None:
    inputs = config.get("inputs") or []
    if not inputs:
        return

    row_map: dict[int, dict[str, dict[str, Any]]] = {}
    for item in inputs:
        cell = str(item.get("cell") or "").strip().upper()
        match = re.match(r"^([A-Z]+)(\d+)$", cell)
        if not match:
            continue
        col, row_text = match.groups()
        row_map.setdefault(int(row_text), {})[col] = item

    schedule_rows = sorted(row for row, cols in row_map.items() if "D" in cols)
    if not schedule_rows:
        return

    blocks = []
    start = schedule_rows[0]
    previous = schedule_rows[0]
    for row in schedule_rows[1:]:
        if row == previous + 1:
            previous = row
            continue
        blocks.append((start, previous))
        start = row
        previous = row
    blocks.append((start, previous))

    schedules = []
    for index, (row_start, row_end) in enumerate(blocks, 1):
        if row_end - row_start + 1 < 3:
            continue

        d_meta = row_map[row_start].get("D", {})
        e_meta = {}
        for row in range(row_start, row_end + 1):
            if "E" in row_map.get(row, {}):
                e_meta = row_map[row].get("E", {})
                break

        group_name = str(d_meta.get("group") or "Coverage")
        key_base = re.sub(r"[^a-z0-9]+", "_", group_name.lower()).strip("_")
        key = f"{key_base}_{row_start}_{row_end}" if key_base else f"schedule_{index}"

        schedules.append(
            {
                "key": key,
                "title": f"{group_name} ({row_start}-{row_end})",
                "rowStart": row_start,
                "rowEnd": row_end,
                "allowBlankRows": True,
                "minActiveRows": 1,
                "columns": [
                    {
                        "field": "location",
                        "column": "D",
                        "type": d_meta.get("type", "text"),
                        "label": str(d_meta.get("label") or "Location #"),
                    },
                    {
                        "field": "expiring_risk_limit",
                        "column": "E",
                        "type": e_meta.get("type", "number"),
                        "label": str(e_meta.get("label") or "Risk Limit"),
                    },
                ],
            }
        )

    if not schedules:
        return

    config["mode"] = "schedule"
    config["writeRules"] = {
        "clearUnusedRows": True,
        "emptyCellWrite": "blank",
        "rowActivePolicy": "any-non-empty-cell",
    }
    config["schedules"] = schedules
