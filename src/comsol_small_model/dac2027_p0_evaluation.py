from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from statistics import median
from typing import Any, Iterable


REQUIRED_TASK_FIELDS = {
    "id", "family", "status", "requirement", "interfaces", "couplings",
    "study", "expected_blocked", "record_status", "author_id",
    "author_affiliation", "adjudicator_id", "independence_attestation",
}


def wilson(successes: int, total: int) -> list[float]:
    if total <= 0:
        return [0.0, 0.0]
    z = 1.959963984540054
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denominator
    return [round(max(0.0, center - margin), 4), round(min(1.0, center + margin), 4)]


def exact_mcnemar(full_correct: Iterable[bool], baseline_correct: Iterable[bool]) -> dict[str, Any]:
    pairs = list(zip(full_correct, baseline_correct))
    full_only = sum(bool(a) and not bool(b) for a, b in pairs)
    baseline_only = sum(not bool(a) and bool(b) for a, b in pairs)
    discordant = full_only + baseline_only
    if discordant == 0:
        p_value = 1.0
    else:
        tail = sum(math.comb(discordant, k) for k in range(min(full_only, baseline_only) + 1))
        p_value = min(1.0, 2.0 * tail / (2 ** discordant))
    return {
        "paired_count": len(pairs),
        "full_only_correct": full_only,
        "baseline_only_correct": baseline_only,
        "discordant_count": discordant,
        "two_sided_exact_p": round(p_value, 6),
    }


def paired_bootstrap_difference(
    full_values: Iterable[float], baseline_values: Iterable[float], *, seed: int, resamples: int
) -> dict[str, Any]:
    pairs = [(float(a), float(b)) for a, b in zip(full_values, baseline_values)]
    if not pairs:
        return {"paired_count": 0, "baseline_minus_full_median": None, "bootstrap95": [None, None]}
    differences = [b - a for a, b in pairs]
    rng = random.Random(seed)
    estimates = []
    for _ in range(resamples):
        estimates.append(median(rng.choice(differences) for _ in differences))
    estimates.sort()
    lo = estimates[int(0.025 * (len(estimates) - 1))]
    hi = estimates[int(0.975 * (len(estimates) - 1))]
    return {
        "paired_count": len(pairs),
        "baseline_minus_full_median": round(median(differences), 4),
        "bootstrap95": [round(lo, 4), round(hi, 4)],
        "positive_favors_full_method": True,
    }


def validate_blind_tasks(tasks: list[dict[str, Any]], protocol: dict[str, Any]) -> dict[str, Any]:
    policy = protocol["blind_task_policy"]
    errors: list[str] = []
    if len(tasks) != int(policy["task_count"]):
        errors.append(f"expected {policy['task_count']} tasks, found {len(tasks)}")
    ids = [str(row.get("id", "")) for row in tasks]
    if len(set(ids)) != len(ids) or any(not item for item in ids):
        errors.append("task ids must be nonempty and unique")
    families = {str(row.get("family", "")) for row in tasks if row.get("family")}
    if len(families) != int(policy["family_count"]):
        errors.append(f"expected {policy['family_count']} families, found {len(families)}")
    counts = Counter(str(row.get("status", "")) for row in tasks)
    if dict(counts) != policy["status_counts"]:
        errors.append(f"status counts mismatch: {dict(counts)}")
    for index, row in enumerate(tasks, 1):
        missing = sorted(REQUIRED_TASK_FIELDS - set(row))
        if missing:
            errors.append(f"row {index} missing fields: {', '.join(missing)}")
            continue
        if row["record_status"] != "measured":
            errors.append(f"row {index} is not a measured blind task")
        if not str(row["requirement"]).strip():
            errors.append(f"row {index} requirement is empty")
        if not isinstance(row["interfaces"], list) or not isinstance(row["couplings"], list):
            errors.append(f"row {index} interfaces/couplings must be arrays")
        if row["status"] == "complete" and bool(row["expected_blocked"]):
            errors.append(f"row {index} complete task must not be blocked")
        if row["status"] in {"missing", "conflict"} and not bool(row["expected_blocked"]):
            errors.append(f"row {index} {row['status']} task must be blocked")
        if not bool(row["independence_attestation"]):
            errors.append(f"row {index} lacks independence attestation")
        affiliation = str(row["author_affiliation"]).strip().lower()
        if affiliation in {"", "project_team", "internal", "same_project"}:
            errors.append(f"row {index} author is not declared external")
        if str(row["author_id"]).strip() == str(row["adjudicator_id"]).strip():
            errors.append(f"row {index} author and adjudicator must differ")
    by_family: dict[str, Counter[str]] = defaultdict(Counter)
    for row in tasks:
        by_family[str(row.get("family", ""))][str(row.get("status", ""))] += 1
    for family, family_counts in by_family.items():
        if family_counts != Counter({"complete": 1, "missing": 1, "conflict": 1}):
            errors.append(f"family {family} must contain one task per status")
    if errors:
        raise ValueError("; ".join(errors))
    return {
        "valid": True,
        "task_count": len(tasks),
        "family_count": len(families),
        "status_counts": dict(counts),
        "independence_basis": "self-reported metadata plus separate adjudicator IDs",
    }


def prepare_method_response_rows(tasks: list[dict[str, Any]], protocol: dict[str, Any]) -> list[dict[str, Any]]:
    validate_blind_tasks(tasks, protocol)
    return [
        {
            "task_id": task["id"],
            "method": method,
            "record_status": "template",
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
            "run_at": ""
        }
        for task in tasks for method in protocol["methods"]
    ]


def evaluate_method_responses(
    tasks: list[dict[str, Any]], responses: list[dict[str, Any]], protocol: dict[str, Any]
) -> dict[str, Any]:
    validation = validate_blind_tasks(tasks, protocol)
    task_by_id = {row["id"]: row for row in tasks}
    expected_keys = {(task_id, method) for task_id in task_by_id for method in protocol["methods"]}
    measured = [row for row in responses if row.get("record_status") == "measured"]
    keys = [(str(row.get("task_id", "")), str(row.get("method", ""))) for row in measured]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate measured method response")
    missing = sorted(expected_keys - set(keys))
    extra = sorted(set(keys) - expected_keys)
    if missing or extra:
        raise ValueError(f"method response coverage mismatch; missing={len(missing)}, extra={len(extra)}")

    for index, row in enumerate(measured, 1):
        for field in ("predicted_interfaces", "predicted_couplings"):
            if not isinstance(row.get(field), list):
                raise ValueError(f"response row {index} {field} must be an array")
        if not isinstance(row.get("predicted_blocked"), bool):
            raise ValueError(f"response row {index} predicted_blocked must be boolean")
        if not str(row.get("predicted_study", "")).strip():
            raise ValueError(f"response row {index} predicted_study is empty")
        for field in ("completion_seconds", "interactions", "human_edits"):
            value = row.get(field)
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
                raise ValueError(f"response row {index} {field} must be a nonnegative number")
        if row["method"] in {"direct_llm", "retrieval_llm"}:
            for field in ("provider", "model_id", "model_version", "operator_id", "run_at"):
                if not str(row.get(field, "")).strip():
                    raise ValueError(f"response row {index} external method metadata missing: {field}")

    details: list[dict[str, Any]] = []
    for row in measured:
        task = task_by_id[row["task_id"]]
        selection_ok = (
            set(row.get("predicted_interfaces", [])) == set(task["interfaces"])
            and set(row.get("predicted_couplings", [])) == set(task["couplings"])
        )
        study_ok = row.get("predicted_study") == task["study"]
        gate_ok = bool(row.get("predicted_blocked")) == bool(task["expected_blocked"])
        details.append({
            **row,
            "expected_status": task["status"],
            "expected_blocked": bool(task["expected_blocked"]),
            "selection_ok": selection_ok,
            "study_ok": study_ok,
            "gate_ok": gate_ok,
        })

    summaries: dict[str, Any] = {}
    rows_by_method = {method: [r for r in details if r["method"] == method] for method in protocol["methods"]}
    for method, rows in rows_by_method.items():
        total = len(rows)
        blocked = [r for r in rows if r["expected_blocked"]]
        complete = [r for r in rows if not r["expected_blocked"]]
        selection = sum(r["selection_ok"] for r in rows)
        study = sum(r["study_ok"] for r in rows)
        gate = sum(r["gate_ok"] for r in rows)
        false_safe = sum(not bool(r["predicted_blocked"]) for r in blocked)
        false_block = sum(bool(r["predicted_blocked"]) for r in complete)
        summaries[method] = {
            "task_count": total,
            "physics_and_coupling_exact_accuracy": round(selection / total, 4),
            "physics_and_coupling_exact_wilson95": wilson(selection, total),
            "study_exact_accuracy": round(study / total, 4),
            "study_exact_wilson95": wilson(study, total),
            "gate_accuracy": round(gate / total, 4),
            "gate_accuracy_wilson95": wilson(gate, total),
            "false_safe_count": false_safe,
            "false_safe_rate": round(false_safe / len(blocked), 4),
            "false_safe_wilson95": wilson(false_safe, len(blocked)),
            "false_block_count": false_block,
            "false_block_rate": round(false_block / len(complete), 4),
            "median_completion_seconds": round(median(float(r["completion_seconds"]) for r in rows), 4),
            "median_interactions": round(median(float(r["interactions"]) for r in rows), 4),
            "median_human_edits": round(median(float(r["human_edits"]) for r in rows), 4),
        }

    full = protocol["full_method"]
    full_rows = {r["task_id"]: r for r in rows_by_method[full]}
    comparisons = {}
    for baseline in protocol["methods"]:
        if baseline == full:
            continue
        base_rows = {r["task_id"]: r for r in rows_by_method[baseline]}
        ids = sorted(task_by_id)
        comparisons[baseline] = {
            "selection_mcnemar": exact_mcnemar(
                [full_rows[i]["selection_ok"] for i in ids], [base_rows[i]["selection_ok"] for i in ids]
            ),
            "gate_mcnemar": exact_mcnemar(
                [full_rows[i]["gate_ok"] for i in ids], [base_rows[i]["gate_ok"] for i in ids]
            ),
            "completion_time": paired_bootstrap_difference(
                [full_rows[i]["completion_seconds"] for i in ids],
                [base_rows[i]["completion_seconds"] for i in ids],
                seed=int(protocol["statistics"]["bootstrap_seed"]),
                resamples=int(protocol["statistics"]["bootstrap_resamples"]),
            ),
        }
    return {
        "schema": "dac2027-p0-blind-evaluation",
        "schemaVersion": "1.0.0",
        "publication_evidence": True,
        "validation": validation,
        "methods": summaries,
        "paired_comparisons_against_full_method": comparisons,
        "details": details,
        "independence_limit": "Independence is supported by submitted attestations and distinct IDs; identity and affiliation still require human audit.",
    }
