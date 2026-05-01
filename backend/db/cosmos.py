from azure.cosmos import CosmosClient, exceptions
from dotenv import load_dotenv
import os
import uuid
import base64
from datetime import datetime

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

# ── Fix emulator key padding issue ────────────────────────────
def fix_key(key):
    # Add padding if needed to make it valid base64
    missing = len(key) % 4
    if missing:
        key += '=' * (4 - missing)
    return key

ENDPOINT = os.getenv("COSMOS_ENDPOINT")
RAW_KEY  = os.getenv("COSMOS_KEY")
KEY      = fix_key(RAW_KEY)

# ── Client setup ──────────────────────────────────────────────
client = CosmosClient(
    url=ENDPOINT,
    credential=KEY,
    connection_verify=False  # emulator only — remove in production
)

db = client.get_database_client(os.getenv("COSMOS_DB"))

raters_container   = db.get_container_client("raters")
records_container  = db.get_container_client("records")
sessions_container = db.get_container_client("sessions")

# ── RATERS ────────────────────────────────────────────────────
def create_rater(name, slug, engine, rater_type, config, workbook_blob_url="", has_schema_sheet=False):
    doc = {
        "id": str(uuid.uuid4()),
        "slug": slug,
        "name": name,
        "engine": engine,
        "rater_type": rater_type,
        "config": config,
        "meta": {
            "uploadedAt": datetime.utcnow().isoformat(),
            "uploadedBy": "admin"
        },
        "workbook_blob_url": workbook_blob_url,
        "has_schema_sheet": has_schema_sheet
    }
    return raters_container.create_item(body=doc)


def get_rater(rater_id, engine):
    return raters_container.read_item(item=rater_id, partition_key=engine)


def list_raters(engine=None):
    if engine:
        query = "SELECT * FROM c WHERE c.engine = @engine"
        params = [{"name": "@engine", "value": engine}]
    else:
        query = "SELECT * FROM c"
        params = []
    return list(raters_container.query_items(
        query=query,
        parameters=params,
        enable_cross_partition_query=True
    ))


def get_rater_by_slug(slug):
    query = "SELECT * FROM c WHERE c.slug = @slug"
    results = list(raters_container.query_items(
        query=query,
        parameters=[{"name": "@slug", "value": slug}],
        enable_cross_partition_query=True
    ))
    return results[0] if results else None


def delete_rater(rater_id, engine):
    return raters_container.delete_item(item=rater_id, partition_key=engine)


# ── RECORDS ───────────────────────────────────────────────────
def create_record(rater_slug, engine, inputs, outputs, downloaded_workbook_url=""):
    doc = {
        "id": str(uuid.uuid4()),
        "rater_slug": rater_slug,
        "engine": engine,
        "inputs": inputs,
        "outputs": outputs,
        "calculated_at": datetime.utcnow().isoformat(),
        "downloaded_workbook_url": downloaded_workbook_url
    }
    return records_container.create_item(body=doc)


def list_records(rater_slug):
    query = "SELECT * FROM c WHERE c.rater_slug = @slug ORDER BY c.calculated_at DESC"
    return list(records_container.query_items(
        query=query,
        parameters=[{"name": "@slug", "value": rater_slug}],
        partition_key=rater_slug
    ))


def get_record(record_id, rater_slug):
    return records_container.read_item(item=record_id, partition_key=rater_slug)


# ── SESSIONS ──────────────────────────────────────────────────
def create_session(upload_id, data):
    doc = {
        "id": str(uuid.uuid4()),
        "upload_id": upload_id,
        "ttl": 7200,
        "created_at": datetime.utcnow().isoformat(),
        **data
    }
    return sessions_container.create_item(body=doc)


def get_session(session_id, upload_id):
    return sessions_container.read_item(item=session_id, partition_key=upload_id)


def update_session(session_id, upload_id, updated_data):
    session = get_session(session_id, upload_id)
    session.update(updated_data)
    return sessions_container.replace_item(item=session_id, body=session)


def delete_session(session_id, upload_id):
    return sessions_container.delete_item(item=session_id, partition_key=upload_id)