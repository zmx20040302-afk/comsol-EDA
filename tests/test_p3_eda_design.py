from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from comsol_small_model.eda_design import (
    design_readiness,
    independent_domain_design,
    latin_hypercube_design,
    load_eda_problem,
    out_of_domain_design,
    pareto_front,
    variable_rows,
    write_p3_design_package,
)
from comsol_small_model.eda_optimization import select_verification_candidates, two_objective_pareto
from web_app import _p3_status_payload


ROOT = Path(__file__).resolve().parents[1]


class P3EdaDesignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.spec = load_eda_problem(ROOT / "configs" / "busbar_eda_design_problem.json")

    def test_fixed_current_problem_builds_non_overlapping_designs(self) -> None:
        initial = latin_hypercube_design(self.spec, count=80, seed=20261009, include_baseline=True)
        holdout = independent_domain_design(self.spec, count=60, seed=20261019, forbidden=initial)
        names = [item["name"] for item in variable_rows(self.spec)]
        left = {tuple(round(float(row[name]), 10) for name in names) for row in initial.to_dict("records")}
        right = {tuple(round(float(row[name]), 10) for name in names) for row in holdout.to_dict("records")}
        self.assertFalse(left & right)
        self.assertTrue((initial["bolt_radius_mm"] <= 0.2 * initial["wbb_mm"] + 1e-12).all())

    def test_out_of_domain_rows_each_have_a_declared_violation(self) -> None:
        frame = out_of_domain_design(self.spec, count=20, seed=20261029)
        ranges = {item["name"]: (item["lower"], item["upper"]) for item in variable_rows(self.spec)}
        for row in frame.to_dict("records"):
            name = row["violated_variable"]
            low, high = ranges[name]
            self.assertTrue(float(row[name]) < float(low) or float(row[name]) > float(high))

    def test_optimization_is_blocked_until_fresh_comsol_outputs_exist(self) -> None:
        initial = latin_hypercube_design(self.spec, count=8, seed=7, include_baseline=True)
        readiness = design_readiness(initial, self.spec)
        self.assertFalse(readiness["ready_for_optimization"])
        self.assertEqual(readiness["decision"], "blocked_pending_comsol_evidence")

    def test_pareto_front_requires_feasible_verified_rows(self) -> None:
        frame = pd.DataFrame([
            {"case_id": "a", "copper_mass_kg": 1.0, "joule_power_W": 3.0, "constraints_passed": True, "comsol_verified": True},
            {"case_id": "b", "copper_mass_kg": 2.0, "joule_power_W": 2.0, "constraints_passed": True, "comsol_verified": True},
            {"case_id": "c", "copper_mass_kg": 3.0, "joule_power_W": 4.0, "constraints_passed": True, "comsol_verified": True},
            {"case_id": "d", "copper_mass_kg": 0.5, "joule_power_W": 1.0, "constraints_passed": False, "comsol_verified": True},
            {"case_id": "e", "copper_mass_kg": 0.2, "joule_power_W": 0.2, "constraints_passed": True, "comsol_verified": False},
        ])
        result = pareto_front(frame)
        self.assertEqual(set(result["case_id"]), {"a", "b"})

    def test_design_package_has_80_60_20_split(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT / ".tmp") as temp_dir:
            report = write_p3_design_package(self.spec, temp_dir)
            self.assertEqual(report["counts"], {"initial_design": 80, "independent_domain_test": 60, "out_of_domain_test": 20})
            self.assertTrue(Path(report["manifest_path"]).is_file())

    def test_fast_two_objective_pareto_and_verification_selection(self) -> None:
        frame = pd.DataFrame([
            {"case_id": "a", "pred_copper_mass_kg": 1.0, "pred_joule_power_W": 5.0},
            {"case_id": "b", "pred_copper_mass_kg": 2.0, "pred_joule_power_W": 3.0},
            {"case_id": "c", "pred_copper_mass_kg": 3.0, "pred_joule_power_W": 4.0},
            {"case_id": "d", "pred_copper_mass_kg": 4.0, "pred_joule_power_W": 2.0},
        ])
        pareto = two_objective_pareto(frame, "pred_copper_mass_kg", "pred_joule_power_W")
        self.assertEqual(set(pareto["case_id"]), {"a", "b", "d"})
        selected = select_verification_candidates(pareto, count=3)
        self.assertEqual(len(selected), 3)
        self.assertTrue(selected["case_id"].str.startswith("pareto_verify_").all())

    def test_final_evaluation_keeps_failed_surrogate_unreleased(self) -> None:
        report = json.loads(
            (ROOT / "generated" / "p3" / "final_evaluation" / "final_evaluation_report.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertTrue(report["execution_passed"])
        self.assertFalse(report["surrogate_release_passed"])
        self.assertEqual(report["counts"]["false_safe_conservative_95"], 0)
        self.assertEqual(report["mean_gate_diagnostic"]["false_safe"], 3)

    def test_web_status_separates_comsol_and_surrogate_release(self) -> None:
        payload = _p3_status_payload()
        self.assertTrue(payload["comsol_execution_passed"])
        self.assertEqual(payload["verified_pareto_count"], 3)
        self.assertFalse(payload["surrogate_release_passed"])


if __name__ == "__main__":
    unittest.main()

