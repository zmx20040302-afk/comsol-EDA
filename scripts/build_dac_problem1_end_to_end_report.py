from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from comsol_small_model.physics_dependency_graph_v11 import compile_physics_dependency_plan_v11  # noqa: E402
from comsol_small_model.problem1_publication_evidence import read_jsonl, sha256_file  # noqa: E402


def main() -> int:
    contracts_path = ROOT / "benchmarks" / "dac_problem1_publication" / "end_to_end_contracts.jsonl"
    java_path = ROOT / "generated" / "p6" / "java_dual_path" / "java_dual_path_report.json"
    p2_path = ROOT / "generated" / "p2" / "end_to_end_benchmark.json"
    contracts = read_jsonl(contracts_path)
    java = json.loads(java_path.read_text(encoding="utf-8"))
    p2 = json.loads(p2_path.read_text(encoding="utf-8"))
    java_by_id = {str(row["id"]): row for row in java.get("templates", [])}
    physical_by_id = {str(row["id"]): row for row in p2.get("representative_comsol_evidence", [])}
    rows = []
    for contract in contracts:
        plan = compile_physics_dependency_plan_v11(contract["requirement"])
        template_id = str(contract["template_id"])
        execution = java_by_id.get(template_id, {})
        physical = physical_by_id.get(template_id, {})
        rebuilt = Path(str(execution.get("output_mph", "")))
        interface_match = set(plan.get("interface_ids", [])) == set(contract["expected_interfaces"])
        coupling_match = set(plan.get("coupling_ids", [])) == set(contract["expected_couplings"])
        study_match = str(plan.get("study", {}).get("type", "")) == str(contract["expected_study"])
        requirement_passed = bool(interface_match and coupling_match and study_match and not plan["decision"]["blocked"])
        comsol_passed = bool(execution.get("compiled") and execution.get("executed") and rebuilt.is_file())
        physical_passed = bool(physical.get("validation_passed"))
        rows.append({
            "id": contract["id"],
            "template_id": template_id,
            "family": contract["family"],
            "requirement_compilation_passed": requirement_passed,
            "interface_match": interface_match,
            "coupling_match": coupling_match,
            "study_match": study_match,
            "blocked": bool(plan["decision"]["blocked"]),
            "compiled": bool(execution.get("compiled")),
            "solved": bool(execution.get("executed")),
            "mph_exists": rebuilt.is_file(),
            "mph_sha256": sha256_file(rebuilt) if rebuilt.is_file() else "",
            "physical_validation_passed": physical_passed,
            "physical_evidence_artifacts": physical.get("artifacts", {}),
            "passed": bool(requirement_passed and comsol_passed and physical_passed),
        })
    passed = sum(bool(row["passed"]) for row in rows)
    report = {
        "schema": "dac-problem1-end-to-end-contract-evidence",
        "schemaVersion": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method_version": "problem1-v1.1.0",
        "contract_file_sha256": sha256_file(contracts_path),
        "java_report_sha256": sha256_file(java_path),
        "physical_evidence_report_sha256": sha256_file(p2_path),
        "summary": {
            "task_count": len(rows),
            "requirement_compilation_passed": sum(bool(row["requirement_compilation_passed"]) for row in rows),
            "comsol_build_solve_artifact_passed": sum(bool(row["compiled"] and row["solved"] and row["mph_exists"]) for row in rows),
            "physical_validation_passed": sum(bool(row["physical_validation_passed"]) for row in rows),
            "full_pipeline_passed": passed,
            "full_pipeline_rate": passed / len(rows),
            "gate_passed": passed == len(rows),
        },
        "rows": rows,
        "scope": "Six frozen representative contracts mapped to six previously matured builders. This establishes contract-to-solve traceability for the supported templates, not unrestricted geometry synthesis.",
    }
    output = ROOT / "generated" / "dac" / "problem1_publication" / "end_to_end_contract_report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0 if report["summary"]["gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
