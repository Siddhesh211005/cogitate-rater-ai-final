<<<<<<< Updated upstream
from fastapi import APIRouter, HTTPException, Request

from db.cosmos import delete_rater, get_record, get_rater_by_slug, list_raters, list_records

=======
from fastapi import APIRouter, HTTPException
from db.cosmos import (
    list_raters,
    get_rater_by_slug,
    delete_rater,
    list_records,
    get_record
)
>>>>>>> Stashed changes

router = APIRouter()


@router.get("/")
def get_all_raters():
    raters = list_raters()
    return {"status": "ok", "count": len(raters), "raters": raters}


@router.get("/{slug}/config")
def get_rater_config(slug: str):
<<<<<<< Updated upstream
    rater = get_rater_by_slug(slug)
    if not rater:
        raise HTTPException(status_code=404, detail=f"Rater '{slug}' not found")
    return {
        "status": "ok",
        "rater": rater,
        "config": rater.get("config"),
    }
=======
    try:
        rater = get_rater_by_slug(slug)
        if not rater:
            raise HTTPException(status_code=404, detail=f"Rater '{slug}' not found")

        from services.schema_parser import normalize_config
        normalized_config = normalize_config(rater.get("config"))
        rater_payload = {**rater, "config": normalized_config}

        return {
            "status": "ok",
            "config": normalized_config,
            "rater": rater_payload
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
>>>>>>> Stashed changes


@router.post("/{slug}/calculate")
<<<<<<< Updated upstream
async def calculate(slug: str, request: Request):
    payload = await request.json()
    inputs = payload.get("inputs", payload) if isinstance(payload, dict) else {}

    rater = get_rater_by_slug(slug)
    if not rater:
        raise HTTPException(status_code=404, detail=f"Rater '{slug}' not found")

    engine = rater.get("engine")
    meta = {}

    try:
=======
def calculate(slug: str, payload: dict):
    try:
        rater = get_rater_by_slug(slug)
        if not rater:
            raise HTTPException(status_code=404, detail=f"Rater '{slug}' not found")

        inputs = payload.get("inputs", payload)
        if not isinstance(inputs, dict):
            raise HTTPException(status_code=400, detail="Invalid calculate payload")

        engine = rater.get("engine")

>>>>>>> Stashed changes
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
<<<<<<< Updated upstream
    delete_rater(rater_id, engine)
    return {"status": "ok", "deleted": rater_id}
=======
    try:
        if not engine:
            from db.cosmos import raters_container
            query = "SELECT c.engine FROM c WHERE c.id = @id"
            results = list(raters_container.query_items(
                query=query,
                parameters=[{"name": "@id", "value": rater_id}],
                enable_cross_partition_query=True
            ))
            if not results:
                raise HTTPException(status_code=404, detail=f"Rater '{rater_id}' not found")
            engine = results[0].get("engine")

        delete_rater(rater_id, engine)
        return {
            "status": "ok",
            "deleted": rater_id
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
>>>>>>> Stashed changes
