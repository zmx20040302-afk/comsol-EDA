from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import Pipeline
from sklearn.compose import TransformedTargetRegressor
from sklearn.preprocessing import PolynomialFeatures, StandardScaler
from sklearn.dummy import DummyRegressor
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
import warnings

from .surrogate_runtime import load_surrogate_payload


@dataclass(frozen=True)
class TrainReport:
    best_model: str
    train_rmse: float
    test_rmse: float
    test_mae: float
    test_r2: float
    rows: int
    input_columns: list[str]
    output_columns: list[str]
    train_rows: int
    test_rows: int
    candidate_reports: list[dict[str, Any]]
    per_output_metrics: dict[str, dict[str, float]]
    data_quality: dict[str, Any]
    feature_stats: dict[str, dict[str, float]]
    output_stats: dict[str, dict[str, float]]
    sample_predictions: list[dict[str, Any]]
    training_summary: list[str]
    recommendations: list[str]
    warnings: list[str]


OUTPUT_NAME_PATTERN = (
    r"(out|output|result|target|response|goal|objective|"
    r"tmax|tavg|temp|temperature|stress|strain|disp|displacement|"
    r"pressure|velocity|flux|current|voltage|loss|power|force|"
    r"volume|area|error|max|min|avg|mean|drop)"
)


def inspect_training_csv(
    csv_path: str | Path,
    input_columns: list[str] | None = None,
    output_columns: list[str] | None = None,
) -> dict[str, Any]:
    data = pd.read_csv(csv_path)
    numeric_columns = _numeric_columns(data)
    inferred = infer_training_columns(data, input_columns=input_columns, output_columns=output_columns)
    selected_inputs = inferred["input_columns"]
    selected_outputs = inferred["output_columns"]
    ready = bool(selected_inputs and selected_outputs)
    if ready:
        warnings_list = _dataset_warnings(data, selected_inputs, selected_outputs)
    else:
        warnings_list = []
    missing_selected = [
        column
        for column in list(input_columns or []) + list(output_columns or [])
        if column not in data.columns
    ]
    limitations = []
    if missing_selected:
        limitations.append(f"Selected columns not found: {', '.join(missing_selected)}")
    if not selected_inputs:
        limitations.append("No numeric input columns were inferred.")
    if not selected_outputs:
        limitations.append("No output columns were inferred; rename result columns or select them manually.")
    if len(data) < 20:
        limitations.append("Dataset is small; use this as a smoke test and add more COMSOL sweep rows.")
    return {
        "kind": "training_csv_inspection",
        "path": str(csv_path),
        "rows": int(len(data)),
        "columns": list(data.columns),
        "numeric_columns": numeric_columns,
        "inferred_input_columns": selected_inputs,
        "inferred_output_columns": selected_outputs,
        "ignored_columns": [column for column in data.columns if column not in numeric_columns],
        "ready_for_training": ready and not missing_selected,
        "warnings": _dedupe(warnings_list),
        "limitations": _dedupe(limitations),
        "automation_plan": _automation_plan(ready, selected_inputs, selected_outputs),
    }


def infer_training_columns(
    data: pd.DataFrame,
    input_columns: list[str] | None = None,
    output_columns: list[str] | None = None,
) -> dict[str, list[str]]:
    numeric = _numeric_columns(data)
    requested_inputs = [column for column in (input_columns or []) if column in numeric]
    requested_outputs = [column for column in (output_columns or []) if column in numeric]
    if requested_inputs and requested_outputs:
        return {"input_columns": requested_inputs, "output_columns": requested_outputs}

    if requested_outputs:
        outputs = requested_outputs
    else:
        outputs = [column for column in numeric if _looks_like_output_column(column)]
        if not outputs and len(numeric) >= 2:
            outputs = numeric[-2:] if len(numeric) >= 4 else numeric[-1:]

    if requested_inputs:
        inputs = requested_inputs
    else:
        outputs_set = set(outputs)
        inputs = [column for column in numeric if column not in outputs_set]

    return {
        "input_columns": inputs,
        "output_columns": outputs,
    }


def auto_train_surrogate(
    csv_path: str | Path,
    model_path: str | Path,
    input_columns: list[str] | None = None,
    output_columns: list[str] | None = None,
    random_state: int = 42,
) -> tuple[TrainReport, dict[str, Any]]:
    inspection = inspect_training_csv(csv_path, input_columns=input_columns, output_columns=output_columns)
    if not inspection["ready_for_training"]:
        raise ValueError("; ".join(inspection["limitations"]) or "CSV is not ready for training")
    report = train_surrogate(
        csv_path=csv_path,
        model_path=model_path,
        input_columns=inspection["inferred_input_columns"],
        output_columns=inspection["inferred_output_columns"],
        random_state=random_state,
    )
    record_path = Path(model_path).with_suffix(".training_record.json")
    record = {
        "kind": "comsol_surrogate_training_record",
        "model_path": str(model_path),
        "csv_path": str(csv_path),
        "inspection": inspection,
        "report": _report_to_dict(report),
    }
    record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    inspection["training_record_path"] = str(record_path)
    return report, inspection


def train_surrogate_with_comsol_holdout(
    csv_path: str | Path,
    holdout_csv_path: str | Path,
    model_path: str | Path,
    input_columns: list[str],
    output_columns: list[str],
    random_state: int = 42,
) -> dict[str, Any]:
    """Select a surrogate using a fresh COMSOL holdout instead of only a random split."""
    training = pd.read_csv(csv_path)
    holdout = pd.read_csv(holdout_csv_path)
    required = input_columns + output_columns
    missing = [name for name in required if name not in training.columns or name not in holdout.columns]
    if missing:
        raise ValueError(f"training or holdout CSV missing columns: {', '.join(sorted(set(missing)))}")
    overlap = find_input_overlap(training, holdout, input_columns)
    if overlap["count"]:
        raise ValueError(
            f"training and holdout CSV share {overlap['count']} identical input condition(s); "
            "use fresh COMSOL conditions for independent validation"
        )
    x_train = training[input_columns].to_numpy(dtype=float)
    y_train = _target_array(training, output_columns)
    x_holdout = holdout[input_columns].to_numpy(dtype=float)
    y_holdout = _target_array(holdout, output_columns)
    candidates: list[dict[str, Any]] = []
    fitted: dict[str, Any] = {}
    for name, model in _candidate_models(len(training), random_state):
        model.fit(x_train, y_train)
        predicted = model.predict(x_holdout)
        candidates.append({
            "name": name,
            "holdout_rmse": _rmse(y_holdout, predicted),
            "holdout_mae": float(mean_absolute_error(y_holdout, predicted)),
            "per_output": _per_output_metrics(y_holdout, predicted, output_columns),
        })
        fitted[name] = model
    best = min(candidates, key=lambda item: (item["holdout_rmse"], item["name"] == "dummy_mean_baseline"))
    selected = fitted[best["name"]]
    Path(model_path).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({
        "model": selected,
        "model_name": best["name"],
        "input_columns": input_columns,
        "output_columns": output_columns,
        "candidate_reports": candidates,
        "selection_method": "fresh_comsol_holdout",
        "training_csv_path": str(csv_path),
        "holdout_csv_path": str(holdout_csv_path),
    }, model_path)
    return {
        "kind": "comsol_holdout_selected_surrogate",
        "model_path": str(model_path),
        "best_model": best["name"],
        "candidate_reports": candidates,
        "selection_method": "fresh_comsol_holdout",
        "rows": int(len(training)),
        "holdout_rows": int(len(holdout)),
    }


def find_input_overlap(training: pd.DataFrame, holdout: pd.DataFrame, input_columns: list[str]) -> dict[str, Any]:
    """Find repeated input conditions that would invalidate an independent holdout claim."""
    missing = [name for name in input_columns if name not in training.columns or name not in holdout.columns]
    if missing:
        raise ValueError(f"input columns missing while checking overlap: {', '.join(missing)}")

    def keys(data: pd.DataFrame) -> set[tuple[float, ...]]:
        return {
            tuple(round(float(value), 12) for value in row)
            for row in data[input_columns].to_numpy(dtype=float)
        }

    shared = sorted(keys(training).intersection(keys(holdout)))
    return {"count": len(shared), "input_columns": input_columns, "examples": [dict(zip(input_columns, row)) for row in shared[:5]]}


def train_surrogate(
    csv_path: str | Path,
    model_path: str | Path,
    input_columns: list[str],
    output_columns: list[str],
    random_state: int = 42,
) -> TrainReport:
    data = pd.read_csv(csv_path)
    missing = [col for col in input_columns + output_columns if col not in data.columns]
    if missing:
        raise ValueError(f"CSV missing required columns: {', '.join(missing)}")
    report_warnings = _dataset_warnings(data, input_columns, output_columns)

    x = data[input_columns].to_numpy(dtype=float)
    y = _target_array(data, output_columns)
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError("CSV contains NaN or infinite values in selected input/output columns")

    test_size = 0.2 if len(data) >= 20 else 0.33
    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=test_size, random_state=random_state
    )

    candidates = _candidate_models(len(data), random_state)
    candidate_reports = []
    fitted_models = {}
    for name, model in candidates:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always", ConvergenceWarning)
            model.fit(x_train, y_train)
        convergence_warnings = [
            "MLP did not fully converge. Add more data, reduce model size, or increase max_iter."
            for warning in caught
            if issubclass(warning.category, ConvergenceWarning)
        ]
        report_warnings.extend(convergence_warnings)
        train_pred = model.predict(x_train)
        test_pred = model.predict(x_test)
        candidate_reports.append(
            {
                "name": name,
                "train_rmse": _rmse(y_train, train_pred),
                "test_rmse": _rmse(y_test, test_pred),
                "test_mae": float(mean_absolute_error(y_test, test_pred)),
                "test_r2": _safe_r2(y_test, test_pred),
                "warnings": convergence_warnings,
            }
        )
        fitted_models[name] = model

    best = _best_candidate(candidate_reports)
    model = fitted_models[best["name"]]
    train_pred = model.predict(x_train)
    test_pred = model.predict(x_test)
    sample_predictions = _sample_predictions(y_test, test_pred, output_columns)
    payload = {
        "model": model,
        "model_name": best["name"],
        "input_columns": input_columns,
        "output_columns": output_columns,
        "training_csv_path": str(Path(csv_path)),
        "validated_input_ranges": {
            name: {"min": float(data[name].min()), "max": float(data[name].max())}
            for name in input_columns
        },
        "candidate_reports": candidate_reports,
        "data_quality": _data_quality(data, input_columns, output_columns),
    }
    Path(model_path).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(payload, model_path)

    return TrainReport(
        best_model=best["name"],
        train_rmse=_rmse(y_train, train_pred),
        test_rmse=_rmse(y_test, test_pred),
        test_mae=float(mean_absolute_error(y_test, test_pred)),
        test_r2=_safe_r2(y_test, test_pred),
        rows=len(data),
        input_columns=list(input_columns),
        output_columns=list(output_columns),
        train_rows=len(x_train),
        test_rows=len(x_test),
        candidate_reports=candidate_reports,
        per_output_metrics=_per_output_metrics(y_test, test_pred, output_columns),
        data_quality=_data_quality(data, input_columns, output_columns),
        feature_stats=_column_stats(data, input_columns),
        output_stats=_column_stats(data, output_columns),
        sample_predictions=sample_predictions,
        training_summary=_training_summary(best, candidate_reports, len(data), input_columns, output_columns),
        recommendations=_recommendations(len(data), best, report_warnings),
        warnings=_dedupe(report_warnings),
    )


def predict(model_path: str | Path, inputs: list[float]) -> dict[str, float]:
    payload = load_surrogate_payload(model_path)
    input_columns = payload["input_columns"]
    output_columns = payload["output_columns"]
    if len(inputs) != len(input_columns):
        raise ValueError(f"Expected {len(input_columns)} inputs: {', '.join(input_columns)}")

    prediction = payload["model"].predict(np.asarray([inputs], dtype=float))[0]
    values = np.asarray(prediction).reshape(-1)
    return {name: float(value) for name, value in zip(output_columns, values)}


def _target_array(data: pd.DataFrame, output_columns: list[str]) -> np.ndarray:
    values = data[output_columns].to_numpy(dtype=float)
    return values[:, 0] if len(output_columns) == 1 else values


def _output_matrix(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values)
    return values.reshape(-1, 1) if values.ndim == 1 else values

def _rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(mean_squared_error(y_true, y_pred) ** 0.5)


def _candidate_models(rows: int, random_state: int) -> list[tuple[str, Any]]:
    hidden_layers = (24, 24) if rows < 100 else (64, 64)
    return [
        ("dummy_mean_baseline", DummyRegressor(strategy="mean")),
        (
            "ridge_scaled",
            TransformedTargetRegressor(
                regressor=Pipeline([("x_scale", StandardScaler()), ("ridge", Ridge(alpha=1.0))]),
                transformer=StandardScaler(),
            ),
        ),
        (
            "polynomial_ridge_degree2",
            Pipeline(
                steps=[
                    ("poly", PolynomialFeatures(degree=2, include_bias=False)),
                    ("x_scale", StandardScaler()),
                    ("ridge", Ridge(alpha=1.0)),
                ]
            ),
        ),
        (
            "random_forest",
            RandomForestRegressor(
                n_estimators=160,
                min_samples_leaf=2 if rows >= 40 else 1,
                random_state=random_state,
            ),
        ),
        (
            "mlp_scaled",
            TransformedTargetRegressor(
                regressor=Pipeline(
                    steps=[
                        ("x_scale", StandardScaler()),
                        (
                            "mlp",
                            MLPRegressor(
                                hidden_layer_sizes=hidden_layers,
                                activation="relu",
                                alpha=1e-4,
                                early_stopping=rows >= 50,
                                validation_fraction=0.15,
                                learning_rate_init=1e-3,
                                max_iter=2500,
                                random_state=random_state,
                            ),
                        ),
                    ]
                ),
                transformer=StandardScaler(),
            ),
        ),
    ]


def _best_candidate(candidate_reports: list[dict[str, Any]]) -> dict[str, Any]:
    non_baseline = [item for item in candidate_reports if item["name"] != "dummy_mean_baseline"]
    pool = non_baseline or candidate_reports
    return min(pool, key=lambda item: item["test_rmse"])


def _safe_r2(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    if len(y_true) < 2:
        return float("nan")
    try:
        score = r2_score(y_true, y_pred, multioutput="variance_weighted")
    except ValueError:
        return float("nan")
    return float(score)


def _per_output_metrics(y_true: np.ndarray, y_pred: np.ndarray, output_columns: list[str]) -> dict[str, dict[str, float]]:
    # Scikit-learn returns a one-dimensional prediction for a single target.
    # Normalize both arrays so callers can use the same per-output loop.
    y_true = np.asarray(y_true)
    y_pred = np.asarray(y_pred)
    if y_true.ndim == 1:
        y_true = y_true.reshape(-1, 1)
    if y_pred.ndim == 1:
        y_pred = y_pred.reshape(-1, 1)
    metrics = {}
    for index, name in enumerate(output_columns):
        actual = y_true[:, index]
        predicted = y_pred[:, index]
        metrics[name] = {
            "rmse": _rmse(actual, predicted),
            "mae": float(mean_absolute_error(actual, predicted)),
            "r2": _safe_r2(actual.reshape(-1, 1), predicted.reshape(-1, 1)),
        }
    return metrics


def _data_quality(data: pd.DataFrame, input_columns: list[str], output_columns: list[str]) -> dict[str, Any]:
    selected = input_columns + output_columns
    return {
        "rows": int(len(data)),
        "columns": list(data.columns),
        "selected_columns": selected,
        "missing_values": {column: int(data[column].isna().sum()) for column in selected},
        "duplicate_rows": int(data.duplicated(subset=selected).sum()),
        "input_columns": list(input_columns),
        "output_columns": list(output_columns),
    }


def _dataset_warnings(data: pd.DataFrame, input_columns: list[str], output_columns: list[str]) -> list[str]:
    warnings_list = []
    if len(data) < 20:
        warnings_list.append(
            f"Dataset has only {len(data)} rows. This is enough for a smoke test, but not enough for a reliable surrogate model."
        )
    selected = input_columns + output_columns
    duplicate_count = int(data.duplicated(subset=selected).sum())
    if duplicate_count:
        warnings_list.append(f"Dataset has {duplicate_count} duplicate selected rows.")
    for column in selected:
        if data[column].isna().any():
            warnings_list.append(f"Column {column} contains missing values.")
        if pd.to_numeric(data[column], errors="coerce").nunique(dropna=True) <= 1:
            warnings_list.append(f"Column {column} has one or fewer unique numeric values.")
    return warnings_list


def _column_stats(data: pd.DataFrame, columns: list[str]) -> dict[str, dict[str, float]]:
    stats = {}
    for column in columns:
        series = pd.to_numeric(data[column], errors="coerce")
        stats[column] = {
            "min": float(series.min()),
            "max": float(series.max()),
            "mean": float(series.mean()),
            "std": float(series.std(ddof=0)),
        }
    return stats


def _sample_predictions(y_true: np.ndarray, y_pred: np.ndarray, output_columns: list[str], limit: int = 5) -> list[dict[str, Any]]:
    y_true = _output_matrix(y_true)
    y_pred = _output_matrix(y_pred)
    rows = []
    for index in range(min(limit, len(y_true))):
        rows.append(
            {
                "actual": {name: float(value) for name, value in zip(output_columns, y_true[index])},
                "predicted": {name: float(value) for name, value in zip(output_columns, y_pred[index])},
                "absolute_error": {
                    name: float(abs(actual - predicted))
                    for name, actual, predicted in zip(output_columns, y_true[index], y_pred[index])
                },
            }
        )
    return rows


def _training_summary(
    best: dict[str, Any],
    candidate_reports: list[dict[str, Any]],
    rows: int,
    input_columns: list[str],
    output_columns: list[str],
) -> list[str]:
    baseline = next((item for item in candidate_reports if item["name"] == "dummy_mean_baseline"), None)
    summary = [
        f"Compared {len(candidate_reports)} candidate regressors on {rows} COMSOL sweep rows.",
        f"Inputs: {', '.join(input_columns)}; outputs: {', '.join(output_columns)}.",
        f"Selected {best['name']} with test RMSE {best['test_rmse']:.6g}, MAE {best['test_mae']:.6g}, R2 {best['test_r2']:.6g}.",
    ]
    if baseline and baseline["test_rmse"] > 0:
        improvement = 100.0 * (baseline["test_rmse"] - best["test_rmse"]) / baseline["test_rmse"]
        summary.append(f"Best model improved RMSE over mean baseline by {improvement:.1f}%.")
    return summary


def _recommendations(rows: int, best: dict[str, Any], warnings_list: list[str]) -> list[str]:
    recommendations = []
    if rows < 50:
        recommendations.append("Add more COMSOL parameter-sweep rows before relying on the surrogate for design decisions.")
    if best["test_r2"] < 0.8:
        recommendations.append("Inspect output nonlinearity and consider denser sweeps near sensitive parameter ranges.")
    if warnings_list:
        recommendations.append("Resolve data warnings, then retrain and compare the candidate reports again.")
    recommendations.append("Validate the saved surrogate on fresh COMSOL runs that were not included in the CSV.")
    recommendations.append("Keep the CSV, constraints JSON, generated script, and trained joblib together as one training record.")
    return _dedupe(recommendations)


def _numeric_columns(data: pd.DataFrame) -> list[str]:
    columns = []
    for column in data.columns:
        numeric = pd.to_numeric(data[column], errors="coerce")
        if numeric.notna().sum() == len(data) and numeric.nunique(dropna=True) > 1:
            columns.append(str(column))
    return columns


def _looks_like_output_column(name: str) -> bool:
    return bool(re.search(OUTPUT_NAME_PATTERN, str(name), flags=re.IGNORECASE))


def _automation_plan(ready: bool, input_columns: list[str], output_columns: list[str]) -> list[str]:
    if ready:
        return [
            f"Use inferred inputs: {', '.join(input_columns)}.",
            f"Use inferred outputs: {', '.join(output_columns)}.",
            "Train baseline, Ridge, RandomForest, and MLP candidates.",
            "Save the best model plus a .training_record.json file.",
            "Validate the surrogate with fresh COMSOL runs before design use.",
        ]
    return [
        "Read the CSV header and keep only numeric columns with more than one unique value.",
        "Mark COMSOL parameter and condition columns as inputs.",
        "Mark result, max/min/avg, force, stress, temperature, pressure, current, or error columns as outputs.",
        "Regenerate the CSV from COMSOL parameter sweep if no output column exists.",
    ]


def _report_to_dict(report: TrainReport) -> dict[str, Any]:
    return asdict(report)


def _dedupe(items: list[str]) -> list[str]:
    result = []
    seen = set()
    for item in items:
        if item and item not in seen:
            result.append(item)
            seen.add(item)
    return result
