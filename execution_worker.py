from __future__ import annotations

import argparse
import json
import msvcrt
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from src.comsol_small_model.execution_jobs import process_next_job


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local Windows COMSOL execution node.")
    parser.add_argument("--job-dir", default="generated/execution_jobs")
    parser.add_argument("--node-config", default="configs/execution_node.json")
    parser.add_argument("--once", action="store_true", help="Process one queued task and exit.")
    parser.add_argument("--poll-seconds", type=int, default=5)
    parser.add_argument("--lock-file", default="generated/execution_jobs/execution_worker.lock")
    parser.add_argument("--status-file", default="generated/execution_jobs/worker_status.json")
    return parser.parse_args()


def acquire_worker_lock(path: str) -> object:
    lock_path = Path(path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+", encoding="utf-8")
    handle.seek(0)
    if not handle.read(1):
        handle.seek(0)
        handle.write("0")
        handle.flush()
    handle.seek(0)
    try:
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError as exc:
        handle.close()
        raise RuntimeError("已有 COMSOL 执行 worker 正在运行。") from exc
    return handle


def write_worker_status(path: str, state: str, job: dict | None = None) -> None:
    status_path = Path(path)
    status_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "state": state,
        "pid": os.getpid(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "last_job_id": str((job or {}).get("id", "")),
        "last_job_status": str((job or {}).get("status", "")),
    }
    temporary = status_path.with_suffix(status_path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    temporary.replace(status_path)


def main() -> None:
    args = parse_args()
    try:
        lock_handle = acquire_worker_lock(args.lock_file)
    except RuntimeError as exc:
        print(str(exc))
        return
    try:
        write_worker_status(args.status_file, "running")
        while True:
            job = process_next_job(job_dir=args.job_dir, node_config_path=args.node_config)
            if job:
                print(f"[{job['id']}] {job['status']}")
            write_worker_status(args.status_file, "running", job)
            if args.once:
                return
            time.sleep(max(1, args.poll_seconds))
    finally:
        write_worker_status(args.status_file, "stopped")
        lock_handle.close()


if __name__ == "__main__":
    main()
