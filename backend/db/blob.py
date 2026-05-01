"""
backend/db/blob.py

Azure Blob Storage client for workbook file storage.
All .xlsx binaries go here. CosmosDB stores only the returned URL.

Env vars:
  AZURE_STORAGE_CONNECTION_STRING  — from Azure portal
  AZURE_STORAGE_CONTAINER          — defaults to "workbooks"
"""

from __future__ import annotations

import os
import uuid
import logging
from typing import Optional

from azure.storage.blob import (
    BlobServiceClient,
    generate_blob_sas,
    BlobSasPermissions,
)
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING", "")
CONTAINER_NAME = os.getenv("AZURE_STORAGE_CONTAINER", "workbooks")

_client: Optional[BlobServiceClient] = None


def get_blob_client() -> BlobServiceClient:
    global _client
    if _client is None:
        if not CONNECTION_STRING:
            raise RuntimeError("AZURE_STORAGE_CONNECTION_STRING not set")
        _client = BlobServiceClient.from_connection_string(CONNECTION_STRING)
    return _client


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def upload_workbook(file_bytes: bytes, filename: str, folder: str = "") -> str:
    """
    Upload an .xlsx file to Blob Storage.
    Returns the full blob URL (no SAS — use generate_download_url for that).
    
    folder: optional prefix e.g. "raters" or "records"
    """
    client = get_blob_client()
    blob_name = f"{folder}/{uuid.uuid4()}_{filename}".lstrip("/")
    blob_client = client.get_blob_client(container=CONTAINER_NAME, blob=blob_name)
    blob_client.upload_blob(file_bytes, overwrite=True)
    url = blob_client.url
    logger.info("Uploaded blob: %s", blob_name)
    return url


def download_workbook(blob_url: str) -> bytes:
    """
    Download a workbook by its full blob URL.
    Returns raw bytes.
    """
    client = get_blob_client()
    blob_name = _url_to_blob_name(blob_url)
    blob_client = client.get_blob_client(container=CONTAINER_NAME, blob=blob_name)
    data = blob_client.download_blob().readall()
    logger.info("Downloaded blob: %s", blob_name)
    return data


def delete_workbook(blob_url: str) -> bool:
    """
    Delete a workbook by its full blob URL.
    Returns True if deleted, False if not found.
    """
    client = get_blob_client()
    blob_name = _url_to_blob_name(blob_url)
    blob_client = client.get_blob_client(container=CONTAINER_NAME, blob=blob_name)
    try:
        blob_client.delete_blob()
        logger.info("Deleted blob: %s", blob_name)
        return True
    except Exception as exc:
        if "BlobNotFound" in str(exc):
            return False
        raise


def generate_download_url(blob_url: str, expiry_hours: int = 1) -> str:
    """
    Generate a time-limited SAS URL for the frontend to trigger a direct
    browser download. Default expiry: 1 hour.
    """
    client = get_blob_client()
    account_name = client.account_name
    account_key = client.credential.account_key
    blob_name = _url_to_blob_name(blob_url)

    sas_token = generate_blob_sas(
        account_name=account_name,
        container_name=CONTAINER_NAME,
        blob_name=blob_name,
        account_key=account_key,
        permission=BlobSasPermissions(read=True),
        expiry=datetime.now(timezone.utc) + timedelta(hours=expiry_hours),
    )

    return f"https://{account_name}.blob.core.windows.net/{CONTAINER_NAME}/{blob_name}?{sas_token}"


# ---------------------------------------------------------------------------
# Internal
# ---------------------------------------------------------------------------

def _url_to_blob_name(blob_url: str) -> str:
    """Extract blob name from full Azure Blob URL."""
    # URL shape: https://<account>.blob.core.windows.net/<container>/<blob_name>
    parts = blob_url.split(f"{CONTAINER_NAME}/", 1)
    if len(parts) != 2:
        raise ValueError(f"Cannot parse blob name from URL: {blob_url}")
    return parts[1].split("?")[0]  # strip SAS token if present