from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from comsol_small_model.dac2027_p0_evaluation import exact_mcnemar, wilson
from comsol_small_model.physics_dependency_graph import compile_physics_dependency_plan
from comsol_small_model.physics_dependency_graph_v11 import compile_physics_dependency_plan_v11
from comsol_small_model.physics_selection import select_modeling_intent


def score(task: dict[str, Any], interfaces: list[str], couplings: list[str], study: str, blocked: bool) -> dict[str, bool]:
    return {
        "selection_ok": set(interfaces) == set(task["interfaces"]) and set(couplings) == set(task["couplings"]),
        "study_ok": study == task["study"],
        "gate_ok": blocked == bool(task["expected_blocked"]),
        "blocked": blocked,
    }


def summarize(rows: list[dict[str, Any]], method: str) -> dict[str, Any]:
    values = [row[method] for row in rows]
    total = len(values)
    blocked = [(row, row[method]) for row in rows if row["expected_blocked"]]
    complete = [(row, row[method]) for row in rows if not row["expected_blocked"]]
    exact = sum(v["selection_ok"] for v in values)
    study = sum(v["study_ok"] for v in values)
    gate = sum(v["gate_ok"] for v in values)
    false_safe = sum(not v["blocked"] for _, v in blocked)
    false_block = sum(v["blocked"] for _, v in complete)
    return {
        "task_count": total,
        "selection_exact": exact,
        "selection_accuracy": round(exact / total, 4),
        "selection_wilson95": wilson(exact, total),
        "study_exact": study,
        "study_accuracy": round(study / total, 4),
        "study_wilson95": wilson(study, total),
        "gate_correct": gate,
        "gate_accuracy": round(gate / total, 4),
        "gate_wilson95": wilson(gate, total),
        "false_safe_count": false_safe,
        "false_safe_rate": round(false_safe / len(blocked), 4),
        "false_block_count": false_block,
        "false_block_rate": round(false_block / len(complete), 4),
    }


def main() -> int:
    task_path = ROOT / "benchmarks" / "dac_problem1_v11" / "final_tasks.jsonl"
    tasks = [json.loads(line) for line in task_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    details = []
    for task in tasks:
        base = select_modeling_intent(task["requirement"], task.get("domains", []))
        v10 = compile_physics_dependency_plan(task["requirement"], task.get("domains", []))
        v11 = compile_physics_dependency_plan_v11(task["requirement"], task.get("domains", []))
        base_blocked = bool(base["abstained"] or base["missing_information"])
        v10_blocked = bool(v10["decision"]["blocked"] or v10["clarification_questions"])
        v11_blocked = bool(v11["decision"]["blocked"])
        details.append({
            "task_id": task["id"],
            "family": task["family"],
            "status": task["status"],
            "expected_blocked": bool(task["expected_blocked"]),
            "existing_selector": score(task, base["selected_interface_ids"], base["coupling_ids"], base["study"]["type"], base_blocked),
            "dependency_v10": score(task, v10["interface_ids"], v10["coupling_ids"], v10["study"]["type"], v10_blocked),
            "contract_dependency_v11": score(task, v11["interface_ids"], v11["coupling_ids"], v11["study"]["type"], v11_blocked),
            "no_safety_gate": score(task, v11["interface_ids"], v11["coupling_ids"], v11["study"]["type"], False),
        })
    methods = ["existing_selector", "dependency_v10", "contract_dependency_v11", "no_safety_gate"]
    summaries = {method: summarize(details, method) for method in methods}
    full = "contract_dependency_v11"
    comparisons = {}
    for method in methods:
        if method == full:
            continue
        comparisons[method] = {
            "selection_mcnemar": exact_mcnemar(
                [row[full]["selection_ok"] for row in details], [row[method]["selection_ok"] for row in details]
            ),
            "gate_mcnemar": exact_mcnemar(
                [row[full]["gate_ok"] for row in details], [row[method]["gate_ok"] for row in details]
            ),
        }
    report = {
        "schema": "dac2027-p0-internal-pilot",
        "schemaVersion": "1.0.0",
        "publication_evidence": False,
        "task_source": "project-authored frozen v1.1 final tasks",
        "task_count": len(tasks),
        "family_count": len({row["family"] for row in tasks}),
        "status_counts": {status: sum(row["status"] == status for row in tasks) for status in ("complete", "missing", "conflict")},
        "methods": summaries,
        "paired_comparisons_against_full_method": comparisons,
        "ablation_mapping": {
            "without_dependency_graph": "existing_selector",
            "without_negation_aware_completeness": "dependency_v10",
            "without_safety_gate": "no_safety_gate"
        },
        "interpretation_limit": "This run verifies the P0 evaluator and reveals implementation behavior. It must not be reported as an independent DAC main result.",
        "details": details,
    }
    output = ROOT / "generated" / "dac2027" / "p0" / "internal_pilot_report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"methods": summaries, "comparisons": comparisons}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
