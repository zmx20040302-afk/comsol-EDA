"""Train a declared-scope COMSOL TE/TM Fresnel-reflectance surrogate."""
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
TRAINING = ROOT / "generated/training_runs/fresnel_equations_rf_training.csv"
HOLDOUT = ROOT / "generated/training_runs/fresnel_equations_rf_holdout.csv"
MODEL = ROOT / "generated/models/fresnel_equations_rf_surrogate.joblib"
INPUTS = ["incident_angle_deg"]
OUTPUTS = ["TE_reflectance", "TM_reflectance"]
SCOPE = (
    "菲涅尔方程 RF 模型；空气 n=1 与无损介质 n=1.5 的平面界面，频率固定为 f0，"
    "入射角 0-75 deg，分别输出 COMSOL 频域计算的 TE 与 TM 功率反射率。"
)


def main() -> int:
    training, holdout = pd.read_csv(TRAINING), pd.read_csv(HOLDOUT)
    x_train, y_train = training[INPUTS].to_numpy(float), training[OUTPUTS].to_numpy(float)
    x_holdout, y_holdout = holdout[INPUTS].to_numpy(float), holdout[OUTPUTS].to_numpy(float)
    candidates = {
        "linear_regression": LinearRegression(),
        "polynomial_degree_4": Pipeline([("poly", PolynomialFeatures(degree=4)), ("linear", LinearRegression())]),
        "distance_weighted_local_interpolation": KNeighborsRegressor(n_neighbors=2, weights="distance"),
    }
    fitted, scores = {}, {}
    for name, candidate in candidates.items():
        candidate.fit(x_train, y_train)
        predicted = candidate.predict(x_holdout)
        absolute = np.abs(predicted - y_holdout)
        relative = absolute / np.maximum(np.abs(y_holdout), 1e-5) * 100.0
        fitted[name] = candidate
        scores[name] = {
            "max_relative_error_percent": float(relative.max()),
            "mean_relative_error_percent": float(relative.mean()),
            "max_absolute_error": float(absolute.max()),
        }
    selected_name = min(scores, key=lambda name: scores[name]["mean_relative_error_percent"])
    selected_metrics = scores[selected_name]
    passed = selected_metrics["max_absolute_error"] <= 0.02
    validation = {
        "kind": "fresnel_equations_rf_independent_comsol_validation",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "training_csv": str(TRAINING.resolve()), "holdout_csv": str(HOLDOUT.resolve()),
        "training_rows": len(training), "holdout_rows": len(holdout),
        "candidate_metrics": scores, "selected_model": selected_name,
        "selection_reason": "Selected by independent COMSOL holdout error; absolute error is primary because TM reflectance approaches zero near Brewster angle.",
        "per_output_absolute_validation": {output: {**selected_metrics, "threshold_absolute_error": 0.02, "passed": passed} for output in OUTPUTS},
        "passed": passed, "scope": SCOPE,
    }
    report_path = MODEL.with_suffix(".holdout_validation.json")
    validation["path"] = str(report_path.resolve())
    report_path.write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    joblib.dump({"model": fitted[selected_name], "model_name": selected_name, "input_columns": INPUTS, "output_columns": OUTPUTS, "selection_method": "independent_comsol_holdout", "training_csv_path": str(TRAINING.resolve()), "holdout_csv_path": str(HOLDOUT.resolve())}, MODEL)
    card = write_general_surrogate_model_card(model_name="菲涅尔方程 TE/TM 反射率代理模型", model_path=MODEL, training_csv=TRAINING, holdout_csv=HOLDOUT, input_columns=INPUTS, output_columns=OUTPUTS, physical_scope=SCOPE, validation=validation, output_dir=MODEL.parent)
    registry = register_general_surrogate(model_name="菲涅尔方程 TE/TM 反射率代理模型", model_path=MODEL, card=card, validation=validation, registry_path=ROOT / "generated/models/surrogate_registry.json")
    print(json.dumps({"validation": validation, "registry": registry}, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
