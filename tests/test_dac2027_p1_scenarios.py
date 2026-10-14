from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from comsol_small_model.dac2027_p1_scenarios import build_p1_report, validate_scenario_contract


class Dac2027P1ScenarioTests(unittest.TestCase):
    def test_project_has_two_complete_traceable_scenario_definitions(self) -> None:
        report = build_p1_report(ROOT)
        self.assertTrue(report["p1_definition_completed"])
        self.assertEqual(report["primary_scenario_count"], 2)
        self.assertEqual(report["definition_ready_count"], 2)
        self.assertTrue(report["submission_two_case_experiment_completed"])
        self.assertEqual(report["fresh_post_freeze_count"], 2)
        self.assertTrue(all(report["gates"].values()))
        self.assertTrue(all(row["fresh_experiment"]["valid"] for row in report["scenarios"]))
        self.assertTrue(
            all(all(row["fresh_experiment"]["checks"].values()) for row in report["scenarios"])
        )

    def test_contract_without_stop_conditions_is_rejected(self) -> None:
        report = build_p1_report(ROOT)
        scenario = copy.deepcopy(report["scenarios"][0])
        invalid = {
            "id": scenario["id"],
            "role": "primary",
            "name_zh": scenario["name_zh"],
            "eda_stage": scenario["eda_stage"],
            "design_question": "test",
            "engineering_decision": {"decision": "d", "value": "v", "decision_owner": "o"},
            "design_variables": [{"name": "x", "unit": "m", "lower": 0, "upper": 1, "meaning": "x"}],
            "operating_variables": [],
            "objectives": [{"name": "y"}],
            "constraints": [{"name": "c"}],
            "required_outputs": [{"name": "y"}],
            "physics_plan": {"interfaces": ["heat_transfer_solids"], "couplings": [], "study": "stationary", "validation_rules": ["r"]},
            "automatic_stop_conditions": [],
            "evidence": {},
        }
        result = validate_scenario_contract(invalid)
        self.assertFalse(result["valid"])
        self.assertFalse(result["checks"]["stop_conditions_present"])


if __name__ == "__main__":
    unittest.main()
