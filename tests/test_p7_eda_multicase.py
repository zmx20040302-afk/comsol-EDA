from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from comsol_small_model.p7_eda_multicase import build_p7_report, evaluate_case


class P7EdaMulticaseTests(unittest.TestCase):
    def test_frozen_project_evidence_passes_all_p7_main_gates(self) -> None:
        report = build_p7_report(ROOT)
        self.assertTrue(report["p7_completed"])
        self.assertEqual(report["passed_main_case_count"], 4)
        self.assertGreaterEqual(report["physics_family_count"], 4)
        self.assertTrue(all(report["gates"].values()))
        self.assertEqual(
            [case["dataset"]["input_overlap_count"] for case in report["cases"] if case["role"] == "main"],
            [0, 0, 0, 0],
        )

    def test_overlapping_holdout_is_rejected_even_when_report_says_passed(self) -> None:
        test_root = ROOT / "generated" / "test_tmp"
        test_root.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix="p7_", dir=test_root))
        try:
            root = temporary
            (root / "data").mkdir()
            (root / "data" / "training.csv").write_text("x,y\n1,2\n2,4\n", encoding="utf-8")
            (root / "data" / "holdout.csv").write_text("x,y\n2.0,4\n", encoding="utf-8")
            (root / "data" / "validation.json").write_text(
                json.dumps(
                    {
                        "passed": True,
                        "per_output_relative_validation": {
                            "y": {
                                "max_relative_error_percent": 0.1,
                                "threshold_relative_error_percent": 1.0,
                                "passed": True,
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )
            (root / "data" / "model.joblib").write_bytes(b"model")
            (root / "data" / "evidence.mph").write_bytes(b"mph")
            case = {
                "id": "overlap",
                "name_zh": "重叠样本",
                "role": "main",
                "physics_family": "test",
                "input_columns": ["x"],
                "training_csv": "data/training.csv",
                "holdout_csv": "data/holdout.csv",
                "validation_report": "data/validation.json",
                "model_artifact": "data/model.joblib",
                "comsol_artifact": "data/evidence.mph",
                "minimum_training_rows": 2,
                "minimum_holdout_rows": 1,
                "validation_mode": "relative_error_gate",
            }
            result = evaluate_case(case, root)
            self.assertFalse(result["passed"])
            self.assertEqual(result["dataset"]["input_overlap_count"], 1)
            self.assertFalse(result["checks"]["independent_holdout_passed"])
        finally:
            shutil.rmtree(temporary, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
