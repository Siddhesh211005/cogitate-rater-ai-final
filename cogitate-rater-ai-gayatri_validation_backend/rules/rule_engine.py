from __future__ import annotations

from typing import Any, Dict, List


def run_business_rules(inputs: Any) -> Dict[str, List[Dict[str, Any]]]:
    rules_triggered: List[Dict[str, Any]] = []

    if not isinstance(inputs, dict):
        return {"rules_triggered": rules_triggered}

    age = inputs.get("age")
    if age is not None and isinstance(age, (int, float)) and age > 60:
        rules_triggered.append(
            {"rule": "age_over_60", "severity": "warning", "message": "age > 60"}
        )

    required_fields = inputs.get("required_fields")
    if isinstance(required_fields, list):
        for field in required_fields:
            if field not in inputs or inputs.get(field) is None:
                rules_triggered.append(
                    {
                        "rule": "missing_required_field",
                        "severity": "error",
                        "field": field,
                        "message": "missing required field",
                    }
                )

    return {"rules_triggered": rules_triggered}
