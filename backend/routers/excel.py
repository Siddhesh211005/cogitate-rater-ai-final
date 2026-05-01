from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse
import shutil
import os
import uuid

router = APIRouter()

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), '..', 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ── Upload + parse rater (_Schema sheet based) ────────────────
@router.post("/upload")
async def upload_rater(
    file: UploadFile = File(...),
    name: str = Form(default=""),
    rater_type: str = Form(default="custom")
):
    try:
        if not file.filename.endswith(".xlsx"):
            raise HTTPException(status_code=400, detail="Only .xlsx files are supported")

        upload_id = str(uuid.uuid4())
        filename = f"{upload_id}_{file.filename}"
        filepath = os.path.join(UPLOAD_DIR, filename)

        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Check for _Schema sheet
        from services.schema_parser import parse_schema, check_schema_sheet
        has_schema_sheet = check_schema_sheet(filepath)

        if not has_schema_sheet:
            # Return fallback signal — frontend shows 3-option UI
            # (as defined in Section 4 of context file)
            return {
                "status": "no_schema",
                "no_schema_detected": True, 
                "upload_id": upload_id,
                "filepath": filepath,
                "filename": file.filename,
                "message": "No _Schema sheet found in this workbook.",
                "options": [
                    "auto_generate",   # scan + generate _Schema automatically
                    "switch_to_schema", # use schema engine instead
                    "upload_manual"     # user uploads _Schema manually
                ]
            }

        # Parse _Schema sheet
        config = parse_schema(filepath)

        # Store warm session
        from db.cosmos import create_session
        session = create_session(upload_id, {
            "filename": filename,
            "filepath": filepath,
            "original_name": file.filename,
            "name": name,
            "rater_type": rater_type,
            "engine": "excel",
            "config": config,
            "has_schema_sheet": True,
            "status": "ready"
        })

        return {
            "status": "ok",
            "upload_id": upload_id,
            "session_id": session["id"],
            "engine": "excel",
            "has_schema_sheet": True,
            "config": config
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Warm session status ───────────────────────────────────────
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
            "status": session.get("status", "warming"),
            "engine": session.get("engine"),
            "rater_slug": session.get("name", ""),
            "parsed_config": session.get("config"),
            "error_message": session.get("error_message"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
# ── Handle no-schema fallback option ─────────────────────────
@router.post("/handle-no-schema")
async def handle_no_schema(payload: dict):
    try:
        option    = payload.get("option")     # auto_generate | switch_to_schema | upload_manual
        upload_id = payload.get("upload_id")
        filepath  = payload.get("filepath")

        if option == "auto_generate":
            from services.schema_parser import auto_generate_schema
            config = auto_generate_schema(filepath)
            return {
                "status": "ok",
                "option": "auto_generate",
                "config": config,
                "message": "Schema auto-generated. Please review before saving."
            }

        elif option == "switch_to_schema":
            from services.schema_parser import parse_schema
            config = parse_schema(filepath)
            return {
                "status": "ok",
                "option": "switch_to_schema",
                "engine": "schema",
                "config": config,
                "message": "Switched to Schema Engine successfully."
            }

        elif option == "upload_manual":
            return {
                "status": "ok",
                "option": "upload_manual",
                "message": "Please re-upload the workbook with a completed _Schema sheet.",
                "template_url": "/api/excel/schema-template"
            }

        else:
            raise HTTPException(status_code=400, detail=f"Unknown option: {option}")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Test calculate from upload session ────────────────────────
@router.post("/test-calculate")
async def test_calculate(payload: dict):
    try:
        upload_id = payload.get("upload_id")
        inputs    = payload.get("inputs", {})

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

        from engines.excel_engine import calculate_from_file
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


# ── Save approved rater ───────────────────────────────────────
@router.post("/save")
async def save_rater(payload: dict):
    try:
        upload_id  = payload.get("upload_id")
        name       = payload.get("name")
        slug       = payload.get("slug")
        rater_type = payload.get("rater_type", "custom")
        config     = payload.get("config")

        if not all([upload_id, name, slug, config]):
            raise HTTPException(status_code=400, detail="Missing required fields")

        from db.cosmos import create_rater
        rater = create_rater(
            name=name,
            slug=slug,
            engine="excel",
            rater_type=rater_type,
            config=config,
            has_schema_sheet=True
        )

        return {
            "status": "ok",
            "rater_id": rater["id"],
            "slug": slug,
            "engine": "excel"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Calculate using excel engine ──────────────────────────────
@router.post("/calculate")
async def calculate(payload: dict):
    try:
        slug   = payload.get("slug")
        inputs = payload.get("inputs", {})

        if not slug:
            raise HTTPException(status_code=400, detail="Missing slug")

        from db.cosmos import get_rater_by_slug
        rater = get_rater_by_slug(slug)
        if not rater:
            raise HTTPException(status_code=404, detail=f"Rater '{slug}' not found")

        from engines.excel_engine import calculate_from_file
        outputs = calculate_from_file(
            rater.get("workbook_blob_url"),
            rater.get("config"),
            inputs
        )

        return {
            "status": "ok",
            "slug": slug,
            "inputs": inputs,
            "outputs": outputs
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── List excel engine raters ──────────────────────────────────
@router.get("/raters")
def list_excel_raters():
    try:
        from db.cosmos import list_raters
        raters = list_raters(engine="excel")
        return {
            "status": "ok",
            "count": len(raters),
            "raters": raters
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Records ───────────────────────────────────────────────────
@router.get("/records")
def list_all_records():
    try:
        from db.cosmos import records_container
        query = "SELECT * FROM c WHERE c.engine = 'excel' ORDER BY c.calculated_at DESC"
        records = list(records_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        return {
            "status": "ok",
            "count": len(records),
            "records": records
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))