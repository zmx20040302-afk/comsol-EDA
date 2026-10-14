from __future__ import annotations

import copy

import pytest

from comsol_small_model.dac2027_p0_evaluation import (
    evaluate_method_responses,
    exact_mcnemar,
    prepare_method_response_rows,
    validate_blind_tasks,
)


def protocol() -> dict:
    return {
        "blind_task_policy": {
            "task_count": 24,
            "family_count": 8,
            "status_counts": {"complete": 8, "missing": 8, "conflict": 8},
        },
        "methods": ["direct_llm", "retrieval_llm", "existing_selector", "contract_dependency_v11"],
        "full_method": "contract_dependency_v11",
        "statistics": {"bootstrap_seed": 7, "bootstrap_resamples": 100},
    }


def tasks() -> list[dict]:
    rows = []
    for family in range(8):
        for status in ("complete", "missing", "conflict"):
            rows.append({
                "id": f"f{family}-{status}",
                "family": f"family-{family}",
                "status": status,
                "requirement": f"external requirement {family} {status}",
                "interfaces": ["heat_transfer_solids"],
                "couplings": [],
                "study": "Stationary",
                "expected_blocked": status != "complete",
                "record_status": "measured",
                "author_id": f"author-{family}",
                "author_affiliation": f"external-lab-{family}",
                "adjudicator_id": f"judge-{family}",
                "independence_attestation": True,
            })
    return rows


def measured_responses(rows: list[dict]) -> list[dict]:
    output = prepare_method_response_rows(rows, protocol())
    by_id = {row["id"]: row for row in rows}
    for row in output:
        task = by_id[row["task_id"]]
        row.update({
            "record_status": "measured",
            "predicted_interfaces": task["interfaces"],
            "predicted_couplings": task["couplings"],
            "predicted_study": task["study"],
            "predicted_blocked": task["expected_blocked"],
            "completion_seconds": 10.0,
            "interactions": 1,
            "human_edits": 0,
            "provider": "provider" if "llm" in row["method"] else "local",
            "model_id": "model" if "llm" in row["method"] else "deterministic",
            "model_version": "frozen-v1",
            "operator_id": "operator-1",
            "run_at": "2026-10-13T00:00:00+08:00",
        })
    return output


def test_validates_balanced_external_blind_tasks() -> None:
    result = validate_blind_tasks(tasks(), protocol())
    assert result["task_count"] == 24
    assert result["family_count"] == 8


@pytest.mark.parametrize("mutation", ["internal", "same_judge", "template"])
def test_rejects_nonpublication_task_metadata(mutation: str) -> None:
    rows = tasks()
    if mutation == "internal":
        rows[0]["author_affiliation"] = "project_team"
    elif mutation == "same_judge":
        rows[0]["adjudicator_id"] = rows[0]["author_id"]
    else:
        rows[0]["record_status"] = "template"
    with pytest.raises(ValueError):
        validate_blind_tasks(rows, protocol())


def test_exact_mcnemar_known_result() -> None:
    result = exact_mcnemar([True] * 8, [False] * 8)
    assert result["full_only_correct"] == 8
    assert result["two_sided_exact_p"] == pytest.approx(0.007812)


def test_four_method_evaluation_is_complete_and_paired() -> None:
    task_rows = tasks()
    report = evaluate_method_responses(task_rows, measured_responses(task_rows), protocol())
    assert report["publication_evidence"] is True
    assert set(report["methods"]) == set(protocol()["methods"])
    assert all(row["gate_accuracy"] == 1.0 for row in report["methods"].values())
    assert report["paired_comparisons_against_full_method"]["direct_llm"]["gate_mcnemar"]["paired_count"] == 24


def test_missing_method_observation_is_never_imputed() -> None:
    task_rows = tasks()
    responses = measured_responses(task_rows)
    responses.pop()
    with pytest.raises(ValueError, match="coverage mismatch"):
        evaluate_method_responses(task_rows, responses, protocol())
