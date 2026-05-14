from __future__ import annotations

from typing import Any, Dict


def compute_risk_score(validation_data: Any) -> Dict[str, int]:
    score = 100

    errors = []
    warnings = []

    if isinstance(validation_data, dict):
        errors = validation_data.get("errors", []) or []
        warnings = validation_data.get("warnings", []) or []

    error_count = len(errors) if isinstance(errors, list) else int(errors)
    warning_count = len(warnings) if isinstance(warnings, list) else int(warnings)

    score -= error_count * 10
    score -= warning_count * 5

    if score < 0:
        score = 0

    return {"risk_score": score}
