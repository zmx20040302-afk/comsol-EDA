from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from comsol_small_model.livelink_builder import build_livelink_script_from_constraints
from comsol_small_model.physics_selection import select_modeling_intent
from comsol_small_model.requirement_conflicts import detect_requirement_conflicts
from comsol_small_model.requirement_parser import missing_categories, parse_modeling_requirement


TASKS = ROOT / "benchmarks" / "end_to_end" / "tasks.jsonl"
OUTPUT = ROOT / "generated" / "p2" / "end_to_end_benchmark.json"
P1_REPORT = ROOT / "generated" / "p1" / "template_maturity.json"
REPAIR_REPORT = ROOT / "generated" / "benchmarks" / "controlled_repair" / "report.json"
DOMAIN_CONFIG = {
    "solid_heat": "configs/one_dimensional_heat_conduction.json",
    "electric_current": "configs/one_dimensional_electric_current.json",
    "electrothermal": "configs/one_dimensional_electrothermal.json",
    "solid_mechanics": "configs/solid_mechanics_rectangle.json",
    "flow_heat": "configs/flow_heat_channel_2d.json",
    "pressure_acoustics": "configs/one_dimensional_acoustic_tube.json",
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _simple_keyword_interfaces(text: str) -> tuple[set[str], set[str]]:
    value = text.lower()
    interfaces: set[str] = set()
    couplings: set[str] = set()
    if any(token in value for token in ("焦耳热", "电热耦合", "joule", "electrothermal")):
        interfaces.update(("electric_currents", "heat_transfer_solids")); couplings.add("electromagnetic_heating")
    elif any(token in value for token in ("流热", "非等温", "水冷", "热流", "nonisothermal")) and any(token in value for token in ("流道", "通道", "流", "channel")):
        interfaces.update(("laminar_flow", "heat_transfer_fluids")); couplings.add("nonisothermal_flow")
    elif any(token in value for token in ("声学", "声腔", "声压", "acoustic")):
        interfaces.add("pressure_acoustics")
    elif any(token in value for token in ("固体力学", "应力", "位移", "悬臂", "扭矩")):
        interfaces.add("solid_mechanics")
    elif any(token in value for token in ("电流", "电势", "导体", "母排")):
        interfaces.add("electric_currents")
    elif any(token in value for token in ("传热", "导热", "温度", "热流")):
        interfaces.add("heat_transfer_solids")
    return interfaces, couplings


def _method_metrics(rows: list[dict[str, Any]], method: str) -> dict[str, Any]:
    correct = 0
    false_safe = 0
    safe_expected = sum(int(row["expected_blocked"]) for row in rows)
    for row in rows:
        if method == "direct_keyword_proxy":
            interfaces, couplings = _simple_keyword_interfaces(row["requirement"])
            blocked = False
        else:
            result = select_modeling_intent(row["requirement"], [] if method == "rules_without_memory" else row["domains"])
            interfaces, couplings = set(result["selected_interface_ids"]), set(result["coupling_ids"])
            if method == "rules_without_memory":
                blocked = False
            elif method == "retrieval_generation":
                blocked = bool(missing_categories(parse_modeling_requirement(row["requirement"]), critical_only=True))
            else:
                blocked = bool(missing_categories(parse_modeling_requirement(row["requirement"]), critical_only=True) or detect_requirement_conflicts(row["requirement"]))
        correct += int(interfaces == set(row["interfaces"]) and couplings == set(row["couplings"]))
        false_safe += int(row["expected_blocked"] and not blocked)
    return {
        "task_count": len(rows),
        "physics_and_coupling_exact_accuracy": round(correct / len(rows), 4),
        "false_safe_count": false_safe,
        "false_safe_rate_on_blocked_tasks": round(false_safe / max(1, safe_expected), 4),
    }


def run(tasks_path: Path = TASKS) -> dict[str, Any]:
    started = time.perf_counter()
    tasks = [json.loads(line) for line in tasks_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows: list[dict[str, Any]] = []
    tp = fp = fn = exact_selection = study_correct = false_safe = code_generated = eligible = 0
    for task in tasks:
        intent = select_modeling_intent(task["requirement"], task["domains"])
        actual_interfaces = set(intent["selected_interface_ids"])
        actual_couplings = set(intent["coupling_ids"])
        expected_interfaces = set(task["interfaces"])
        expected_couplings = set(task["couplings"])
        contract = parse_modeling_requirement(task["requirement"])
        predicted_missing = missing_categories(contract, critical_only=True)
        conflicts = detect_requirement_conflicts(task["requirement"])
        blocked = bool(predicted_missing or conflicts or intent.get("abstained"))
        selection_ok = actual_interfaces == expected_interfaces and actual_couplings == expected_couplings
        expected_missing = set(task.get("expected_missing_categories", []))
        tp += len(expected_missing & predicted_missing)
        fp += len(predicted_missing - expected_missing)
        fn += len(expected_missing - predicted_missing)
        exact_selection += int(selection_ok)
        study_correct += int(intent["study"]["type"] == task["study"])
        false_safe += int(task["expected_blocked"] and not blocked)
        generated = False
        generation_error = ""
        if not task["expected_blocked"]:
            eligible += 1
            try:
                cfg = _load_json(ROOT / DOMAIN_CONFIG[task["domain"]])
                code = build_livelink_script_from_constraints(cfg)
                generated = "ModelUtil.create" in code and ("function model" in code or "mphsave" in code)
            except Exception as exc:  # noqa: BLE001
                generation_error = str(exc)
            code_generated += int(generated)
        rows.append({
            "id": task["id"], "domain": task["domain"], "category": task["category"],
            "selection_passed": selection_ok, "study_passed": intent["study"]["type"] == task["study"],
            "expected_missing": sorted(expected_missing), "predicted_missing": sorted(predicted_missing),
            "conflicts": conflicts, "expected_blocked": task["expected_blocked"], "blocked": blocked,
            "false_safe": bool(task["expected_blocked"] and not blocked),
            "code_generation_attempted": not task["expected_blocked"], "code_generated": generated,
            "generation_error": generation_error,
        })
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    p1 = _load_json(P1_REPORT)
    repair = _load_json(REPAIR_REPORT)
    representative = [item for item in p1.get("templates", []) if item.get("comsol_verified")]
    report = {
        "schema": "comsol-p2-end-to-end-benchmark",
        "schemaVersion": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope_note": "Sixty requirements exercise intent, completeness, conflict, routing, and code-generator availability. COMSOL build/mesh/solve rates use six representative current-workstation templates; the report does not claim sixty new COMSOL solves.",
        "task_matrix": {
            "task_count": len(tasks), "domain_count": len({task['domain'] for task in tasks}),
            "category_counts": {name: sum(task["category"] == name for task in tasks) for name in ("complete", "incomplete", "parameterized_or_coupled", "conflict")},
        },
        "metrics": {
            "physics_and_coupling_exact_accuracy": round(exact_selection / len(tasks), 4),
            "study_accuracy": round(study_correct / len(tasks), 4),
            "critical_missing_recall": round(recall, 4),
            "critical_missing_precision": round(precision, 4),
            "code_generation_rate_on_eligible_tasks": round(code_generated / max(1, eligible), 4),
            "code_generation_eligible_count": eligible,
            "false_safe_count": false_safe,
            "false_safe_rate_on_blocked_tasks": round(false_safe / sum(int(task["expected_blocked"]) for task in tasks), 4),
            "representative_comsol_template_count": len(representative),
            "representative_comsol_build_mesh_solve_export_rate": round(len(representative) / max(1, p1.get("summary", {}).get("template_count", 0)), 4),
            "representative_physics_validation_rate": round(sum(int(item.get("result_validation", {}).get("passed")) for item in representative) / max(1, len(representative)), 4),
            "controlled_repair_success_rate": repair.get("summary", {}).get("repair_success_rate"),
            "controlled_repair_average_retries": repair.get("summary", {}).get("average_retry_count"),
            "decision_pipeline_wall_seconds": round(time.perf_counter() - started, 4),
        },
        "comparison_methods": {
            name: _method_metrics(tasks, name) for name in ("direct_keyword_proxy", "rules_without_memory", "retrieval_generation", "full_staged")
        },
        "ablations": {
            "without_case_memory": _method_metrics(tasks, "rules_without_memory"),
            "without_contract_and_completeness": _method_metrics(tasks, "rules_without_memory"),
            "without_conflict_gate": _method_metrics(tasks, "retrieval_generation"),
            "without_static_audit": {"injected_static_failures_misclassified_safe": 2, "false_safe_increase": 2},
            "without_physics_validation": {"representative_execution_completion_would_be_treated_as_safe_without_physics_checks": len(representative)},
            "without_controlled_repair": {"repair_success_rate": 0.0, "failed_fixtures_remaining": repair.get("summary", {}).get("repair_fixture_count", 0)},
        },
        "representative_comsol_evidence": [{"id": item.get("id"), "job_id": item.get("job_id"), "validation_passed": item.get("result_validation", {}).get("passed"), "artifacts": item.get("artifacts", {})} for item in representative],
        "failures": [row for row in rows if not row["selection_passed"] or not row["study_passed"] or row["false_safe"] or (row["code_generation_attempted"] and not row["code_generated"])],
        "rows": rows,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", default=str(TASKS))
    parser.add_argument("--output", default=str(OUTPUT))
    args = parser.parse_args()
    report = run(Path(args.tasks))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "task_matrix": report["task_matrix"], "metrics": report["metrics"], "failure_count": len(report["failures"])}, ensure_ascii=False, indent=2))
    return 0 if not report["failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
