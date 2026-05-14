from __future__ import annotations

from typing import Any, Dict, List, Set


def _extract_fields(schema: Any) -> Set[str]:
    if schema is None:
        return set()

    if isinstance(schema, dict):
        return set(schema.keys())

    fields = []
    if hasattr(schema, "input_fields"):
        fields = getattr(schema, "input_fields") or []
    elif hasattr(schema, "fields"):
        fields = getattr(schema, "fields") or []

    names = set()
    for field in fields:
        name = (
            getattr(field, "name", None)
            or getattr(field, "field_name", None)
            or getattr(field, "key", None)
        )
        if name:
            names.add(name)

    return names


def detect_schema_drift(schema: Any, previous_schema: Any = None) -> Dict[str, List[str]]:
    current_fields = _extract_fields(schema)
    previous_fields = _extract_fields(previous_schema)

    added = sorted(list(current_fields - previous_fields))
    removed = sorted(list(previous_fields - current_fields))

    return {"added": added, "removed": removed}
