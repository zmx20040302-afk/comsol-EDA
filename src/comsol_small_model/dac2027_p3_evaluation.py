from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median
from typing import Any

from .dac2027_p0_evaluation import exact_mcnemar, paired_bootstrap_difference, validate_blind_tasks, wilson


REQUIRED_RESPONSE_FIELDS = {
    "task_id", "method", "repeat_index", "record_status", "parse_valid",
    "predicted_interfaces", "predicted_couplings", "predicted_study",
    "predicted_blocked", "completion_seconds", "interactions", "human_edits",
    "provider", "model_id", "model_version", "operator_id", "run_at",
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


def validate_frozen_assets(root: Path, protocol: dict[str, Any]) -> dict[str, Any]:
    declared = [
        *protocol.get("retrieval_corpus", []),
        *protocol.get("local_method_sources", []),
        *protocol.get("historical_family_sources", []),
    ]
    checks: list[dict[str, Any]] = []
    for item in declared:
        path = root / str(item["path"])
        actual = sha256(path) if path.is_file() else ""
        checks.append({
            "path": str(item["path"]),
            "exists": path.is_file(),
            "expected_sha256": str(item["sha256"]),
            "actual_sha256": actual,
            "matches": path.is_file() and actual == str(item["sha256"]),
        })
    failed = [row["path"] for row in checks if not row["matches"]]
    if failed:
        raise ValueError(f"frozen P3 asset hash mismatch: {failed}")
    return {"valid": True, "file_count": len(checks), "files": checks}


def historical_families(root: Path, protocol: dict[str, Any]) -> set[str]:
    values: set[str] = set()
    for item in protocol.get("historical_family_sources", []):
        for row in load_jsonl(root / str(item["path"])):
            family = str(row.get("family", "")).strip().casefold()
            if family:
                values.add(family)
    return values


def validate_case_isolation(tasks: list[dict[str, Any]], historical: set[str]) -> dict[str, Any]:
    current = {str(row.get("family", "")).strip().casefold() for row in tasks if str(row.get("family", "")).strip()}
    overlap = sorted(current & historical)
    if overlap:
        raise ValueError(f"P3 family leakage detected: {overlap}")
    return {
        "valid": True,
        "prospective_family_count": len(current),
        "historical_family_count": len(historical),
        "overlap_count": 0,
        "overlap": [],
    }


def expected_response_keys(tasks: list[dict[str, Any]], protocol: dict[str, Any]) -> set[tuple[str, str, int]]:
    return {
        (str(task["id"]), method, repeat_index)
        for task in tasks
        for method in protocol["methods"]
        for repeat_index in range(1, int(protocol["repetitions"][method]) + 1)
    }


def prepare_response_rows(tasks: list[dict[str, Any]], protocol: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for task_id, method, repeat_index in sorted(expected_response_keys(tasks, protocol)):
        rows.append({
            "task_id": task_id,
            "method": method,
            "repeat_index": repeat_index,
            "record_status": "template",
            "parse_valid": False,
            "predicted_interfaces": [],
            "predicted_couplings": [],
            "predicted_study": "",
            "predicted_blocked": None,
            "completion_seconds": None,
            "interactions": None,
            "human_edits": None,
            "provider": "",
            "model_id": "",
            "model_version": "",
            "operator_id": "",
            "run_at": "",
        })
    return rows


def _prediction_key(row: dict[str, Any]) -> tuple[bool, tuple[str, ...], tuple[str, ...], str, bool]:
    return (
        bool(row["parse_valid"]),
        tuple(sorted(str(value) for value in row["predicted_interfaces"])),
        tuple(sorted(str(value) for value in row["predicted_couplings"])),
        str(row["predicted_study"]),
        bool(row["predicted_blocked"]),
    )


def _consensus(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter(_prediction_key(row) for row in rows)
    best_count = max(counts.values())
    winners = sorted(key for key, count in counts.items() if count == best_count)
    key = winners[0]
    return {
        "parse_valid": key[0],
        "predicted_interfaces": list(key[1]),
        "predicted_couplings": list(key[2]),
        "predicted_study": key[3],
        "predicted_blocked": key[4],
        "consensus_votes": best_count,
        "repeat_count": len(rows),
        "unanimous": len(counts) == 1,
        "unique_prediction_count": len(counts),
        "median_completion_seconds": round(median(float(row["completion_seconds"]) for row in rows), 4),
    }


def _score(task: dict[str, Any], prediction: dict[str, Any]) -> dict[str, Any]:
    if not bool(prediction.get("parse_valid")):
        return {
            "selection_ok": False,
            "study_ok": False,
            "gate_ok": False,
            "failure_types": ["invalid_output"],
        }
    selection_ok = (
        set(prediction["predicted_interfaces"]) == set(task["interfaces"])
        and set(prediction["predicted_couplings"]) == set(task["couplings"])
    )
    study_ok = prediction["predicted_study"] == task["study"]
    gate_ok = bool(prediction["predicted_blocked"]) == bool(task["expected_blocked"])
    failures = []
    if not selection_ok:
        failures.append("physics_or_coupling_mismatch")
    if not study_ok:
        failures.append("study_mismatch")
    if bool(task["expected_blocked"]) and not bool(prediction["predicted_blocked"]):
        failures.append("false_safe")
    if not bool(task["expected_blocked"]) and bool(prediction["predicted_blocked"]):
        failures.append("false_block")
    return {
        "selection_ok": selection_ok,
        "study_ok": study_ok,
        "gate_ok": gate_ok,
        "failure_types": failures or ["correct"],
    }


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    blocked = [row for row in rows if row["expected_blocked"]]
    complete = [row for row in rows if not row["expected_blocked"]]
    selection = sum(bool(row["selection_ok"]) for row in rows)
    study = sum(bool(row["study_ok"]) for row in rows)
    gate = sum(bool(row["gate_ok"]) for row in rows)
    false_safe = sum("false_safe" in row["failure_types"] for row in blocked)
    false_block = sum("false_block" in row["failure_types"] for row in complete)
    return {
        "task_count": total,
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
        "false_safe_rate": round(false_safe / len(blocked), 4) if blocked else 0.0,
        "false_safe_wilson95": wilson(false_safe, len(blocked)),
        "false_block_count": false_block,
        "false_block_rate": round(false_block / len(complete), 4) if complete else 0.0,
        "failure_taxonomy": dict(sorted(Counter(value for row in rows for value in row["failure_types"] if value != "correct").items())),
    }


def evaluate_p3(
    root: Path,
    tasks: list[dict[str, Any]],
    responses: list[dict[str, Any]],
    protocol: dict[str, Any],
) -> dict[str, Any]:
    assets = validate_frozen_assets(root, protocol)
    task_validation = validate_blind_tasks(tasks, {
        "blind_task_policy": {
            "task_count": protocol["task_source"]["required_task_count"],
            "family_count": protocol["task_source"]["required_family_count"],
            "status_counts": protocol["task_source"]["required_status_counts"],
        }
    })
    isolation = validate_case_isolation(tasks, historical_families(root, protocol))
    expected = expected_response_keys(tasks, protocol)
    keys = [(str(row.get("task_id", "")), str(row.get("method", "")), int(row.get("repeat_index", 0))) for row in responses]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate P3 response row")
    missing = expected - set(keys)
    extra = set(keys) - expected
    if missing or extra:
        raise ValueError(f"P3 response coverage mismatch; missing={len(missing)}, extra={len(extra)}")
    task_by_id = {str(row["id"]): row for row in tasks}
    for index, row in enumerate(responses, 1):
        absent = REQUIRED_RESPONSE_FIELDS - set(row)
        if absent:
            raise ValueError(f"response row {index} missing fields: {sorted(absent)}")
        if row["record_status"] != "measured":
            raise ValueError(f"response row {index} is not measured")
        if not isinstance(row["parse_valid"], bool):
            raise ValueError(f"response row {index} parse_valid must be boolean")
        if not isinstance(row["predicted_interfaces"], list) or not isinstance(row["predicted_couplings"], list):
            raise ValueError(f"response row {index} interfaces/couplings must be arrays")
        if row["parse_valid"] and row["predicted_study"] not in ALLOWED_STUDIES:
            raise ValueError(f"response row {index} study is invalid")
        if not isinstance(row["predicted_blocked"], bool):
            raise ValueError(f"response row {index} prediction contract is invalid")
        for field in ("completion_seconds", "interactions", "human_edits"):
            value = row[field]
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
                raise ValueError(f"response row {index} {field} must be nonnegative")

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in responses:
        grouped[(str(row["task_id"]), str(row["method"]))].append(row)
    consensus_rows: list[dict[str, Any]] = []
    repeat_stability: dict[str, Any] = {}
    for method in protocol["methods"]:
        unanimous = 0
        varying: list[str] = []
        for task in tasks:
            runs = sorted(grouped[(str(task["id"]), method)], key=lambda row: int(row["repeat_index"]))
            prediction = _consensus(runs)
            scored = _score(task, prediction)
            consensus_rows.append({
                "task_id": task["id"],
                "family": task["family"],
                "status": task["status"],
                "method": method,
                "expected_interfaces": task["interfaces"],
                "expected_couplings": task["couplings"],
                "expected_study": task["study"],
                "expected_blocked": bool(task["expected_blocked"]),
                **prediction,
                **scored,
            })
            if prediction["unanimous"]:
                unanimous += 1
            else:
                varying.append(str(task["id"]))
        repeat_stability[method] = {
            "task_count": len(tasks),
            "repeat_count_per_task": int(protocol["repetitions"][method]),
            "unanimous_task_count": unanimous,
            "unanimous_task_rate": round(unanimous / len(tasks), 4),
            "varying_task_count": len(varying),
            "varying_task_ids": varying,
        }

    by_method = {method: [row for row in consensus_rows if row["method"] == method] for method in protocol["methods"]}
    summaries = {method: _summary(rows) for method, rows in by_method.items()}
    per_family: dict[str, Any] = {}
    for family in sorted({str(task["family"]) for task in tasks}):
        per_family[family] = {
            method: _summary([row for row in by_method[method] if row["family"] == family])
            for method in protocol["methods"]
        }
    full_method = str(protocol["full_method"])
    full = {str(row["task_id"]): row for row in by_method[full_method]}
    ordered_ids = sorted(task_by_id)
    comparisons: dict[str, Any] = {}
    for method in protocol["methods"]:
        if method == full_method:
            continue
        base = {str(row["task_id"]): row for row in by_method[method]}
        comparisons[method] = {
            "selection_mcnemar": exact_mcnemar(
                [full[item]["selection_ok"] for item in ordered_ids],
                [base[item]["selection_ok"] for item in ordered_ids],
            ),
            "gate_mcnemar": exact_mcnemar(
                [full[item]["gate_ok"] for item in ordered_ids],
                [base[item]["gate_ok"] for item in ordered_ids],
            ),
            "completion_time": paired_bootstrap_difference(
                [full[item]["median_completion_seconds"] for item in ordered_ids],
                [base[item]["median_completion_seconds"] for item in ordered_ids],
                seed=int(protocol["statistics"]["bootstrap_seed"]),
                resamples=int(protocol["statistics"]["bootstrap_resamples"]),
            ),
        }
    return {
        "schema": "dac2027-p3-prospective-multicase-report",
        "schemaVersion": "1.0.0",
        "publication_main_result": True,
        "frozen_assets": assets,
        "task_validation": task_validation,
        "case_isolation": isolation,
        "task_count": len(tasks),
        "family_count": isolation["prospective_family_count"],
        "measured_observation_count": len(responses),
        "expected_observation_count": len(expected),
        "methods": summaries,
        "repeat_stability": repeat_stability,
        "per_family": per_family,
        "paired_comparisons_against_full_method": comparisons,
        "details": consensus_rows,
        "evidence_boundary": protocol["evidence_boundary"],
    }
