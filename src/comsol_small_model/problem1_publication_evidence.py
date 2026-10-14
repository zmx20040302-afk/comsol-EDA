from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .static_model_audit import audit_generated_model_code, contract_sha256


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"JSONL 第 {number} 行必须为对象。")
        rows.append(value)
    return rows


def write_jsonl(path: str | Path, rows: Iterable[dict[str, Any]]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    return target


def prepare_external_regeneration_template(
    task_path: str | Path,
    output_path: str | Path,
) -> dict[str, Any]:
    tasks = read_jsonl(task_path)
    if not tasks:
        raise ValueError("外部整段重生成任务集不能为空。")
    output_target = Path(output_path)
    if output_target.is_file():
        existing = read_jsonl(output_target)
        measured = sum(str(row.get("record_status", "")).lower() in {"measured", "valid"} for row in existing)
        return {
            "task_count": len(existing),
            "output": str(output_target),
            "sha256": sha256_file(output_target),
            "status": "external_observations_present" if measured else "awaiting_external_model_observations",
            "measured_count": measured,
            "preserved_existing_file": True,
        }
    seen: set[str] = set()
    rows = []
    for task in tasks:
        task_id = str(task.get("id", "")).strip()
        if not task_id or task_id in seen:
            raise ValueError("任务 id 不能为空或重复。")
        seen.add(task_id)
        prompt = (
            "根据给定建模合同和失败信息，重新生成完整 MATLAB LiveLink for COMSOL 程序。"
            "只返回完整程序，不要返回局部补丁。程序必须创建模型、几何、材料、物理场、研究、结果并保存 MPH。"
        )
        rows.append({
            "task_id": task_id,
            "record_status": "template",
            "model_provider": "",
            "model_id": "",
            "model_version": "",
            "temperature": 0,
            "max_output_tokens": int(task.get("max_output_tokens", 8000)),
            "prompt": prompt,
            "contract": task["contract"],
            "failure_message": task["failure_message"],
            "broken_code": task["broken_code"],
            "broken_code_sha256": hashlib.sha256(task["broken_code"].encode("utf-8")).hexdigest(),
            "generated_code": "",
            "started_at": "",
            "completed_at": "",
            "run_id": "",
            "operator_id": "",
        })
    output = write_jsonl(output_target, rows)
    return {
        "task_count": len(rows),
        "output": str(output),
        "sha256": sha256_file(output),
        "status": "awaiting_external_model_observations",
        "measured_count": 0,
        "preserved_existing_file": False,
    }


def evaluate_external_regeneration(
    task_path: str | Path,
    response_path: str | Path,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    tasks = {str(row["id"]): row for row in read_jsonl(task_path)}
    responses = read_jsonl(response_path)
    active = [row for row in responses if str(row.get("record_status", "")).lower() in {"measured", "valid"}]
    if not active:
        report = {
            "schema": "dac-problem1-external-regeneration-evidence",
            "schemaVersion": "1.0.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "awaiting_external_model_observations",
            "passed": False,
            "measured_count": 0,
            "required_count": len(tasks),
            "policy": "Template, local proxy, or synthetic responses do not count as measured external-model evidence.",
        }
        return _write_report(report, output_path)
    if len(active) != len(tasks):
        raise ValueError(f"外部模型 measured 记录必须完整覆盖 {len(tasks)} 个任务。")
    ids = [str(row.get("task_id", "")) for row in active]
    if len(set(ids)) != len(ids) or set(ids) != set(tasks):
        raise ValueError("外部模型 task_id 必须无重复且与冻结任务集完全一致。")

    results = []
    for response in active:
        task = tasks[str(response["task_id"])]
        for field in ("model_provider", "model_id", "model_version", "run_id", "operator_id", "started_at", "completed_at"):
            if not str(response.get(field, "")).strip():
                raise ValueError(f"{response['task_id']} 缺少真实观测元数据：{field}")
        code = str(response.get("generated_code", ""))
        if not code.strip():
            raise ValueError(f"{response['task_id']} 缺少 generated_code。")
        audit = audit_generated_model_code(task["contract"], code)
        markers = [str(value) for value in task.get("required_markers", [])]
        missing_markers = [marker for marker in markers if marker not in code]
        results.append({
            "task_id": response["task_id"],
            "model_provider": response["model_provider"],
            "model_id": response["model_id"],
            "model_version": response["model_version"],
            "run_id": response["run_id"],
            "contract_sha256": contract_sha256(task["contract"]),
            "generated_code_sha256": hashlib.sha256(code.encode("utf-8")).hexdigest(),
            "static_audit_passed": bool(audit["passed"]),
            "contract_markers_passed": not missing_markers,
            "missing_contract_markers": missing_markers,
            "full_artifact_line_count": len(code.splitlines()),
            "passed": bool(audit["passed"] and not missing_markers),
        })
    passed = sum(bool(row["passed"]) for row in results)
    report = {
        "schema": "dac-problem1-external-regeneration-evidence",
        "schemaVersion": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "complete",
        "passed": passed == len(results),
        "measured_count": len(results),
        "required_count": len(tasks),
        "full_regeneration_success_count": passed,
        "full_regeneration_success_rate": passed / len(results),
        "task_file_sha256": sha256_file(task_path),
        "response_file_sha256": sha256_file(response_path),
        "results": results,
        "interpretation_limit": "Static audit and contract markers are necessary checks; COMSOL build and solve results must be recorded separately.",
    }
    return _write_report(report, output_path)


def validate_blind_task_submission(
    submission_path: str | Path,
    *,
    minimum_tasks: int = 24,
    minimum_families: int = 8,
) -> dict[str, Any]:
    rows = [row for row in read_jsonl(submission_path) if str(row.get("record_status", "")).lower() in {"measured", "valid"}]
    errors: list[str] = []
    if len(rows) < minimum_tasks:
        errors.append(f"真实盲测任务不足：{len(rows)}/{minimum_tasks}")
    ids = [str(row.get("id", "")).strip() for row in rows]
    if any(not value for value in ids) or len(set(ids)) != len(ids):
        errors.append("任务 id 存在空值或重复。")
    families = {str(row.get("family", "")).strip() for row in rows if str(row.get("family", "")).strip()}
    if len(families) < minimum_families:
        errors.append(f"器件族不足：{len(families)}/{minimum_families}")
    for row in rows:
        author = str(row.get("author_id", "")).strip()
        adjudicator = str(row.get("adjudicator_id", "")).strip()
        if not author or not adjudicator or author == adjudicator:
            errors.append(f"{row.get('id', '<unknown>')} 的作者与裁决者必须非空且不同。")
        if str(row.get("author_affiliation", "")).strip().lower() in {"project_team", "internal", "本项目组"}:
            errors.append(f"{row.get('id', '<unknown>')} 不是外部独立作者。")
        for field in ("requirement", "expected_interfaces", "expected_couplings", "expected_study", "expected_blocked", "authored_at", "adjudicated_at"):
            if field not in row or row[field] in (None, ""):
                errors.append(f"{row.get('id', '<unknown>')} 缺少 {field}。")
    return {
        "schema": "dac-problem1-blind-task-validation",
        "schemaVersion": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "complete" if not errors else ("awaiting_external_contributors" if not rows else "invalid"),
        "passed": not errors,
        "measured_task_count": len(rows),
        "family_count": len(families),
        "minimum_tasks": minimum_tasks,
        "minimum_families": minimum_families,
        "errors": errors,
        "submission_sha256": sha256_file(submission_path),
        "policy": "Project-authored, synthetic, template, or same-person authored-and-adjudicated tasks are rejected as independent blind evidence.",
    }


def _write_report(report: dict[str, Any], output_path: str | Path | None) -> dict[str, Any]:
    if output_path is not None:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
