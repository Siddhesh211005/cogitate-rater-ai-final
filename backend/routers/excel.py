<<<<<<< Updated upstream
import re
=======
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
>>>>>>> Stashed changes
import shutil
import time
import uuid
<<<<<<< Updated upstream
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from engines import excel_engine
from services import warm_session
from services.schema_parser import auto_generate_schema, check_schema_sheet, parse_schema

=======
import re
>>>>>>> Stashed changes

router = APIRouter()

BACKEND_DIR = Path(__file__).resolve().parents[1]
UPLOAD_DIR = BACKEND_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or f"rater-{uuid.uuid4().hex[:8]}"


def _http_excel_error(exc: Exception) -> HTTPException:
    detail = str(exc)
    status = 503 if "COM" in detail or "Excel" in detail or "pywin32" in detail else 500
    return HTTPException(status_code=status, detail=detail)


<<<<<<< Updated upstream
=======
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


# ── Upload + parse rater (_Schema sheet based) ────────────────
>>>>>>> Stashed changes
@router.post("/upload")
async def upload_rater(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    name: str = Form(default=""),
    rater_type: str = Form(default="custom"),
):
    if not file.filename or not file.filename.lower().endswith((".xlsx", ".xlsm", ".xls")):
        raise HTTPException(status_code=400, detail="Only Excel workbook files are supported")

    upload_id = str(uuid.uuid4())
    upload_path = UPLOAD_DIR / f"{upload_id}.xlsx"

<<<<<<< Updated upstream
    with open(upload_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
=======
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
        config["name"] = name or os.path.splitext(file.filename)[0]
        config["slug"] = _slugify(name or os.path.splitext(file.filename)[0])

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
>>>>>>> Stashed changes

    if not check_schema_sheet(upload_path):
        return {
            "status": "no_schema",
            "no_schema_detected": True,
            "upload_id": upload_id,
            "filepath": str(upload_path),
            "filename": file.filename,
            "message": "No _Schema sheet found in this workbook.",
            "options": ["auto_generate", "switch_to_schema", "upload_manual"],
        }

    try:
        config = parse_schema(upload_path, require_schema_sheet=True)
    except ValueError as exc:
        upload_path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        upload_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Error parsing Excel schema: {exc}") from exc

    warm_session.expire_old_sessions()
    warm_session.create_session(
        upload_id,
        upload_path,
        config,
        filename=file.filename,
        name=name or Path(file.filename).stem,
        rater_type=rater_type,
        status="warming",
    )
    background_tasks.add_task(excel_engine.run_upload_warmup, upload_id, upload_path, config)

    return {
        "status": "ok",
        "upload_id": upload_id,
        "engine": "excel",
        "has_schema_sheet": True,
        "config": config,
        "parsed_config": config,
        "warm_status": "warming",
        "rater_slug": _slugify(name or Path(file.filename).stem),
    }


@router.get("/warm-status/{upload_id}")
def warm_status(upload_id: str):
    warm_session.expire_old_sessions()
    session = warm_session.get_session(upload_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    return {
        "upload_id": upload_id,
        "status": session.get("status", "missing"),
        "engine": session.get("engine"),
        "rater_slug": _slugify(session.get("name") or session.get("filename") or upload_id),
        "filename": session.get("filename"),
        "parsed_config": session.get("config"),
        "config": session.get("config"),
        "error_message": session.get("error_message"),
        "active_operation": session.get("active_operation"),
        "created_at": session.get("created_at"),
        "last_used_at": session.get("last_used_at"),
    }


@router.post("/handle-no-schema")
async def handle_no_schema(payload: dict, background_tasks: BackgroundTasks):
    option = payload.get("option")
    filepath = payload.get("filepath")
    upload_id = payload.get("upload_id") or str(uuid.uuid4())

    if option == "upload_manual":
        return {
            "status": "ok",
            "option": "upload_manual",
            "message": "Please re-upload the workbook with a completed _Schema sheet.",
        }

    if not filepath or not Path(filepath).exists():
        raise HTTPException(status_code=404, detail="Uploaded workbook not found")

    if option == "auto_generate":
        config = auto_generate_schema(filepath)
        path = Path(filepath)
        warm_session.create_session(
            upload_id,
            path,
            config,
            filename=path.name,
            name=path.stem,
            status="warming",
        )
        background_tasks.add_task(excel_engine.run_upload_warmup, upload_id, path, config)
        return {
            "status": "ok",
            "option": "auto_generate",
            "upload_id": upload_id,
            "engine": "excel",
            "config": config,
            "warm_status": "warming",
            "message": "Schema auto-generated. Please review before saving.",
        }

    if option == "switch_to_schema":
        config = parse_schema(filepath, require_schema_sheet=False)
        from db.cosmos import create_session

        path = Path(filepath)
        create_session(upload_id, {
            "filename": path.name,
            "filepath": str(path),
            "original_name": path.name,
            "name": path.stem,
            "rater_type": "custom",
            "engine": "schema",
            "config": config,
            "has_schema_sheet": False,
            "status": "parsed",
        })
        return {
            "status": "ok",
            "option": "switch_to_schema",
            "upload_id": upload_id,
            "engine": "schema",
            "config": config,
            "message": "Switched to Schema Engine.",
        }

    raise HTTPException(status_code=400, detail=f"Unknown no-schema option: {option}")


@router.post("/test-calculate")
async def test_calculate(payload: dict):
    upload_id = payload.get("upload_id")
    inputs = payload.get("inputs", {})
    if not upload_id:
        raise HTTPException(status_code=400, detail="upload_id is required")

    if not warm_session.try_start_execution(upload_id, "test-calculate"):
        session = warm_session.get_session(upload_id)
        active = session.get("active_operation") if session else "another operation"
        raise HTTPException(status_code=409, detail=f"Calculation already in progress ({active})")

    try:
        outputs, meta = excel_engine.calculate_for_upload_session(upload_id, inputs)
    except Exception as exc:
        raise _http_excel_error(exc) from exc
    finally:
        warm_session.finish_execution(upload_id, "test-calculate")

<<<<<<< Updated upstream
    return {
        "status": "ok",
        "upload_id": upload_id,
        "inputs": inputs,
        "outputs": outputs,
        "warm_used": meta.get("warm_used", False),
        "warm_state": meta.get("warm_state"),
        "timings": meta.get("timings", {}),
    }
=======
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
>>>>>>> Stashed changes


@router.post("/test-download")
async def test_download(payload: dict):
    upload_id = payload.get("upload_id")
    inputs = payload.get("inputs", {})
    if not upload_id:
        raise HTTPException(status_code=400, detail="upload_id is required")

    if not warm_session.try_start_execution(upload_id, "test-download"):
        session = warm_session.get_session(upload_id)
        active = session.get("active_operation") if session else "another operation"
        raise HTTPException(status_code=409, detail=f"Calculation already in progress ({active})")

    try:
        outputs, _ = excel_engine.calculate_for_upload_session(upload_id, inputs, keep_file=True)
    except Exception as exc:
        raise _http_excel_error(exc) from exc
    finally:
        warm_session.finish_execution(upload_id, "test-download")

    output_path = outputs.get("_output_file")
    if not output_path or not Path(output_path).exists():
        raise HTTPException(status_code=500, detail="Output file not found")

    return FileResponse(
        path=output_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename="test_calculated.xlsx",
    )


@router.post("/save")
async def save_rater(payload: dict):
    upload_id = payload.get("upload_id")
    name = payload.get("name") or ""
    slug = payload.get("slug") or _slugify(name)
    rater_type = payload.get("rater_type", "custom")
    config = payload.get("config")

    if not upload_id or not slug or not config:
        raise HTTPException(status_code=400, detail="upload_id, slug, and config are required")

    from db.cosmos import create_rater, get_rater_by_slug

    if get_rater_by_slug(slug):
        raise HTTPException(status_code=409, detail=f"Rater '{slug}' already exists")

    session = warm_session.get_session(upload_id)
    if not session:
        raise HTTPException(status_code=404, detail="Upload session not found or expired")
    source_path = Path(session["workbook_path"])
    if not source_path.exists():
        raise HTTPException(status_code=404, detail="Uploaded workbook file not found")

    excel_engine.shutdown_upload_session(upload_id)
    time.sleep(1.0)

    try:
        target_dir = excel_engine.RATERS_DIR / slug
        target_dir.mkdir(parents=True, exist_ok=True)
        workbook_path = target_dir / "template.xlsx"
        shutil.copy(source_path, workbook_path)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to persist workbook: {exc}") from exc

<<<<<<< Updated upstream
    rater = create_rater(
        name=name or slug,
        slug=slug,
        engine="excel",
        rater_type=rater_type,
        config=config,
        workbook_local_path=str(workbook_path),
        has_schema_sheet=True,
    )

    return {
        "status": "ok",
        "rater_id": rater["id"],
        "slug": slug,
        "engine": "excel",
        "workbook_local_path": str(workbook_path),
    }
=======
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
        rater = create_rater(
            name=name,
            slug=resolved_slug,
            engine="excel",
            rater_type=rater_type,
            config=config,
            workbook_blob_url=filepath,
            has_schema_sheet=session.get("has_schema_sheet", True)
        )

        return {
            "status": "ok",
            "rater_id": rater["id"],
            "slug": resolved_slug,
            "engine": "excel"
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
>>>>>>> Stashed changes


@router.post("/calculate")
async def calculate(payload: dict):
    slug = payload.get("slug")
    inputs = payload.get("inputs", {})
    if not slug:
        raise HTTPException(status_code=400, detail="Missing slug")

    from db.cosmos import get_rater_by_slug

    rater = get_rater_by_slug(slug)
    if not rater:
        raise HTTPException(status_code=404, detail=f"Rater '{slug}' not found")

    try:
<<<<<<< Updated upstream
        outputs, meta = excel_engine.calculate(rater, inputs)
    except Exception as exc:
        raise _http_excel_error(exc) from exc

    return {
        "status": "ok",
        "slug": slug,
        "inputs": inputs,
        "outputs": outputs,
        "timings": meta.get("timings", {}),
    }
=======
        slug   = payload.get("slug")
        inputs = payload.get("inputs", payload)

        if not slug:
            raise HTTPException(status_code=400, detail="Missing slug")
        if not isinstance(inputs, dict):
            raise HTTPException(status_code=400, detail="Invalid calculate payload")

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
>>>>>>> Stashed changes


@router.get("/raters")
def list_excel_raters():
    from db.cosmos import list_raters

    raters = list_raters(engine="excel")
    return {"status": "ok", "count": len(raters), "raters": raters}


@router.get("/records")
def list_all_records():
<<<<<<< Updated upstream
    from db.cosmos import records_container

    records = list(
        records_container.query_items(
            query="SELECT * FROM c WHERE c.engine = 'excel' ORDER BY c.calculated_at DESC",
            enable_cross_partition_query=True,
        )
    )
    return {"status": "ok", "count": len(records), "records": records}
=======
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
>>>>>>> Stashed changes
