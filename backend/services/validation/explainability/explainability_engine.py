from __future__ import annotations

from typing import Any, Dict, List


def generate_explanation(inputs: Any, formulas: Any) -> Dict[str, List[str]]:
    explanations: List[str] = []

    if not isinstance(inputs, dict) or not formulas:
        explanations.append("No inputs matched formulas.")
        return {"explanations": explanations}

    used_inputs = set()
    for key in inputs.keys():
        for formula in formulas:
            if isinstance(formula, str) and key in formula:
                used_inputs.add(key)
                break

    if used_inputs:
        names = ", ".join(sorted(used_inputs))
        explanations.append(f"Inputs used in formulas: {names}")
    else:
        explanations.append("No inputs matched formulas.")

    return {"explanations": explanations}
