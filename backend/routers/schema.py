from fastapi import APIRouter, HTTPException, UploadFile, File, Form
import shutil
import os
import uuid

router = APIRouter()

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), '..', 'uploads')
os.makedirs(UPLOAD_DIR, exist_ok=True)


# ── Upload + parse rater (no _Schema required) ────────────────
@router.post("/upload")
async def upload_rater(
    file: UploadFile = File(...),
    name: str = Form(...),
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

        # Check if _Schema sheet exists
        has_schema_sheet = config.get("has_schema_sheet", False)

        # Store session in CosmosDB
        from db.cosmos import create_session
        session = create_session(upload_id, {
            "filename": filename,
            "filepath": filepath,
            "original_name": file.filename,
            "name": name,
            "rater_type": rater_type,
            "engine": "schema",
            "config": config,
            "has_schema_sheet": has_schema_sheet,
            "status": "parsed"
        })

        return {
            "status": "ok",
            "upload_id": upload_id,
            "session_id": session["id"],
            "engine": "schema",
            "has_schema_sheet": has_schema_sheet,
            "config": config
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

        if not all([upload_id, name, slug, config]):
            raise HTTPException(status_code=400, detail="Missing required fields: upload_id, name, slug, config")

        from db.cosmos import create_rater
        rater = create_rater(
            name=name,
            slug=slug,
            engine="schema",
            rater_type=rater_type,
            config=config,
            has_schema_sheet=config.get("has_schema_sheet", False)
        )

        return {
            "status": "ok",
            "rater_id": rater["id"],
            "slug": slug,
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
        rater_id = payload.get("rater_id")
        inputs   = payload.get("inputs", {})

        if not rater_id:
            raise HTTPException(status_code=400, detail="Missing rater_id")

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