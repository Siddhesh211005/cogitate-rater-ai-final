from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from db.cosmos import (
    list_raters,
    get_rater_by_slug,
    delete_rater,
    list_records,
    get_record
)

router = APIRouter()


# ── List all raters (both engines, unified) ───────────────────
@router.get("/")
def get_all_raters():
    try:
        raters = list_raters()
        return {
            "status": "ok",
            "count": len(raters),
            "raters": raters
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Get rater config by slug ──────────────────────────────────
@router.get("/{slug}/config")
def get_rater_config(slug: str):
    try:
        rater = get_rater_by_slug(slug)
        if not rater:
            raise HTTPException(status_code=404, detail=f"Rater '{slug}' not found")
        return {
            "status": "ok",
            "rater": rater
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Calculate — dispatches to correct engine ──────────────────
@router.post("/{slug}/calculate")
def calculate(slug: str, inputs: dict):
    try:
        rater = get_rater_by_slug(slug)
        if not rater:
            raise HTTPException(status_code=404, detail=f"Rater '{slug}' not found")

        engine = rater.get("engine")

        if engine == "schema":
            from engines.schema_engine import calculate as schema_calculate
            outputs = schema_calculate(rater, inputs)

        elif engine == "excel":
            from engines.excel_engine import calculate as excel_calculate
            outputs = excel_calculate(rater, inputs)

        else:
            raise HTTPException(status_code=400, detail=f"Unknown engine: {engine}")

        # ── Save immutable record to CosmosDB ─────────────────
        from db.cosmos import create_record
        create_record(
            rater_slug=slug,
            engine=engine,
            inputs=inputs,
            outputs=outputs
        )

        return {
            "status": "ok",
            "slug": slug,
            "engine": engine,
            "inputs": inputs,
            "outputs": outputs
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Get execution records for a rater ─────────────────────────
@router.get("/{slug}/records")
def get_rater_records(slug: str):
    try:
        records = list_records(slug)
        return {
            "status": "ok",
            "slug": slug,
            "count": len(records),
            "records": records
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Get single record ─────────────────────────────────────────
@router.get("/{slug}/records/{record_id}")
def get_single_record(slug: str, record_id: str):
    try:
        record = get_record(record_id, slug)
        if not record:
            raise HTTPException(status_code=404, detail=f"Record '{record_id}' not found")
        return {
            "status": "ok",
            "record": record
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Delete rater ──────────────────────────────────────────────
@router.delete("/{rater_id}")
def remove_rater(rater_id: str, engine: str):
    try:
        delete_rater(rater_id, engine)
        return {
            "status": "ok",
            "deleted": rater_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))