from __future__ import annotations

import json
import tempfile
import unittest
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from comsol_small_model.surrogate_runtime import load_surrogate_payload, predict_validated_surrogate
from comsol_small_model.surrogate_runtime_audit import audit_registered_surrogates


ROOT = Path(__file__).resolve().parents[1]


class SurrogateRuntimeAuditTests(unittest.TestCase):
    def test_surrogate_payload_loader_filters_only_known_joblib_shape_warning(self) -> None:
        payload = {
            "array": np.array([[1.0, 2.0]]),
            "input_columns": ["x"],
            "output_columns": ["y"],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "payload.joblib"
            joblib.dump(payload, path)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                loaded = load_surrogate_payload(path)
        self.assertEqual(loaded["array"].shape, (1, 2))
        self.assertFalse(any("Setting the shape" in str(item.message) for item in caught))

    def test_prediction_preserves_dataframe_feature_names_without_warning(self) -> None:
        estimator = LinearRegression().fit(pd.DataFrame({"x": [0.0, 1.0]}), [0.0, 2.0])
        result, messages = self._predict_with_estimator(estimator)
        self.assertTrue(result["ok"])
        self.assertFalse(any("feature names" in message for message in messages))

    def test_prediction_keeps_numpy_input_for_estimator_without_feature_names(self) -> None:
        estimator = LinearRegression().fit(np.array([[0.0], [1.0]]), [0.0, 2.0])
        result, messages = self._predict_with_estimator(estimator)
        self.assertTrue(result["ok"])
        self.assertFalse(any("feature names" in message for message in messages))

    def test_registry_audit_exercises_all_validated_models(self) -> None:
        report = audit_registered_surrogates(
            ROOT / "generated" / "models" / "surrogate_registry.json"
        )
        self.assertGreaterEqual(report["validated_models"], 1)
        self.assertEqual(report["failed"], 0)
        self.assertEqual(report["feature_name_warning_count"], 0)
        self.assertIn("compatibility_notices", report)
        self.assertEqual(report["passed"], report["validated_models"])
        self.assertTrue(report["overall_passed"])

    def _predict_with_estimator(self, estimator: LinearRegression) -> tuple[dict, list[str]]:
        payload = {
            "model": estimator,
            "model_name": "linear_test",
            "input_columns": ["x"],
            "output_columns": ["y"],
            "training_csv_path": "Z:/missing/training.csv",
            "validated_input_ranges": {"x": {"min": 0.0, "max": 1.0}},
        }
        with tempfile.TemporaryDirectory() as directory:
            model_path = Path(directory) / "model.joblib"
            joblib.dump(payload, model_path)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                result = predict_validated_surrogate(model_path, {"x": 0.5})
        return result, [str(item.message) for item in caught]


if __name__ == "__main__":
    unittest.main()
