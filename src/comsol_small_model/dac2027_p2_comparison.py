from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any

from .dac2027_p0_evaluation import exact_mcnemar, paired_bootstrap_difference, wilson


REQUIRED_RESPONSE_FIELDS = {
    "task_id",
    "method",
    "record_status",
    "parse_valid",
    "predicted_interfaces",
    "predicted_couplings",
    "predicted_study",
    "predicted_blocked",
    "completion_seconds",
    "interactions",
    "human_edits",
    "provider",
    "model_id",
    "model_version",
    "operator_id",
    "run_at",
}
ALLOWED_STUDIES = {"Stationary", "TimeDependent", "Frequency", "Eigenfrequency"}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def validate_frozen_inputs(root: Path, protocol: dict[str, Any]) -> dict[str, Any]:
    declared = [protocol["task_set"], *protocol["retrieval_corpus"], *protocol["local_method_sources"]]
    checks = []
    for item in declared:
        path = root / str(item["path"])
        actual = sha256(path) if path.is_file() else ""
        checks.append(
            {
                "path": str(item["path"]),
                "exists": path.is_file(),
                "expected_sha256": str(item["sha256"]),
                "actual_sha256": actual,
                "matches": path.is_file() and actual == str(item["sha256"]),
            }
        )
    if not all(row["matches"] for row in checks):
        failed = [row["path"] for row in checks if not row["matches"]]
        raise ValueError(f"frozen P2 input hash mismatch: {failed}")
    return {"valid": True, "files": checks}


def validate_internal_tasks(tasks: list[dict[str, Any]], protocol: dict[str, Any]) -> dict[str, Any]:
    expected = protocol["task_set"]
    errors: list[str] = []
    if len(tasks) != int(expected["task_count"]):
        errors.append(f"expected {expected['task_count']} tasks, found {len(tasks)}")
    families = {str(row.get("family", "")) for row in tasks}
    if len(families) != int(expected["family_count"]):
        errors.append(f"expected {expected['family_count']} families, found {len(families)}")
    counts = Counter(str(row.get("status", "")) for row in tasks)
    if dict(counts) != expected["status_counts"]:
        errors.append(f"status counts mismatch: {dict(counts)}")
    ids = [str(row.get("id", "")) for row in tasks]
    if any(not item for item in ids) or len(set(ids)) != len(ids):
        errors.append("task ids must be unique and nonempty")
    required = {"id", "family", "status", "requirement", "interfaces", "couplings", "study", "expected_blocked"}
    for index, row in enumerate(tasks, 1):
        missing = sorted(required - set(row))
        if missing:
            errors.append(f"row {index} missing {missing}")
        if row.get("study") not in ALLOWED_STUDIES:
            errors.append(f"row {index} has unsupported study")
        if not isinstance(row.get("interfaces"), list) or not isinstance(row.get("couplings"), list):
            errors.append(f"row {index} interfaces/couplings must be arrays")
    if errors:
        raise ValueError("; ".join(errors))
    return {"valid": True, "task_count": len(tasks), "family_count": len(families), "status_counts": dict(counts)}


def parse_llm_output(text: str) -> dict[str, Any]:
    clean = text.strip()
    if clean.startswith("```"):
        lines = clean.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        clean = "\n".join(lines).strip()
    start = clean.find("{")
    end = clean.rfind("}")
    if start < 0 or end < start:
        raise ValueError("LLM output contains no JSON object")
    data = json.loads(clean[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("LLM output must be a JSON object")
    interfaces = data.get("predicted_interfaces")
    couplings = data.get("predicted_couplings")
    study = data.get("predicted_study")
    blocked = data.get("predicted_blocked")
    if not isinstance(interfaces, list) or not all(isinstance(value, str) for value in interfaces):
        raise ValueError("predicted_interfaces must be a string array")
    if not isinstance(couplings, list) or not all(isinstance(value, str) for value in couplings):
        raise ValueError("predicted_couplings must be a string array")
    if study not in ALLOWED_STUDIES:
        raise ValueError("predicted_study is invalid")
    if not isinstance(blocked, bool):
        raise ValueError("predicted_blocked must be boolean")
    return {
        "predicted_interfaces": interfaces,
        "predicted_couplings": couplings,
        "predicted_study": study,
        "predicted_blocked": blocked,
    }


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    blocked_tasks = [row for row in rows if row["expected_blocked"]]
    complete_tasks = [row for row in rows if not row["expected_blocked"]]
    selection = sum(row["selection_ok"] for row in rows)
    study = sum(row["study_ok"] for row in rows)
    gate = sum(row["gate_ok"] for row in rows)
    valid = sum(row["parse_valid"] for row in rows)
    false_safe = sum(row["parse_valid"] and not row["predicted_blocked"] for row in blocked_tasks)
    false_block = sum(row["parse_valid"] and row["predicted_blocked"] for row in complete_tasks)
    return {
        "task_count": total,
        "valid_output_count": valid,
        "invalid_output_count": total - valid,
        "physics_and_coupling_exact_count": selection,
        "physics_and_coupling_exact_accuracy": round(selection / total, 4),
        "physics_and_coupling_exact_wilson95": wilson(selection, total),
        "study_exact_count": study,
        "study_exact_accuracy": round(study / total, 4),
        "study_exact_wilson95": wilson(study, total),
        "gate_correct_count": gate,
        "gate_accuracy": round(gate / total, 4),
        "gate_accuracy_wilson95": wilson(gate, total),
        "false_safe_count": false_safe,
        "false_safe_rate": round(false_safe / len(blocked_tasks), 4),
        "false_safe_wilson95": wilson(false_safe, len(blocked_tasks)),
        "false_block_count": false_block,
        "false_block_rate": round(false_block / len(complete_tasks), 4),
        "median_completion_seconds": round(median(float(row["completion_seconds"]) for row in rows), 4),
        "median_interactions": round(median(float(row["interactions"]) for row in rows), 4),
        "median_human_edits": round(median(float(row["human_edits"]) for row in rows), 4),
    }


def evaluate_p2(
    tasks: list[dict[str, Any]], responses: list[dict[str, Any]], protocol: dict[str, Any]
) -> dict[str, Any]:
    task_validation = validate_internal_tasks(tasks, protocol)
    task_by_id = {str(row["id"]): row for row in tasks}
    methods = list(protocol["methods"])
    expected_keys = {(task_id, method) for task_id in task_by_id for method in methods}
    keys = [(str(row.get("task_id", "")), str(row.get("method", ""))) for row in responses]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate P2 response row")
    missing = expected_keys - set(keys)
    extra = set(keys) - expected_keys
    if missing or extra:
        raise ValueError(f"P2 response coverage mismatch; missing={len(missing)}, extra={len(extra)}")
    details: list[dict[str, Any]] = []
    for index, row in enumerate(responses, 1):
        missing_fields = REQUIRED_RESPONSE_FIELDS - set(row)
        if missing_fields:
            raise ValueError(f"response row {index} missing fields: {sorted(missing_fields)}")
        if row["record_status"] != "measured":
            raise ValueError(f"response row {index} is not measured")
        task = task_by_id[str(row["task_id"])]
        parse_valid = bool(row["parse_valid"])
        selection_ok = parse_valid and set(row["predicted_interfaces"]) == set(task["interfaces"]) and set(
            row["predicted_couplings"]
        ) == set(task["couplings"])
        study_ok = parse_valid and row["predicted_study"] == task["study"]
        gate_ok = parse_valid and bool(row["predicted_blocked"]) == bool(task["expected_blocked"])
        details.append(
            {
                **row,
                "family": task["family"],
                "status": task["status"],
                "expected_interfaces": task["interfaces"],
                "expected_couplings": task["couplings"],
                "expected_study": task["study"],
                "expected_blocked": bool(task["expected_blocked"]),
                "selection_ok": selection_ok,
                "study_ok": study_ok,
                "gate_ok": gate_ok,
            }
        )
    rows_by_method = {method: [row for row in details if row["method"] == method] for method in methods}
    summaries = {method: _summarize(rows) for method, rows in rows_by_method.items()}
    full_method = "contract_dependency_v11"
    full = {row["task_id"]: row for row in rows_by_method[full_method]}
    comparisons: dict[str, Any] = {}
    ordered_ids = sorted(task_by_id)
    for method in methods:
        if method == full_method:
            continue
        baseline = {row["task_id"]: row for row in rows_by_method[method]}
        comparisons[method] = {
            "selection_mcnemar": exact_mcnemar(
                [full[item]["selection_ok"] for item in ordered_ids],
                [baseline[item]["selection_ok"] for item in ordered_ids],
            ),
            "gate_mcnemar": exact_mcnemar(
                [full[item]["gate_ok"] for item in ordered_ids],
                [baseline[item]["gate_ok"] for item in ordered_ids],
            ),
            "completion_time": paired_bootstrap_difference(
                [full[item]["completion_seconds"] for item in ordered_ids],
                [baseline[item]["completion_seconds"] for item in ordered_ids],
                seed=int(protocol["statistics"]["bootstrap_seed"]),
                resamples=int(protocol["statistics"]["bootstrap_resamples"]),
            ),
        }
    return {
        "schema": "dac2027-p2-controlled-comparison-report",
        "schemaVersion": "1.0.0",
        "publication_main_result": False,
        "evidence_tier": protocol["evidence_tier"],
        "task_validation": task_validation,
        "method_count": len(methods),
        "measured_response_count": len(responses),
        "methods": summaries,
        "paired_comparisons_against_full_method": comparisons,
        "details": details,
        "evidence_boundary": protocol["evidence_boundary"],
    }

