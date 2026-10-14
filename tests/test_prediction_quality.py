from __future__ import annotations

import unittest
from unittest.mock import patch

import pandas as pd

from comsol_small_model.surrogate_runtime import assess_prediction_quality, predict_validated_surrogate
from comsol_small_model.validation_design import build_independent_thermal_holdout
from web_app import _attach_prediction_quality


class PredictionQualityTests(unittest.TestCase):
    def test_inside_prediction_gets_calibrated_interval_and_high_confidence(self) -> None:
        result = assess_prediction_quality(
            inputs={"x": 0.5},
            validated_ranges={"x": {"min": 0.0, "max": 1.0}},
            prediction={"temperature_K": 320.0},
            validation={
                "available": True,
                "passed": True,
                "per_output": {"temperature_K": {"rmse": 1.0}},
            },
            training_data=pd.DataFrame({"x": [0.0, 0.5, 1.0]}),
        )
        interval = result["uncertainty"]["intervals"]["temperature_K"]
        self.assertTrue(interval["available"])
        self.assertLess(interval["lower"], 320.0)
        self.assertGreater(interval["upper"], 320.0)
        self.assertEqual(result["confidence"]["level"], "high")
        self.assertFalse(result["confidence"]["requires_comsol"])

    def test_outside_training_domain_forces_low_confidence(self) -> None:
        result = assess_prediction_quality(
            inputs={"x": 1.2},
            validated_ranges={"x": {"min": 0.0, "max": 1.0}},
            prediction={},
            validation={"available": True, "passed": True},
        )
        self.assertEqual(result["input_domain"]["status"], "outside")
        self.assertIn("x", result["input_domain"]["out_of_range"])
        self.assertEqual(result["confidence"]["level"], "low")
        self.assertTrue(result["confidence"]["requires_comsol"])

    def test_declared_validated_range_is_stricter_than_training_csv_extent(self) -> None:
        payload = {
            "input_columns": ["x"],
            "output_columns": ["temperature_K"],
            "training_csv_path": "wider_training_data.csv",
            "validated_input_ranges": {"x": {"min": 0.0, "max": 1.0}},
            "model_name": "range-precedence-test",
        }
        with (
            patch("comsol_small_model.surrogate_runtime.load_surrogate_payload", return_value=payload),
            patch(
                "comsol_small_model.surrogate_runtime._load_holdout_validation",
                return_value={"available": True, "passed": True},
            ),
            patch("comsol_small_model.surrogate_runtime._load_model_card", return_value={}),
            patch(
                "comsol_small_model.surrogate_runtime._load_training_data",
                return_value=pd.DataFrame({"x": [0.0, 1.0, 2.0]}),
            ),
        ):
            result = predict_validated_surrogate("declared-range.joblib", {"x": 1.5})
        self.assertFalse(result["ok"])
        self.assertEqual(result["validated_ranges"]["x"]["max"], 1.0)
        self.assertEqual(result["input_domain"]["status"], "outside")
        self.assertEqual(result["confidence"]["level"], "low")

    def test_dialogue_exposes_confidence_and_interval(self) -> None:
        quality = assess_prediction_quality(
            inputs={"x": 0.5},
            validated_ranges={"x": {"min": 0.0, "max": 1.0}},
            prediction={"temperature_K": 320.0},
            validation={
                "available": True,
                "passed": True,
                "error_quantile_95": {"temperature_K": 2.5},
            },
        )
        response = _attach_prediction_quality(
            {"intent": ["validated_surrogate_prediction"], "assistant_message": "预测完成。"},
            quality,
        )
        titles = [section["title"] for section in response["explanation_sections"]]
        self.assertIn("预测可信度", titles)
        self.assertIn("不确定性区间", titles)

    def test_expanded_holdout_covers_required_regions_without_training_overlap(self) -> None:
        spec = {
            "sampling": {
                "L_m": [0.04, 0.08],
                "W_m": [0.015, 0.03],
                "k_W_mK": [10.0, 25.0, 60.0],
                "T_hot_K": [333.15, 373.15],
                "T_cold_K": [273.15, 293.15],
            }
        }
        first = build_independent_thermal_holdout(spec, count=18, seed=101)
        second = build_independent_thermal_holdout(spec, count=18, seed=102)
        self.assertEqual(first["sample_count"], 18)
        self.assertEqual(first["training_overlap_count"], 0)
        self.assertGreaterEqual(first["coverage"]["boundary"], 2)
        self.assertGreaterEqual(first["coverage"]["center"], 1)
        self.assertGreaterEqual(first["coverage"]["high_temperature"], 3)
        first_points = {tuple(row[name] for name in first["input_columns"]) for row in first["rows"]}
        second_points = {tuple(row[name] for name in second["input_columns"]) for row in second["rows"]}
        self.assertFalse(first_points.intersection(second_points))


if __name__ == "__main__":
    unittest.main()
