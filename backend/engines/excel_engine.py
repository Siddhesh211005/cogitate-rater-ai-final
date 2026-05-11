import shutil
import time
from pathlib import Path
from typing import Any

from engines.excel_worker import ExcelWorker
from services import warm_session


BACKEND_DIR = Path(__file__).resolve().parents[1]
UPLOADS_DIR = BACKEND_DIR / "uploads"
RATERS_DIR = BACKEND_DIR / "raters"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
RATERS_DIR.mkdir(parents=True, exist_ok=True)


def build_prime_inputs(config: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for item in config.get("inputs") or []:
        field = item.get("field")
        if field and "default" in item:
            payload[field] = item.get("default")
    return payload


def prime_upload_session(upload_id: str, workbook_path: Path, config: dict[str, Any]) -> dict[str, Any]:
    worker = ExcelWorker(upload_id, workbook_path, config)
    worker.start()

    start_wait = time.time()
    while not worker.is_ready and worker.error is None:
        if time.time() - start_wait > 30:
            worker.shutdown()
            raise RuntimeError("Excel worker start timeout")
        time.sleep(0.1)

    if worker.error:
        worker.shutdown()
        raise RuntimeError(f"Failed to start Excel worker: {worker.error}")

    warm_session.set_worker(upload_id, worker)
    _, timings = worker.calculate_sync(build_prime_inputs(config), keep_file=False)
    return {"upload_id": upload_id, "timings": timings}


def run_upload_warmup(upload_id: str, workbook_path: Path, config: dict[str, Any]) -> None:
    if not warm_session.try_start_execution(upload_id, "warm-prime"):
        return
    try:
        warm_session.mark_state(upload_id, "warming")
        prime_upload_session(upload_id, workbook_path, config)
        warm_session.mark_ready(upload_id)
    except Exception as exc:
        warm_session.mark_failed(upload_id, str(exc))
    finally:
        warm_session.finish_execution(upload_id, "warm-prime")


def calculate_for_upload_session(
    upload_id: str,
    inputs: dict[str, Any],
    *,
    keep_file: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    worker = warm_session.get_worker(upload_id)
    if not worker or not worker.is_ready or worker.error:
        raise RuntimeError(f"Missing active Excel worker for upload_id: {upload_id}")

    warm_session.mark_used(upload_id)
    outputs, timings = worker.calculate_sync(inputs, keep_file=keep_file)
    return outputs, {"warm_used": True, "warm_state": "active", "timings": timings}


def calculate_from_file(
    workbook_path: str | Path,
    config: dict[str, Any],
    inputs: dict[str, Any],
    *,
    keep_file: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    path = Path(workbook_path)
    if not path.exists():
        raise FileNotFoundError(f"Workbook not found at: {path}")

    worker = warm_session.get_template_worker(path, config)
    if not worker or not worker.is_ready or worker.error:
        raise RuntimeError(f"Excel COM worker unavailable. Error: {worker.error if worker else 'worker missing'}")

    outputs, timings = worker.calculate_sync(inputs, keep_file=keep_file)
    return outputs, {"warm_used": True, "warm_state": "template-pool", "timings": timings}


def resolve_workbook_path(rater: dict[str, Any]) -> Path:
    local_path = rater.get("workbook_local_path") or rater.get("workbook_path")
    if local_path and Path(local_path).exists():
        return Path(local_path)

    blob_or_legacy = rater.get("workbook_blob_url")
    if blob_or_legacy and Path(str(blob_or_legacy)).exists():
        return Path(str(blob_or_legacy))

    raise FileNotFoundError(
        f"Workbook path missing for rater '{rater.get('slug', rater.get('id', 'unknown'))}'"
    )


def calculate(
    rater: dict[str, Any],
    inputs: dict[str, Any],
    *,
    keep_file: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    workbook_path = resolve_workbook_path(rater)
    return calculate_from_file(workbook_path, rater.get("config") or {}, inputs, keep_file=keep_file)


def persist_uploaded_workbook(upload_id: str, slug: str) -> Path:
    session = warm_session.get_session(upload_id)
    if not session:
        raise FileNotFoundError("Upload session not found or expired")

    source_path = Path(session["workbook_path"])
    if not source_path.exists():
        raise FileNotFoundError(f"Uploaded workbook not found at: {source_path}")

    target_dir = RATERS_DIR / slug
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / "template.xlsx"
    shutil.copy(source_path, target_path)
    return target_path


def shutdown_upload_session(upload_id: str) -> None:
    warm_session.delete_session(upload_id)
