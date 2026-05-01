"""
backend/services/warm_session.py

Warm Session Management Service
================================
Manages transient upload/review session state in CosmosDB `sessions` container.
Sessions have a 2-hour TTL (configured at CosmosDB container level) and are
partitioned by upload_id.

Session lifecycle:
  1. Created at upload time with status="warming" + initial parse results
  2. Polled via GET /api/excel/warm-status/{upload_id}
  3. Updated to status="ready" once warm + workbook is open in COM
  4. Updated with test-calculate results, download URLs, etc.
  5. Promoted to saved rater (status="saved") on admin confirmation
  6. Auto-purged by CosmosDB TTL after 2 hours

Status values:
  warming   → workbook is being opened / COM warming up
  ready     → workbook open, COM session live, ready for test-calculate
  testing   → test-calculate in progress
  saving    → being written to raters container + blob
  saved     → persisted, session no longer needed (will TTL out)
  error     → something went wrong; error_message populated
"""

from __future__ import annotations

import uuid
import time
import logging
from datetime import datetime, timezone
from typing import Optional, Any

from backend.db.cosmos import get_container

logger = logging.getLogger(__name__)

SESSIONS_CONTAINER = "sessions"

# TTL we write into each document (seconds). Must be ≤ the container-level
# default TTL. Set to 7200 = 2 hours.
SESSION_TTL_SECONDS = 7200


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _container():
    """Return the sessions CosmosDB container client."""
    return get_container(SESSIONS_CONTAINER)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def create_session(
    *,
    upload_id: Optional[str] = None,
    rater_slug: str,
    engine: str,
    filename: str,
    blob_url: str,
    parsed_config: Optional[dict] = None,
    status: str = "warming",
    extra: Optional[dict] = None,
) -> dict:
    """
    Create a new warm session document in CosmosDB.

    Parameters
    ----------
    upload_id   : Caller-supplied ID (used as document id + partition key).
                  If None, a new UUID4 is generated.
    rater_slug  : Slug of the rater being uploaded (may be tentative).
    engine      : "excel" | "schema"
    filename    : Original filename of the uploaded workbook.
    blob_url    : Azure Blob URL of the uploaded workbook.
    parsed_config: Initial parsed inputs/outputs config (may be None if
                  parsing happens asynchronously after session creation).
    status      : Initial status string (default "warming").
    extra       : Any additional key/value pairs to merge into the document.

    Returns
    -------
    The created session document dict.
    """
    if upload_id is None:
        upload_id = str(uuid.uuid4())

    doc: dict[str, Any] = {
        "id": upload_id,
        "upload_id": upload_id,       # explicit field for query convenience
        "rater_slug": rater_slug,
        "engine": engine,
        "filename": filename,
        "blob_url": blob_url,
        "parsed_config": parsed_config,
        "status": status,
        "error_message": None,
        "test_result": None,
        "test_download_url": None,
        "created_at": _now_iso(),
        "updated_at": _now_iso(),
        "ttl": SESSION_TTL_SECONDS,   # CosmosDB honours this per-document TTL
    }

    if extra:
        doc.update(extra)

    container = _container()
    container.upsert_item(doc)
    logger.info("Session created: upload_id=%s engine=%s status=%s", upload_id, engine, status)
    return doc


async def get_session(upload_id: str) -> Optional[dict]:
    """
    Fetch a session document by upload_id.

    Returns None if not found (expired or never existed).
    """
    container = _container()
    try:
        item = container.read_item(item=upload_id, partition_key=upload_id)
        return item
    except Exception as exc:
        # CosmosDB raises a CosmosResourceNotFoundError (404) when missing.
        if "404" in str(exc) or "NotFound" in type(exc).__name__:
            return None
        raise


async def update_session(upload_id: str, **fields) -> Optional[dict]:
    """
    Patch specific fields on an existing session document.

    Unknown upload_ids are silently ignored (session may have TTL'd out).

    Usage:
        await update_session(upload_id, status="ready", parsed_config={...})
        await update_session(upload_id, status="error", error_message="COM failed")
    """
    container = _container()
    try:
        doc = container.read_item(item=upload_id, partition_key=upload_id)
    except Exception as exc:
        if "404" in str(exc) or "NotFound" in type(exc).__name__:
            logger.warning("update_session: upload_id=%s not found (TTL'd?)", upload_id)
            return None
        raise

    for key, value in fields.items():
        doc[key] = value
    doc["updated_at"] = _now_iso()
    # Refresh TTL on every update so active sessions don't expire mid-flow.
    doc["ttl"] = SESSION_TTL_SECONDS

    container.upsert_item(doc)
    logger.info("Session updated: upload_id=%s fields=%s", upload_id, list(fields.keys()))
    return doc


async def set_status(upload_id: str, status: str, **extra_fields) -> Optional[dict]:
    """
    Convenience wrapper — update only the status (+ any extra fields).

    Examples
    --------
    await set_status(upload_id, "ready")
    await set_status(upload_id, "error", error_message="Excel COM unavailable")
    await set_status(upload_id, "testing")
    await set_status(upload_id, "saved")
    """
    return await update_session(upload_id, status=status, **extra_fields)


async def set_ready(upload_id: str, parsed_config: dict) -> Optional[dict]:
    """
    Mark session as ready after warm-up completes; attach final parsed config.
    Called by excel_engine once the workbook COM session is live.
    """
    return await update_session(
        upload_id,
        status="ready",
        parsed_config=parsed_config,
    )


async def set_error(upload_id: str, message: str) -> Optional[dict]:
    """Mark session as errored with a human-readable message."""
    return await update_session(
        upload_id,
        status="error",
        error_message=message,
    )


async def record_test_result(
    upload_id: str,
    test_inputs: dict,
    test_outputs: dict,
    download_url: Optional[str] = None,
) -> Optional[dict]:
    """
    Store the result of a test-calculate run in the session.

    Parameters
    ----------
    upload_id     : Session ID.
    test_inputs   : The inputs dict that was sent.
    test_outputs  : The outputs dict returned by the engine.
    download_url  : Blob URL of the calculated workbook (Excel engine only).
    """
    test_result = {
        "inputs": test_inputs,
        "outputs": test_outputs,
        "calculated_at": _now_iso(),
    }
    return await update_session(
        upload_id,
        status="ready",             # back to ready after test completes
        test_result=test_result,
        test_download_url=download_url,
    )


async def mark_saved(upload_id: str, rater_id: str, rater_slug: str) -> Optional[dict]:
    """
    Mark session as saved after the rater has been persisted to CosmosDB.
    The session will still TTL out normally; this is just a state marker.
    """
    return await update_session(
        upload_id,
        status="saved",
        saved_rater_id=rater_id,
        saved_rater_slug=rater_slug,
    )


async def delete_session(upload_id: str) -> bool:
    """
    Explicitly delete a session document (e.g. on admin cancel).
    Returns True if deleted, False if already gone.
    """
    container = _container()
    try:
        container.delete_item(item=upload_id, partition_key=upload_id)
        logger.info("Session deleted: upload_id=%s", upload_id)
        return True
    except Exception as exc:
        if "404" in str(exc) or "NotFound" in type(exc).__name__:
            return False
        raise


# ---------------------------------------------------------------------------
# Status polling helper (used by the router)
# ---------------------------------------------------------------------------

async def get_warm_status(upload_id: str) -> dict:
    """
    Return a clean status payload suitable for the frontend polling endpoint.

    Response shape:
    {
        "upload_id": "...",
        "status": "warming | ready | testing | saving | saved | error",
        "engine": "excel | schema",
        "rater_slug": "...",
        "parsed_config": { ... } | null,
        "test_result": { ... } | null,
        "test_download_url": "..." | null,
        "error_message": "..." | null,
        "created_at": "ISO",
        "updated_at": "ISO"
    }

    If the session is not found (expired or bad ID), returns:
    {
        "upload_id": "...",
        "status": "not_found",
        "error_message": "Session not found or expired."
    }
    """
    session = await get_session(upload_id)

    if session is None:
        return {
            "upload_id": upload_id,
            "status": "not_found",
            "error_message": "Session not found or expired.",
        }

    return {
        "upload_id": upload_id,
        "status": session.get("status"),
        "engine": session.get("engine"),
        "rater_slug": session.get("rater_slug"),
        "filename": session.get("filename"),
        "parsed_config": session.get("parsed_config"),
        "test_result": session.get("test_result"),
        "test_download_url": session.get("test_download_url"),
        "error_message": session.get("error_message"),
        "created_at": session.get("created_at"),
        "updated_at": session.get("updated_at"),
    }


# ---------------------------------------------------------------------------
# Async warm-up launcher (called from upload endpoint background task)
# ---------------------------------------------------------------------------

async def run_warm_up(
    upload_id: str,
    blob_url: str,
    engine: str,
    parsed_config: dict,
) -> None:
    """
    Background task: perform any slow warm-up work, then flip status to "ready".

    For the Excel engine this is where we could pre-open the COM workbook
    (if a persistent COM session approach is used). For now it records the
    parsed config and marks the session ready — actual COM opening happens
    at calculate time, which is fast enough for the current design.

    For the schema engine, the `formulas` model is preloaded at startup, so
    there's nothing to warm here beyond storing the config.

    This function is intentionally lightweight. If a future design keeps a
    live COM process resident between test-calculate calls, the heavy work
    (subprocess.Popen, win32com init) would go here.
    """
    try:
        logger.info("Warm-up start: upload_id=%s engine=%s", upload_id, engine)

        if engine == "excel":
            # Placeholder for COM pre-open logic.
            # For now, just a brief yield to simulate async work.
            import asyncio
            await asyncio.sleep(0.1)

        elif engine == "schema":
            # Schema engine is preloaded at app startup.
            pass

        await set_ready(upload_id, parsed_config=parsed_config)
        logger.info("Warm-up complete: upload_id=%s status=ready", upload_id)

    except Exception as exc:
        logger.exception("Warm-up failed: upload_id=%s", upload_id)
        await set_error(upload_id, message=str(exc))