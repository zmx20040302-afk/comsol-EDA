from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from comsol_small_model.physics_dependency_graph import compile_physics_dependency_plan
from comsol_small_model.physics_selection import select_modeling_intent


DEFAULT_TASKS = ROOT / "benchmarks" / "dac_problem1" / "development_tasks.jsonl"
DEFAULT_OUTPUT = ROOT / "generated" / "dac" / "problem1_development_report.json"


def _keyword_baseline(text: str) -> tuple[set[str], set[str]]:
    value = text.lower()
    interfaces: set[str] = set()
    couplings: set[str] = set()
    rules = (
        ("heat_transfer_solids", ("导热", "固体传热", "热流", "温度")),
        ("electric_currents", ("电流", "电压", "电势", "电阻", "阻抗")),
        ("solid_mechanics", ("应力", "位移", "变形", "悬臂梁")),
        ("laminar_flow", ("流道", "微通道", "压降", "入口速度", "质量流量")),
        ("pressure_acoustics", ("声学", "共振频率")),
        ("transport_diluted_species", ("浓度", "扩散")),
    )
    for interface_id, words in rules:
        if any(word in value for word in words):
            interfaces.add(interface_id)
    if "焦耳热" in value:
        couplings.add("electromagnetic_heating")
    if "热膨胀" in value or "热应力" in value:
        couplings.add("thermal_expansion")
    if "非等温" in value or "流热" in value:
        couplings.add("nonisothermal_flow")
    return interfaces, couplings


def _score(rows: list[dict[str, Any]], method: str) -> dict[str, Any]:
    exact = study = 0
    details: list[dict[str, Any]] = []
    for task in rows:
        if method == "keyword_baseline":
            interfaces, couplings = _keyword_baseline(task["requirement"])
            study_type = "Stationary"
        elif method == "existing_selector":
            result = select_modeling_intent(task["requirement"], task.get("domains", []))
            interfaces = set(result["selected_interface_ids"])
            couplings = set(result["coupling_ids"])
            study_type = result["study"]["type"]
        else:
            result = compile_physics_dependency_plan(task["requirement"], task.get("domains", []))
            interfaces = set(result["interface_ids"])
            couplings = set(result["coupling_ids"])
            study_type = result["study"]["type"]
        selection_ok = interfaces == set(task["interfaces"]) and couplings == set(task["couplings"])
        study_ok = study_type == task["study"]
        exact += int(selection_ok)
        study += int(study_ok)
        details.append({
            "id": task["id"],
            "selection_ok": selection_ok,
            "study_ok": study_ok,
            "actual_interfaces": sorted(interfaces),
            "actual_couplings": sorted(couplings),
            "actual_study": study_type,
        })
    return {
        "task_count": len(rows),
        "physics_and_coupling_exact_count": exact,
        "physics_and_coupling_exact_accuracy": round(exact / len(rows), 4),
        "study_exact_count": study,
        "study_exact_accuracy": round(study / len(rows), 4),
        "details": details,
    }


def run(tasks_path: Path = DEFAULT_TASKS) -> dict[str, Any]:
    rows = [json.loads(line) for line in tasks_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("development task ids must be unique")
    methods = {name: _score(rows, name) for name in ("keyword_baseline", "existing_selector", "dependency_graph")}
    return {
        "schema": "dac-problem1-development-benchmark",
        "schemaVersion": "0.1.0",
        "split": "development_only",
        "task_count": len(rows),
        "method_frozen_for_final_evaluation": False,
        "independent_final_test_claimed": False,
        "methods": methods,
        "interpretation_limit": "This set was created during method development. It can diagnose implementation behavior but cannot support a final generalization claim.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", type=Path, default=DEFAULT_TASKS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = run(args.tasks)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {name: {key: value for key, value in row.items() if key != "details"} for name, row in report["methods"].items()}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
