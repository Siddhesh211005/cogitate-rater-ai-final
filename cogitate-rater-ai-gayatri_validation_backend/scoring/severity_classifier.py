from __future__ import annotations

from typing import Any, Dict, List


def _bucket_for_issue(issue: Any) -> str:
    if isinstance(issue, dict):
        severity = (
            issue.get("severity")
            or issue.get("level")
            or issue.get("type")
            or ""
        )
        severity = str(severity).lower()
    else:
        severity = str(issue).lower()

    if "critical" in severity or "error" in severity:
        return "critical"
    if "warn" in severity:
        return "warning"

    return "info"


def classify_issues(all_issues: Any) -> Dict[str, List[Any]]:
    buckets: Dict[str, List[Any]] = {
        "critical": [],
        "warning": [],
        "info": [],
    }

    if not all_issues:
        return buckets

    for issue in all_issues:
        bucket = _bucket_for_issue(issue)
        buckets[bucket].append(issue)

    return buckets
