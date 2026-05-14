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


def _normalize_schema(schema: Any) -> Dict[str, Dict[str, Any]]:
    if schema is None:
        return {}

    if isinstance(schema, dict):
        return schema

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

    for key, value in inputs.items():
        if value is None:
            errors.append(f"{key} is None")
            continue

        rule = rules.get(key, {})
        expected = rule.get("type")
        if expected is not None and not _matches_type(value, expected):
            errors.append(f"{key} has type mismatch")

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
