import json
import os
import uuid
import logging
import ssl
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parents[2] / ".env")

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[1]
LOCAL_DB_DIR = BACKEND_DIR / "local_db"
LOCAL_DB_DIR.mkdir(parents=True, exist_ok=True)


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


class LocalContainer:
    def __init__(self, name: str):
        self.name = name
        self.path = LOCAL_DB_DIR / f"{name}.json"
        if not self.path.exists():
            self.path.write_text("[]", encoding="utf-8")

    def _read_all(self) -> list[dict[str, Any]]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def _write_all(self, items: list[dict[str, Any]]) -> None:
        self.path.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")

    def read(self) -> dict[str, Any]:
        return {"id": self.name, "mode": "local"}

    def create_item(self, body: dict[str, Any]) -> dict[str, Any]:
        items = self._read_all()
        items.append(body)
        self._write_all(items)
        return body

    def upsert_item(self, body: dict[str, Any]) -> dict[str, Any]:
        items = self._read_all()
        for index, item in enumerate(items):
            if item.get("id") == body.get("id"):
                items[index] = body
                self._write_all(items)
                return body
        items.append(body)
        self._write_all(items)
        return body

    def read_item(self, item: str, partition_key: Any = None) -> dict[str, Any]:
        for doc in self._read_all():
            if doc.get("id") == item:
                return doc
        raise KeyError(f"Item not found: {item}")

    def delete_item(self, item: str, partition_key: Any = None) -> None:
        items = self._read_all()
        kept = [doc for doc in items if doc.get("id") != item]
        self._write_all(kept)

    def replace_item(self, item: str, body: dict[str, Any]) -> dict[str, Any]:
        return self.upsert_item(body)

    def query_items(
        self,
        query: str | None = None,
        parameters: list[dict[str, Any]] | None = None,
        enable_cross_partition_query: bool = False,
        partition_key: Any = None,
    ) -> list[dict[str, Any]]:
        items = self._read_all()
        params = {p["name"]: p["value"] for p in parameters or []}

        if "@engine" in params:
            items = [item for item in items if item.get("engine") == params["@engine"]]
        if "@slug" in params:
            items = [
                item
                for item in items
                if item.get("slug") == params["@slug"] or item.get("rater_slug") == params["@slug"]
            ]
        if "@uid" in params:
            items = [item for item in items if item.get("upload_id") == params["@uid"]]
        if "@id" in params:
            items = [item for item in items if item.get("id") == params["@id"]]

        if query and "ORDER BY c.calculated_at DESC" in query:
            items.sort(key=lambda item: item.get("calculated_at", ""), reverse=True)

        # Handle engine filter in raw query (e.g. "WHERE c.engine = 'excel'")
        if query and "@engine" not in params:
            import re
            engine_match = re.search(r"c\.engine\s*=\s*'(\w+)'", query or "")
            if engine_match:
                engine_val = engine_match.group(1)
                items = [item for item in items if item.get("engine") == engine_val]

        return items


# ── Partition key mapping per container ────────────────────────
_PARTITION_KEYS = {
    "raters": "/engine",
    "records": "/rater_slug",
    "sessions": "/upload_id",
}


def _make_cosmos_container(name: str):
    """Try to connect to CosmosDB Emulator. Falls back to LocalContainer
    if the SDK isn't installed or connection fails."""
    try:
        from azure.cosmos import CosmosClient, PartitionKey
        from azure.cosmos.exceptions import CosmosResourceNotFoundError
    except ImportError:
        logger.warning("azure-cosmos SDK not installed — using local JSON file DB for '%s'", name)
        return LocalContainer(name)

    endpoint = os.getenv("COSMOS_ENDPOINT")
    key = os.getenv("COSMOS_KEY")
    database_name = os.getenv("COSMOS_DB") or os.getenv("COSMOS_DATABASE")
    if not endpoint or not key or not database_name:
        logger.warning(
            "COSMOS_ENDPOINT/COSMOS_KEY/COSMOS_DB not set — using local JSON file DB for '%s'", name
        )
        return LocalContainer(name)

    try:
        # Disable SSL verification warnings for the emulator's self-signed cert
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        client = CosmosClient(url=endpoint, credential=key, connection_verify=False)

        # Auto-create database if it doesn't exist
        try:
            db = client.create_database_if_not_exists(id=database_name)
            logger.info("CosmosDB database '%s' ready", database_name)
        except Exception as db_err:
            logger.warning("Failed to create/get database '%s': %s — trying get_database_client", database_name, db_err)
            db = client.get_database_client(database_name)

        # Auto-create container with correct partition key if it doesn't exist
        partition_key_path = _PARTITION_KEYS.get(name, "/id")
        try:
            container = db.create_container_if_not_exists(
                id=name,
                partition_key=PartitionKey(path=partition_key_path),
            )
            logger.info(
                "CosmosDB container '%s' ready (partition key: %s) at %s",
                name, partition_key_path, endpoint
            )
        except Exception as container_err:
            logger.warning(
                "Failed to create container '%s': %s — trying get_container_client",
                name, container_err
            )
            container = db.get_container_client(name)

        # Quick health check — verify we can read container properties
        container.read()
        logger.info("CosmosDB container '%s' health check passed ✓", name)
        return container

    except Exception as exc:
        logger.error(
            "CosmosDB connection failed for '%s' at %s: %s — falling back to local JSON file DB",
            name, endpoint, exc
        )
        return LocalContainer(name)


raters_container = _make_cosmos_container("raters")
records_container = _make_cosmos_container("records")
sessions_container = _make_cosmos_container("sessions")

# Log which storage backend is active
for _name, _container in [("raters", raters_container), ("records", records_container), ("sessions", sessions_container)]:
    _mode = "CosmosDB" if not isinstance(_container, LocalContainer) else "Local JSON"
    logger.info("Container '%s' → %s", _name, _mode)


def create_rater(
    name: str,
    slug: str,
    engine: str,
    rater_type: str,
    config: dict[str, Any],
    workbook_blob_url: str = "",
    has_schema_sheet: bool = False,
    workbook_local_path: str = "",
) -> dict[str, Any]:
    doc = {
        "id": str(uuid.uuid4()),
        "slug": slug,
        "name": name,
        "engine": engine,
        "rater_type": rater_type,
        "config": config,
        "meta": {
            "uploadedAt": _now_iso(),
            "uploadedBy": "admin",
        },
        "workbook_blob_url": workbook_blob_url,
        "workbook_local_path": workbook_local_path,
        "has_schema_sheet": has_schema_sheet,
    }
    result = raters_container.create_item(body=doc)
    logger.info("Created rater '%s' (id=%s, engine=%s)", slug, doc["id"], engine)
    return result


def get_rater(rater_id: str, engine: str | None = None) -> dict[str, Any]:
    return raters_container.read_item(item=rater_id, partition_key=engine)


def list_raters(engine: str | None = None) -> list[dict[str, Any]]:
    if engine:
        query = "SELECT * FROM c WHERE c.engine = @engine"
        params = [{"name": "@engine", "value": engine}]
    else:
        query = "SELECT * FROM c"
        params = []
    return list(
        raters_container.query_items(
            query=query,
            parameters=params,
            enable_cross_partition_query=True,
        )
    )


def get_rater_by_slug(slug: str) -> dict[str, Any] | None:
    results = list(
        raters_container.query_items(
            query="SELECT * FROM c WHERE c.slug = @slug",
            parameters=[{"name": "@slug", "value": slug}],
            enable_cross_partition_query=True,
        )
    )
    return results[0] if results else None


def delete_rater(rater_id: str, engine: str | None = None) -> None:
    raters_container.delete_item(item=rater_id, partition_key=engine)
    logger.info("Deleted rater id=%s", rater_id)


def create_record(
    rater_slug: str,
    engine: str,
    inputs: dict[str, Any],
    outputs: dict[str, Any],
    downloaded_workbook_url: str = "",
) -> dict[str, Any]:
    doc = {
        "id": str(uuid.uuid4()),
        "rater_slug": rater_slug,
        "engine": engine,
        "inputs": inputs,
        "outputs": outputs,
        "calculated_at": _now_iso(),
        "downloaded_workbook_url": downloaded_workbook_url,
    }
    result = records_container.create_item(body=doc)
    logger.info("Created record for rater '%s' (id=%s)", rater_slug, doc["id"])
    return result


def list_records(rater_slug: str) -> list[dict[str, Any]]:
    return list(
        records_container.query_items(
            query="SELECT * FROM c WHERE c.rater_slug = @slug ORDER BY c.calculated_at DESC",
            parameters=[{"name": "@slug", "value": rater_slug}],
            partition_key=rater_slug,
        )
    )


def get_record(record_id: str, rater_slug: str) -> dict[str, Any]:
    return records_container.read_item(item=record_id, partition_key=rater_slug)


def create_session(upload_id: str, data: dict[str, Any]) -> dict[str, Any]:
    doc = {
        "id": str(uuid.uuid4()),
        "upload_id": upload_id,
        "ttl": 7200,
        "created_at": _now_iso(),
        **data,
    }
    result = sessions_container.create_item(body=doc)
    logger.info("Created session upload_id=%s", upload_id)
    return result


def get_session(session_id: str, upload_id: str | None = None) -> dict[str, Any]:
    return sessions_container.read_item(item=session_id, partition_key=upload_id)


def update_session(session_id: str, upload_id: str | None, updated_data: dict[str, Any]) -> dict[str, Any]:
    session = get_session(session_id, upload_id)
    session.update(updated_data)
    return sessions_container.replace_item(item=session_id, body=session)


def delete_session(session_id: str, upload_id: str | None = None) -> None:
    sessions_container.delete_item(item=session_id, partition_key=upload_id)
