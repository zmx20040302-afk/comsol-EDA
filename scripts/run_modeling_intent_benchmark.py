from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from comsol_small_model.physics_selection import select_modeling_intent


def run_benchmark(tasks_path: Path) -> dict:
    tasks = [json.loads(line) for line in tasks_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows = []
    totals = {"interface_tp": 0, "interface_fp": 0, "interface_fn": 0, "coupling_correct": 0, "study_correct": 0, "high_confidence_errors": 0}
    for task in tasks:
        result = select_modeling_intent(task["requirement"], task.get("domains", []))
        actual = set(result["selected_interface_ids"])
        expected = set(task.get("interfaces", []))
        forbidden = set(task.get("forbidden", []))
        actual_couplings = set(result["coupling_ids"])
        expected_couplings = set(task.get("couplings", []))
        interface_ok = actual == expected and not actual.intersection(forbidden)
        coupling_ok = actual_couplings == expected_couplings
        study_ok = result["study"]["type"] == task["study"]
        totals["interface_tp"] += len(actual & expected)
        totals["interface_fp"] += len(actual - expected)
        totals["interface_fn"] += len(expected - actual)
        totals["coupling_correct"] += int(coupling_ok)
        totals["study_correct"] += int(study_ok)
        error = not (interface_ok and coupling_ok and study_ok)
        totals["high_confidence_errors"] += int(error and result["confidence"] >= 0.8 and not result["abstained"])
        rows.append({
            "id": task["id"], "passed": not error, "requirement": task["requirement"],
            "expected": {"interfaces": sorted(expected), "couplings": sorted(expected_couplings), "study": task["study"]},
            "actual": {"interfaces": sorted(actual), "couplings": sorted(actual_couplings), "study": result["study"]["type"]},
            "confidence": result["confidence"], "abstained": result["abstained"],
        })
    precision = totals["interface_tp"] / max(1, totals["interface_tp"] + totals["interface_fp"])
    recall = totals["interface_tp"] / max(1, totals["interface_tp"] + totals["interface_fn"])
    f1 = 2 * precision * recall / max(1e-12, precision + recall)
    return {
        "schema": "comsol-modeling-intent-benchmark",
        "schemaVersion": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "task_count": len(tasks),
        "passed": sum(int(row["passed"]) for row in rows),
        "metrics": {
            "interface_precision": round(precision, 4), "interface_recall": round(recall, 4), "interface_f1": round(f1, 4),
            "coupling_accuracy": round(totals["coupling_correct"] / max(1, len(tasks)), 4),
            "study_accuracy": round(totals["study_correct"] / max(1, len(tasks)), 4),
            "high_confidence_error_rate": round(totals["high_confidence_errors"] / max(1, len(tasks)), 4),
        },
        "errors": [row for row in rows if not row["passed"]],
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", default="benchmarks/physics_selection/tasks.jsonl")
    parser.add_argument("--output", default="generated/benchmarks/physics_selection/report.json")
    args = parser.parse_args()
    report = run_benchmark(ROOT / args.tasks)
    output = ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "task_count": report["task_count"], "passed": report["passed"], "metrics": report["metrics"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
