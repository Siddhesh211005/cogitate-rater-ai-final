import openpyxl
import os

SCHEMA_SHEET_NAME = "_Schema"


# ── Check if _Schema sheet exists ────────────────────────────
def check_schema_sheet(filepath: str) -> bool:
    try:
        wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
        result = SCHEMA_SHEET_NAME in wb.sheetnames
        wb.close()
        return result
    except Exception:
        return False


# ── Parse _Schema sheet into engine-neutral config ────────────
# Config shape defined in Section 10 of context file
def parse_schema(filepath: str) -> dict:
    wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)

    has_schema_sheet = SCHEMA_SHEET_NAME in wb.sheetnames

    if has_schema_sheet:
        config = _parse_from_schema_sheet(wb)
    else:
        config = _infer_from_workbook(wb)

    config["has_schema_sheet"] = has_schema_sheet

    # Store sheet names for reference
    config["sheets"] = wb.sheetnames

    wb.close()
    return config


# ── Parse from _Schema sheet (Excel engine path) ─────────────
def _parse_from_schema_sheet(wb) -> dict:
    ws = wb[SCHEMA_SHEET_NAME]
    rows = list(ws.iter_rows(values_only=True))

    if not rows:
        return {"inputs": [], "outputs": []}

    # Header row: field, cell, type, label, direction, group, options, default
    headers = [str(h).strip().lower() if h else "" for h in rows[0]]

    inputs = []
    outputs = []

    for row in rows[1:]:
        if not any(row):
            continue

        entry = {}
        for i, header in enumerate(headers):
            val = row[i] if i < len(row) else None
            entry[header] = val

        field     = entry.get("field")
        cell      = entry.get("cell")
        ftype     = entry.get("type", "text")
        label     = entry.get("label", field)
        direction = str(entry.get("direction", "input")).lower()
        group     = entry.get("group", "General")
        options   = entry.get("options", "")
        default   = entry.get("default", "")

        if not field or not cell:
            continue

        # Parse options — semicolon separated in _Schema sheet
        parsed_options = []
        if options:
            parsed_options = [o.strip() for o in str(options).split(";") if o.strip()]

        item = {
            "field":   field,
            "cell":    cell,
            "type":    ftype,
            "label":   label,
            "group":   group,
            "default": default,
        }

        if parsed_options:
            item["options"] = parsed_options

        if direction == "output":
            item["primary"] = entry.get("primary", False)
            outputs.append(item)
        else:
            inputs.append(item)

    return {"inputs": inputs, "outputs": outputs}


# ── Infer schema from workbook structure (Schema engine path) ──
def _infer_from_workbook(wb) -> dict:
    # Use first non-hidden sheet as the rater sheet
    rater_sheet = None
    for name in wb.sheetnames:
        if not name.startswith("_"):
            rater_sheet = name
            break

    if not rater_sheet:
        return {"inputs": [], "outputs": [], "sheet": None}

    ws = wb[rater_sheet]
    inputs = []
    seen_cells = set()

    for row in ws.iter_rows(values_only=True):
        for i, val in enumerate(row):
            if val is None:
                continue
            # Basic heuristic: collect non-empty string/number cells in col B
            # as candidate inputs — schema engine will refine via formulas
            col_letter = openpyxl.utils.get_column_letter(i + 1)
            if col_letter == "B" and val not in seen_cells:
                seen_cells.add(val)

    return {
        "inputs": [],   # schema engine infers these from formula graph
        "outputs": [],
        "sheet": rater_sheet,
        "inferred": True
    }


# ── Auto-generate _Schema from workbook (no-schema fallback) ──
# Used when admin picks "Auto-generate Schema" option
# (Section 4 of context file — no-schema fallback UI)
def auto_generate_schema(filepath: str) -> dict:
    wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)

    rater_sheet = None
    for name in wb.sheetnames:
        if not name.startswith("_") and name.lower() != "application":
            rater_sheet = name
            break

    if not rater_sheet:
        wb.close()
        return {"inputs": [], "outputs": [], "auto_generated": True}

    ws = wb[rater_sheet]
    inputs = []
    outputs = []
    seen = set()

    for row in ws.iter_rows():
        for cell in row:
            if cell.value is None:
                continue
            col = openpyxl.utils.get_column_letter(cell.column)
            ref = f"{col}{cell.row}"

            # Heuristic: col B = likely inputs, col C onwards with numbers = outputs
            if col == "B" and ref not in seen:
                seen.add(ref)
                val = cell.value
                ftype = "number" if isinstance(val, (int, float)) else "text"
                inputs.append({
                    "field":   f"field_{ref.lower()}",
                    "cell":    ref,
                    "type":    ftype,
                    "label":   f"Field {ref}",
                    "group":   "Auto-Generated",
                    "default": val
                })

    wb.close()

    return {
        "inputs": inputs,
        "outputs": outputs,
        "sheet": rater_sheet,
        "auto_generated": True,
        "has_schema_sheet": False,
        "note": "Auto-generated schema — please review and edit field labels before saving."
    }