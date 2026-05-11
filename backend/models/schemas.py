"""
backend/models/schemas.py

Pydantic models for all request/response shapes across both engines.
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Field-level models (shared by both engines)
# ---------------------------------------------------------------------------

class FieldDef(BaseModel):
    field: str
    cell: str
    type: str                          # text | number | dropdown | checkbox
    label: str
    description: str = ""
    group: str = ""
    options: list[str] = []
    default: Any = None
    direction: str = "input"           # input | output
    primary: bool = False              # True for the main output (e.g. Total Premium)


class RaterConfig(BaseModel):
    slug: str
    name: str
    sheet: str
    inputs: list[FieldDef]
    outputs: list[FieldDef]


# ---------------------------------------------------------------------------
# Rater document (as stored in CosmosDB `raters` container)
# ---------------------------------------------------------------------------

class RaterDocument(BaseModel):
    id: str
    slug: str
    name: str
    engine: str                        # excel | schema
    rater_type: str = "custom"         # mpl | par | homeowners | excess | custom
    config: RaterConfig
    workbook_blob_url: str
    workbook_local_path: str = ""
    has_schema_sheet: bool = False
    meta: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Calculation request / response
# ---------------------------------------------------------------------------

class CalculateRequest(BaseModel):
    inputs: dict[str, Any]


class CalculateResponse(BaseModel):
    status: str = "ok"
    outputs: dict[str, Any]
    download_url: Optional[str] = None  # populated by Excel engine only


# ---------------------------------------------------------------------------
# Record document (CosmosDB `records` container)
# ---------------------------------------------------------------------------

class RecordDocument(BaseModel):
    id: str
    rater_slug: str
    engine: str
    inputs: dict[str, Any]
    outputs: dict[str, Any]
    calculated_at: str
    downloaded_workbook_url: Optional[str] = None


# ---------------------------------------------------------------------------
# Upload responses
# ---------------------------------------------------------------------------

class UploadResponse(BaseModel):
    status: str = "ok"
    upload_id: str
    rater_slug: str
    engine: str
    parsed_config: Optional[RaterConfig] = None
    warm_status: str = "warming"
    message: str = ""


class WarmStatusResponse(BaseModel):
    upload_id: str
    status: str                        # warming | ready | testing | saving | saved | error | not_found
    engine: Optional[str] = None
    rater_slug: Optional[str] = None
    filename: Optional[str] = None
    parsed_config: Optional[RaterConfig] = None
    test_result: Optional[dict[str, Any]] = None
    test_download_url: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ---------------------------------------------------------------------------
# Save rater request (admin confirms after review)
# ---------------------------------------------------------------------------

class SaveRaterRequest(BaseModel):
    upload_id: str
    name: str                          # admin may have edited the display name
    rater_type: str = "custom"
    config: RaterConfig                # admin may have edited labels


# ---------------------------------------------------------------------------
# Batch calculation (PAR model)
# ---------------------------------------------------------------------------

class BatchCalculateRequest(BaseModel):
    rows: list[dict[str, Any]]         # each dict is one record's inputs


class BatchCalculateResponse(BaseModel):
    status: str = "ok"
    count: int
    results: list[dict[str, Any]]      # each dict has inputs + outputs merged
    download_url: Optional[str] = None
