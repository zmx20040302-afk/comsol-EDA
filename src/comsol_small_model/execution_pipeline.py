from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


EXECUTION_STAGES: tuple[tuple[str, str], ...] = (
    ("connect_server", "连接 mphserver"),
    ("build_model_tree", "构建模型树"),
    ("build_geometry", "构建几何"),
    ("check_selections", "检查选择"),
    ("build_mesh", "构建网格"),
    ("run_study", "执行研究"),
    ("export_results", "导出结果"),
    ("save_mph", "保存 MPH"),
    ("generate_preview", "生成预览"),
)


def create_execution_evidence(
    job_id: str,
    *,
    contract_sha256: str = "",
    node: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = _now()
    return {
        "schema": "comsol-staged-execution-evidence",
        "schemaVersion": "1.0.0",
        "job_id": job_id,
        "status": "running",
        "started_at": now,
        "finished_at": "",
        "contract_sha256": contract_sha256,
        "node": dict(node or {}),
        "stages": [
            {"id": stage_id, "title": title, "status": "pending", "started_at": "", "finished_at": "", "message": "", "artifacts": []}
            for stage_id, title in EXECUTION_STAGES
        ],
        "failed_stage": "",
    }


def start_stage(record: dict[str, Any], stage_id: str, message: str = "") -> dict[str, Any]:
    stage = _stage(record, stage_id)
    stage.update({"status": "running", "started_at": stage.get("started_at") or _now(), "message": message})
    return record


def complete_stage(
    record: dict[str, Any],
    stage_id: str,
    *,
    message: str = "",
    artifacts: list[str | Path] | None = None,
) -> dict[str, Any]:
    stage = _stage(record, stage_id)
    stage.update({"status": "completed", "started_at": stage.get("started_at") or _now(), "finished_at": _now(), "message": message})
    stage["artifacts"] = [artifact_descriptor(path) for path in (artifacts or [])]
    return record


def skip_stage(record: dict[str, Any], stage_id: str, message: str) -> dict[str, Any]:
    stage = _stage(record, stage_id)
    stage.update({"status": "skipped", "started_at": _now(), "finished_at": _now(), "message": message})
    return record


def fail_stage(record: dict[str, Any], stage_id: str, error: str) -> dict[str, Any]:
    stage = _stage(record, stage_id)
    stage.update({"status": "failed", "started_at": stage.get("started_at") or _now(), "finished_at": _now(), "message": str(error)[-2000:]})
    record.update({"status": "failed", "failed_stage": stage_id, "finished_at": _now()})
    return record


def finish_execution(record: dict[str, Any]) -> dict[str, Any]:
    pending = [row for row in record.get("stages", []) if row.get("status") in {"pending", "running"}]
    record["status"] = "completed" if not pending and not record.get("failed_stage") else record.get("status", "incomplete")
    record["finished_at"] = _now()
    return record


def write_execution_evidence(record: dict[str, Any], path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return destination


def artifact_descriptor(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    exists = source.is_file()
    return {
        "path": str(source),
        "exists": exists,
        "size_bytes": source.stat().st_size if exists else 0,
        "sha256": _sha256(source) if exists else "",
    }


class ExecutionLease:
    """Exclusive, recoverable file lease for one MATLAB/COMSOL process tree."""

    def __init__(self, path: str | Path, job_id: str):
        self.path = Path(path)
        self.job_id = job_id
        self.acquired = False

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"job_id": self.job_id, "pid": os.getpid(), "created_at": _now()}, ensure_ascii=False)
        try:
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if self._stale():
                self.path.unlink(missing_ok=True)
                return self.acquire()
            return False
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(payload)
        self.acquired = True
        return True

    def release(self) -> None:
        if self.acquired:
            self.path.unlink(missing_ok=True)
            self.acquired = False

    def __enter__(self) -> "ExecutionLease":
        if not self.acquire():
            raise RuntimeError("another COMSOL execution owns the node lease")
        return self

    def __exit__(self, *_: object) -> None:
        self.release()

    def _stale(self) -> bool:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            pid = int(payload.get("pid", -1))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return True
        if pid <= 0:
            return True
        if os.name == "nt":
            import subprocess

            if pid == os.getpid():
                return False
            result = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True, check=False)
            # If process inspection is unavailable (for example under a
            # restricted service account), keep the lock.  Deleting a lease
            # without proof that its owner exited can start two COMSOL solves.
            if result.returncode != 0:
                return False
            return str(pid) not in result.stdout
        try:
            os.kill(pid, 0)
            return False
        except OSError:
            return True


def _stage(record: dict[str, Any], stage_id: str) -> dict[str, Any]:
    for row in record.get("stages", []):
        if row.get("id") == stage_id:
            return row
    raise KeyError(f"unknown execution stage: {stage_id}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
