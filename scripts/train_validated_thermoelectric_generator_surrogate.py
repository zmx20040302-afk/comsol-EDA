"""Train a declared-scope COMSOL thermoelectric-generator surrogate."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.neighbors import KNeighborsRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import PolynomialFeatures

from comsol_small_model.surrogate_model_card import register_general_surrogate, write_general_surrogate_model_card

ROOT = Path(__file__).resolve().parents[1]
TRAINING = ROOT / "generated/training_runs/thermoelectric_generator_training.csv"
HOLDOUT = ROOT / "generated/training_runs/thermoelectric_generator_holdout.csv"
MODEL = ROOT / "generated/models/thermoelectric_generator_surrogate.joblib"
INPUTS = ["hot_temperature_degC"]
OUTPUTS = ["open_circuit_voltage_V"]
SCOPE = "三维热电发电机稳态耦合模型；冷端 0 degC、热端温度 T0=100-200 degC，铜和 Bi-Sb-Te 材料、温度相关 Seebeck 系数/电导率/导热率、几何、网格、接地和浮动端子固定，输出浮动端开路电压。"


def main() -> int:
    training, holdout = pd.read_csv(TRAINING), pd.read_csv(HOLDOUT)
    x_train, y_train = training[INPUTS].to_numpy(float), training[OUTPUTS].to_numpy(float)
    x_holdout, y_holdout = holdout[INPUTS].to_numpy(float), holdout[OUTPUTS].to_numpy(float)
    candidates = {"linear_regression": LinearRegression(), "polynomial_degree_2": Pipeline([("poly", PolynomialFeatures(degree=2)), ("linear", LinearRegression())]), "distance_weighted_local_interpolation": KNeighborsRegressor(n_neighbors=2, weights="distance")}
    fitted, scores = {}, {}
    for name, candidate in candidates.items():
        candidate.fit(x_train, y_train)
        predicted = candidate.predict(x_holdout)
        errors = np.abs(predicted - y_holdout) / np.maximum(np.abs(y_holdout), 1e-30) * 100.0
        fitted[name] = candidate
        scores[name] = {"max_relative_error_percent": float(errors.max()), "mean_relative_error_percent": float(errors.mean())}
    selected_name = min(scores, key=lambda name: scores[name]["mean_relative_error_percent"])
    selected_metrics = scores[selected_name]
    passed = selected_metrics["max_relative_error_percent"] <= 2.0
    validation = {"kind": "thermoelectric_generator_independent_comsol_validation", "created_at": datetime.now(timezone.utc).isoformat(), "training_csv": str(TRAINING.resolve()), "holdout_csv": str(HOLDOUT.resolve()), "training_rows": len(training), "holdout_rows": len(holdout), "candidate_metrics": scores, "selected_model": selected_name, "selection_reason": "Selected by independent COMSOL holdout error for coupled thermoelectric response with temperature-dependent material properties.", "per_output_relative_validation": {OUTPUTS[0]: {**selected_metrics, "threshold_relative_error_percent": 2.0, "passed": passed}}, "passed": passed, "scope": SCOPE}
    report_path = MODEL.with_suffix(".holdout_validation.json")
    validation["path"] = str(report_path.resolve())
    report_path.write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    joblib.dump({"model": fitted[selected_name], "model_name": selected_name, "input_columns": INPUTS, "output_columns": OUTPUTS, "selection_method": "independent_comsol_holdout", "training_csv_path": str(TRAINING.resolve()), "holdout_csv_path": str(HOLDOUT.resolve())}, MODEL)
    card = write_general_surrogate_model_card(model_name="热电发电机开路电压代理模型", model_path=MODEL, training_csv=TRAINING, holdout_csv=HOLDOUT, input_columns=INPUTS, output_columns=OUTPUTS, physical_scope=SCOPE, validation=validation, output_dir=MODEL.parent)
    register_general_surrogate(model_name="热电发电机开路电压代理模型", model_path=MODEL, card=card, validation=validation, registry_path=ROOT / "generated/models/surrogate_registry.json")
    print(json.dumps(validation, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
