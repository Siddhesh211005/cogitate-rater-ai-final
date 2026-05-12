import re
from pathlib import Path
from typing import Any

import openpyxl
<<<<<<< Updated upstream

=======
import os
import re
>>>>>>> Stashed changes

SCHEMA_SHEET_NAME = "_Schema"
CLASS_BUCKET_PATTERN = re.compile(r"^class\s+(?:[ivxlcdm]+|\d+)$", re.IGNORECASE)


def check_schema_sheet(filepath: str | Path) -> bool:
    try:
        wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
        found = SCHEMA_SHEET_NAME in wb.sheetnames
        wb.close()
        return found
    except Exception:
        return False


<<<<<<< Updated upstream
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
=======
# ── Parse _Schema sheet into engine-neutral config ────────────
# Config shape defined in Section 10 of context file
def parse_schema(filepath: str) -> dict:
    # Use normal mode for robust inference: PAR-style workbooks often need
    # random cell access and accurate worksheet dimensions, which are not
    # reliable in read_only mode for all files.
    wb = openpyxl.load_workbook(filepath, read_only=False, data_only=False)

    has_schema_sheet = SCHEMA_SHEET_NAME in wb.sheetnames

    if has_schema_sheet:
        config = _parse_from_schema_sheet(wb)
    else:
        config = _infer_from_workbook(wb)

    if not config.get("sheet"):
        config["sheet"] = _resolve_rater_sheet(wb)

    config = normalize_config(config)
    config["has_schema_sheet"] = has_schema_sheet

    # Store sheet names for reference
    config["sheets"] = wb.sheetnames

    wb.close()
    return config
>>>>>>> Stashed changes


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
<<<<<<< Updated upstream
        raise ValueError("_Schema sheet is empty.")

    headers = [str(header).strip().lower() if header else "" for header in rows[0]]
    inputs: list[dict[str, Any]] = []
    outputs: list[dict[str, Any]] = []
=======
        return {"inputs": [], "outputs": [], "sheet": _resolve_rater_sheet(wb)}

    # Header row: field, cell, type, label, direction, group, options, default
    headers = [str(h).strip().lower() if h else "" for h in rows[0]]

    inputs = []
    outputs = []
    seen_fields = set()
    schema_sheet = None
>>>>>>> Stashed changes

    for row in rows[1:]:
        if not any(row):
            continue

        entry = {}
<<<<<<< Updated upstream
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
=======
        for i, header in enumerate(headers):
            val = row[i] if i < len(row) else None
            entry[header] = val

        field_raw = entry.get("field")
        cell      = entry.get("cell")
        ftype     = entry.get("type", "text")
        label     = entry.get("label", field_raw)
        direction = str(entry.get("direction", "input")).lower()
        group     = entry.get("group", "General")
        options   = entry.get("options", "")
        default   = entry.get("default", "")
        row_sheet = entry.get("sheet")

        if row_sheet and not schema_sheet:
            schema_sheet = str(row_sheet).strip()

        if not cell:
            continue

        field_seed = field_raw or label or cell
        field = _unique_field_name(_sanitize_field_name(str(field_seed)), seen_fields)

        # Parse options — semicolon separated in _Schema sheet
        parsed_options = []
        if options:
            parsed_options = [o.strip() for o in str(options).split(";") if o.strip()]
>>>>>>> Stashed changes

        item: dict[str, Any] = {
            "field": field,
            "cell": cell,
            "type": field_type,
            "label": label,
            "group": group,
        }

        if direction == "output":
<<<<<<< Updated upstream
            item["primary"] = _coerce_bool(entry.get("primary")) or field == "premium"
=======
            item["primary"] = _to_bool(entry.get("primary", False))
>>>>>>> Stashed changes
            outputs.append(item)
        else:
            if options:
                item["options"] = options
                item["type"] = "dropdown"
            if default is not None:
                item["default"] = default
            inputs.append(item)

<<<<<<< Updated upstream
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

=======
    return {
        "inputs": inputs,
        "outputs": outputs,
        "sheet": schema_sheet or _resolve_rater_sheet(wb),
    }


# ── Infer schema from workbook structure (Schema engine path) ──
def _infer_from_workbook(wb) -> dict:
    # Skip hidden/utility sheets and infer from the "best" candidate sheet.
    skip = {"_schema", "application", "pick list", "concatanate", "code"}
    candidate_sheets = [
        name for name in wb.sheetnames
        if name.lower() not in skip and not name.startswith("_")
    ]

    if not candidate_sheets:
        return {"inputs": [], "outputs": [], "sheet": None}

    best_sheet = None
    best_inputs = []
    best_outputs = []
    best_score = -1

    for sheet_name in candidate_sheets:
        ws = wb[sheet_name]
        inputs, outputs = _infer_fields_from_sheet(ws)
        score = len(inputs) + len(outputs)
        lower_name = sheet_name.lower()
        if "input" in lower_name and "output" in lower_name:
            score += 10
        elif "output" in lower_name:
            score += 5
        if score > best_score:
            best_sheet = sheet_name
            best_inputs = inputs
            best_outputs = outputs
            best_score = score

    if not best_sheet:
        return {"inputs": [], "outputs": [], "sheet": None}
>>>>>>> Stashed changes

def _infer_from_workbook(wb) -> dict[str, Any]:
    rater_sheet = next((name for name in wb.sheetnames if not name.startswith("_")), None)
    return {
<<<<<<< Updated upstream
        "inputs": [],
        "outputs": [],
        "sheet": rater_sheet,
        "inferred": True,
        "note": "No _Schema sheet found. Schema inference is not production-ready for Excel COM raters.",
    }


def auto_generate_schema(filepath: str | Path) -> dict[str, Any]:
=======
        "inputs": best_inputs,
        "outputs": best_outputs,
        "sheet": best_sheet,
        "inferred": True,
    }


def _infer_fields_from_sheet(ws) -> tuple[list[dict], list[dict]]:
    # Bound scanning to the likely active area; avoids noisy trailing columns/rows.
    max_col = min(max(ws.max_column or 1, 1), 40)
    max_row = min(max(ws.max_row or 1, 1), 500)

    inputs: list[dict] = []
    outputs: list[dict] = []
    seen_fields: set[str] = set()
    seen_value_cells: set[str] = set()

    for row_num in range(1, max_row + 1):
        non_empty_cells = []
        for col_num in range(1, max_col + 1):
            cell = ws.cell(row=row_num, column=col_num)
            if _has_value(cell.value):
                non_empty_cells.append(cell)

        if len(non_empty_cells) < 2:
            continue

        for label_cell in non_empty_cells:
            label = label_cell.value
            if not _is_label_candidate(label):
                continue

            label_str = str(label).strip()
            if _is_heading_text(label_str):
                continue

            value_cell = _find_value_cell_to_right(
                ws=ws,
                row_num=row_num,
                start_col=label_cell.column,
                max_col=max_col,
                seen_value_cells=seen_value_cells,
            )
            if value_cell is None:
                continue

            section_header = _find_section_header(ws, row_num, label_cell.column, max_col)
            if _is_excluded_section(section_header):
                continue

            raw_value = value_cell.value
            field_name = _unique_field_name(_sanitize_field_name(label_str), seen_fields)
            is_output = _is_output_section(section_header) or _looks_like_formula(raw_value)
            is_number = _is_number_like(raw_value) or _looks_like_formula(raw_value)

            if is_output:
                outputs.append({
                    "field": field_name,
                    "cell": value_cell.coordinate,
                    "type": "number" if is_number else "text",
                    "label": label_str,
                    "group": "Results",
                    "default": None,
                    "primary": len(outputs) == 0,
                })
            else:
                inputs.append({
                    "field": field_name,
                    "cell": value_cell.coordinate,
                    "type": "number" if is_number else "text",
                    "label": label_str,
                    "group": "Rating Inputs",
                    "default": raw_value,
                    "options": [],
                })

            seen_value_cells.add(value_cell.coordinate)

    return inputs, outputs


def _find_value_cell_to_right(ws, row_num: int, start_col: int, max_col: int, seen_value_cells: set[str]):
    # Support organized layouts where labels and values are separated by one or more columns
    # (e.g. B label -> D value, F label -> H value).
    for col_num in range(start_col + 1, min(start_col + 4, max_col) + 1):
        candidate = ws.cell(row=row_num, column=col_num)
        if candidate.coordinate in seen_value_cells:
            continue
        if not _has_value(candidate.value):
            continue
        if _is_heading_text(str(candidate.value).strip()):
            continue
        return candidate
    return None


def _find_section_header(ws, row_num: int, col_num: int, max_col: int) -> str:
    for r in range(row_num - 1, max(0, row_num - 7), -1):
        for c in range(max(1, col_num - 2), min(max_col, col_num + 2) + 1):
            v = ws.cell(row=r, column=c).value
            if not isinstance(v, str):
                continue
            text = v.strip()
            if _is_heading_text(text):
                return text
    return ""


def _has_value(value) -> bool:
    if value is None:
        return False
    if isinstance(value, str) and not value.strip():
        return False
    return True


def _is_label_candidate(value) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if len(text) < 2:
        return False
    if text.startswith("="):
        return False
    if text.replace(".", "").replace("-", "").isdigit():
        return False
    return True


def _is_heading_text(value: str) -> bool:
    raw = value.strip().lower()
    if not raw:
        return False
    text = re.sub(r"[^a-z0-9 ]+", "", raw).strip()
    if text.startswith("please fill"):
        return True
    return text in {
        "output",
        "outputs",
        "result",
        "results",
        "input",
        "inputs",
        "boundary conditions",
        "parameter",
        "minimum",
        "maximum",
    }


def _is_output_section(header: str) -> bool:
    h = (header or "").strip().lower()
    return "output" in h or "result" in h


def _is_excluded_section(header: str) -> bool:
    h = (header or "").strip().lower()
    return "boundary" in h


def _is_number_like(value) -> bool:
    if isinstance(value, (int, float)):
        return True
    if not isinstance(value, str):
        return False
    raw = value.strip().replace(",", "").replace("$", "")
    if not raw:
        return False
    if raw.startswith("(") and raw.endswith(")"):
        raw = "-" + raw[1:-1]
    if raw.endswith("%"):
        raw = raw[:-1]
    try:
        float(raw)
        return True
    except Exception:
        return False


def _resolve_rater_sheet(wb) -> str | None:
    for name in wb.sheetnames:
        if not name.startswith("_") and name.lower() != "application":
            return name
    return wb.sheetnames[0] if wb.sheetnames else None


def _sanitize_field_name(raw: str) -> str:
    base = (
        raw.lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("-", "_")
        .replace("(", "")
        .replace(")", "")
        .replace(".", "")
        .replace(",", "")
        .replace("'", "")
        .replace("%", "pct")
        [:40]
        .strip("_")
    )
    return base or "field"


def _unique_field_name(base: str, seen: set[str]) -> str:
    candidate = base
    i = 2
    while candidate in seen:
        candidate = f"{base}_{i}"
        i += 1
    seen.add(candidate)
    return candidate


def _to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def _looks_like_formula(value) -> bool:
    return isinstance(value, str) and value.strip().startswith("=")


def normalize_config(config: dict) -> dict:
    if not isinstance(config, dict):
        return config

    normalized = dict(config)
    inputs = normalized.get("inputs")
    if isinstance(inputs, list):
        normalized["inputs"] = _normalize_class_inputs(inputs)
    return normalized


def _normalize_class_inputs(inputs: list[dict]) -> list[dict]:
    normalized_inputs: list[dict] = []
    class_options: list[str] = []
    class_field_index: int | None = None

    for field in inputs:
        field_copy = dict(field)
        label = str(field_copy.get("label", "")).strip()
        label_lower = label.lower()

        if label_lower == "class":
            if class_field_index is None:
                class_field_index = len(normalized_inputs)
                normalized_inputs.append(field_copy)
            continue

        if CLASS_BUCKET_PATTERN.match(label_lower):
            if label and label not in class_options:
                class_options.append(label)
            continue

        normalized_inputs.append(field_copy)

    if class_field_index is not None and class_options:
        class_field = normalized_inputs[class_field_index]

        existing_options = class_field.get("options") or []
        merged_options = list(existing_options)
        for option in class_options:
            if option not in merged_options:
                merged_options.append(option)

        class_field["type"] = "dropdown"
        class_field["options"] = merged_options

        default_value = class_field.get("default")
        default_str = str(default_value).strip() if default_value is not None else ""
        if (
            not default_str
            or _looks_like_formula(default_value)
            or default_str not in merged_options
        ):
            class_field["default"] = merged_options[0]

    return normalized_inputs
# ── Auto-generate _Schema from workbook (no-schema fallback) ──
# Used when admin picks "Auto-generate Schema" option
# (Section 4 of context file — no-schema fallback UI)
def auto_generate_schema(filepath: str) -> dict:
>>>>>>> Stashed changes
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

<<<<<<< Updated upstream
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
=======
    return {
        "inputs": inputs,
        "outputs": outputs,
        "sheet": rater_sheet,
        "auto_generated": True,
        "has_schema_sheet": False,
        "note": "Auto-generated schema — please review and edit field labels before saving."
    }
>>>>>>> Stashed changes
