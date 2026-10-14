from __future__ import annotations

import difflib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from comsol_small_model.bounded_repair import apply_bounded_repair
from comsol_small_model.repair_policy import build_repair_decision
from comsol_small_model.static_model_audit import audit_generated_model_code


BASE = """model = ModelUtil.create('Model');
model.component.create('comp1', true);
model.component('comp1').geom.create('geom1', 2);
model.component('comp1').material.create('mat1');
model.component('comp1').material('mat1').selection.all;
model.component('comp1').physics.create('ht', 'HeatTransfer', 'geom1');
model.study.create('std1');
model.study('std1').create('stat', 'Stationary');
model.result.numerical.create('gev1', 'EvalGlobal');
model.result.numerical('gev1').set('expr', 'ht.T');
mphsave(model, 'outputs/model.mph');"""


def _fixtures() -> list[dict[str, Any]]:
    return [
        {
            "id": "undefined_parameter",
            "error": "未定义变量 T_initial",
            "broken": BASE.replace("model.component.create", "model.param.set('T0', 'T_initial');\nmodel.component.create", 1),
            "patch": {"field": "generated_code", "old": "model.param.set('T0', 'T_initial');", "new": "model.param.set('T_initial', '293[K]');\nmodel.param.set('T0', 'T_initial');"},
        },
        {
            "id": "empty_selection",
            "error": "参数值无效: empty selection",
            "broken": BASE.replace(".material('mat1').selection.all;", ".material('mat1').selection.set([]);"),
            "patch": {"field": "generated_code", "old": ".material('mat1').selection.set([]);", "new": ".material('mat1').selection.set([1]);"},
        },
        {
            "id": "missing_material",
            "error": "solver failed because material is missing",
            "broken": BASE.replace("model.component('comp1').material.create('mat1');\nmodel.component('comp1').material('mat1').selection.all;\n", ""),
            "patch": {"field": "generated_code", "old": "model.component('comp1').physics.create('ht', 'HeatTransfer', 'geom1');", "new": "model.component('comp1').material.create('mat1');\nmodel.component('comp1').material('mat1').selection.all;\nmodel.component('comp1').physics.create('ht', 'HeatTransfer', 'geom1');"},
        },
        {
            "id": "missing_study",
            "error": "solver study is missing",
            "broken": BASE.replace("model.study.create('std1');\nmodel.study('std1').create('stat', 'Stationary');\n", ""),
            "patch": {"field": "generated_code", "old": "model.result.numerical.create('gev1', 'EvalGlobal');", "new": "model.study.create('std1');\nmodel.study('std1').create('stat', 'Stationary');\nmodel.result.numerical.create('gev1', 'EvalGlobal');"},
        },
        {
            "id": "unknown_result_prefix",
            "error": "physical result validation unknown variable bad.T",
            "broken": BASE.replace("'ht.T');", "'bad.T');"),
            "patch": {"field": "generated_code", "old": "'bad.T');", "new": "'ht.T');"},
        },
        {
            "id": "unsafe_output_path",
            "error": "mph artifact output path invalid",
            "broken": BASE.replace("outputs/model.mph", "../outputs/model.mph"),
            "patch": {"field": "generated_code", "old": "../outputs/model.mph", "new": "outputs/model.mph"},
        },
    ]


def _changed_lines(before: str, after: str) -> int:
    rows = difflib.ndiff(before.splitlines(), after.splitlines())
    return sum(row.startswith(("+ ", "- ")) for row in rows)


def run() -> dict[str, Any]:
    contract = {"schemaVersion": "1.0.0", "task": {"name": "frozen repair fixture"}, "physics": {"interfaces": ["heat_transfer_solids"]}}
    details = []
    for fixture in _fixtures():
        before = audit_generated_model_code(contract, fixture["broken"])
        decision = build_repair_decision(fixture["error"], attempt=0, proposed_changes=[fixture["patch"]])
        result = apply_bounded_repair(contract, fixture["broken"], fixture["patch"])
        after = audit_generated_model_code(contract, result["code"])
        changed = _changed_lines(fixture["broken"], result["code"])
        details.append({
            "id": fixture["id"],
            "initial_audit_passed": before["passed"],
            "policy_auto_repair_allowed": decision["auto_repair_allowed"],
            "repair_applied": result["applied"],
            "final_audit_passed": after["passed"],
            "contract_preserved": result["contract_sha256_before"] == result["contract_sha256_after"],
            "local_changed_lines": changed,
            "whole_artifact_replacement_scope_lines": len(fixture["broken"].splitlines()),
            "local_scope_fraction": round(changed / len(fixture["broken"].splitlines()), 4),
            "remaining_findings": after["findings"],
        })
    passed = sum(row["repair_applied"] and row["final_audit_passed"] for row in details)
    preserved = sum(row["contract_preserved"] for row in details)
    return {
        "schema": "dac-problem1-bounded-repair-benchmark",
        "schemaVersion": "1.0.0",
        "task_count": len(details),
        "bounded_repair_success_count": passed,
        "bounded_repair_success_rate": round(passed / len(details), 4),
        "contract_preservation_count": preserved,
        "contract_preservation_rate": round(preserved / len(details), 4),
        "mean_local_scope_fraction": round(sum(row["local_scope_fraction"] for row in details) / len(details), 4),
        "comparison_type": "deterministic whole-artifact replacement scope proxy",
        "details": details,
        "interpretation_limit": "This verifies patch locality, static-audit recovery, and contract preservation on injected faults. It does not measure semantic drift from an external LLM whole-code regeneration system.",
    }


def main() -> int:
    report = run()
    output = ROOT / "generated" / "dac" / "problem1_repair_report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in report.items() if key != "details"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
