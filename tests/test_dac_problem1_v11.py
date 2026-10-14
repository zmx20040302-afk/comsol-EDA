from __future__ import annotations

import unittest
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from comsol_small_model.physics_dependency_graph_v11 import compile_physics_dependency_plan_v11


class RequirementCompletenessV11Tests(unittest.TestCase):
    def test_missing_thermal_clause_is_not_positive_evidence(self) -> None:
        plan = compile_physics_dependency_plan_v11(
            "建立散热板稳态固体传热模型，输出最高温度，但环境温度和散热边界尚未给出。"
        )
        self.assertTrue(plan["decision"]["blocked"])
        self.assertIn("MISSING_THERMAL_BOUNDARY", plan["decision"]["reason_codes"])

    def test_fixed_temperatures_are_valid_thermal_boundaries(self) -> None:
        plan = compile_physics_dependency_plan_v11(
            "建立BGA稳态热应力模型，芯片侧保持353 K且板侧保持293 K，板底固定，输出温度和最大应力。"
        )
        self.assertFalse(plan["decision"]["blocked"])

    def test_unresolved_objective_does_not_select_alternatives(self) -> None:
        plan = compile_physics_dependency_plan_v11(
            "建立MEMS麦克风模型，但未说明观察声压、位移还是共振频率。"
        )
        self.assertEqual(plan["interface_ids"], [])
        self.assertIn("OBJECTIVE_MISSING_OR_UNRESOLVED", plan["decision"]["reason_codes"])

    def test_modal_structure_does_not_require_mechanical_load(self) -> None:
        plan = compile_physics_dependency_plan_v11(
            "建立石英梁特征频率模型，底座固定，输出前五阶固有频率和振型位移。"
        )
        self.assertFalse(plan["decision"]["blocked"])


if __name__ == "__main__":
    unittest.main()
