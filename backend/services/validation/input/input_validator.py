from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict


_TYPE_MAP = {
    "int": int,
    "integer": int,
    "float": float,
    "number": (int, float),
    "str": str,
    "string": str,
    "bool": bool,
    "boolean": bool,
    "date": date,
    "datetime": datetime,
}

_NUMERIC_FIELD_HINTS = (
    "year",
    "limit",
    "premium",
    "deductible",
    "amount",
    "factor",
    "surcharge",
    "rate",
    "score",
)

_SEMANTIC_NUMERIC_HINTS = _NUMERIC_FIELD_HINTS + (
    "value",
    "cost",
    "age",
    "construction",
)


def _normalize_schema(schema: Any) -> Dict[str, Dict[str, Any]]:
    if schema is None:
        return {}

    if isinstance(schema, dict):
        inputs = schema.get("inputs") if isinstance(schema.get("inputs"), list) else None
        if not inputs:
            return schema

        rules: Dict[str, Dict[str, Any]] = {}
        for field in inputs:
            if not isinstance(field, dict):
                continue
            name = field.get("field") or field.get("name") or field.get("key")
            if not name:
                continue
            rule: Dict[str, Any] = {}
            if "type" in field:
                rule["type"] = field.get("type")
            if "min" in field:
                rule["min"] = field.get("min")
            if "max" in field:
                rule["max"] = field.get("max")
            if "required" in field:
                rule["required"] = field.get("required")
            rules[name] = rule

        return rules

    fields = []
    if hasattr(schema, "input_fields"):
        fields = getattr(schema, "input_fields") or []
    elif hasattr(schema, "fields"):
        fields = getattr(schema, "fields") or []

    rules: Dict[str, Dict[str, Any]] = {}

    for field in fields:
        name = (
            getattr(field, "name", None)
            or getattr(field, "field_name", None)
            or getattr(field, "key", None)
        )
        if not name:
            continue

        rule: Dict[str, Any] = {}
        if hasattr(field, "type"):
            rule["type"] = getattr(field, "type")
        if hasattr(field, "data_type"):
            rule["type"] = getattr(field, "data_type")
        if hasattr(field, "min"):
            rule["min"] = getattr(field, "min")
        if hasattr(field, "min_value"):
            rule["min"] = getattr(field, "min_value")
        if hasattr(field, "minimum"):
            rule["min"] = getattr(field, "minimum")
        if hasattr(field, "max"):
            rule["max"] = getattr(field, "max")
        if hasattr(field, "max_value"):
            rule["max"] = getattr(field, "max_value")
        if hasattr(field, "maximum"):
            rule["max"] = getattr(field, "maximum")
        if hasattr(field, "required"):
            rule["required"] = getattr(field, "required")

        rules[name] = rule

    return rules


def _matches_type(value: Any, expected: Any) -> bool:
    if expected is None:
        return True

    if isinstance(expected, str):
        expected_type = _TYPE_MAP.get(expected.lower())
        if expected_type is None:
            return True
        expected = expected_type

    if expected is int:
        return isinstance(value, int) and not isinstance(value, bool)

    return isinstance(value, expected)


def _is_empty_value(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def _looks_numeric_field(field_name: str) -> bool:
    name = str(field_name).lower()
    return any(token in name for token in _NUMERIC_FIELD_HINTS)


def _semantic_hint(text: str) -> bool:
    lowered = str(text).lower()
    return any(token in lowered for token in _SEMANTIC_NUMERIC_HINTS)


def _is_numeric_value(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "")
        if cleaned == "":
            return False
        try:
            float(cleaned)
            return True
        except ValueError:
            return False
    return False


def _build_semantic_map(schema: Any) -> Dict[str, Dict[str, Any]]:
    if not isinstance(schema, dict):
        return {}

    inputs = schema.get("inputs")
    if not isinstance(inputs, list):
        return {}

    semantic_map: Dict[str, Dict[str, Any]] = {}
    for field in inputs:
        if not isinstance(field, dict):
            continue
        field_key = field.get("field")
        if not field_key:
            continue
        semantic_map[field_key] = {
            "label": field.get("label") or field_key,
            "description": field.get("description") or "",
            "type": field.get("type"),
        }

    return semantic_map


def _display_name(field_key: str, semantic: Dict[str, Any] | None) -> str:
    if semantic and semantic.get("label"):
        return str(semantic.get("label"))
    return field_key


def _is_placeholder(value: Any, semantic: Dict[str, Any] | None) -> bool:
    if not isinstance(value, str) or not semantic:
        return False
    label = semantic.get("label")
    if not label:
        return False
    return value.strip().lower() == str(label).strip().lower()


def validate_inputs(inputs: Any, schema: Any) -> Dict[str, Any]:
    errors = []
    warnings = []

    if inputs is None:
        errors.append("inputs is None")
        return {"errors": errors, "warnings": warnings, "valid": False}

    if not isinstance(inputs, dict):
        errors.append("inputs must be a dict")
        return {"errors": errors, "warnings": warnings, "valid": False}

    rules = _normalize_schema(schema)
    semantic_map = _build_semantic_map(schema)

    for key, value in inputs.items():
        semantic = semantic_map.get(key)
        display_name = _display_name(key, semantic)

        if _is_empty_value(value):
            errors.append(f"{display_name} cannot be empty")
            continue

        rule = rules.get(key, {})
        expected = rule.get("type")
        numeric_expected = False
        if expected is not None:
            if isinstance(expected, str) and expected.lower() in {"int", "integer", "float", "number"}:
                numeric_expected = True
            elif expected in (int, float) or expected == (int, float):
                numeric_expected = True

        if not numeric_expected and semantic:
            if _semantic_hint(semantic.get("label", "")):
                numeric_expected = True
            elif _semantic_hint(semantic.get("description", "")):
                numeric_expected = True
            elif semantic.get("type") and str(semantic.get("type")).lower() in {"int", "integer", "float", "number"}:
                numeric_expected = True

        if numeric_expected or _looks_numeric_field(key):
            if _is_placeholder(value, semantic):
                errors.append(f"{display_name} must be numeric")
                continue
            if not _is_numeric_value(value):
                errors.append(f"{display_name} must be numeric")
                continue

        if expected is not None and not _matches_type(value, expected):
            errors.append(f"{display_name} has type mismatch")

        min_val = rule.get("min")
        max_val = rule.get("max")
        if min_val is not None and isinstance(value, (int, float)):
            if value < min_val:
                errors.append(f"{key} below minimum")
        if max_val is not None and isinstance(value, (int, float)):
            if value > max_val:
                errors.append(f"{key} above maximum")

    for field_name, rule in rules.items():
        if rule.get("required") and field_name not in inputs:
            errors.append(f"{field_name} missing required field")

    valid = len(errors) == 0

    return {"errors": errors, "warnings": warnings, "valid": valid}
