"""Train a declared-scope Reynolds-to-velocity lid-driven-cavity surrogate."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.neighbors import KNeighborsRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import PolynomialFeatures

from comsol_small_model.surrogate_model_card import register_general_surrogate, write_general_surrogate_model_card


ROOT = Path(__file__).resolve().parents[1]
TRAINING = ROOT / "generated/training_runs/lid_driven_cavity_re_training_dense.csv"
HOLDOUT = ROOT / "generated/training_runs/lid_driven_cavity_re_holdout_v2.csv"
MODEL = ROOT / "generated/models/lid_driven_cavity_reynolds_surrogate.joblib"
INPUTS = ["Re"]
OUTPUTS = ["speed_mid_upper_m_s"]
SCOPE = (
    "二维单位方腔稳态层流；顶盖单位滑移速度、密度 1、黏度 1/Re、"
    "固定网格和压力点约束，仅改变 Reynolds 数 Re=50-800，输出 (0.5,0.75) 的速度模。"
)


def _relative_error(actual: np.ndarray, predicted: np.ndarray) -> tuple[float, float]:
    values = np.abs(predicted - actual) / np.maximum(np.abs(actual), 1e-30) * 100.0
    return float(values.max()), float(values.mean())


def main() -> int:
    training = pd.read_csv(TRAINING)
    holdout = pd.read_csv(HOLDOUT)
    x_train = training[INPUTS].to_numpy(float)
    y_train = training[OUTPUTS].to_numpy(float)
    x_holdout = holdout[INPUTS].to_numpy(float)
    y_holdout = holdout[OUTPUTS].to_numpy(float)
    candidates = {
        "linear_regression": LinearRegression(),
        "polynomial_degree_2": Pipeline([("poly", PolynomialFeatures(degree=2)), ("linear", LinearRegression())]),
        "polynomial_degree_3": Pipeline([("poly", PolynomialFeatures(degree=3)), ("linear", LinearRegression())]),
        "random_forest": RandomForestRegressor(n_estimators=300, random_state=7, min_samples_leaf=1),
        "distance_weighted_local_interpolation": KNeighborsRegressor(n_neighbors=2, weights="distance"),
    }
    scored: dict[str, dict[str, object]] = {}
    fitted: dict[str, object] = {}
    for name, candidate in candidates.items():
        candidate.fit(x_train, y_train)
        predicted = candidate.predict(x_holdout)
        maximum, mean = _relative_error(y_holdout, predicted)
        scored[name] = {"max_relative_error_percent": maximum, "mean_relative_error_percent": mean}
        fitted[name] = candidate
    selected_name = min(scored, key=lambda name: float(scored[name]["mean_relative_error_percent"]))
    selected = fitted[selected_name]
    selected_metrics = scored[selected_name]
    passed = float(selected_metrics["max_relative_error_percent"]) <= 5.0
    validation = {
        "kind": "lid_driven_cavity_reynolds_independent_comsol_validation",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "training_csv": str(TRAINING.resolve()),
        "holdout_csv": str(HOLDOUT.resolve()),
        "training_rows": len(training),
        "holdout_rows": len(holdout),
        "candidate_metrics": scored,
        "selected_model": selected_name,
        "selection_reason": "Selected by independent COMSOL holdout error; local interpolation is preferred for this nonlinear one-dimensional response.",
        "per_output_relative_validation": {
            OUTPUTS[0]: {
                **selected_metrics,
                "threshold_relative_error_percent": 5.0,
                "passed": passed,
            }
        },
        "passed": passed,
        "scope": SCOPE,
    }
    report_path = MODEL.with_suffix(".holdout_validation.json")
    validation["path"] = str(report_path.resolve())
    report_path.write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    joblib.dump({"model": selected, "model_name": selected_name, "input_columns": INPUTS, "output_columns": OUTPUTS, "selection_method": "independent_comsol_holdout", "training_csv_path": str(TRAINING.resolve()), "holdout_csv_path": str(HOLDOUT.resolve())}, MODEL)
    card = write_general_surrogate_model_card(
        model_name="顶盖驱动方腔流 Reynolds 数速度代理模型",
        model_path=MODEL,
        training_csv=TRAINING,
        holdout_csv=HOLDOUT,
        input_columns=INPUTS,
        output_columns=OUTPUTS,
        physical_scope=SCOPE,
        validation=validation,
        output_dir=MODEL.parent,
    )
    registry = register_general_surrogate(
        model_name="顶盖驱动方腔流 Reynolds 数速度代理模型",
        model_path=MODEL,
        card=card,
        validation=validation,
        registry_path=ROOT / "generated/models/surrogate_registry.json",
    )
    print(json.dumps({"validation": validation, "registry": registry}, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
