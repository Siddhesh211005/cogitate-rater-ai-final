from fastapi import APIRouter, HTTPException, UploadFile, File, Form
import shutil
import os
import uuid
import re

router = APIRouter()

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), '..', 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return cleaned or "rater"


def _resolve_unique_slug(seed: str) -> str:
    from db.cosmos import get_rater_by_slug

    base = _slugify(seed)
    candidate = base
    index = 2
    while get_rater_by_slug(candidate):
        candidate = f"{base}-{index}"
        index += 1
    return candidate


# ── Upload + parse rater (no _Schema required) ────────────────
@router.post("/upload")
async def upload_rater(
    file: UploadFile = File(...),
    name: str = Form(default=""),
    rater_type: str = Form(default="custom")
):
    try:
        # Validate file type
        if not file.filename.endswith(".xlsx"):
            raise HTTPException(status_code=400, detail="Only .xlsx files are supported")

        # Save uploaded file
        upload_id = str(uuid.uuid4())
        filename = f"{upload_id}_{file.filename}"
        filepath = os.path.join(UPLOAD_DIR, filename)

        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Parse schema from workbook
        from services.schema_parser import parse_schema
        config = parse_schema(filepath)
        config["name"] = name or os.path.splitext(file.filename)[0]
        config["slug"] = _slugify(name or os.path.splitext(file.filename)[0])

        # Check if _Schema sheet exists
        has_schema_sheet = config.get("has_schema_sheet", False)
        if not has_schema_sheet:
            from services.nim_enrichment import enrich_fields, enrich_outputs

            config["inputs"] = await enrich_fields(config.get("inputs") or [])
            config["outputs"] = await enrich_outputs(config.get("outputs") or [])

        # Store session in CosmosDB
        from db.cosmos import create_session
        session = create_session(upload_id, {
            "filename": filename,
            "filepath": filepath,
            "original_name": file.filename,
            "name": name or os.path.splitext(file.filename)[0],
            "rater_type": rater_type,
            "engine": "schema",
            "config": config,
            "has_schema_sheet": has_schema_sheet,
            "status": "ready"   # ← was "parsed"
        })

        return {
            "status": "ok",
            "upload_id": upload_id,
            "session_id": session["id"],
            "engine": "schema",
            "has_schema_sheet": has_schema_sheet,
            "config": config,
            "parsed_config": config,
            "rater_slug": (name or os.path.splitext(file.filename)[0]).lower().replace(" ", "-")
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Save approved rater to CosmosDB ──────────────────────────
@router.post("/save")
async def save_rater(payload: dict):
    try:
        upload_id   = payload.get("upload_id")
        name        = payload.get("name")
        slug        = payload.get("slug")
        rater_type  = payload.get("rater_type", "custom")
        config      = payload.get("config")

        if not all([upload_id, name, config]):
            raise HTTPException(status_code=400, detail="Missing required fields: upload_id, name, config")

        from db.cosmos import sessions_container
        query = "SELECT * FROM c WHERE c.upload_id = @uid"
        results = list(sessions_container.query_items(
            query=query,
            parameters=[{"name": "@uid", "value": upload_id}],
            enable_cross_partition_query=True
        ))
        if not results:
            raise HTTPException(status_code=404, detail="Upload session not found")

        session = results[0]
        filepath = session.get("filepath")
        if not filepath:
            raise HTTPException(status_code=400, detail="Workbook filepath missing in upload session")

        resolved_slug = _resolve_unique_slug(slug or config.get("slug") or name)
        config["slug"] = resolved_slug
        config["name"] = name

        from db.cosmos import create_rater
        from db.cosmos import sessions_container
        query = "SELECT * FROM c WHERE c.upload_id = @uid"
        results = list(sessions_container.query_items(
            query=query,
            parameters=[{"name": "@uid", "value": upload_id}],
            enable_cross_partition_query=True
        ))
        workbook_local_path = results[0].get("filepath", "") if results else ""

        rater = create_rater(
            name=name,
            slug=resolved_slug,
            engine="schema",
            rater_type=rater_type,
            config=config,
            workbook_blob_url=filepath,
            workbook_local_path=workbook_local_path,
            has_schema_sheet=session.get("has_schema_sheet", config.get("has_schema_sheet", False))
        )

        return {
            "status": "ok",
            "rater_id": rater["id"],
            "slug": resolved_slug,
            "engine": "schema"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Calculate using schema engine ─────────────────────────────
@router.post("/calculate")
async def calculate(payload: dict):
    try:
        rater_id = payload.get("slug") or payload.get("rater_id")
        inputs   = payload.get("inputs", payload)

        if not isinstance(inputs, dict):
            raise HTTPException(status_code=400, detail="Invalid calculate payload")

        if not rater_id:
            raise HTTPException(status_code=400, detail="Missing slug or rater_id")

        from db.cosmos import get_rater_by_slug
        rater = get_rater_by_slug(rater_id)
        if not rater:
            raise HTTPException(status_code=404, detail=f"Rater '{rater_id}' not found")

        from engines.schema_engine import calculate as schema_calculate
        outputs = schema_calculate(rater, inputs)

        return {
            "status": "ok",
            "inputs": inputs,
            "outputs": outputs
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── List schema engine raters ─────────────────────────────────
@router.get("/raters")
def list_schema_raters():
    try:
        from db.cosmos import list_raters
        raters = list_raters(engine="schema")
        return {
            "status": "ok",
            "count": len(raters),
            "raters": raters
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Delete schema rater ───────────────────────────────────────
@router.delete("/raters/{rater_id}")
def delete_schema_rater(rater_id: str):
    try:
        from db.cosmos import delete_rater
        delete_rater(rater_id, "schema")
        return {
            "status": "ok",
            "deleted": rater_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.post("/test-calculate")
async def test_calculate(payload: dict):
    try:
        upload_id = payload.get("upload_id")
        inputs    = payload.get("inputs", {})

        if not upload_id:
            raise HTTPException(status_code=400, detail="Missing upload_id")

        from db.cosmos import sessions_container
        query = "SELECT * FROM c WHERE c.upload_id = @uid"
        results = list(sessions_container.query_items(
            query=query,
            parameters=[{"name": "@uid", "value": upload_id}],
            enable_cross_partition_query=True
        ))
        if not results:
            raise HTTPException(status_code=404, detail="Session not found")

        session  = results[0]
        filepath = session.get("filepath")
        config   = session.get("config")

        from engines.schema_engine import calculate_from_file
        outputs = calculate_from_file(filepath, config, inputs)

        return {
            "status": "ok",
            "upload_id": upload_id,
            "inputs": inputs,
            "outputs": outputs
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
   
@router.get("/warm-status/{upload_id}")
def warm_status(upload_id: str):
    try:
        from db.cosmos import sessions_container
        query = "SELECT * FROM c WHERE c.upload_id = @uid"
        results = list(sessions_container.query_items(
            query=query,
            parameters=[{"name": "@uid", "value": upload_id}],
            enable_cross_partition_query=True
        ))
        if not results:
            raise HTTPException(status_code=404, detail="Session not found")

        session = results[0]
        return {
            "upload_id": upload_id,
            "status": session.get("status", "ready"),
            "engine": session.get("engine"),
            "rater_slug": session.get("name", ""),
            "parsed_config": session.get("config"),
            "error_message": session.get("error_message"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
