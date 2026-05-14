from __future__ import annotations

from typing import Any, Dict, List


def _get_premium(output: Any) -> Any:
    if isinstance(output, dict):
        for key in ("premium", "total_premium", "rate"):
            if key in output:
                return output.get(key)
    return None


def compare_raters(current_output: Any, other_outputs: Any) -> Dict[str, List[Dict[str, Any]]]:
    differences: List[Dict[str, Any]] = []

    current_premium = _get_premium(current_output)

    if not isinstance(other_outputs, list):
        return {"differences": differences}

    for index, other in enumerate(other_outputs):
        other_premium = _get_premium(other)
        if isinstance(current_premium, (int, float)) and isinstance(other_premium, (int, float)):
            differences.append(
                {
                    "index": index,
                    "current": current_premium,
                    "other": other_premium,
                    "difference": other_premium - current_premium,
                }
            )

    return {"differences": differences}
