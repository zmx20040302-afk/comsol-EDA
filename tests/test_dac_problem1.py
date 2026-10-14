from __future__ import annotations

import sys
import unittest
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from comsol_small_model.physics_dependency_graph import compile_physics_dependency_plan
from comsol_small_model.bounded_repair import apply_bounded_repair
from comsol_small_model.requirement_parser import parse_modeling_requirement
from scripts.run_dac_problem1_development_benchmark import run
from scripts.run_dac_problem1_frozen_evaluation import evaluate


class DacProblemOneTests(unittest.TestCase):
    def test_output_dependencies_complete_thermal_actuator(self) -> None:
        result = compile_physics_dependency_plan(
            "建立硅热执行器稳态模型，施加5 V电压，环境293 K并考虑对流，固定锚点，计算最高温度和末端位移。"
        )
        self.assertEqual(
            set(result["interface_ids"]),
            {"electric_currents", "heat_transfer_solids", "solid_mechanics"},
        )
        self.assertEqual(
            set(result["coupling_ids"]),
            {"electromagnetic_heating", "thermal_expansion"},
        )

    def test_fluid_temperature_uses_fluid_heat_interface(self) -> None:
        result = compile_physics_dependency_plan(
            "建立二维水冷流道稳态模型，给定入口速度和入口温度，壁面固定温度，输出压降和出口温度。"
        )
        self.assertEqual(set(result["interface_ids"]), {"laminar_flow", "heat_transfer_fluids"})
        self.assertEqual(set(result["coupling_ids"]), {"nonisothermal_flow"})

    def test_explicit_conflict_blocks_plan(self) -> None:
        result = compile_physics_dependency_plan(
            "建立稳态焦耳热模型但禁止传热，施加5 V并输出最高温度。"
        )
        self.assertTrue(result["decision"]["blocked"])
        self.assertIn("REQUIREMENT_CONFLICT", result["decision"]["reason_codes"])

    def test_development_benchmark_is_labeled_non_independent(self) -> None:
        report = run()
        self.assertEqual(report["task_count"], 18)
        self.assertEqual(report["split"], "development_only")
        self.assertFalse(report["independent_final_test_claimed"])
        self.assertGreaterEqual(
            report["methods"]["dependency_graph"]["physics_and_coupling_exact_accuracy"],
            report["methods"]["existing_selector"]["physics_and_coupling_exact_accuracy"],
        )

    def test_dependency_plan_is_embedded_in_modeling_contract(self) -> None:
        contract = parse_modeling_requirement(
            "建立硅热执行器稳态模型，施加5 V电压，环境293 K并考虑对流，固定锚点，计算最高温度和末端位移。"
        )
        self.assertEqual(
            {item["id"] for item in contract["physics"]["interfaces"]},
            {"electric_currents", "heat_transfer_solids", "solid_mechanics"},
        )
        self.assertEqual(
            {item["id"] for item in contract["physics"]["couplings"]},
            {"electromagnetic_heating", "thermal_expansion"},
        )
        self.assertEqual(
            contract["decision_support"]["physics_dependency_graph"]["schema"],
            "comsol-physics-dependency-plan",
        )

    def test_frozen_protocol_hashes_match(self) -> None:
        protocol = json.loads((ROOT / "configs" / "dac_problem1_frozen_protocol.json").read_text(encoding="utf-8"))
        for section in ("method_files_sha256", "datasets_sha256"):
            for relative, expected in protocol[section].items():
                actual = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
                self.assertEqual(actual, expected, relative)

    def test_bounded_repair_preserves_contract_and_rejects_broad_patch(self) -> None:
        contract = {"schemaVersion": "1.0.0", "physics": {"interfaces": ["heat_transfer_solids"]}}
        result = apply_bounded_repair(
            contract,
            "a\nb\nc",
            {"field": "generated_code", "old": "b", "new": "b_fixed"},
        )
        self.assertTrue(result["applied"])
        self.assertEqual(result["contract_sha256_before"], result["contract_sha256_after"])
        rejected = apply_bounded_repair(
            contract,
            "a\nb\nc\nd",
            {"field": "generated_code", "old": "a\nb\nc\nd", "new": "x"},
        )
        self.assertFalse(rejected["applied"])
        self.assertIn("patch_span_exceeds_limit", rejected["reason_codes"])

    def test_frozen_evaluation_is_labeled_non_blinded(self) -> None:
        report = evaluate("validation")
        self.assertTrue(report["post_freeze"])
        self.assertFalse(report["independently_authored_or_blinded"])
        self.assertEqual(report["methods"]["dependency_graph"]["task_count"], 12)


if __name__ == "__main__":
    unittest.main()
