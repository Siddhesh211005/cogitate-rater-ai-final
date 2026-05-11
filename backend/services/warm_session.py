import hashlib
import json
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engines.excel_worker import ExcelWorker


SESSION_TTL_SECONDS = 7200

_lock = threading.RLock()
_sessions: dict[str, dict[str, Any]] = {}
_workers: dict[str, Any] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _copy_json(value: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(value))


def compute_config_hash(config: dict[str, Any]) -> str:
    payload = json.dumps(config, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def create_session(
    upload_id: str,
    workbook_path: Path,
    config: dict[str, Any],
    *,
    engine: str = "excel",
    filename: str = "",
    name: str = "",
    rater_type: str = "custom",
    status: str = "warming",
) -> dict[str, Any]:
    now = time.time()
    doc = {
        "upload_id": upload_id,
        "workbook_path": str(workbook_path),
        "filename": filename,
        "name": name,
        "rater_type": rater_type,
        "engine": engine,
        "config": _copy_json(config),
        "config_hash": compute_config_hash(config),
        "status": status,
        "error_message": None,
        "active_operation": None,
        "created_at": _now_iso(),
        "created_at_ts": now,
        "updated_at": _now_iso(),
        "last_used_at": None,
        "last_used_at_ts": None,
    }
    with _lock:
        _sessions[upload_id] = doc
        return dict(doc)


def get_session(upload_id: str) -> dict[str, Any] | None:
    with _lock:
        doc = _sessions.get(upload_id)
        return dict(doc) if doc else None


def get_session_config(upload_id: str) -> dict[str, Any] | None:
    with _lock:
        doc = _sessions.get(upload_id)
        if not doc or not isinstance(doc.get("config"), dict):
            return None
        return _copy_json(doc["config"])


def update_session_config(upload_id: str, config: dict[str, Any]) -> dict[str, Any] | None:
    with _lock:
        doc = _sessions.get(upload_id)
        if not doc:
            return None
        doc["config"] = _copy_json(config)
        doc["config_hash"] = compute_config_hash(config)
        doc["updated_at"] = _now_iso()
        return dict(doc)


def mark_state(upload_id: str, status: str, error_message: str | None = None) -> dict[str, Any] | None:
    with _lock:
        doc = _sessions.get(upload_id)
        if not doc:
            return None
        doc["status"] = status
        doc["error_message"] = error_message
        doc["updated_at"] = _now_iso()
        return dict(doc)


def mark_ready(upload_id: str) -> dict[str, Any] | None:
    return mark_state(upload_id, "ready")


def mark_failed(upload_id: str, error_message: str) -> dict[str, Any] | None:
    return mark_state(upload_id, "failed", error_message)


def mark_used(upload_id: str) -> dict[str, Any] | None:
    now = time.time()
    with _lock:
        doc = _sessions.get(upload_id)
        if not doc:
            return None
        doc["last_used_at"] = _now_iso()
        doc["last_used_at_ts"] = now
        doc["updated_at"] = _now_iso()
        return dict(doc)


def try_start_execution(upload_id: str, operation: str) -> bool:
    with _lock:
        doc = _sessions.get(upload_id)
        if not doc:
            return False
        if doc.get("active_operation"):
            return False
        doc["active_operation"] = operation
        doc["active_operation_started_at"] = _now_iso()
        doc["updated_at"] = _now_iso()
        return True


def finish_execution(upload_id: str, operation: str | None = None) -> None:
    with _lock:
        doc = _sessions.get(upload_id)
        if not doc:
            return
        if operation and doc.get("active_operation") not in {None, operation}:
            return
        doc["active_operation"] = None
        doc["active_operation_started_at"] = None
        doc["updated_at"] = _now_iso()


def set_worker(key: str, worker: Any) -> None:
    with _lock:
        _workers[key] = worker


def get_worker(key: str) -> Any:
    with _lock:
        return _workers.get(key)


def cleanup_worker(key: str) -> None:
    with _lock:
        worker = _workers.pop(key, None)
    if worker:
        threading.Thread(target=worker.shutdown, daemon=True).start()


def delete_session(upload_id: str) -> bool:
    cleanup_worker(upload_id)
    with _lock:
        return _sessions.pop(upload_id, None) is not None


def expire_old_sessions(ttl_sec: int = SESSION_TTL_SECONDS) -> list[str]:
    now = time.time()
    expired: list[str] = []

    with _lock:
        for upload_id, doc in list(_sessions.items()):
            created = float(doc.get("created_at_ts") or 0)
            if now - created > ttl_sec:
                expired.append(upload_id)
                _sessions.pop(upload_id, None)

    for upload_id in expired:
        cleanup_worker(upload_id)

    return expired


class TemplateWorkerPool:
    def __init__(self, size: int, name_prefix: str, template_path: Path, config: dict[str, Any]):
        self.workers: list[ExcelWorker] = []
        self.error: str | None = None
        self.is_ready = False
        self._lock = threading.Lock()

        for index in range(size):
            worker = ExcelWorker(f"{name_prefix}-{index}", template_path, config)
            worker.start()
            self.workers.append(worker)

        start = time.time()
        while True:
            if all(worker.is_ready or worker.error for worker in self.workers):
                break
            if time.time() - start > 60:
                self.error = "Excel worker pool start timeout"
                for worker in self.workers:
                    worker.shutdown()
                return
            time.sleep(0.1)

        errors = [worker.error for worker in self.workers if worker.error]
        if errors:
            self.error = errors[0]
            for worker in self.workers:
                worker.shutdown()
            return

        self.is_ready = True

    def calculate_sync(
        self,
        inputs: dict[str, Any],
        *,
        keep_file: bool = False,
        timeout: float = 60.0,
    ) -> tuple[dict[str, Any], dict[str, float]]:
        with self._lock:
            worker = min(self.workers, key=lambda item: item.request_queue.qsize())
        return worker.calculate_sync(inputs, keep_file=keep_file, timeout=timeout)

    def shutdown(self) -> None:
        for worker in self.workers:
            threading.Thread(target=worker.shutdown, daemon=True).start()


def get_template_worker(template_path: Path, config: dict[str, Any], pool_size: int = 2) -> TemplateWorkerPool:
    key = f"template:{Path(template_path).resolve()}:{compute_config_hash(config)}"
    with _lock:
        worker = _workers.get(key)
        if worker:
            return worker

    worker = TemplateWorkerPool(pool_size, f"tpl-{abs(hash(key))}", template_path, config)
    set_worker(key, worker)
    return worker
