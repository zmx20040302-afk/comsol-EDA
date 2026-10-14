from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from comsol_small_model.modeling_contract import (
    add_missing_information,
    compare_contracts,
    create_empty_contract,
    load_modeling_contract,
    migrate_modeling_contract,
    save_modeling_contract,
    update_field_evidence,
    validate_modeling_contract,
)
from comsol_small_model.requirement_parser import missing_categories, parse_modeling_requirement
from comsol_small_model.staged_modeling import (
    STAGE_DEFINITIONS,
    create_staged_workflow,
    load_workflow,
    record_execution_validation,
)
from scripts.run_requirement_completeness_benchmark import run_benchmark


class ModelingContractTests(unittest.TestCase):
    def test_empty_contract_has_stable_schema(self) -> None:
        contract = create_empty_contract("建立二维传热模型")
        report = validate_modeling_contract(contract)
        self.assertTrue(report["valid"])
        self.assertFalse(report["ready_for_generation"])
        self.assertEqual(contract["schemaVersion"], "1.0.0")

    def test_numeric_quantity_requires_unit(self) -> None:
        contract = create_empty_contract("建立二维传热模型")
        contract["geometry"]["parameters"] = [
            {"name": "length", "value": 100, "unit": "", "evidence_level": "user_confirmed", "source": "user"}
        ]
        report = validate_modeling_contract(contract)
        self.assertFalse(report["valid"])
        self.assertTrue(any("unit is required" in item for item in report["errors"]))

    def test_duplicate_comsol_tags_are_rejected(self) -> None:
        contract = create_empty_contract("建立电热模型")
        item = {"name": "Heat Transfer", "tag": "p1", "evidence_level": "proposed", "source": "test"}
        contract["physics"]["interfaces"] = [item, {**item, "name": "Electric Currents"}]
        report = validate_modeling_contract(contract)
        self.assertFalse(report["valid"])
        self.assertTrue(any("duplicate COMSOL tag" in error for error in report["errors"]))

    def test_automatic_solve_is_blocked_for_non_a_risk(self) -> None:
        contract = create_empty_contract("建立二维传热模型")
        contract["execution_policy"].update({"risk_level": "B", "allow_automatic_solve": True})
        report = validate_modeling_contract(contract)
        self.assertFalse(report["valid"])
        self.assertIn("automatic solve is only allowed for risk level A", report["errors"])

    def test_missing_information_blocks_automatic_solve(self) -> None:
        contract = create_empty_contract("建立二维传热模型")
        contract["execution_policy"].update({"risk_level": "A", "allow_automatic_solve": True})
        add_missing_information(contract, "geometry", "geometry.parameters", "请补充尺寸", "geometry")
        report = validate_modeling_contract(contract)
        self.assertFalse(report["ready_for_solve"])
        self.assertFalse(contract["execution_policy"]["allow_automatic_solve"])

    def test_contract_round_trip_and_evidence(self) -> None:
        contract = parse_modeling_requirement(
            "建立一维铜棒稳态传热模型，长度100 mm，左端固定温度300 K，右端固定温度350 K，输出最高温度和热流"
        )
        update_field_evidence(contract, "physics.interfaces", "user_confirmed", "review")
        with tempfile.TemporaryDirectory(dir=ROOT / "generated") as directory:
            path = Path(directory) / "contract.json"
            save_modeling_contract(contract, path)
            loaded = load_modeling_contract(path)
        self.assertEqual(loaded["contract_id"], contract["contract_id"])
        evidence = next(item for item in loaded["evidence"] if item["field"] == "physics.interfaces")
        self.assertEqual(evidence["level"], "user_confirmed")

    def test_legacy_contract_migration_preserves_requirement(self) -> None:
        migrated = migrate_modeling_contract({"requirement": "建立二维传热模型", "status": "waiting_for_approval"})
        self.assertEqual(migrated["raw_requirement"], "建立二维传热模型")
        self.assertEqual(migrated["status"], "ready_for_review")
        self.assertIn("migration", migrated)

    def test_contract_diff_records_field_change(self) -> None:
        before = create_empty_contract("建立二维传热模型")
        after = json.loads(json.dumps(before, ensure_ascii=False))
        after["geometry"]["dimension"] = "2D"
        changes = compare_contracts(before, after)
        self.assertTrue(any(item["path"] == "geometry.dimension" for item in changes))

    def test_complete_heat_requirement_has_no_critical_gap(self) -> None:
        contract = parse_modeling_requirement(
            "建立一维铜棒稳态传热模型，长度100 mm，左端固定温度300 K，右端固定温度350 K，输出最高温度和热流"
        )
        self.assertEqual(missing_categories(contract, critical_only=True), set())
        self.assertEqual(contract["execution_policy"]["risk_level"], "A")

    def test_ambiguous_requirement_has_structured_questions(self) -> None:
        contract = parse_modeling_requirement("自动建立一个模型")
        categories = missing_categories(contract, critical_only=True)
        self.assertTrue({"physics", "geometry", "boundary_conditions", "outputs"}.issubset(categories))
        self.assertTrue(contract["clarifying_questions"])
        self.assertEqual(contract["status"], "missing_information")

    def test_dimension_mismatch_does_not_get_a_risk(self) -> None:
        contract = parse_modeling_requirement(
            "建立三维铜导线稳态焦耳热模型，长度100 mm，端子电流10 A，另一端接地，表面对流，输出最高温度"
        )
        self.assertFalse(contract["validated_template"].get("compatible_with_contract"))
        self.assertNotEqual(contract["execution_policy"]["risk_level"], "A")

    def test_requirement_completeness_benchmark_meets_recall_gate(self) -> None:
        report = run_benchmark(ROOT / "benchmarks" / "requirement_completeness" / "tasks.json")
        self.assertEqual(report["case_count"], 30)
        self.assertGreaterEqual(report["critical_missing_recall"], 0.95)
        self.assertTrue(report["target_passed"])

    def test_ten_stage_workflow_is_created(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "generated") as directory:
            workflow = create_staged_workflow(
                "建立一维铜棒稳态传热模型，长度100 mm，左端固定温度300 K，右端固定温度350 K，输出最高温度和热流",
                memory_path=ROOT / "generated" / "case_memory" / "case_memory.json",
                output_dir=directory,
            )
        self.assertEqual(len(STAGE_DEFINITIONS), 10)
        self.assertEqual(len(workflow["steps"]), 10)
        self.assertEqual(workflow["steps"][0]["id"], "task_definition")
        self.assertEqual(workflow["steps"][-1]["id"], "execution_validation")
        self.assertIn("modeling_contract", workflow)

    def test_legacy_seven_stage_workflow_is_migrated(self) -> None:
        legacy_steps = [
            {"id": item, "status": "approved", "approval": {"approved": True}}
            for item in ("physics", "materials", "data_structure", "mesh", "study_solver", "results_export", "final_generation")
        ]
        payload = {
            "kind": "comsol_staged_modeling_workflow",
            "requirement": "建立一维铜棒稳态传热模型，长度100 mm，左端固定温度300 K，输出最高温度",
            "plan": {"inferred_domains": ["heat_transfer"], "candidate_parameters": [], "candidate_outputs": ["T_max"]},
            "steps": legacy_steps,
            "approval_log": [{"step_id": "physics", "approved": True}],
        }
        with tempfile.TemporaryDirectory(dir=ROOT / "generated") as directory:
            path = Path(directory) / "legacy.workflow.json"
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            migrated = load_workflow(path)
        self.assertEqual(migrated["workflow_version"], "2.0.0")
        self.assertEqual(len(migrated["steps"]), 10)
        self.assertEqual(migrated["approval_log"], payload["approval_log"])
        self.assertEqual(migrated["status"], "approved_for_generation")

    def test_final_stage_requires_runtime_evidence(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / "generated") as directory:
            workflow = create_staged_workflow(
                "建立一维铜棒稳态传热模型，长度100 mm，左端固定温度300 K，右端固定温度350 K，输出最高温度",
                memory_path=ROOT / "generated" / "case_memory" / "case_memory.json",
                output_dir=directory,
            )
            path = Path(workflow["outputs"]["workflow"])
            with self.assertRaisesRegex(ValueError, "execution evidence is missing"):
                record_execution_validation(path, {"mph_model": "model.mph"}, passed=True, output_dir=directory)
            completed = record_execution_validation(
                path,
                {
                    "mph_model": "model.mph",
                    "result_data": "results.csv",
                    "execution_log": "execution.log",
                    "physics_validation_report": "validation.json",
                },
                passed=True,
                output_dir=directory,
            )
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["steps"][-1]["status"], "approved")


if __name__ == "__main__":
    unittest.main()
