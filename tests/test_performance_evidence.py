from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPEATED = ROOT / "generated" / "benchmarks" / "comsol_repeat_20261009" / "repeated_comsol_performance.json"
RUNTIME = ROOT / "generated" / "benchmarks" / "runtime_performance_20261009.json"
MULTIPHYSICS_SWEEP = (
    ROOT
    / "generated"
    / "benchmarks"
    / "busbar_multiphysics_sweep_20261009"
    / "busbar_multiphysics_sweep_benchmark.json"
)
DENSE_MULTIPHYSICS_SWEEP = (
    ROOT
    / "generated"
    / "benchmarks"
    / "busbar_dense_multiphysics_sweep_20261009"
    / "busbar_dense_multiphysics_sweep_benchmark.json"
)


class PerformanceEvidenceTests(unittest.TestCase):
    def test_repeated_comsol_report_includes_mphserver_and_combined_resources(self) -> None:
        report = json.loads(REPEATED.read_text(encoding="utf-8"))
        summary = report["summary"]
        self.assertEqual(summary["run_count"], 3)
        self.assertTrue(summary["all_passed"])
        self.assertGreater(summary["mphserver_peak_working_set_mb_max"], 0)
        self.assertGreater(summary["combined_peak_working_set_mb_max"], summary["matlab_peak_working_set_mb_max"])
        self.assertGreater(summary["combined_peak_private_memory_mb_max"], summary["matlab_peak_private_memory_mb_max"])
        self.assertTrue(all(row["temperature_max_K"] == 373.15 for row in report["runs"]))

    def test_runtime_report_uses_same_comsol_resource_evidence(self) -> None:
        repeated = json.loads(REPEATED.read_text(encoding="utf-8"))
        runtime = json.loads(RUNTIME.read_text(encoding="utf-8"))
        summary = repeated["summary"]
        reference = runtime["comsol_reference"]
        self.assertEqual(reference["duration_seconds"], summary["wall_seconds_median"])
        self.assertEqual(reference["combined_peak_working_set_mb_max"], summary["combined_peak_working_set_mb_max"])
        self.assertEqual(reference["combined_peak_private_memory_mb_max"], summary["combined_peak_private_memory_mb_max"])
        self.assertGreater(runtime["speedup_vs_comsol"]["direct_median_times"], 1000)

    def test_complete_3d_multiphysics_sweep_passes_physics_checks(self) -> None:
        report = json.loads(MULTIPHYSICS_SWEEP.read_text(encoding="utf-8"))
        self.assertEqual(report["model"]["dimension"], "3D")
        self.assertEqual(report["execution"]["completed_cases"], 9)
        self.assertTrue(report["validation"]["all_passed"])
        self.assertLess(report["validation"]["maximum_energy_imbalance_percent"], 0.1)
        self.assertEqual(len(report["rows"]), 9)
        self.assertGreater(report["execution"]["wall_seconds"], sum(row["solve_seconds"] for row in report["rows"]))

    def test_multiphysics_sweep_captures_matlab_and_mphserver_resources(self) -> None:
        report = json.loads(MULTIPHYSICS_SWEEP.read_text(encoding="utf-8"))
        resources = report["resources"]
        self.assertGreater(resources["matlab_peak_working_set_mb"], 0)
        self.assertGreater(resources["mphserver_peak_working_set_mb"], 0)
        self.assertGreater(resources["combined_peak_working_set_mb"], resources["matlab_peak_working_set_mb"])
        self.assertGreater(resources["combined_peak_private_memory_mb"], resources["matlab_peak_private_memory_mb"])

    def test_dense_3d_sweep_recomputes_all_training_rows(self) -> None:
        report = json.loads(DENSE_MULTIPHYSICS_SWEEP.read_text(encoding="utf-8"))
        self.assertEqual(report["execution"]["completed_cases"], 49)
        self.assertTrue(report["validation"]["all_passed"])
        comparison = report["validation"]["historical_dense_csv_comparison"]
        self.assertTrue(comparison["all_passed"])
        self.assertEqual(comparison["matched_rows"], 49)
        self.assertLess(comparison["maximum_absolute_differences"]["Tmax_K"], 0.001)
        self.assertGreater(report["resources"]["combined_peak_working_set_mb"], 0)


if __name__ == "__main__":
    unittest.main()
