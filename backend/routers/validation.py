from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter

from backend.services.validation.core.newvalidator import enterprise_validate

router = APIRouter()


def _load_workbook_bytes(config: Any) -> tuple[bytes | None, str | None]:
    if not isinstance(config, dict):
        return None, "config must be an object"

    workbook_path = (
        config.get("workbook_local_path")
        or config.get("workbook_path")
        or config.get("filepath")
    )
    if not workbook_path:
        return None, "workbook_local_path missing"

    path = Path(str(workbook_path))
    if not path.exists():
        return None, "workbook path not found"

    return path.read_bytes(), None


@router.post("/validate")
async def validate(payload: dict):
    inputs = payload.get("inputs") if isinstance(payload, dict) else {}
    config = payload.get("config") if isinstance(payload, dict) else {}

    file_content, error = _load_workbook_bytes(config)
    if file_content is None:
        return {
            "status": "ok",
            "validation": {
                "status": "skipped",
                "reason": error or "workbook not available",
            },
        }

    validation = enterprise_validate(inputs, file_content, schema=config)

    return {
        "status": "ok",
        "validation": validation,
    }
