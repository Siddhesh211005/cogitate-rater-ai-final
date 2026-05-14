from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional


def _coerce_date(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).date()
        except ValueError:
            return None
    return None


def validate_cross_fields(inputs: Any) -> Dict[str, List[Dict[str, Any]]]:
    issues: List[Dict[str, Any]] = []

    if not isinstance(inputs, dict):
        return {"issues": issues}

    start_date = _coerce_date(inputs.get("start_date"))
    end_date = _coerce_date(inputs.get("end_date"))

    if start_date and end_date and start_date >= end_date:
        issues.append(
            {
                "field": "start_date",
                "message": "start_date must be before end_date",
                "severity": "error",
            }
        )

    premium = inputs.get("premium")
    if premium is not None and isinstance(premium, (int, float)):
        if premium <= 0:
            issues.append(
                {
                    "field": "premium",
                    "message": "premium must be greater than 0",
                    "severity": "error",
                }
            )

    return {"issues": issues}
