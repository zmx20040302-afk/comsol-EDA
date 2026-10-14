from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from comsol_small_model.experimental_validation import validate_temperature_experiment
from web_app import _experimental_validation_status


class ExperimentalValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = {
            "input_columns": ["x"],
            "output_columns": ["Tmax_K", "Tavg_K"],
        }
        self.config = {
            "minimum_measured_samples": 1,
            "required_outputs": ["Tmax_K", "Tavg_K"],
            "absolute_tolerance_K": {"Tmax_K": 2.0, "Tavg_K": 2.0},
            "require_comsol_values": True,
            "require_all_rows_in_validated_domain": True,
        }

    def _write(self, root: Path, row: dict[str, object]) -> tuple[Path, Path]:
        csv_path = root / "measurements.csv"
        config_path = root / "config.json"
        pd.DataFrame([row]).to_csv(csv_path, index=False)
        config_path.write_text(json.dumps(self.config), encoding="utf-8")
        return csv_path, config_path

    def test_empty_template_stays_awaiting_measurements(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            csv_path, config_path = self._write(
                root,
                {
                    "sample_id": "EXP-001",
                    "record_status": "template",
                    "x": 0.5,
                    "measured_Tmax_K": "",
                    "measurement_u95_Tmax_K": "",
                    "comsol_Tmax_K": "",
                    "measured_Tavg_K": "",
                    "measurement_u95_Tavg_K": "",
                    "comsol_Tavg_K": "",
                },
            )
            with patch(
                "comsol_small_model.experimental_validation.load_surrogate_payload",
                return_value=self.payload,
            ):
                result = validate_temperature_experiment(csv_path, root / "model.joblib", config_path=config_path)
        self.assertEqual(result["status"], "awaiting_measurements")
        self.assertFalse(result["passed"])

    def test_measured_row_passes_three_way_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            csv_path, config_path = self._write(
                root,
                {
                    "sample_id": "EXP-001",
                    "record_status": "measured",
                    "x": 0.5,
                    "measured_Tmax_K": 350.0,
                    "measurement_u95_Tmax_K": 0.5,
                    "comsol_Tmax_K": 351.0,
                    "measured_Tavg_K": 310.0,
                    "measurement_u95_Tavg_K": 0.5,
                    "comsol_Tavg_K": 311.0,
                },
            )
            prediction = {
                "ok": True,
                "prediction": {"Tmax_K": 350.8, "Tavg_K": 310.8},
                "confidence": {"level": "high"},
                "uncertainty": {
                    "intervals": {
                        "Tmax_K": {"lower": 349.0, "upper": 352.0},
                        "Tavg_K": {"lower": 309.0, "upper": 312.0},
                    }
                },
            }
            with (
                patch("comsol_small_model.experimental_validation.load_surrogate_payload", return_value=self.payload),
                patch("comsol_small_model.experimental_validation.predict_validated_surrogate", return_value=prediction),
            ):
                result = validate_temperature_experiment(csv_path, root / "model.joblib", config_path=config_path)
        self.assertTrue(result["passed"])
        self.assertEqual(result["metrics"]["Tmax_K"]["comsol_vs_measurement"]["pass_rate"], 1.0)
        self.assertTrue(
            result["rows"][0]["outputs"]["Tmax_K"]["surrogate"]
            ["measurement_interval_overlaps_prediction_interval"]
        )

    def test_out_of_domain_surrogate_fails_release_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            csv_path, config_path = self._write(
                root,
                {
                    "sample_id": "EXP-001",
                    "record_status": "measured",
                    "x": 1.5,
                    "measured_Tmax_K": 350.0,
                    "measurement_u95_Tmax_K": 0.5,
                    "comsol_Tmax_K": 350.0,
                    "measured_Tavg_K": 310.0,
                    "measurement_u95_Tavg_K": 0.5,
                    "comsol_Tavg_K": 310.0,
                },
            )
            with (
                patch("comsol_small_model.experimental_validation.load_surrogate_payload", return_value=self.payload),
                patch(
                    "comsol_small_model.experimental_validation.predict_validated_surrogate",
                    return_value={"ok": False, "confidence": {"level": "low", "requires_comsol": True}},
                ),
            ):
                result = validate_temperature_experiment(csv_path, root / "model.joblib", config_path=config_path)
        self.assertFalse(result["passed"])
        self.assertFalse(result["all_rows_in_validated_domain"])
        self.assertFalse(result["rows"][0]["outputs"]["Tmax_K"]["surrogate"]["available"])

    def test_web_status_does_not_treat_pending_report_as_passed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report_path = Path(directory) / "report.json"
            report_path.write_text(
                json.dumps(
                    {
                        "status": "awaiting_measurements",
                        "passed": False,
                        "sample_count": 0,
                        "interpretation": "waiting",
                    }
                ),
                encoding="utf-8",
            )
            status = _experimental_validation_status(report_path)
        self.assertTrue(status["available"])
        self.assertEqual(status["status"], "awaiting_measurements")
        self.assertFalse(status["passed"])


if __name__ == "__main__":
    unittest.main()
