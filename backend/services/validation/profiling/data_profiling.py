from __future__ import annotations

from statistics import mean, pstdev
from typing import Any, Dict, List, Tuple


def _detect_outliers(values: List[float]) -> List[float]:
    if len(values) < 2:
        return []

    avg = mean(values)
    deviation = pstdev(values)
    if deviation == 0:
        return []

    limit = deviation * 3
    return [v for v in values if abs(v - avg) > limit]


def profile_data(inputs: Any) -> Dict[str, Any]:
    null_count = 0
    unique_values: Dict[str, Any] = {}
    outliers: List[Any] = []

    if inputs is None:
        return {"null_count": null_count, "unique_values": unique_values, "outliers": outliers}

    if isinstance(inputs, dict):
        for key, value in inputs.items():
            if value is None:
                null_count += 1
            unique_values[key] = len({value}) if value is not None else 0
        return {"null_count": null_count, "unique_values": unique_values, "outliers": outliers}

    if isinstance(inputs, list):
        seen_rows = set()
        for index, row in enumerate(inputs):
            if isinstance(row, dict):
                row_items = tuple(sorted(row.items()))
                if row_items in seen_rows:
                    outliers.append({"type": "duplicate", "index": index})
                seen_rows.add(row_items)
                for key, value in row.items():
                    if value is None:
                        null_count += 1
                    unique_values.setdefault(key, set()).add(value)
            else:
                if row is None:
                    null_count += 1

        for key, values in list(unique_values.items()):
            unique_values[key] = len([v for v in values if v is not None])

        numeric_values: Dict[str, List[float]] = {}
        for row in inputs:
            if isinstance(row, dict):
                for key, value in row.items():
                    if isinstance(value, (int, float)):
                        numeric_values.setdefault(key, []).append(float(value))

        for key, values in numeric_values.items():
            for outlier_value in _detect_outliers(values):
                outliers.append({"field": key, "value": outlier_value})

    return {"null_count": null_count, "unique_values": unique_values, "outliers": outliers}
