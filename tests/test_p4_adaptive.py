from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from comsol_small_model.eda_adaptive import ENGINEERED_FEATURES, physics_features
from web_app import _p4_status_payload


ROOT = Path(__file__).resolve().parents[1]
P4 = ROOT / "generated" / "p4"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class P4AdaptiveSurrogateTests(unittest.TestCase):
    def test_physics_features_are_finite_and_complete(self) -> None:
        frame = pd.DataFrame(
            [{
                "L_mm": 90.0,
                "wbb_mm": 25.0,
                "tbb_mm": 3.0,
                "bolt_radius_mm": 4.0,
                "I_load_A": 160.0,
                "htc_W_m2K": 5.0,
                "T_amb_K": 293.15,
            }]
        )
        transformed = physics_features(frame)
        self.assertTrue(set(ENGINEERED_FEATURES).issubset(transformed.columns))
        self.assertTrue(np.isfinite(transformed.to_numpy(dtype=float)).all())
        self.assertGreater(float(transformed.loc[0, "cross_section_mm2"]), 0.0)

    def test_sealed_final_design_hashes_match_manifest(self) -> None:
        manifest = json.loads(
            (P4 / "sealed_final_design" / "sealed_design_manifest.json").read_text(encoding="utf-8")
        )
        for detail in manifest["files"].values():
            path = ROOT / detail["path"]
            self.assertTrue(path.is_file())
            self.assertEqual(sha256(path), detail["sha256"])

    def test_final_evaluation_passes_accuracy_but_blocks_release_coverage(self) -> None:
        report = json.loads(
            (P4 / "final_evaluation" / "p4_final_evaluation_report.json").read_text(encoding="utf-8")
        )
        checks = report["release_checks"]
        self.assertTrue(report["execution_passed"])
        self.assertTrue(checks["tmax_rmse_at_most_15_K"])
        self.assertTrue(checks["power_relative_rmse_at_most_15_percent"])
        self.assertTrue(checks["all_intervals_picp_at_least_0_90"])
        self.assertFalse(checks["safe_release_coverage_at_least_0_10"])
        self.assertFalse(report["surrogate_release_passed"])
        self.assertEqual(report["counts"]["false_safe_conservative_95"], 0)

    def test_web_status_keeps_accuracy_and_release_separate(self) -> None:
        payload = _p4_status_payload()
        self.assertEqual(payload["adaptive_comsol_cases"], 80)
        self.assertEqual(payload["training_rows"], 220)
        self.assertTrue(payload["comsol_execution_passed"])
        self.assertTrue(payload["accuracy_passed"])
        self.assertFalse(payload["surrogate_release_passed"])
        self.assertAlmostEqual(payload["safe_release_coverage"], 2.0 / 60.0)


if __name__ == "__main__":
    unittest.main()
