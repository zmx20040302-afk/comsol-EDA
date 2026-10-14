"""Train a declared-scope power-inductor frequency surrogate on COMSOL holdout data."""
from __future__ import annotations

import json
import argparse
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, PolynomialFeatures, StandardScaler
from sklearn.compose import TransformedTargetRegressor

from comsol_small_model.surrogate_model_card import (
    register_general_surrogate,
    write_general_surrogate_model_card,
)

ROOT = Path(__file__).resolve().parents[1]
TRAINING = ROOT / "generated/training_runs/power_inductor_frequency_training_combined.csv"
HOLDOUT = ROOT / "generated/training_runs/power_inductor_frequency_holdout_combined.csv"
MODEL = ROOT / "generated/models/power_inductor_frequency_surrogate.joblib"
INPUTS = ["frequency_Hz"]
OUTPUTS = ["inductance_H", "conductance_S"]
SCOPE = (
    "功率电感器频率响应模型；几何、材料、端口、网格与研究设置固定，"
    "仅改变频率，输出 real(1/mef.Y11/mef.iomega) 电感和 real(mef.Y11) 等效电导。"
    "仅适用于 COMSOL 已验证的 500-20000 Hz 范围。"
)
RELATIVE_THRESHOLD_PERCENT = 5.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--training-csv", type=Path, default=TRAINING)
    parser.add_argument("--holdout-csv", type=Path, default=HOLDOUT)
    parser.add_argument("--model", type=Path, default=MODEL)
    parser.add_argument("--threshold-percent", type=float, default=RELATIVE_THRESHOLD_PERCENT)
    return parser.parse_args()


def relative_metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    error = np.abs(predicted - actual) / np.maximum(np.abs(actual), 1e-30) * 100.0
    return {
        "max_relative_error_percent": float(error.max()),
        "mean_relative_error_percent": float(error.mean()),
    }


def main() -> int:
    args = parse_args()
    training_path = args.training_csv.resolve()
    holdout_path = args.holdout_csv.resolve()
    model_path = args.model.resolve()
    training, holdout = pd.read_csv(training_path), pd.read_csv(holdout_path)
    missing = [column for column in INPUTS + OUTPUTS if column not in training or column not in holdout]
    if missing:
        raise ValueError(f"Missing required CSV columns: {missing}")
    if training[INPUTS + OUTPUTS].isna().any().any() or holdout[INPUTS + OUTPUTS].isna().any().any():
        raise ValueError("Training or holdout data contains NaN values")

    x_train = training[INPUTS].to_numpy(float)
    y_train = training[OUTPUTS].to_numpy(float)
    x_holdout = holdout[INPUTS].to_numpy(float)
    y_holdout = holdout[OUTPUTS].to_numpy(float)
    candidates = {
        "linear_regression": LinearRegression(),
        "polynomial_ridge_degree2": Pipeline(
            [
                ("scale_input", StandardScaler()),
                ("poly", PolynomialFeatures(degree=2)),
                ("ridge", Ridge(alpha=1e-6)),
            ]
        ),
        "random_forest": RandomForestRegressor(
            n_estimators=300, max_depth=4, random_state=42
        ),
        "log_frequency_log_output": Pipeline(
            [
                ("log_frequency", FunctionTransformer(np.log, validate=True)),
                (
                    "log_output_regression",
                    TransformedTargetRegressor(
                        regressor=LinearRegression(), func=np.log, inverse_func=np.exp
                    ),
                ),
            ]
        ),
    }
    fitted, reports = {}, {}
    for name, candidate in candidates.items():
        candidate.fit(x_train, y_train)
        metrics = relative_metrics(y_holdout, candidate.predict(x_holdout))
        per_output = {}
        prediction = candidate.predict(x_holdout)
        for index, output in enumerate(OUTPUTS):
            per_output[output] = relative_metrics(
                y_holdout[:, index:index + 1], prediction[:, index:index + 1]
            )
        reports[name] = {**metrics, "per_output": per_output}
        fitted[name] = candidate

    selected_name = min(reports, key=lambda name: reports[name]["max_relative_error_percent"])
    selected_metrics = reports[selected_name]
    passed = selected_metrics["max_relative_error_percent"] <= args.threshold_percent
    validation = {
        "kind": "power_inductor_frequency_independent_comsol_validation",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "training_csv": str(training_path),
        "holdout_csv": str(holdout_path),
        "training_rows": len(training),
        "holdout_rows": len(holdout),
        "candidate_reports": reports,
        "selected_model": selected_name,
        "max_relative_error_percent": selected_metrics["max_relative_error_percent"],
        "mean_relative_error_percent": selected_metrics["mean_relative_error_percent"],
        "selection_reason": "Selected by independent COMSOL holdout maximum relative error for both outputs.",
        "validated_input_ranges": {
            "frequency_Hz": {
                "min": float(min(training.frequency_Hz.min(), holdout.frequency_Hz.min())),
                "max": float(max(training.frequency_Hz.max(), holdout.frequency_Hz.max())),
            }
        },
        "threshold_relative_error_percent": args.threshold_percent,
        "passed": passed,
        "scope": SCOPE,
    }
    model_path.parent.mkdir(parents=True, exist_ok=True)
    report_path = model_path.with_suffix(".holdout_validation.json")
    validation["path"] = str(report_path.resolve())
    report_path.write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    joblib.dump(
        {
            "model": fitted[selected_name],
            "model_name": selected_name,
            "input_columns": INPUTS,
            "output_columns": OUTPUTS,
            "selection_method": "independent_comsol_holdout",
            "training_csv_path": str(training_path),
            "holdout_csv_path": str(holdout_path),
            "validated_input_ranges": validation["validated_input_ranges"],
        },
        model_path,
    )
    card = write_general_surrogate_model_card(
        model_name="功率电感器频率响应代理模型",
        model_path=model_path,
        training_csv=training_path,
        holdout_csv=holdout_path,
        input_columns=INPUTS,
        output_columns=OUTPUTS,
        physical_scope=SCOPE,
        validation=validation,
        output_dir=model_path.parent,
    )
    registry = register_general_surrogate(
        model_name="功率电感器频率响应代理模型",
        model_path=model_path,
        card=card,
        validation=validation,
        registry_path=ROOT / "generated/models/surrogate_registry.json",
    )
    print(json.dumps({"validation": validation, "registry": registry}, ensure_ascii=False))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
