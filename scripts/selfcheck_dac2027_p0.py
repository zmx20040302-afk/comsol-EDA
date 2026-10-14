from __future__ import annotations

import copy
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from comsol_small_model.dac2027_p0_evaluation import (
    evaluate_method_responses,
    exact_mcnemar,
    prepare_method_response_rows,
    validate_blind_tasks,
)


def expect_value_error(function, *args) -> None:
    try:
        function(*args)
    except ValueError:
        return
    raise AssertionError("expected ValueError")


def main() -> int:
    protocol = {
        "blind_task_policy": {"task_count": 24, "family_count": 8, "status_counts": {"complete": 8, "missing": 8, "conflict": 8}},
        "methods": ["direct_llm", "retrieval_llm", "existing_selector", "contract_dependency_v11"],
        "full_method": "contract_dependency_v11",
        "statistics": {"bootstrap_seed": 7, "bootstrap_resamples": 100},
    }
    tasks = []
    for family in range(8):
        for status in ("complete", "missing", "conflict"):
            tasks.append({
                "id": f"f{family}-{status}", "family": f"family-{family}", "status": status,
                "requirement": f"requirement {family} {status}", "interfaces": ["heat_transfer_solids"],
                "couplings": [], "study": "Stationary", "expected_blocked": status != "complete",
                "record_status": "measured", "author_id": f"author-{family}",
                "author_affiliation": f"external-lab-{family}", "adjudicator_id": f"judge-{family}",
                "independence_attestation": True,
            })
    assert validate_blind_tasks(tasks, protocol)["task_count"] == 24
    bad = copy.deepcopy(tasks)
    bad[0]["record_status"] = "template"
    expect_value_error(validate_blind_tasks, bad, protocol)
    bad = copy.deepcopy(tasks)
    bad[0]["author_affiliation"] = "project_team"
    expect_value_error(validate_blind_tasks, bad, protocol)
    assert exact_mcnemar([True] * 8, [False] * 8)["two_sided_exact_p"] == 0.007812
    responses = prepare_method_response_rows(tasks, protocol)
    by_id = {row["id"]: row for row in tasks}
    for row in responses:
        task = by_id[row["task_id"]]
        row.update({
            "record_status": "measured", "predicted_interfaces": task["interfaces"],
            "predicted_couplings": [], "predicted_study": "Stationary",
            "predicted_blocked": task["expected_blocked"], "completion_seconds": 10.0,
            "interactions": 1, "human_edits": 0, "provider": "frozen-provider",
            "model_id": "frozen-model", "model_version": "v1", "operator_id": "operator",
            "run_at": "2026-10-13T00:00:00+08:00",
        })
    report = evaluate_method_responses(tasks, responses, protocol)
    assert all(row["gate_accuracy"] == 1.0 for row in report["methods"].values())
    expect_value_error(evaluate_method_responses, tasks, responses[:-1], protocol)
    print("dac2027_p0 selfcheck: 7/7 checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
