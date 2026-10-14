from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold

from .eda_design import latin_hypercube_design
from .eda_optimization import FEATURES, TARGETS


ENGINEERED_FEATURES = [
    "cross_section_mm2",
    "surface_proxy_mm2",
    "resistance_proxy",
    "current_density_proxy",
    "joule_proxy",
    "cooling_proxy",
    "thermal_rise_proxy",
    "bolt_width_ratio",
]


def physics_features(frame: pd.DataFrame) -> pd.DataFrame:
    values = frame[FEATURES].astype(float).copy()
    area = values["wbb_mm"] * values["tbb_mm"]
    surface = 2.0 * (
        values["L_mm"] * values["wbb_mm"]
        + values["L_mm"] * values["tbb_mm"]
        + values["wbb_mm"] * values["tbb_mm"]
    )
    values["cross_section_mm2"] = area
    values["surface_proxy_mm2"] = surface
    values["resistance_proxy"] = values["L_mm"] / area
    values["current_density_proxy"] = values["I_load_A"] / area
    values["joule_proxy"] = values["I_load_A"] ** 2 * values["L_mm"] / area
    values["cooling_proxy"] = values["htc_W_m2K"] * surface
    values["thermal_rise_proxy"] = values["joule_proxy"] / values["cooling_proxy"].clip(lower=1e-12)
    values["bolt_width_ratio"] = values["bolt_radius_mm"] / values["wbb_mm"]
    return values[[*FEATURES, *ENGINEERED_FEATURES]]


def _forward_target(target: str, values: np.ndarray, ambient: np.ndarray) -> np.ndarray:
    if target == "Tmax_K":
        return np.log(np.maximum(values - ambient, 1e-6))
    return np.log(np.maximum(values, 1e-12))


def _inverse_target(target: str, values: np.ndarray, ambient: np.ndarray) -> np.ndarray:
    restored = np.exp(values)
    if target == "Tmax_K":
        restored = restored + ambient
    return restored


def _estimator(kind: str, seed: int):
    common = {"n_estimators": 480, "n_jobs": -1, "random_state": seed}
    if kind == "extra_trees_leaf1":
        return ExtraTreesRegressor(max_features=1.0, min_samples_leaf=1, **common)
    if kind == "extra_trees_leaf2":
        return ExtraTreesRegressor(max_features=1.0, min_samples_leaf=2, **common)
    if kind == "random_forest_leaf1":
        return RandomForestRegressor(max_features=0.9, min_samples_leaf=1, **common)
    if kind == "random_forest_leaf2":
        return RandomForestRegressor(max_features=0.9, min_samples_leaf=2, **common)
    raise ValueError(f"unknown P4 estimator: {kind}")


@dataclass
class P4TargetModel:
    target: str
    estimator_kind: str
    estimator: Any
    conformal_absolute_error_95: float

    def predict(self, frame: pd.DataFrame) -> np.ndarray:
        x = physics_features(frame)
        transformed = self.estimator.predict(x)
        return _inverse_target(self.target, transformed, frame["T_amb_K"].to_numpy(dtype=float))

    def tree_stats(self, frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        x = physics_features(frame).to_numpy(dtype=float)
        ambient = frame["T_amb_K"].to_numpy(dtype=float)
        predictions = np.vstack(
            [_inverse_target(self.target, tree.predict(x), ambient) for tree in self.estimator.estimators_]
        )
        return predictions.mean(axis=0), predictions.std(axis=0, ddof=1)


def _metrics(truth: np.ndarray, prediction: np.ndarray) -> dict[str, float]:
    return {
        "rmse": float(mean_squared_error(truth, prediction) ** 0.5),
        "mae": float(mean_absolute_error(truth, prediction)),
        "r2": float(r2_score(truth, prediction)),
        "maximum_absolute_error": float(np.max(np.abs(truth - prediction))),
    }


def fit_p4_models(
    frame: pd.DataFrame,
    *,
    seed: int = 20261110,
    candidate_kinds: tuple[str, ...] = (
        "extra_trees_leaf1",
        "extra_trees_leaf2",
        "random_forest_leaf1",
        "random_forest_leaf2",
    ),
) -> dict[str, Any]:
    required = [*FEATURES, *TARGETS]
    missing = [name for name in required if name not in frame.columns]
    if missing:
        raise ValueError(f"P4 training table missing columns: {', '.join(missing)}")
    if len(frame) < 80:
        raise ValueError("P4 requires at least 80 solved rows")
    clean = frame.dropna(subset=required).reset_index(drop=True)
    x = physics_features(clean)
    folds = KFold(n_splits=5, shuffle=True, random_state=seed)
    models: dict[str, P4TargetModel] = {}
    comparison: dict[str, Any] = {}
    for target_index, target in enumerate(TARGETS):
        truth = clean[target].to_numpy(dtype=float)
        ambient = clean["T_amb_K"].to_numpy(dtype=float)
        transformed = _forward_target(target, truth, ambient)
        candidates: dict[str, Any] = {}
        best_kind = ""
        best_prediction: np.ndarray | None = None
        best_rmse = float("inf")
        for kind_index, kind in enumerate(candidate_kinds):
            oof = np.empty(len(clean), dtype=float)
            for train_index, test_index in folds.split(x):
                estimator = _estimator(kind, seed + 100 * target_index + kind_index)
                estimator.fit(x.iloc[train_index], transformed[train_index])
                predicted_transformed = estimator.predict(x.iloc[test_index])
                oof[test_index] = _inverse_target(target, predicted_transformed, ambient[test_index])
            candidate_metrics = _metrics(truth, oof)
            candidates[kind] = candidate_metrics
            if candidate_metrics["rmse"] < best_rmse:
                best_rmse = candidate_metrics["rmse"]
                best_kind = kind
                best_prediction = oof.copy()
        assert best_prediction is not None
        final_estimator = _estimator(best_kind, seed + 1000 + target_index)
        final_estimator.fit(x, transformed)
        q95 = float(np.quantile(np.abs(truth - best_prediction), 0.95, method="higher"))
        models[target] = P4TargetModel(target, best_kind, final_estimator, q95)
        comparison[target] = {
            "selected": best_kind,
            "selected_cross_validation": _metrics(truth, best_prediction),
            "conformal_absolute_error_95": q95,
            "candidates": candidates,
        }
    return {
        "schema": "comsol-p4-physics-feature-surrogate",
        "schemaVersion": "1.0.0",
        "training_rows": len(clean),
        "features": [*FEATURES, *ENGINEERED_FEATURES],
        "targets": TARGETS,
        "models": models,
        "comparison": comparison,
        "interval_policy": "symmetric split-free 95 percent bound from five-fold out-of-fold absolute residuals",
    }


def predict_bundle(bundle: dict[str, Any], frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for target, model in bundle["models"].items():
        mean, tree_std = model.tree_stats(frame)
        result[f"pred_{target}"] = mean
        result[f"tree_std_{target}"] = tree_std
        result[f"interval_half_width_{target}"] = float(model.conformal_absolute_error_95)
    return result


def select_adaptive_batch(
    spec: dict[str, Any],
    bundle: dict[str, Any],
    existing: pd.DataFrame,
    *,
    count: int,
    seed: int,
    pool_size: int = 12000,
) -> pd.DataFrame:
    pool = latin_hypercube_design(spec, count=pool_size, seed=seed, include_baseline=False)
    keys = {
        tuple(round(float(row[name]), 9) for name in FEATURES)
        for row in existing[FEATURES].to_dict("records")
    }
    mask = [tuple(round(float(row[name]), 9) for name in FEATURES) not in keys for row in pool.to_dict("records")]
    pool = pool.loc[mask].reset_index(drop=True)
    predicted = predict_bundle(bundle, pool)
    score = np.zeros(len(predicted), dtype=float)
    for target, scale in (
        ("Tmax_K", 50.0),
        ("Jmax_A_m2", 2.0e6),
        ("normalized_voltage_at_160A_mV", 8.0),
        ("joule_power_W", 3.0),
    ):
        score += predicted[f"tree_std_{target}"].to_numpy(dtype=float) / scale
    score += np.exp(-np.abs(predicted["pred_Tmax_K"].to_numpy(dtype=float) - 373.15) / 25.0)
    score += np.exp(-np.abs(predicted["pred_normalized_voltage_at_160A_mV"].to_numpy(dtype=float) - 20.0) / 4.0)
    predicted["acquisition_score"] = score

    ranges = {
        item["name"]: (float(item["lower"]), float(item["upper"]))
        for item in [*spec["decision_variables"], *spec["operating_variables"]]
    }
    normalized = np.column_stack(
        [
            (predicted[name].to_numpy(dtype=float) - ranges[name][0]) / (ranges[name][1] - ranges[name][0])
            for name in FEATURES
        ]
    )
    base_score = predicted["acquisition_score"].to_numpy(dtype=float)
    base_score = (base_score - base_score.min()) / max(float(base_score.max() - base_score.min()), 1e-12)
    selected: list[int] = [int(np.argmax(base_score))]
    minimum_distance = np.linalg.norm(normalized - normalized[selected[0]], axis=1)
    while len(selected) < count:
        combined = 0.65 * base_score + 0.35 * np.minimum(minimum_distance / np.sqrt(len(FEATURES)), 1.0)
        combined[selected] = -1.0
        next_index = int(np.argmax(combined))
        selected.append(next_index)
        minimum_distance = np.minimum(
            minimum_distance,
            np.linalg.norm(normalized - normalized[next_index], axis=1),
        )
    batch = predicted.iloc[selected].copy().reset_index(drop=True)
    return batch


def diagnostic_metrics(bundle: dict[str, Any], frame: pd.DataFrame) -> dict[str, Any]:
    predicted = predict_bundle(bundle, frame)
    return {
        target: _metrics(frame[target].to_numpy(dtype=float), predicted[f"pred_{target}"].to_numpy(dtype=float))
        for target in TARGETS
    }
