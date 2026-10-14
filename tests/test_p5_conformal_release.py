from __future__ import annotations

import hashlib
import json
import unittest
import zipfile
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from comsol_small_model.eda_conformal import CONSTRAINT_TARGETS, finite_sample_quantile, upper_bounds
from web_app import _p5_status_payload


ROOT = Path(__file__).resolve().parents[1]
P5 = ROOT / "generated" / "p5"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class P5ConformalReleaseTests(unittest.TestCase):
    def test_finite_sample_quantile_is_conservative(self) -> None:
        scores = np.arange(1.0, 21.0)
        self.assertEqual(finite_sample_quantile(scores, coverage=0.95), 20.0)

    def test_sealed_inputs_and_frozen_artifacts_match_manifest(self) -> None:
        manifest = json.loads(
            (P5 / "sealed_final_design" / "sealed_design_manifest.json").read_text(encoding="utf-8")
        )
        for section in ("files", "frozen_before_sealing"):
            for detail in manifest[section].values():
                path = ROOT / detail["path"]
                self.assertTrue(path.is_file())
                self.assertEqual(sha256(path), detail["sha256"])

    def test_selected_model_produces_finite_upper_bounds(self) -> None:
        package = joblib.load(P5 / "p5_one_sided_surrogate.joblib")
        frame = pd.read_csv(P5 / "sealed_final_design" / "p5_independent_domain_inputs.csv").head(2)
        bounded = upper_bounds(
            package["p4_bundle"],
            package["calibration"],
            frame,
            method=package["calibration"]["selected_method"],
        )
        for target in CONSTRAINT_TARGETS:
            self.assertTrue(np.isfinite(bounded[f"upper_95_{target}"]).all())
            self.assertTrue((bounded[f"upper_margin_{target}"] >= 0.0).all())

    def test_final_independent_release_passes_without_false_safe(self) -> None:
        report = json.loads(
            (P5 / "final_evaluation" / "p5_final_evaluation_report.json").read_text(encoding="utf-8")
        )
        self.assertTrue(report["execution_passed"])
        self.assertTrue(all(report["release_checks"].values()))
        self.assertTrue(report["surrogate_release_passed"])
        self.assertEqual(report["counts"]["released_safe_upper_95"], 10)
        self.assertEqual(report["counts"]["false_safe_upper_95"], 0)
        self.assertAlmostEqual(report["safe_release_coverage"], 1.0 / 6.0)

    def test_web_status_reports_controlled_release(self) -> None:
        payload = _p5_status_payload()
        self.assertEqual(payload["calibration_method"], "normalized_one_sided")
        self.assertTrue(payload["comsol_execution_passed"])
        self.assertEqual(payload["released_safe_count"], 10)
        self.assertEqual(payload["false_safe_count"], 0)
        self.assertTrue(payload["surrogate_release_passed"])

    def test_p5_release_package_has_matching_manifest_and_controlled_policy(self) -> None:
        release = P5 / "release"
        summary = json.loads((release / "release_summary.json").read_text(encoding="utf-8"))
        manifest = json.loads((release / "release_manifest.json").read_text(encoding="utf-8"))
        archive_path = ROOT / summary["archive"]
        self.assertTrue(archive_path.is_file())
        self.assertEqual(sha256(archive_path), summary["sha256"])
        self.assertTrue(summary["surrogate_release_passed"])
        self.assertEqual(0, summary["false_safe_count"])
        self.assertEqual("comsol-p5-release-manifest", manifest["schema"])
        with zipfile.ZipFile(archive_path) as archive:
            names = set(archive.namelist())
            self.assertIn("P5_RELEASE_MANIFEST.json", names)
            self.assertIn("P5_COMPLETION_REPORT.md", names)
            self.assertIn("generated/p5/p5_one_sided_surrogate.joblib", names)
            self.assertNotIn("generated/p5/final_evaluation/p5_final_evaluation_final.mph", names)


if __name__ == "__main__":
    unittest.main()
