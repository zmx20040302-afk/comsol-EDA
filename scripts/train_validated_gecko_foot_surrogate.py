"""Train and independently validate a declared-scope gecko-foot surrogate.

Model selection is performed only with shuffled K-fold cross-validation on the
training CSV.  The COMSOL holdout CSV is kept untouched until final scoring.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import RepeatedKFold
from sklearn.neighbors import KNeighborsRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import PolynomialFeatures, StandardScaler

from comsol_small_model.surrogate import find_input_overlap
from comsol_small_model.surrogate_model_card import (
    register_general_surrogate,
    write_general_surrogate_model_card,
)


ROOT = Path(__file__).resolve().parents[1]
INPUTS = ["Fc_uN", "Ff_uN", "theta_deg"]
OUTPUTS = ["max_v_Mises_Pa", "max_disp_m", "max_ep1"]
DEFAULT_BASE_TRAINING = ROOT / "generated" / "training_runs" / "gecko_foot_load_training.csv"
DEFAULT_ANGLE_TRAINING = ROOT / "generated" / "training_runs" / "gecko_foot_angle_training.csv"
DEFAULT_HOLDOUT = ROOT / "generated" / "training_runs" / "gecko_foot_load_holdout.csv"
DEFAULT_COMBINED = ROOT / "generated" / "training_runs" / "gecko_foot_combined_training.csv"
DEFAULT_MODEL = ROOT / "generated" / "models" / "gecko_foot_surrogate.joblib"
HOLDOUT_THRESHOLD_PERCENT = 5.0
RANDOM_STATE = 42
SCOPE = (
    "壁虎足三维固体力学静态模型；几何、材料、网格、约束和边界载荷定义固定，"
    "仅在 Fc_uN、Ff_uN、theta_deg 的已采样范围内预测 max_v_Mises_Pa、"
    "max_disp_m 和 max_ep1。该代理模型用于快速筛选，最终设计仍须回到 COMSOL。"
)


def _candidate_factories(rows: int) -> dict[str, Callable[[], Any]]:
    leaf = 2 if rows >= 40 else 1
    factories: dict[str, Callable[[], Any]] = {
        "linear_regression": lambda: Pipeline(
            [("x_scale", StandardScaler()), ("linear", LinearRegression())]
        ),
        "polynomial_ridge_degree2": lambda: Pipeline(
            [
                ("poly", PolynomialFeatures(degree=2, include_bias=False)),
                ("x_scale", StandardScaler()),
                ("ridge", Ridge(alpha=1.0)),
            ]
        ),
        "random_forest": lambda: RandomForestRegressor(
            n_estimators=240,
            min_samples_leaf=leaf,
            random_state=RANDOM_STATE,
        ),
        "extra_trees": lambda: ExtraTreesRegressor(
            n_estimators=240,
            min_samples_leaf=leaf,
            random_state=RANDOM_STATE,
        ),
    }
    for neighbors in (2, 3, 4, 5, 8):
        factories[f"knn_scaled_distance_weighted_{neighbors}"] = lambda n=neighbors: Pipeline(
            [
                ("x_scale", StandardScaler()),
                ("knn", KNeighborsRegressor(n_neighbors=n, weights="distance")),
            ]
        )
    return factories


def _finite_frame(data: pd.DataFrame, columns: list[str], label: str) -> None:
    missing = [column for column in columns if column not in data.columns]
    if missing:
        raise ValueError(f"{label} CSV missing columns: {', '.join(missing)}")
    values = data[columns].apply(pd.to_numeric, errors="coerce").to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError(f"{label} CSV contains missing, NaN, or infinite selected values")


def _read_and_combine(source_paths: list[Path], combined_path: Path) -> tuple[pd.DataFrame, int]:
    frames: list[pd.DataFrame] = []
    for source_path in source_paths:
        frame = pd.read_csv(source_path)
        _finite_frame(frame, INPUTS + OUTPUTS, f"training source {source_path.name}")
        frames.append(frame[INPUTS + OUTPUTS])
    data = pd.concat(frames, ignore_index=True)
    duplicate_inputs = data.duplicated(subset=INPUTS, keep=False)
    deduplicated_rows = 0
    if duplicate_inputs.any():
        duplicate_groups = data.loc[duplicate_inputs].groupby(INPUTS, dropna=False)
        conflicting_groups = []
        for input_values, group in duplicate_groups:
            output_values = group[OUTPUTS].to_numpy(dtype=float)
            if not np.allclose(output_values, output_values[0], rtol=1e-9, atol=1e-15):
                conflicting_groups.append(dict(zip(INPUTS, input_values if isinstance(input_values, tuple) else (input_values,))))
        if conflicting_groups:
            raise ValueError(
                "combined training data repeats input conditions with conflicting outputs: "
                f"{conflicting_groups[:5]}"
            )
        original_rows = len(data)
        data = data.drop_duplicates(subset=INPUTS, keep="first").reset_index(drop=True)
        deduplicated_rows = original_rows - len(data)
    combined_path.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(combined_path, index=False)
    return data, deduplicated_rows


def _relative_errors(actual: np.ndarray, predicted: np.ndarray) -> np.ndarray:
    floor = max(float(np.max(np.abs(actual))) * 1e-12, 1e-30)
    return np.abs(predicted - actual) / np.maximum(np.abs(actual), floor) * 100.0


def _metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    relative = _relative_errors(actual, predicted)
    scale = max(float(np.ptp(actual)), float(np.mean(np.abs(actual))), 1e-30)
    return {
        "rmse": float(mean_squared_error(actual, predicted) ** 0.5),
        "mae": float(mean_absolute_error(actual, predicted)),
        "r2": float(r2_score(actual, predicted)) if len(actual) > 1 else float("nan"),
        "normalized_rmse_percent": float(mean_squared_error(actual, predicted) ** 0.5 / scale * 100.0),
        "mean_relative_error_percent": float(relative.mean()),
        "max_relative_error_percent": float(relative.max()),
    }


def _cross_validate(data: pd.DataFrame, output: str, factories: dict[str, Callable[[], Any]]) -> tuple[str, dict[str, Any]]:
    x = data[INPUTS].to_numpy(dtype=float)
    y = data[output].to_numpy(dtype=float)
    folds = RepeatedKFold(n_splits=5, n_repeats=5, random_state=RANDOM_STATE)
    reports: dict[str, Any] = {}
    for name, factory in factories.items():
        actual_parts: list[np.ndarray] = []
        predicted_parts: list[np.ndarray] = []
        fold_metrics: list[dict[str, Any]] = []
        for train_indices, test_indices in folds.split(x):
            model = factory()
            model.fit(x[train_indices], y[train_indices])
            predicted = np.asarray(model.predict(x[test_indices]), dtype=float)
            actual = y[test_indices]
            actual_parts.append(actual)
            predicted_parts.append(predicted)
            fold_metrics.append({"rows": int(len(test_indices)), **_metrics(actual, predicted)})
        all_actual = np.concatenate(actual_parts)
        all_predicted = np.concatenate(predicted_parts)
        reports[name] = {
            "folds": fold_metrics,
            "aggregate": _metrics(all_actual, all_predicted),
        }
    selected = min(
        reports,
        key=lambda name: (
            reports[name]["aggregate"]["normalized_rmse_percent"],
            reports[name]["aggregate"]["mean_relative_error_percent"],
            name,
        ),
    )
    return selected, reports


def _validate_holdout(
    data: pd.DataFrame,
    holdout: pd.DataFrame,
    selected_models: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, dict[str, float]]]:
    x_train = data[INPUTS].to_numpy(dtype=float)
    x_holdout = holdout[INPUTS].to_numpy(dtype=float)
    predictions: dict[str, list[float]] = {}
    per_output: dict[str, dict[str, float]] = {}
    for output, model in selected_models.items():
        model.fit(x_train, data[output].to_numpy(dtype=float))
        predicted = np.asarray(model.predict(x_holdout), dtype=float)
        predictions[output] = [float(value) for value in predicted]
        per_output[output] = _metrics(holdout[output].to_numpy(dtype=float), predicted)
    return {"predictions": predictions}, per_output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-training-csv", type=Path, default=DEFAULT_BASE_TRAINING)
    parser.add_argument("--angle-training-csv", type=Path, default=DEFAULT_ANGLE_TRAINING)
    parser.add_argument(
        "--additional-training-csv",
        type=Path,
        action="append",
        default=[],
        help="Additional COMSOL CSV; may be supplied more than once.",
    )
    parser.add_argument("--holdout-csv", type=Path, default=DEFAULT_HOLDOUT)
    parser.add_argument("--combined-training-csv", type=Path, default=DEFAULT_COMBINED)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    args = parser.parse_args()

    base_path = args.base_training_csv.resolve()
    angle_path = args.angle_training_csv.resolve()
    holdout_path = args.holdout_csv.resolve()
    combined_path = args.combined_training_csv.resolve()
    model_path = args.model.resolve()
    additional_paths = [path.resolve() for path in args.additional_training_csv]
    source_paths = [base_path, angle_path, *additional_paths]
    data, deduplicated_rows = _read_and_combine(source_paths, combined_path)
    holdout = pd.read_csv(holdout_path)
    _finite_frame(holdout, INPUTS + OUTPUTS, "COMSOL holdout")
    overlap = find_input_overlap(data, holdout, INPUTS)
    if overlap["count"]:
        raise ValueError(
            f"training and holdout CSV share {overlap['count']} input condition(s): {overlap['examples']}"
        )

    factories = _candidate_factories(len(data))
    selected_models: dict[str, Any] = {}
    selection_reports: dict[str, Any] = {}
    selected_names: dict[str, str] = {}
    for output in OUTPUTS:
        selected, reports = _cross_validate(data, output, factories)
        selected_names[output] = selected
        selection_reports[output] = {
            "selected_model": selected,
            "candidates": reports,
            "selection_method": "5_fold_repeated_5_times_cross_validation_on_training_csv_only",
        }
        selected_models[output] = factories[selected]()

    holdout_predictions, per_output = _validate_holdout(data, holdout, selected_models)
    passed_outputs = {
        output: metrics["max_relative_error_percent"] <= HOLDOUT_THRESHOLD_PERCENT
        for output, metrics in per_output.items()
    }
    validation_passed = all(passed_outputs.values())
    validation = {
        "kind": "gecko_foot_independent_comsol_holdout_validation",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "training_csv": str(combined_path),
        "source_training_csvs": [str(path) for path in source_paths],
        "holdout_csv": str(holdout_path),
        "training_rows": int(len(data)),
        "holdout_rows": int(len(holdout)),
        "input_columns": INPUTS,
        "output_columns": OUTPUTS,
        "candidate_reports": selection_reports,
        "selected_models": selected_names,
        "holdout_predictions": holdout_predictions["predictions"],
        "per_output_relative_validation": {
            output: {**metrics, "threshold_relative_error_percent": HOLDOUT_THRESHOLD_PERCENT, "passed": passed_outputs[output]}
            for output, metrics in per_output.items()
        },
        "max_relative_error_percent": {
            output: metrics["max_relative_error_percent"] for output, metrics in per_output.items()
        },
        "threshold_relative_error_percent": HOLDOUT_THRESHOLD_PERCENT,
        "passed": validation_passed,
        "status": "validated_for_declared_scope" if validation_passed else "needs_more_comsol_evidence",
        "scope": SCOPE,
        "data_quality": {
            "finite_selected_values": True,
            "training_input_duplicates": 0,
            "deduplicated_identical_training_rows": deduplicated_rows,
            "holdout_training_input_overlap": overlap,
        },
    }
    model_path.parent.mkdir(parents=True, exist_ok=True)
    validated_input_ranges = {
        name: {"min": float(data[name].min()), "max": float(data[name].max())}
        for name in INPUTS
    }
    payload = {
        "model_name": "gecko_foot_per_output_surrogates",
        "models": selected_models,
        "selected_models": selected_names,
        "input_columns": INPUTS,
        "output_columns": OUTPUTS,
        "selection_method": "5_fold_repeated_5_times_cross_validation_on_training_csv_only",
        "training_csv_path": str(combined_path),
        "holdout_csv_path": str(holdout_path),
        "validated_input_ranges": validated_input_ranges,
        "validation_status": validation["status"],
        "scope": SCOPE,
    }
    joblib.dump(payload, model_path)

    report_path = model_path.with_suffix(".holdout_validation.json")
    validation["path"] = str(report_path)
    report_path.write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    card = write_general_surrogate_model_card(
        model_name="壁虎足载荷与角度响应代理模型",
        model_path=model_path,
        training_csv=combined_path,
        holdout_csv=holdout_path,
        input_columns=INPUTS,
        output_columns=OUTPUTS,
        physical_scope=SCOPE,
        validation=validation,
        output_dir=model_path.parent,
    )
    registry = register_general_surrogate(
        model_name="壁虎足载荷与角度响应代理模型",
        model_path=model_path,
        card=card,
        validation=validation,
        registry_path=ROOT / "generated" / "models" / "surrogate_registry.json",
    )
    result = {
        "training_rows": len(data),
        "holdout_rows": len(holdout),
        "selected_models": selected_names,
        "per_output_relative_validation": validation["per_output_relative_validation"],
        "passed": validation_passed,
        "status": validation["status"],
        "combined_training_csv": str(combined_path),
        "model": str(model_path),
        "validation_report": str(report_path),
        "model_card": card,
        "registry": registry["path"],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if validation_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
