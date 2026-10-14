from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from comsol_small_model.repair_policy import build_repair_decision
from comsol_small_model.static_model_audit import audit_generated_model_code


ROOT = Path(__file__).resolve().parents[1]
TASKS = ROOT / "benchmarks" / "controlled_repair" / "tasks.jsonl"
OUTPUT = ROOT / "generated" / "benchmarks" / "controlled_repair" / "report.json"


def _load_tasks() -> list[dict]:
    return [json.loads(line) for line in TASKS.read_text(encoding="utf-8").splitlines() if line.strip()]


def _repair_fixtures() -> list[dict]:
    contract = {"schemaVersion": "1.0.0"}
    common = "\n".join([
        "model.component('comp1').material.create('mat1', 'Common');",
        "model.component('comp1').material('mat1').selection.all;",
        "model.component('comp1').physics.create('ht', 'HeatTransfer', 'geom1');",
        "model.study.create('std1');",
        "model.study('std1').create('stat', 'Stationary');",
        "% Saving is handled by the execution wrapper with mphsave(model, output_path).",
    ])
    fixtures = [
        (
            "undefined_parameter",
            common + "\nmodel.component('comp1').physics('ht').feature('init1').set('Tinit', 'T_initial');",
            "model.param.set('T_initial', '293.15[K]');\n" + common + "\nmodel.component('comp1').physics('ht').feature('init1').set('Tinit', 'T_initial');",
        ),
        (
            "empty_selection",
            common + "\nmodel.component('comp1').physics('ht').selection.set([]);",
            common + "\nmodel.component('comp1').physics('ht').selection.set([1]);",
        ),
    ]
    rows = []
    for fixture_id, before, after in fixtures:
        before_report = audit_generated_model_code(contract, before)
        after_report = audit_generated_model_code(contract, after)
        rows.append({
            "id": fixture_id,
            "before_passed": before_report["passed"],
            "after_passed": after_report["passed"],
            "repair_succeeded": not before_report["passed"] and after_report["passed"],
            "retry_count": 1,
            "before_findings": before_report["findings"],
            "after_findings": after_report["findings"],
        })
    return rows


def main() -> None:
    results = []
    for task in _load_tasks():
        decision = build_repair_decision(
            task["error"],
            attempt=task.get("attempt", 1),
            max_attempts=task.get("max_attempts", 3),
            proposed_changes=task.get("changes", []),
        )
        checks = {
            "category": decision["primary_error_category"] == task["expected_category"],
            "auto": decision["auto_repair_allowed"] is task["expected_auto"],
            "approval": decision["requires_user_approval"] is task.get("expected_approval", False),
            "retry": decision["retry_allowed"] is task.get("expected_retry", True),
        }
        results.append({"id": task["id"], "passed": all(checks.values()), "checks": checks, "decision": decision})
    fixtures = _repair_fixtures()
    fixture_successes = sum(int(row["repair_succeeded"]) for row in fixtures)
    report = {
        "schema": "comsol-controlled-repair-benchmark",
        "schemaVersion": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "task_count": len(results),
            "tasks_passed": sum(int(row["passed"]) for row in results),
            "classification_accuracy": sum(int(row["checks"]["category"]) for row in results) / len(results),
            "policy_decision_accuracy": sum(int(row["passed"]) for row in results) / len(results),
            "repair_fixture_count": len(fixtures),
            "repair_success_rate": fixture_successes / len(fixtures),
            "average_retry_count": sum(row["retry_count"] for row in fixtures) / len(fixtures),
        },
        "tasks": results,
        "repair_fixtures": fixtures,
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    if report["summary"]["tasks_passed"] != len(results) or fixture_successes != len(fixtures):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
