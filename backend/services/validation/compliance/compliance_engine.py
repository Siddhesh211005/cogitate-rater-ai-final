from __future__ import annotations

from typing import Any, Dict, List


def check_compliance(inputs: Any) -> Dict[str, List[Dict[str, Any]]]:
    compliance_issues: List[Dict[str, Any]] = []

    if not isinstance(inputs, dict):
        return {"compliance_issues": compliance_issues}

    sum_insured = inputs.get("sum_insured")
    if sum_insured is None:
        sum_insured = inputs.get("sum_insured_amount")

    if sum_insured is not None and isinstance(sum_insured, (int, float)):
        if sum_insured < 50000:
            compliance_issues.append(
                {
                    "rule": "min_sum_insured",
                    "severity": "error",
                    "message": "sum insured below 50000",
                }
            )

    return {"compliance_issues": compliance_issues}
