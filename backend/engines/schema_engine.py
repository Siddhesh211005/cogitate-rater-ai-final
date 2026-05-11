import openpyxl
import os
import re


# ── Main calculate function ───────────────────────────────────
# Called by both /api/schema/calculate and /api/raters/{slug}/calculate
def calculate(rater: dict, inputs: dict) -> dict:
    config   = rater.get("config", {})
    filepath = rater.get("workbook_local_path") or rater.get("workbook_blob_url", "")

    if not filepath or not os.path.exists(filepath):
        raise FileNotFoundError(f"Workbook not found at: {filepath}")

    return calculate_from_file(filepath, config, inputs)


# ── Core calculation logic ────────────────────────────────────
def calculate_from_file(filepath: str, config: dict, inputs: dict) -> dict:
    wb = openpyxl.load_workbook(filepath, data_only=False)

    # Determine which sheet to use
    sheet_name = config.get("sheet")
    if not sheet_name or sheet_name not in wb.sheetnames:
        # Fall back to first non-hidden, non-schema sheet
        sheet_name = next(
            (s for s in wb.sheetnames if not s.startswith("_") and s.lower() != "application"),
            wb.sheetnames[0]
        )

    ws = wb[sheet_name]

    # ── Write inputs into workbook ────────────────────────────
    input_fields = config.get("inputs", [])
    for field_def in input_fields:
        field = field_def.get("field")
        cell  = field_def.get("cell")
        ftype = field_def.get("type", "text")

        if not cell:
            continue

        value = inputs.get(field, field_def.get("default"))

        if value is not None:
            value = _cast_value(value, ftype)
            ws[cell] = value

    # ── Save to temp file and reload with data_only ───────────
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        wb.save(tmp_path)
        wb.close()

        # Try formula evaluation with formulas library
        try:
            outputs = _evaluate_with_formulas(tmp_path, config)
        except Exception:
            # Fallback: read with openpyxl data_only
            outputs = _evaluate_with_openpyxl(tmp_path, config)

    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    return outputs


# ── Evaluate using Python formulas library ────────────────────
def _evaluate_with_formulas(filepath: str, config: dict) -> dict:
    try:
        import formulas
        xl_model = formulas.ExcelModel().loads(filepath).finish()
        xl_model.calculate()

        outputs = {}
        output_fields = config.get("outputs", [])

        # Get sheet name
        sheet_name = config.get("sheet", "Rater")

        for field_def in output_fields:
            field = field_def.get("field")
            cell  = field_def.get("cell")
            if not field or not cell:
                continue
            try:
                # formulas lib uses uppercase sheet+cell reference
                ref = f"'{sheet_name}'!{cell.upper()}"
                val = xl_model.cells.get(ref)
                if val is not None:
                    result = val.value
                    if hasattr(result, '__iter__') and not isinstance(result, str):
                        result = list(result)[0] if result else None
                    outputs[field] = _serialize(result)
                else:
                    outputs[field] = None
            except Exception:
                outputs[field] = None

        return outputs

    except ImportError:
        raise Exception("formulas library not installed")


# ── Fallback: read calculated values with openpyxl ───────────
def _evaluate_with_openpyxl(filepath: str, config: dict) -> dict:
    wb = openpyxl.load_workbook(filepath, data_only=True)

    sheet_name = config.get("sheet")
    if not sheet_name or sheet_name not in wb.sheetnames:
        sheet_name = next(
            (s for s in wb.sheetnames if not s.startswith("_")),
            wb.sheetnames[0]
        )

    ws = wb[sheet_name]
    outputs = {}

    output_fields = config.get("outputs", [])
    for field_def in output_fields:
        field = field_def.get("field")
        cell  = field_def.get("cell")
        if not field or not cell:
            continue
        try:
            outputs[field] = _serialize(ws[cell].value)
        except Exception:
            outputs[field] = None

    wb.close()
    return outputs


# ── Helpers ───────────────────────────────────────────────────
def _cast_value(value, ftype: str):
    try:
        if ftype == "number":
            return float(value)
        elif ftype == "dropdown":
            return str(value)
        else:
            return str(value)
    except Exception:
        return value


def _serialize(value):
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return round(float(value), 4)
    return str(value)
