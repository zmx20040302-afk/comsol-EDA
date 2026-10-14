from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import time
import uuid
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .code_generator import generate_comsol_code_from_memory
from .case_memory import sync_template_validations
from .comsol_server import ensure_comsol_server
from .constraints import load_constraints
from .execution_diagnostics import diagnose_execution_failure
from .execution_pipeline import (
    ExecutionLease,
    complete_stage,
    create_execution_evidence,
    fail_stage,
    finish_execution,
    skip_stage,
    start_stage,
    write_execution_evidence,
)
from .livelink_builder import build_livelink_script_from_constraints
from .result_validation import validate_constraint_results
from .surrogate import auto_train_surrogate, train_surrogate_with_comsol_holdout
from .surrogate_runtime import load_surrogate_payload
from .surrogate_model_card import write_thermal_plate_model_card
from .surrogate_validation import validate_surrogate_holdout
from .thermal_sweep import build_thermal_samples_matlab, build_thermal_sweep_matlab, write_thermal_sweep_matlab
from .validation_design import build_independent_thermal_holdout
from .validated_templates import select_validated_template


DEFAULT_JOB_DIR = Path("generated/execution_jobs")
DEFAULT_NODE_CONFIG = Path("configs/execution_node.json")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
BUSBAR_BENCHMARK_DIR = PROJECT_ROOT / "generated" / "benchmarks" / "busbar_joule_heat" / "builders"
JOULE_HEAT_REQUIREMENT = (
    "建立母线板焦耳热标杆模型：使用 Electric Currents 和 Heat Transfer in Solids，"
    "通过 Joule Heating 耦合；设置端子、接地、绝缘、对流换热和环境温度；"
    "输出最高温度、平均温度、电流密度和端子电流，并为电压、电流和换热系数参数扫描导出 CSV。"
)


def create_job(
    requirement: str,
    *,
    job_type: str = "comsol_modeling",
    job_dir: str | Path = DEFAULT_JOB_DIR,
    memory_path: str | Path = "generated/case_memory/case_memory.json",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    clean_requirement = " ".join(str(requirement or "").split())
    if not clean_requirement:
        raise ValueError("requirement is empty")
    store = JobStore(job_dir)
    job_id = f"job_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}"
    payload = {
        "requirement": clean_requirement,
        "memory_path": str(memory_path),
        "metadata": metadata or {},
    }
    store.insert(job_id, job_type, payload)
    store.append_log(job_id, "任务已创建，等待本机 COMSOL 执行节点处理。")
    return store.get(job_id)


def create_joule_heat_benchmark_job(
    *,
    job_dir: str | Path = DEFAULT_JOB_DIR,
    memory_path: str | Path = "generated/case_memory/case_memory.json",
) -> dict[str, Any]:
    prepared_builder = {
        "matlab": str(BUSBAR_BENCHMARK_DIR / "busbar_joule_heat_baseline.m"),
        "java": str(BUSBAR_BENCHMARK_DIR / "BusbarJouleHeatBaseline.java"),
        "runner": str(BUSBAR_BENCHMARK_DIR / "run_busbar_joule_heat_baseline.m"),
        "mph_output": str(BUSBAR_BENCHMARK_DIR / "busbar_joule_heat_baseline.mph"),
    }
    has_prepared_builder = all(Path(path).is_file() for key, path in prepared_builder.items() if key != "mph_output")
    return create_job(
        JOULE_HEAT_REQUIREMENT,
        job_type="joule_heat_benchmark",
        job_dir=job_dir,
        memory_path=memory_path,
        metadata={
            "benchmark": "busbar_joule_heating",
            "required_interfaces": ["Electric Currents", "Heat Transfer in Solids", "Joule Heating"],
            "required_outputs": ["Tmax", "Tavg", "current_density", "terminal_current"],
            "prepared_builder": prepared_builder if has_prepared_builder else {},
        },
    )


def create_constraint_template_job(
    constraint_path: str | Path,
    *,
    job_dir: str | Path = DEFAULT_JOB_DIR,
) -> dict[str, Any]:
    source = Path(constraint_path)
    config = load_constraints(source)
    return create_job(
        f"Execute validated COMSOL constraint template: {config['model_name']}",
        job_type="constraint_template",
        job_dir=job_dir,
        metadata={
            "constraint_template": {
                "path": str(source),
                "model_name": str(config["model_name"]),
                "physics": str(config["physics"]),
            },
            "execution_review_approved": True,
        },
    )


def create_matched_template_job(requirement: str, *, job_dir: str | Path = DEFAULT_JOB_DIR) -> dict[str, Any]:
    match = select_validated_template(requirement, PROJECT_ROOT)
    if not match.get("matched"):
        raise ValueError(str(match["reason"]))
    job = create_constraint_template_job(str(match["template_path"]), job_dir=job_dir)
    job["template_match"] = match
    return job


def create_thermal_sweep_training_job(
    *,
    job_dir: str | Path = DEFAULT_JOB_DIR,
    spec_path: str | Path = PROJECT_ROOT / "configs" / "thermal_plate_sweep_training.json",
) -> dict[str, Any]:
    source = Path(spec_path)
    if not source.is_file():
        raise FileNotFoundError(f"thermal sweep spec not found: {source}")
    return create_job(
        "Run verified COMSOL thermal-plate sweep and train a local surrogate model.",
        job_type="thermal_sweep_training",
        job_dir=job_dir,
        metadata={
            "thermal_sweep": {"spec_path": str(source)},
            "execution_review_approved": True,
        },
    )


def create_thermal_augmentation_job(
    plan_path: str | Path,
    *,
    job_dir: str | Path = DEFAULT_JOB_DIR,
) -> dict[str, Any]:
    source = Path(plan_path)
    if not source.is_file():
        raise FileNotFoundError(f"thermal augmentation plan not found: {source}")
    plan = json.loads(source.read_text(encoding="utf-8"))
    if plan.get("kind") != "comsol_thermal_surrogate_augmentation_plan":
        raise ValueError("file is not a thermal surrogate augmentation plan")
    samples = plan.get("recommended_comsol_samples", [])
    if not isinstance(samples, list) or not samples:
        raise ValueError("thermal augmentation plan does not contain samples")
    return create_job(
        "Run COMSOL thermal-plate augmentation samples for surrogate learning.",
        job_type="thermal_augmentation",
        job_dir=job_dir,
        metadata={
            "thermal_augmentation": {"plan_path": str(source)},
            "execution_review_approved": True,
        },
    )


def create_thermal_augmentation_retrain_job(
    augmentation_job_id: str,
    *,
    job_dir: str | Path = DEFAULT_JOB_DIR,
) -> dict[str, Any]:
    store = JobStore(job_dir)
    source_job = store.get(augmentation_job_id)
    if source_job["job_type"] != "thermal_augmentation" or source_job["status"] != "completed":
        raise ValueError("补充扫描任务必须已成功完成后才能重新训练。")
    result = dict(source_job.get("result", {}))
    augmentation = dict(result.get("augmentation_dataset", {}))
    thermal_meta = dict(result.get("thermal_augmentation", {}))
    plan_path = Path(str(thermal_meta.get("plan_path", "")))
    augmentation_csv = Path(str(augmentation.get("path", "")))
    if not plan_path.is_file() or not augmentation_csv.is_file():
        raise FileNotFoundError("补充扫描任务缺少计划文件或结果 CSV。")
    return create_job(
        "Merge verified thermal augmentation samples, retrain the surrogate, and validate it with fresh COMSOL samples.",
        job_type="thermal_augmentation_retrain",
        job_dir=job_dir,
        metadata={
            "thermal_augmentation_retrain": {
                "augmentation_job_id": source_job["id"],
                "plan_path": str(plan_path),
                "augmentation_csv": str(augmentation_csv),
            },
            "execution_review_approved": True,
        },
    )


def create_approved_package_job(
    package_path: str | Path,
    *,
    job_dir: str | Path = DEFAULT_JOB_DIR,
) -> dict[str, Any]:
    source = Path(package_path)
    if not source.is_file():
        raise FileNotFoundError(f"approved package not found: {source}")
    package = json.loads(source.read_text(encoding="utf-8"))
    if package.get("kind") != "approved_comsol_modeling_package":
        raise ValueError("package is not an approved COMSOL modeling package")
    outputs = package.get("generated_code", {}).get("outputs", {})
    matlab_path = Path(str(outputs.get("matlab", "")))
    java_path = Path(str(outputs.get("java", "")))
    if not matlab_path.is_file() or not java_path.is_file():
        raise ValueError("approved package is missing generated MATLAB or Java files")
    handoff = package.get("execution_handoff", {})
    if not handoff.get("ready_to_open", False):
        raise ValueError("approved package is not ready to open in COMSOL")
    return create_job(
        str(package.get("requirement", "")),
        job_type="approved_model_package",
        job_dir=job_dir,
        memory_path=str(package.get("memory_path", "generated/case_memory/case_memory.json")),
        metadata={
            "approved_package": {
                "path": str(source),
                "matlab": str(matlab_path),
                "java": str(java_path),
                "verification": str(outputs.get("verification", "")),
                "execution_handoff": handoff,
                "approved_step_ids": list(package.get("approved_decisions", {}).keys()),
            },
            "execution_review_approved": False,
        },
    )


def process_next_job(
    *,
    job_dir: str | Path = DEFAULT_JOB_DIR,
    node_config_path: str | Path = DEFAULT_NODE_CONFIG,
) -> dict[str, Any] | None:
    store = JobStore(job_dir)
    job = store.claim_next()
    if job is None:
        return None
    try:
        store.append_log(job["id"], "开始生成 COMSOL MATLAB/Java 文件和执行包装脚本。")
        result = _prepare_job(job, store)
        config = load_execution_node_config(node_config_path)
        if not config["enabled"]:
            return store.update(
                job["id"],
                "awaiting_execution_configuration",
                result=result,
                message="执行器未启用；已生成脚本，等待配置 MATLAB LiveLink 路径。",
            )
        return _run_prepared_job(job, result, config, store)
    except Exception as exc:  # noqa: BLE001
        store.append_log(job["id"], f"任务失败：{exc}")
        return store.update(job["id"], "failed", error=str(exc))


def load_execution_node_config(path: str | Path = DEFAULT_NODE_CONFIG) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(json.dumps(default_execution_node_config(), ensure_ascii=False, indent=2), encoding="utf-8")
    config = json.loads(source.read_text(encoding="utf-8"))
    merged = default_execution_node_config()
    merged.update(config if isinstance(config, dict) else {})
    merged["config_path"] = str(source)
    return merged


def default_execution_node_config() -> dict[str, Any]:
    return {
        "node_id": "local-windows-comsol-node",
        "enabled": False,
        "matlab_executable": "",
        "livelink_matlab_path": r"D:\COMSOL64\Multiphysics\mli",
        "comsol_executable": r"D:\COMSOL64\Multiphysics\bin\win64\comsol.exe",
        "comsol_server_executable": r"D:\COMSOL64\Multiphysics\bin\win64\comsolmphserver.exe",
        "comsol_server_host": "localhost",
        "comsol_server_port": 2036,
        "start_comsol_server": True,
        "comsol_server_startup_timeout_seconds": 60,
        "comsol_server_multi_connection": True,
        "comsol_server_silent": True,
        "working_directory": "generated/execution_jobs",
        "timeout_seconds": 3600,
        "kill_matlab_process_tree_on_timeout": True,
        "allow_external_execution": False,
        "note": "先填写 matlab_executable，并确认 MATLAB 已配置 LiveLink for COMSOL；再把 enabled 和 allow_external_execution 设为 true。",
    }


class JobStore:
    def __init__(self, job_dir: str | Path) -> None:
        self.root = Path(job_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self.database = self.root / "jobs.sqlite3"
        self.logs_dir = self.root / "logs"
        self.logs_dir.mkdir(exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with closing(self._connect()) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                  id TEXT PRIMARY KEY,
                  job_type TEXT NOT NULL,
                  status TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL,
                  payload_json TEXT NOT NULL,
                  result_json TEXT NOT NULL DEFAULT '{}',
                  error TEXT NOT NULL DEFAULT ''
                )
                """
            )
            connection.commit()

    def insert(self, job_id: str, job_type: str, payload: dict[str, Any]) -> None:
        now = _now()
        with closing(self._connect()) as connection:
            connection.execute(
                "INSERT INTO jobs VALUES (?, ?, ?, ?, ?, ?, '{}', '')",
                (job_id, job_type, "queued", now, now, json.dumps(payload, ensure_ascii=False)),
            )
            connection.commit()

    def get(self, job_id: str) -> dict[str, Any]:
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise KeyError(f"job not found: {job_id}")
        return self._row(row)

    def list(self, limit: int = 30) -> list[dict[str, Any]]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (max(1, min(int(limit), 200)),)
            ).fetchall()
        return [self._row(row) for row in rows]

    def claim_next(self) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM jobs WHERE status = 'queued' ORDER BY created_at LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                "UPDATE jobs SET status = ?, updated_at = ? WHERE id = ?",
                ("preparing", _now(), row["id"]),
            )
            connection.commit()
        return self.get(str(row["id"]))

    def update(
        self,
        job_id: str,
        status: str,
        *,
        result: dict[str, Any] | None = None,
        error: str = "",
        message: str = "",
    ) -> dict[str, Any]:
        with closing(self._connect()) as connection:
            connection.execute(
                "UPDATE jobs SET status = ?, updated_at = ?, result_json = ?, error = ? WHERE id = ?",
                (status, _now(), json.dumps(result or {}, ensure_ascii=False), error, job_id),
            )
            connection.commit()
        if message:
            self.append_log(job_id, message)
        return self.get(job_id)

    def requeue(self, job_id: str) -> dict[str, Any]:
        job = self.get(job_id)
        if job["status"] in {"completed", "running"}:
            raise ValueError(f"job cannot be requeued from status {job['status']}")
        with closing(self._connect()) as connection:
            connection.execute(
                "UPDATE jobs SET status = ?, updated_at = ?, result_json = ?, error = '' WHERE id = ?",
                ("queued", _now(), "{}", job_id),
            )
            connection.commit()
        self.append_log(job_id, "任务已重新排队。")
        return self.get(job_id)

    def approve_execution_review(self, job_id: str) -> dict[str, Any]:
        job = self.get(job_id)
        if job["status"] != "awaiting_model_review":
            raise ValueError(f"job is not awaiting model review: {job['status']}")
        payload = dict(job["payload"])
        metadata = dict(payload.get("metadata", {}))
        metadata["execution_review_approved"] = True
        payload["metadata"] = metadata
        with closing(self._connect()) as connection:
            connection.execute(
                "UPDATE jobs SET status = ?, updated_at = ?, payload_json = ?, error = '' WHERE id = ?",
                ("queued", _now(), json.dumps(payload, ensure_ascii=False), job_id),
            )
            connection.commit()
        self.append_log(job_id, "Execution review approved; job requeued for external COMSOL execution.")
        return self.get(job_id)

    def append_log(self, job_id: str, message: str) -> None:
        line = f"[{_now()}] {message}\n"
        with (self.logs_dir / f"{job_id}.log").open("a", encoding="utf-8") as handle:
            handle.write(line)

    def _row(self, row: sqlite3.Row) -> dict[str, Any]:
        result = json.loads(row["result_json"] or "{}")
        payload = json.loads(row["payload_json"] or "{}")
        return {
            "id": row["id"],
            "job_type": row["job_type"],
            "status": row["status"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "payload": payload,
            "result": result,
            "error": row["error"],
            "log_path": str(self.logs_dir / f"{row['id']}.log"),
        }


def rebuild_artifact_index(job_dir: str | Path = DEFAULT_JOB_DIR, *, limit: int = 200) -> dict[str, Any]:
    """Create a stable, rebuildable inventory of task files and result evidence."""
    store = JobStore(job_dir)
    records: list[dict[str, Any]] = []
    for job in store.list(limit):
        result = dict(job.get("result", {}))
        model = dict(result.get("model_artifact", {}))
        csv_artifact = dict(result.get("result_artifact", {}))
        has_artifact = bool(model.get("path") or csv_artifact.get("path") or result.get("runner_path"))
        if not has_artifact:
            continue
        records.append({
            "job_id": job["id"],
            "status": job["status"],
            "job_type": job["job_type"],
            "requirement": str(job.get("payload", {}).get("requirement", "")),
            "updated_at": job["updated_at"],
            "mph": model,
            "results_csv": csv_artifact,
            "matlab_builder": str(result.get("constraint_template", {}).get("builder", "")),
            "runner": str(result.get("runner_path", "")),
            "log": job["log_path"],
            "validation": result.get("result_validation", {}),
            "diagnosis": result.get("diagnosis", {}),
        })
    payload = {
        "kind": "comsol_execution_artifact_index",
        "generated_at": _now(),
        "root": str(store.root.resolve()),
        "record_count": len(records),
        "completed_count": sum(record["status"] == "completed" for record in records),
        "failed_count": sum(record["status"] == "failed" for record in records),
        "records": records,
    }
    destination = store.root / "artifact_index.json"
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(destination)
    payload["path"] = str(destination)
    return payload


def summarize_artifacts(job_dir: str | Path = DEFAULT_JOB_DIR, *, limit: int = 8) -> dict[str, Any]:
    """Return a compact result view suitable for the conversational UI."""
    index = rebuild_artifact_index(job_dir)
    recent: list[dict[str, Any]] = []
    for record in index["records"]:
        if record["status"] != "completed":
            continue
        validation = record.get("validation", {})
        values = validation.get("values", {}) if isinstance(validation, dict) else {}
        recent.append({
            "job_id": record["job_id"],
            "requirement": record["requirement"],
            "updated_at": record["updated_at"],
            "physics": validation.get("physics", "") if isinstance(validation, dict) else "",
            "result_values": values,
            "validation_passed": bool(validation.get("passed", False)) if isinstance(validation, dict) else False,
            "mph_path": record.get("mph", {}).get("path", ""),
            "csv_path": record.get("results_csv", {}).get("path", ""),
        })
        if len(recent) >= max(1, min(int(limit), 30)):
            break
    return {
        "kind": "comsol_recent_result_summary",
        "index_path": index["path"],
        "record_count": index["record_count"],
        "completed_count": index["completed_count"],
        "failed_count": index["failed_count"],
        "recent": recent,
    }


def _prepare_job(job: dict[str, Any], store: JobStore) -> dict[str, Any]:
    payload = job["payload"]
    thermal_retrain = payload.get("metadata", {}).get("thermal_augmentation_retrain", {})
    if isinstance(thermal_retrain, dict) and Path(str(thermal_retrain.get("plan_path", ""))).is_file():
        plan_path = Path(str(thermal_retrain["plan_path"]))
        augmentation_csv = Path(str(thermal_retrain.get("augmentation_csv", "")))
        if not augmentation_csv.is_file():
            raise FileNotFoundError(f"thermal augmentation CSV not found: {augmentation_csv}")
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        model_path = Path(str(plan.get("model_path", "")))
        if not model_path.is_file():
            raise FileNotFoundError(f"source surrogate model not found: {model_path}")
        model_payload = load_surrogate_payload(model_path)
        base_csv = Path(str(model_payload.get("training_csv_path", "")))
        if not base_csv.is_file():
            raise FileNotFoundError(f"source surrogate training CSV not found: {base_csv}")
        holdout_rows = _thermal_augmentation_holdout_rows(plan)
        destination = store.root / job["id"]
        destination.mkdir(parents=True, exist_ok=True)
        runner_path = (destination / f"run_{job['id']}_holdout.m").resolve()
        holdout_csv = (destination / "thermal_augmentation_holdout.csv").resolve()
        runner_path.write_text(build_thermal_samples_matlab(holdout_rows, holdout_csv), encoding="utf-8")
        return {
            "kind": "thermal_augmentation_retrain_job",
            "thermal_retrain": {
                **thermal_retrain,
                "base_training_csv": str(base_csv),
                "source_model": str(model_path),
                "holdout_samples": holdout_rows,
            },
            "runner_path": str(runner_path),
            "results_csv_path": str(holdout_csv),
            "execution_readiness": {"ready_to_open": True, "ready_to_solve": True, "source": "thermal_augmentation_retrain"},
        }
    thermal_augmentation = payload.get("metadata", {}).get("thermal_augmentation", {})
    if isinstance(thermal_augmentation, dict) and Path(str(thermal_augmentation.get("plan_path", ""))).is_file():
        plan_path = Path(str(thermal_augmentation["plan_path"]))
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        samples = plan.get("recommended_comsol_samples", [])
        if not isinstance(samples, list) or not samples:
            raise ValueError("thermal augmentation plan does not contain COMSOL samples")
        destination = store.root / job["id"]
        destination.mkdir(parents=True, exist_ok=True)
        csv_path = (destination / "thermal_augmentation_samples.csv").resolve()
        runner_path = (destination / f"run_{job['id']}.m").resolve()
        normalized = [{name: float(row[name]) for name in ("L_m", "W_m", "k_W_mK", "T_hot_K", "T_cold_K")} for row in samples]
        runner_path.write_text(build_thermal_samples_matlab(normalized, csv_path), encoding="utf-8")
        return {
            "kind": "thermal_augmentation_job",
            "thermal_augmentation": {"plan_path": str(plan_path), "sample_count": len(normalized), "samples": normalized},
            "runner_path": str(runner_path),
            "results_csv_path": str(csv_path),
            "execution_readiness": {"ready_to_open": True, "ready_to_solve": True, "source": "thermal_augmentation"},
        }
    thermal_sweep = payload.get("metadata", {}).get("thermal_sweep", {})
    if isinstance(thermal_sweep, dict) and Path(str(thermal_sweep.get("spec_path", ""))).is_file():
        destination = store.root / job["id"]
        destination.mkdir(parents=True, exist_ok=True)
        csv_path = (destination / "thermal_sweep_training.csv").resolve()
        runner_path = (destination / f"run_{job['id']}.m").resolve()
        prepared = write_thermal_sweep_matlab(thermal_sweep["spec_path"], runner_path, csv_path)
        spec = dict(prepared["spec"])
        holdout = dict(spec.get("holdout_sampling", {}))
        holdout_design_config = dict(spec.get("holdout_design", {}))
        holdout_csv_path = (destination / "thermal_sweep_holdout.csv").resolve()
        holdout_runner_path = (destination / f"run_{job['id']}_holdout.m").resolve()
        designed_holdout: dict[str, Any] = {}
        holdout_rows: list[dict[str, float]] = []
        if holdout_design_config:
            designed_holdout = build_independent_thermal_holdout(
                spec,
                count=int(holdout_design_config.get("count", 18)),
                seed=int(holdout_design_config.get("seed", 20261008)),
            )
            holdout_rows = [
                {name: float(row[name]) for name in ("L_m", "W_m", "k_W_mK", "T_hot_K", "T_cold_K")}
                for row in designed_holdout["rows"]
            ]
            holdout_runner_path.write_text(
                build_thermal_samples_matlab(holdout_rows, holdout_csv_path),
                encoding="utf-8",
            )
        elif holdout:
            holdout_spec = {**spec, "sampling": holdout}
            holdout_runner_path.write_text(build_thermal_sweep_matlab(holdout_spec, holdout_csv_path), encoding="utf-8")
        return {
            "kind": "thermal_sweep_training_job",
            "thermal_sweep": {**thermal_sweep, **prepared},
            "runner_path": str(runner_path),
            "results_csv_path": str(csv_path),
            "holdout": {
                "runner_path": str(holdout_runner_path),
                "csv_path": str(holdout_csv_path),
                "sample_count": (
                    len(holdout_rows)
                    if holdout_rows
                    else len(holdout.get("L_m", [])) * len(holdout.get("W_m", []))
                    * len(holdout.get("k_W_mK", [])) * len(holdout.get("T_hot_K", []))
                    * len(holdout.get("T_cold_K", []))
                ),
                "design": designed_holdout,
            } if holdout_rows or holdout else {},
            "execution_readiness": {"ready_to_open": True, "ready_to_solve": True, "source": "thermal_sweep_training"},
        }
    constraint_template = payload.get("metadata", {}).get("constraint_template", {})
    if isinstance(constraint_template, dict) and Path(str(constraint_template.get("path", ""))).is_file():
        destination = store.root / job["id"]
        destination.mkdir(parents=True, exist_ok=True)
        config = load_constraints(str(constraint_template["path"]))
        function_name = f"generated_build_{config['model_name']}"
        builder_path = (destination / f"{function_name}.m").resolve()
        runner_path = (destination / f"run_{job['id']}.m").resolve()
        mph_path = (destination / f"{job['id']}.mph").resolve()
        results_csv_path = (destination / f"{job['id']}_results.csv").resolve()
        builder_path.write_text(build_livelink_script_from_constraints(config), encoding="utf-8")
        output_definitions = dict(config.get("outputs", {}))
        runner_path.write_text(
            _matlab_runner(str(builder_path), mph_path, results_csv_path, output_definitions),
            encoding="utf-8",
        )
        result = {
            "kind": "constraint_template_execution_job",
            "constraint_template": {**constraint_template, "builder": str(builder_path)},
            "runner_path": str(runner_path),
            "mph_output_path": str(mph_path),
            "results_csv_path": str(results_csv_path),
            "result_export": {"expected": bool(output_definitions), "outputs": output_definitions},
            "result_validation_config": config,
            "execution_readiness": {
                "ready_to_open": True,
                "ready_to_solve": True,
                "source": "validated_constraint_template",
            },
        }
        store.append_log(job["id"], "Prepared validated constraint-template MATLAB builder.")
        return result
    approved_package = payload.get("metadata", {}).get("approved_package", {})
    if isinstance(approved_package, dict) and _approved_package_exists(approved_package):
        destination = store.root / job["id"]
        destination.mkdir(parents=True, exist_ok=True)
        runner_path = (destination / f"run_{job['id']}.m").resolve()
        mph_path = (destination / f"{job['id']}.mph").resolve()
        runner_path.write_text(_matlab_runner(str(approved_package["matlab"]), mph_path), encoding="utf-8")
        result = {
            "kind": "approved_package_execution_job",
            "generated_code": {
                "outputs": {
                    "matlab": approved_package["matlab"],
                    "java": approved_package["java"],
                    "verification": approved_package.get("verification", ""),
                }
            },
            "approved_package_path": approved_package["path"],
            "approved_step_ids": list(approved_package.get("approved_step_ids", [])),
            "runner_path": str(runner_path),
            "mph_output_path": str(mph_path),
            "execution_readiness": dict(approved_package.get("execution_handoff", {})),
        }
        store.append_log(job["id"], "Prepared runner from an approved staged modeling package.")
        return result
    prepared_builder = payload.get("metadata", {}).get("prepared_builder", {})
    if isinstance(prepared_builder, dict) and _prepared_builder_exists(prepared_builder):
        result = {
            "kind": "prepared_source_case_execution_job",
            "generated_code": {"outputs": {"matlab": prepared_builder["matlab"], "java": prepared_builder["java"]}},
            "runner_path": prepared_builder["runner"],
            "mph_output_path": prepared_builder["mph_output"],
            "execution_readiness": {"ready_to_open": True, "ready_to_solve": False, "source": "approved_busbar_case"},
        }
        store.append_log(job["id"], "使用已批准的母线板焦耳热基准建模文件。")
        return result
    destination = store.root / job["id"]
    generated = generate_comsol_code_from_memory(
        requirement=str(payload["requirement"]),
        memory_path=str(payload["memory_path"]),
        output_dir=destination,
        output_prefix=job["id"],
    )
    runner_path = (destination / f"run_{job['id']}.m").resolve()
    mph_path = (destination / f"{job['id']}.mph").resolve()
    runner_path.write_text(_matlab_runner(generated.matlab_path, mph_path), encoding="utf-8")
    result = {
        "kind": "prepared_comsol_execution_job",
        "generated_code": generated.as_dict(),
        "runner_path": str(runner_path),
        "mph_output_path": str(mph_path),
        "execution_readiness": generated.generation_readiness,
    }
    store.append_log(job["id"], f"已生成 MATLAB：{generated.matlab_path}")
    store.append_log(job["id"], f"已生成执行包装脚本：{runner_path}")
    return result


def _prepared_builder_exists(builder: dict[str, Any]) -> bool:
    return all(Path(str(builder.get(key, ""))).is_file() for key in ("matlab", "java", "runner"))


def _approved_package_exists(package: dict[str, Any]) -> bool:
    return all(Path(str(package.get(key, ""))).is_file() for key in ("path", "matlab", "java"))


def _run_guarded_process(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: int,
    kill_process_tree: bool,
) -> subprocess.CompletedProcess[str]:
    """Run MATLAB with a hard deadline and remove its child process tree on timeout."""
    creationflags = 0
    if os.name == "nt":
        creationflags = int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
    process = subprocess.Popen(
        command,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        creationflags=creationflags,
    )
    try:
        stdout, stderr = process.communicate(timeout=max(1, int(timeout)))
    except subprocess.TimeoutExpired as exc:
        if kill_process_tree and os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )
        else:
            process.kill()
        stdout, stderr = process.communicate(timeout=30)
        raise subprocess.TimeoutExpired(
            command,
            timeout,
            output=stdout or exc.output,
            stderr=stderr or exc.stderr,
        ) from exc
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def _run_prepared_job(job: dict[str, Any], result: dict[str, Any], config: dict[str, Any], store: JobStore) -> dict[str, Any]:
    readiness = result.get("execution_readiness", {})
    is_approved_benchmark = (
        result.get("kind") == "prepared_source_case_execution_job"
        and readiness.get("source") == "approved_busbar_case"
    )
    execution_review_approved = bool(job.get("payload", {}).get("metadata", {}).get("execution_review_approved", False))
    if not readiness.get("ready_to_solve", False) and not is_approved_benchmark and not execution_review_approved:
        return store.update(
            job["id"],
            "awaiting_model_review",
            result=result,
            message=(
                "Generated model is structurally complete but still has unresolved modeling items; "
                "review and approve named selections and boundary conditions before external execution."
            ),
        )
    if not config.get("allow_external_execution"):
        return store.update(
            job["id"],
            "awaiting_execution_approval",
            result=result,
            message="执行器已启用，但 allow_external_execution=false；需要明确允许后才会调用 MATLAB。",
        )
    matlab = Path(str(config.get("matlab_executable", "")))
    if not matlab.is_file():
        return store.update(
            job["id"],
            "awaiting_execution_configuration",
            result=result,
            message="找不到 matlab_executable；请在 configs/execution_node.json 中配置 MATLAB 路径。",
        )
    evidence_path = store.root / job["id"] / "execution_evidence.json"
    handoff = dict(result.get("execution_readiness", {}))
    execution_evidence = create_execution_evidence(
        job["id"],
        contract_sha256=str(handoff.get("contract_sha256", "")),
        node={
            "node_id": str(config.get("node_id", "")),
            "matlab_executable": str(matlab),
            "comsol_server": f"{config.get('comsol_server_host', 'localhost')}:{config.get('comsol_server_port', 2036)}",
        },
    )
    result["execution_evidence"] = {"path": str(evidence_path), "record": execution_evidence}
    start_stage(execution_evidence, "connect_server", "正在检查或启动 mphserver。")
    write_execution_evidence(execution_evidence, evidence_path)
    server = _ensure_comsol_server(config, store, job["id"])
    result["comsol_server"] = server
    if not server["ready"]:
        fail_stage(execution_evidence, "connect_server", server["message"])
        write_execution_evidence(execution_evidence, evidence_path)
        result["diagnosis"] = diagnose_execution_failure(server["message"], stage="server")
        return store.update(
            job["id"],
            "failed",
            result=result,
            error=server["message"],
        )
    complete_stage(execution_evidence, "connect_server", message=f"已连接 {server['host']}:{server['port']}。")
    write_execution_evidence(execution_evidence, evidence_path)
    runner = Path(result["runner_path"]).resolve()
    livelink_path = Path(str(config.get("livelink_matlab_path", "")))
    startup = f"run('{runner.as_posix()}')"
    if livelink_path.is_dir():
        startup = f"addpath('{livelink_path.as_posix()}'); {startup}"
    command = [str(matlab), "-batch", startup]
    store.append_log(job["id"], "开始调用 MATLAB LiveLink 执行 COMSOL 模型。")
    environment = os.environ.copy()
    environment["COMSOL_MPH_HOST"] = str(server["host"])
    environment["COMSOL_MPH_PORT"] = str(server["port"])
    execution_started = time.monotonic()
    lease = ExecutionLease(store.root / ".locks" / "comsol_execution.lock", job["id"])
    if not lease.acquire():
        result["execution_evidence"] = {"path": str(evidence_path), "record": execution_evidence}
        return store.update(job["id"], "queued", result=result, message="COMSOL 执行节点正被另一个任务占用，本任务已返回队列。")
    start_stage(execution_evidence, "build_model_tree", "MATLAB LiveLink 已启动。")
    write_execution_evidence(execution_evidence, evidence_path)
    try:
        try:
            completed = _run_guarded_process(
                command,
                cwd=runner.parent,
                env=environment,
                timeout=int(config.get("timeout_seconds", 3600)),
                kill_process_tree=bool(config.get("kill_matlab_process_tree_on_timeout", True)),
            )
        finally:
            lease.release()
    except subprocess.TimeoutExpired as exc:
        timeout_error = f"MATLAB/COMSOL execution timed out after {config.get('timeout_seconds', 3600)} seconds.\n{exc.stdout or ''}\n{exc.stderr or ''}"
        fail_stage(execution_evidence, "run_study", timeout_error)
        write_execution_evidence(execution_evidence, evidence_path)
        result["diagnosis"] = diagnose_execution_failure(timeout_error, stage="timeout")
        return store.update(job["id"], "failed", result=result, error=timeout_error[-4000:])
    execution = {
        "command": command,
        "return_code": completed.returncode,
        "stdout": completed.stdout[-12000:],
        "stderr": completed.stderr[-12000:],
        "duration_seconds": round(time.monotonic() - execution_started, 3),
    }
    result["execution"] = execution
    if completed.returncode != 0:
        failure_text = f"{completed.stdout}\n{completed.stderr}".strip()
        result["diagnosis"] = diagnose_execution_failure(failure_text)
        fail_stage(execution_evidence, _execution_failure_stage(result["diagnosis"]), failure_text)
        write_execution_evidence(execution_evidence, evidence_path)
        return store.update(job["id"], "failed", result=result, error=failure_text[-4000:])
    for stage_id in ("build_model_tree", "build_geometry", "check_selections", "build_mesh", "run_study"):
        complete_stage(execution_evidence, stage_id, message="MATLAB/COMSOL 执行成功。")
    write_execution_evidence(execution_evidence, evidence_path)
    if result.get("kind") == "thermal_sweep_training_job":
        return _finalize_thermal_sweep_training(job, result, store, config)
    if result.get("kind") == "thermal_augmentation_job":
        return _finalize_thermal_augmentation(job, result, store)
    if result.get("kind") == "thermal_augmentation_retrain_job":
        return _finalize_thermal_augmentation_retrain(job, result, store)
    artifact_path = Path(str(result.get("mph_output_path", "")))
    results_csv_path = Path(str(result.get("results_csv_path", "")))
    result_export = dict(result.get("result_export", {}))
    result_csv = {
        "kind": "comsol_global_results_csv",
        "path": str(results_csv_path),
        "expected": bool(result_export.get("expected", False)),
        "exists": results_csv_path.is_file(),
        "size_bytes": results_csv_path.stat().st_size if results_csv_path.is_file() else 0,
        "outputs": result_export.get("outputs", {}),
    }
    artifact = {
        "kind": "comsol_mph_artifact",
        "path": str(artifact_path),
        "exists": artifact_path.is_file(),
        "size_bytes": artifact_path.stat().st_size if artifact_path.is_file() else 0,
        "execution_duration_seconds": execution["duration_seconds"],
        "parameter_source": result.get("constraint_template") or result.get("approved_package_path") or "generated_model_plan",
        "next_action": "inspect_results_in_comsol_and_validate_csv",
    }
    result["model_artifact"] = artifact
    result["result_artifact"] = result_csv
    if not artifact["exists"] or not artifact["size_bytes"]:
        fail_stage(execution_evidence, "save_mph", "COMSOL completed but the expected MPH artifact was not created.")
        write_execution_evidence(execution_evidence, evidence_path)
        result["diagnosis"] = diagnose_execution_failure("COMSOL completed but the expected MPH artifact was not created.")
        return store.update(job["id"], "failed", result=result, error="COMSOL completed but the expected MPH artifact was not created.")
    if result_csv["expected"] and (not result_csv["exists"] or not result_csv["size_bytes"]):
        fail_stage(execution_evidence, "export_results", "COMSOL completed but the expected results CSV was not created.")
        write_execution_evidence(execution_evidence, evidence_path)
        result["diagnosis"] = diagnose_execution_failure("COMSOL completed but the expected results CSV was not created.")
        return store.update(
            job["id"],
            "failed",
            result=result,
            error="COMSOL completed but the expected results CSV was not created.",
        )
    validation_config = result.get("result_validation_config")
    if isinstance(validation_config, dict) and result_csv["expected"]:
        validation = validate_constraint_results(validation_config, results_csv_path)
        result["result_validation"] = validation
        if not validation["passed"]:
            fail_stage(execution_evidence, "export_results", "COMSOL physical result validation did not pass.")
            write_execution_evidence(execution_evidence, evidence_path)
            result["diagnosis"] = diagnose_execution_failure("COMSOL completed but physical result validation did not pass.")
            return store.update(
                job["id"],
                "failed",
                result=result,
                error="COMSOL completed but physical result validation did not pass.",
            )
    complete_stage(execution_evidence, "export_results", message="结果导出完成。", artifacts=[results_csv_path] if result_csv["exists"] else [])
    complete_stage(execution_evidence, "save_mph", message="MPH 保存完成。", artifacts=[artifact_path])
    preview_path = artifact_path.with_name(artifact_path.stem + "_preview.png")
    if preview_path.is_file():
        complete_stage(execution_evidence, "generate_preview", message="预览图已生成。", artifacts=[preview_path])
    else:
        skip_stage(execution_evidence, "generate_preview", "模型已完成，但当前模板未导出预览图。")
    finish_execution(execution_evidence)
    write_execution_evidence(execution_evidence, evidence_path)
    result["execution_evidence"] = {"path": str(evidence_path), "record": execution_evidence}
    completed_job = store.update(job["id"], "completed", result=result, message="COMSOL 任务已完成。")
    index = rebuild_artifact_index(store.root)
    try:
        sync_template_validations(index["path"])
        store.append_log(job["id"], "已将通过的模板结果同步到本地知识库。")
    except Exception as exc:  # noqa: BLE001
        store.append_log(job["id"], f"模板验证结果未同步到知识库：{exc}")
    return completed_job


def _finalize_thermal_augmentation(job: dict[str, Any], result: dict[str, Any], store: JobStore) -> dict[str, Any]:
    csv_path = Path(str(result.get("results_csv_path", "")))
    if not csv_path.is_file() or not csv_path.stat().st_size:
        error = "COMSOL thermal augmentation completed but the sample CSV was not created."
        result["diagnosis"] = diagnose_execution_failure(error)
        return store.update(job["id"], "failed", result=result, error=error)
    samples = dict(result.get("thermal_augmentation", {}))
    result["augmentation_dataset"] = {
        "path": str(csv_path),
        "exists": True,
        "size_bytes": csv_path.stat().st_size,
        "sample_count": int(samples.get("sample_count", 0)),
        "columns": ["L_m", "W_m", "k_W_mK", "T_hot_K", "T_cold_K", "Tmax_K", "Tavg_K"],
    }
    result["next_action"] = "将补充 CSV 与原训练数据合并，并安排新的独立 COMSOL 验证后重新训练代理模型。"
    return store.update(job["id"], "completed", result=result, message="COMSOL 补充扫描已完成，真实样本已导出为 CSV。")


def _thermal_augmentation_holdout_rows(plan: dict[str, Any]) -> list[dict[str, float]]:
    samples = plan.get("recommended_comsol_samples", [])
    out_of_range = plan.get("out_of_range", {})
    if not isinstance(samples, list) or not samples:
        raise ValueError("thermal augmentation plan has no samples")
    center = {name: float(value) for name, value in dict(plan.get("requested_inputs", samples[0])).items()}
    names = [name for name in out_of_range if name in center]
    rows: list[dict[str, float]] = []
    for name in names:
        values = sorted({float(row[name]) for row in samples if isinstance(row, dict) and name in row})
        for low, high in zip(values, values[1:]):
            row = dict(center)
            row[name] = (low + high) / 2.0
            rows.append(row)
    if not rows:
        row = dict(center)
        row["L_m"] = row["L_m"] * 1.025
        rows.append(row)
    unique: list[dict[str, float]] = []
    for row in rows:
        if row not in unique:
            unique.append(row)
    return unique


def _finalize_thermal_augmentation_retrain(job: dict[str, Any], result: dict[str, Any], store: JobStore) -> dict[str, Any]:
    holdout_csv = Path(str(result.get("results_csv_path", "")))
    meta = dict(result.get("thermal_retrain", {}))
    base_csv = Path(str(meta.get("base_training_csv", "")))
    augmentation_csv = Path(str(meta.get("augmentation_csv", "")))
    if not holdout_csv.is_file() or not augmentation_csv.is_file() or not base_csv.is_file():
        error = "thermal retraining is missing base, augmentation, or fresh-COMSOL holdout CSV data"
        result["diagnosis"] = diagnose_execution_failure(error)
        return store.update(job["id"], "failed", result=result, error=error)
    destination = store.root / job["id"]
    merged_csv = destination / "thermal_augmentation_merged_training.csv"
    merged = pd.concat([pd.read_csv(base_csv), pd.read_csv(augmentation_csv)], ignore_index=True)
    merged = merged.drop_duplicates().reset_index(drop=True)
    merged.to_csv(merged_csv, index=False)
    spec = json.loads((PROJECT_ROOT / "configs" / "thermal_plate_sweep_training.json").read_text(encoding="utf-8"))
    model_path = destination / "thermal_plate_surrogate_augmented_validated.joblib"
    try:
        selected = train_surrogate_with_comsol_holdout(
            merged_csv,
            holdout_csv,
            model_path,
            input_columns=list(spec["inputs"]),
            output_columns=list(spec["outputs"]),
        )
        validation = validate_surrogate_holdout(
            model_path,
            holdout_csv,
            destination / "thermal_augmentation_holdout_validation.json",
        )
        card = write_thermal_plate_model_card(
            spec=spec,
            training_csv=merged_csv,
            model_path=model_path,
            validation=validation,
            output_dir=destination,
        )
    except Exception as exc:  # noqa: BLE001
        result["diagnosis"] = diagnose_execution_failure(f"thermal augmentation retraining failed: {exc}")
        return store.update(job["id"], "failed", result=result, error=str(exc))
    result["merged_training_dataset"] = {"path": str(merged_csv), "rows": int(len(merged)), "base_rows": int(len(pd.read_csv(base_csv))), "augmentation_rows": int(len(pd.read_csv(augmentation_csv)))}
    result["holdout_dataset"] = {"path": str(holdout_csv), "rows": int(len(pd.read_csv(holdout_csv))), "fresh_comsol": True}
    result["training_model"] = {"path": str(model_path), "exists": model_path.is_file(), "best_model": selected["best_model"]}
    result["training_report"] = {"best_model": selected["best_model"], "candidate_reports": selected["candidate_reports"], "holdout_validation": validation}
    result["model_card"] = {"json_path": card["json_path"], "markdown_path": card["markdown_path"]}
    if not validation.get("passed"):
        result["diagnosis"] = diagnose_execution_failure("Augmented surrogate did not pass fresh COMSOL holdout validation.")
        return store.update(job["id"], "failed", result=result, error="Augmented surrogate did not pass fresh COMSOL holdout validation.")
    return store.update(job["id"], "completed", result=result, message="补充数据已合并，代理模型已通过新的独立 COMSOL 验证。")


def _finalize_thermal_sweep_training(job: dict[str, Any], result: dict[str, Any], store: JobStore, config: dict[str, Any]) -> dict[str, Any]:
    csv_path = Path(str(result.get("results_csv_path", "")))
    sweep = dict(result.get("thermal_sweep", {}))
    spec = dict(sweep.get("spec", {}))
    if not csv_path.is_file() or not csv_path.stat().st_size:
        result["diagnosis"] = diagnose_execution_failure("COMSOL thermal sweep completed but the training CSV was not created.")
        return store.update(job["id"], "failed", result=result, error="COMSOL thermal sweep training CSV was not created.")
    holdout = dict(result.get("holdout", {}))
    holdout_csv_path = Path(str(holdout.get("csv_path", "")))
    holdout_runner_path = Path(str(holdout.get("runner_path", "")))
    if holdout_runner_path.is_file():
        matlab = Path(str(config.get("matlab_executable", "")))
        livelink_path = Path(str(config.get("livelink_matlab_path", "")))
        startup = f"run('{holdout_runner_path.as_posix()}')"
        if livelink_path.is_dir():
            startup = f"addpath('{livelink_path.as_posix()}'); {startup}"
        environment = os.environ.copy()
        environment["COMSOL_MPH_HOST"] = str(config.get("comsol_server_host", "localhost"))
        environment["COMSOL_MPH_PORT"] = str(config.get("comsol_server_port", 2036))
        holdout_started = time.monotonic()
        try:
            completed = _run_guarded_process(
                [str(matlab), "-batch", startup],
                cwd=holdout_runner_path.parent,
                env=environment,
                timeout=int(config.get("timeout_seconds", 3600)),
                kill_process_tree=bool(config.get("kill_matlab_process_tree_on_timeout", True)),
            )
        except subprocess.TimeoutExpired as exc:
            error = f"thermal holdout timed out: {exc}"
            result["diagnosis"] = diagnose_execution_failure(error, stage="timeout")
            return store.update(job["id"], "failed", result=result, error=error)
        result["holdout_execution"] = {
            "return_code": completed.returncode,
            "stdout": completed.stdout[-12000:],
            "stderr": completed.stderr[-12000:],
            "duration_seconds": round(time.monotonic() - holdout_started, 3),
        }
        if completed.returncode != 0 or not holdout_csv_path.is_file() or not holdout_csv_path.stat().st_size:
            error = f"thermal holdout COMSOL execution failed: {completed.stdout}\n{completed.stderr}".strip()
            result["diagnosis"] = diagnose_execution_failure(error)
            return store.update(job["id"], "failed", result=result, error=error[-4000:])
    model_path = (store.root / job["id"] / "thermal_plate_surrogate_comsol_validated.joblib").resolve()
    try:
        if holdout_csv_path.is_file() and holdout_csv_path.stat().st_size:
            selected = train_surrogate_with_comsol_holdout(
                csv_path,
                holdout_csv_path,
                model_path,
                input_columns=list(spec.get("inputs", [])),
                output_columns=list(spec.get("outputs", [])),
            )
            validation = validate_surrogate_holdout(
                model_path,
                holdout_csv_path,
                store.root / job["id"] / "thermal_sweep_holdout_validation.json",
            )
            training_report = {
                "best_model": selected["best_model"],
                "rows": selected["rows"],
                "test_rmse": next(row["holdout_rmse"] for row in selected["candidate_reports"] if row["name"] == selected["best_model"]),
                "test_mae": next(row["holdout_mae"] for row in selected["candidate_reports"] if row["name"] == selected["best_model"]),
                "test_r2": "fresh_comsol_holdout",
                "candidate_reports": selected["candidate_reports"],
                "holdout_validation": validation,
            }
        else:
            report, inspection = auto_train_surrogate(
                csv_path,
                model_path,
                input_columns=list(spec.get("inputs", [])),
                output_columns=list(spec.get("outputs", [])),
            )
            training_report = {
                "best_model": report.best_model,
                "rows": report.rows,
                "test_rmse": report.test_rmse,
                "test_mae": report.test_mae,
                "test_r2": report.test_r2,
                "per_output_metrics": report.per_output_metrics,
                "recommendations": report.recommendations,
                "training_record_path": inspection.get("training_record_path", ""),
            }
    except Exception as exc:  # noqa: BLE001
        result["diagnosis"] = diagnose_execution_failure(f"thermal sweep training failed: {exc}")
        return store.update(job["id"], "failed", result=result, error=str(exc))
    result["training_dataset"] = {
        "path": str(csv_path),
        "exists": True,
        "size_bytes": csv_path.stat().st_size,
        "sample_count": int(sweep.get("sample_count", 0)),
        "inputs": list(spec.get("inputs", [])),
        "outputs": list(spec.get("outputs", [])),
    }
    result["training_model"] = {"path": str(model_path), "exists": model_path.is_file()}
    result["training_report"] = training_report
    if holdout_csv_path.is_file():
        result["holdout_dataset"] = {"path": str(holdout_csv_path), "exists": True, "size_bytes": holdout_csv_path.stat().st_size, "sample_count": holdout.get("sample_count", 0)}
    try:
        card = write_thermal_plate_model_card(
            spec=spec,
            training_csv=csv_path,
            model_path=model_path,
            validation=training_report.get("holdout_validation", {}),
            output_dir=store.root / job["id"],
        )
        result["model_card"] = {"json_path": card["json_path"], "markdown_path": card["markdown_path"]}
    except Exception as exc:  # noqa: BLE001
        store.append_log(job["id"], f"Unable to write thermal surrogate model card: {exc}")
    return store.update(job["id"], "completed", result=result, message="COMSOL 参数扫描与本地代理模型训练已完成。")


def _ensure_comsol_server(config: dict[str, Any], store: JobStore, job_id: str) -> dict[str, Any]:
    host = str(config.get("comsol_server_host", "localhost"))
    port = int(config.get("comsol_server_port", 2036))
    log_path = store.logs_dir / f"{job_id}.mphserver.log"
    result = ensure_comsol_server(config, log_path=log_path)
    result["started_by_worker"] = bool(result.pop("started", False))
    if result.get("ready") and result.get("started_by_worker"):
        store.append_log(job_id, f"已请求启动 COMSOL mphserver：{host}:{port}。")
    return result


def _execution_failure_stage(diagnosis: dict[str, Any]) -> str:
    category = str(diagnosis.get("category", ""))
    return {
        "connection": "connect_server",
        "license": "connect_server",
        "livelink": "connect_server",
        "mesh": "build_mesh",
        "solver": "run_study",
        "timeout": "run_study",
        "result_validation": "export_results",
        "artifact": "save_mph",
        "variable": "build_model_tree",
        "api_property": "build_model_tree",
        "physics_interface": "build_model_tree",
    }.get(category, "build_model_tree")


def _matlab_runner(
    builder_path: str,
    mph_path: Path,
    results_csv_path: Path | None = None,
    output_definitions: dict[str, str] | None = None,
) -> str:
    builder = Path(builder_path)
    function_name = builder.stem
    definitions = output_definitions or {}
    preview_path = mph_path.with_name(f"{mph_path.stem}_preview.png")
    export_lines: list[str] = []
    if results_csv_path is not None and definitions:
        names = "{" + ", ".join(_matlab_string(name) for name in definitions) + "}"
        expressions = "{" + ", ".join(_matlab_string(expr) for expr in definitions.values()) + "}"
        export_lines = [
            f"  output_names = {names};",
            f"  output_expressions = {expressions};",
            f"  results_file = '{results_csv_path.as_posix()}';",
            "  results_fid = fopen(results_file, 'w');",
            "  if results_fid < 0, error('Unable to create results CSV: %s', results_file); end",
            "  fprintf(results_fid, 'name,expression,value\\n');",
            "  for output_index = 1:numel(output_names)",
            "    output_value = mphglobal(model, output_expressions{output_index});",
            "    fprintf(results_fid, '%s,\\\"%s\\\",%.16g\\n', output_names{output_index}, output_expressions{output_index}, output_value(1));",
            "  end",
            "  fclose(results_fid);",
            "  disp(['COMSOL_RESULTS_CSV=' results_file]);",
        ]
    return "\n".join(
        [
            "try",
            f"  addpath('{builder.parent.as_posix()}');",
            "  if exist('mphstart', 'file') ~= 0",
            "    server_host = getenv('COMSOL_MPH_HOST');",
            "    if isempty(server_host), server_host = 'localhost'; end",
            "    server_port = str2double(getenv('COMSOL_MPH_PORT'));",
            "    if isnan(server_port), server_port = 2036; end",
            "    mphstart(server_host, server_port);",
            "  else",
            "    error('LiveLink for COMSOL is not available on the MATLAB path.');",
            "  end",
            f"  model = {function_name}();",
            "  % Re-run mesh and study here so result export always targets a solved dataset.",
            "  model.component('comp1').mesh('mesh1').run;",
            "  model.study('std1').run;",
            f"  mphsave(model, '{mph_path.as_posix()}');",
            "  % Export a browser-friendly preview without making preview failure fail the model run.",
            f"  preview_file = '{preview_path.as_posix()}';",
            "  try",
            "    result_tags = model.result.tags;",
            "    if ~isempty(result_tags)",
            "      if iscell(result_tags), plot_group_tag = result_tags{1}; else, plot_group_tag = char(result_tags(1)); end",
            "      try, model.result.export.remove('observer_image'); catch, end",
            "      model.result.export.create('observer_image', 'Image');",
            "      model.result.export('observer_image').set('plotgroup', plot_group_tag);",
            "      model.result.export('observer_image').set('pngfilename', preview_file);",
            "      model.result.export('observer_image').run;",
            "    end",
            "  catch preview_result_error",
            "    disp(['COMSOL_PREVIEW_RESULT_WARNING=' preview_result_error.message]);",
            "  end",
            "  if exist(preview_file, 'file') == 0",
            "    try",
            "      preview_figure = figure('Visible', 'off', 'Color', 'white');",
            "      mphgeom(model, 'geom1');",
            "      axis equal;",
            "      print(preview_figure, preview_file, '-dpng', '-r160');",
            "      close(preview_figure);",
            "    catch preview_geometry_error",
            "      disp(['COMSOL_PREVIEW_GEOMETRY_WARNING=' preview_geometry_error.message]);",
            "      try, close(preview_figure); catch, end",
            "    end",
            "  end",
            "  if exist(preview_file, 'file') ~= 0, disp(['COMSOL_PREVIEW_PNG=' preview_file]); end",
            *export_lines,
            "  disp('COMSOL_EXECUTION_SUCCESS');",
            "catch ME",
            "  disp(getReport(ME, 'extended', 'hyperlinks', 'off'));",
            "  rethrow(ME);",
            "end",
            "",
        ]
    )


def _matlab_string(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
