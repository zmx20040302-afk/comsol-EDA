from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from comsol_small_model.physics_dependency_graph import compile_physics_dependency_plan
from comsol_small_model.physics_dependency_graph_v11 import compile_physics_dependency_plan_v11


def _blocked_v10(plan: dict) -> bool:
    return bool(plan["decision"]["blocked"] or plan["clarification_questions"])


def evaluate() -> dict:
    path = ROOT / "benchmarks" / "dac_problem1_v11" / "development_negation_tasks.jsonl"
    tasks = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    details = []
    for task in tasks:
        old = compile_physics_dependency_plan(task["requirement"], task.get("domains", []))
        new = compile_physics_dependency_plan_v11(task["requirement"], task.get("domains", []))
        expected = bool(task["expected_blocked"])
        old_blocked = _blocked_v10(old)
        new_blocked = bool(new["decision"]["blocked"])
        details.append({
            "id": task["id"],
            "family": task["family"],
            "expected_blocked": expected,
            "v10_blocked": old_blocked,
            "v11_blocked": new_blocked,
            "v10_gate_ok": old_blocked == expected,
            "v11_gate_ok": new_blocked == expected,
            "v11_reason_codes": new["decision"]["reason_codes"],
            "v11_missing_fields": new["completeness"]["missing_fields"],
        })
    blocked = [row for row in details if row["expected_blocked"]]
    ready = [row for row in details if not row["expected_blocked"]]
    def summary(prefix: str) -> dict:
        return {
            "gate_accuracy": round(sum(row[f"{prefix}_gate_ok"] for row in details) / len(details), 4),
            "false_safe_count": sum(not row[f"{prefix}_blocked"] for row in blocked),
            "false_safe_rate": round(sum(not row[f"{prefix}_blocked"] for row in blocked) / len(blocked), 4),
            "false_block_count": sum(row[f"{prefix}_blocked"] for row in ready),
            "false_block_rate": round(sum(row[f"{prefix}_blocked"] for row in ready) / len(ready), 4),
        }
    return {
        "schema": "dac-problem1-v11-development",
        "schemaVersion": "1.0.0",
        "task_count": len(tasks),
        "blocked_task_count": len(blocked),
        "complete_task_count": len(ready),
        "v10": summary("v10"),
        "v11": summary("v11"),
        "details": details,
        "evidence_limit": "Project-authored adversarial development data used for v1.1 rule selection; not independent validation evidence.",
    }


def main() -> int:
    report = evaluate()
    output = ROOT / "generated" / "dac" / "problem1_v11_development_report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"v10": report["v10"], "v11": report["v11"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
