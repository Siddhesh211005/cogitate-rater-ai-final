from fastapi import APIRouter, HTTPException, Request

from db.cosmos import delete_rater, get_record, get_rater_by_slug, list_raters, list_records


router = APIRouter()


@router.get("/")
def get_all_raters():
    raters = list_raters()
    return {"status": "ok", "count": len(raters), "raters": raters}


@router.get("/{slug}/config")
def get_rater_config(slug: str):
    rater = get_rater_by_slug(slug)
    if not rater:
        raise HTTPException(status_code=404, detail=f"Rater '{slug}' not found")
    return {
        "status": "ok",
        "rater": rater,
        "config": rater.get("config"),
    }


@router.post("/{slug}/calculate")
async def calculate(slug: str, request: Request):
    payload = await request.json()
    inputs = payload.get("inputs", payload) if isinstance(payload, dict) else {}

    rater = get_rater_by_slug(slug)
    if not rater:
        raise HTTPException(status_code=404, detail=f"Rater '{slug}' not found")

    engine = rater.get("engine")
    meta = {}

    try:
        if engine == "schema":
            from engines.schema_engine import calculate as schema_calculate

            outputs = schema_calculate(rater, inputs)
        elif engine == "excel":
            from engines.excel_engine import calculate as excel_calculate

            outputs, meta = excel_calculate(rater, inputs)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown engine: {engine}")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    from db.cosmos import create_record

    create_record(rater_slug=slug, engine=engine, inputs=inputs, outputs=outputs)

    return {
        "status": "ok",
        "slug": slug,
        "engine": engine,
        "inputs": inputs,
        "outputs": outputs,
        "timings": meta.get("timings", {}),
    }


@router.get("/{slug}/records")
def get_rater_records(slug: str):
    records = list_records(slug)
    return {"status": "ok", "slug": slug, "count": len(records), "records": records}


@router.get("/{slug}/records/{record_id}")
def get_single_record(slug: str, record_id: str):
    try:
        record = get_record(record_id, slug)
    except Exception as exc:
        raise HTTPException(status_code=404, detail=f"Record '{record_id}' not found") from exc
    return {"status": "ok", "record": record}


@router.delete("/{rater_id}")
def remove_rater(rater_id: str, engine: str | None = None):
    delete_rater(rater_id, engine)
    return {"status": "ok", "deleted": rater_id}
