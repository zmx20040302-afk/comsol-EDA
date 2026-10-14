from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "configs" / "busbar_eda_design_problem.json"


class EdaDesignProblemTests(unittest.TestCase):
    def test_busbar_eda_problem_has_consistent_variables_objectives_and_evidence_roles(self) -> None:
        spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
        self.assertEqual(spec["drive_definition"]["optimization_mode"], "fixed_terminal_current")
        self.assertEqual(len(spec["decision_variables"]), 4)
        for variable in spec["decision_variables"]:
            self.assertLess(variable["lower"], variable["baseline"])
            self.assertLess(variable["baseline"], variable["upper"])
            self.assertTrue(variable.get("comsol_parameter"))
        objective_names = {item["name"] for item in spec["objectives"]}
        self.assertEqual(objective_names, {"copper_mass_kg", "joule_power_W"})
        output_names = set(spec["required_outputs"])
        self.assertTrue({"Tmax_K", "Jmax_A_m2", "voltage_drop_mV", "copper_mass_kg"} <= output_names)
        plan = spec["evaluation_plan"]
        self.assertGreaterEqual(plan["independent_domain_test_cases"], 40)
        self.assertGreaterEqual(plan["independent_out_of_domain_cases"], 20)
        self.assertIn("false_safe_rate", plan["release_metrics"])
        self.assertIn("All final Pareto candidates require fresh COMSOL verification", spec["fixed_assumptions"])


if __name__ == "__main__":
    unittest.main()
