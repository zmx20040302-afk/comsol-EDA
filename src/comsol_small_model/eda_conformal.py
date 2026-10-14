from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from sklearn.model_selection import KFold

from .eda_adaptive import _estimator, _forward_target, _inverse_target, physics_features
from .eda_optimization import FEATURES


CONSTRAINT_TARGETS = ("Tmax_K", "normalized_voltage_at_160A_mV", "Jmax_A_m2")


def finite_sample_quantile(values: np.ndarray, *, coverage: float = 0.95) -> float:
    clean = np.asarray(values, dtype=float)
    if clean.ndim != 1 or len(clean) == 0 or not np.isfinite(clean).all():
        raise ValueError("conformal scores must be a finite nonempty vector")
    level = min(1.0, math.ceil((len(clean) + 1) * coverage) / len(clean))
    return float(np.quantile(clean, level, method="higher"))


def _tree_mean_std(target: str, estimator: Any, frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    x = physics_features(frame).to_numpy(dtype=float)
    ambient = frame["T_amb_K"].to_numpy(dtype=float)
    predictions = np.vstack(
        [_inverse_target(target, tree.predict(x), ambient) for tree in estimator.estimators_]
    )
    return predictions.mean(axis=0), predictions.std(axis=0, ddof=1)


def fit_one_sided_calibration(
    training: pd.DataFrame,
    p4_bundle: dict[str, Any],
    *,
    seed: int = 20270110,
    coverage: float = 0.95,
) -> dict[str, Any]:
    missing = [name for name in [*FEATURES, *CONSTRAINT_TARGETS] if name not in training.columns]
    if missing:
        raise ValueError(f"P5 calibration table missing columns: {', '.join(missing)}")
    clean = training.dropna(subset=[*FEATURES, *CONSTRAINT_TARGETS]).reset_index(drop=True)
    folds = KFold(n_splits=5, shuffle=True, random_state=seed)
    targets: dict[str, Any] = {}
    for target_index, target in enumerate(CONSTRAINT_TARGETS):
        kind = str(p4_bundle["models"][target].estimator_kind)
        truth = clean[target].to_numpy(dtype=float)
        ambient = clean["T_amb_K"].to_numpy(dtype=float)
        transformed = _forward_target(target, truth, ambient)
        x = physics_features(clean)
        oof_mean = np.empty(len(clean), dtype=float)
        oof_std = np.empty(len(clean), dtype=float)
        for fold_index, (train_index, test_index) in enumerate(folds.split(x)):
            estimator = _estimator(kind, seed + 100 * target_index + fold_index)
            estimator.fit(x.iloc[train_index], transformed[train_index])
            mean, std = _tree_mean_std(target, estimator, clean.iloc[test_index])
            oof_mean[test_index] = mean
            oof_std[test_index] = std
        signed_error = truth - oof_mean
        scale_floor = max(float(np.median(oof_std)) * 0.10, 1e-12)
        local_scale = np.maximum(oof_std, scale_floor)
        targets[target] = {
            "estimator_kind": kind,
            "training_rows": len(clean),
            "coverage": coverage,
            "global_one_sided_q": finite_sample_quantile(signed_error, coverage=coverage),
            "normalized_one_sided_q": finite_sample_quantile(signed_error / local_scale, coverage=coverage),
            "scale_floor": scale_floor,
            "oof_upper_coverage_global": float(
                np.mean(truth <= oof_mean + finite_sample_quantile(signed_error, coverage=coverage))
            ),
            "oof_upper_coverage_normalized": float(
                np.mean(
                    truth
                    <= oof_mean
                    + finite_sample_quantile(signed_error / local_scale, coverage=coverage) * local_scale
                )
            ),
        }
    return {
        "schema": "comsol-p5-one-sided-conformal-calibration",
        "schemaVersion": "1.0.0",
        "coverage": coverage,
        "folds": 5,
        "seed": seed,
        "targets": targets,
        "candidate_methods": ["global_one_sided", "normalized_one_sided"],
        "policy": "Only upper error bounds are calibrated because all three release constraints are upper limits.",
    }


def upper_bounds(
    p4_bundle: dict[str, Any],
    calibration: dict[str, Any],
    frame: pd.DataFrame,
    *,
    method: str,
) -> pd.DataFrame:
    if method not in calibration["candidate_methods"]:
        raise ValueError(f"unknown P5 calibration method: {method}")
    result = frame.copy()
    for target in CONSTRAINT_TARGETS:
        mean, std = p4_bundle["models"][target].tree_stats(frame)
        detail = calibration["targets"][target]
        if method == "global_one_sided":
            margin = np.full(len(frame), float(detail["global_one_sided_q"]), dtype=float)
        else:
            scale = np.maximum(std, float(detail["scale_floor"]))
            margin = float(detail["normalized_one_sided_q"]) * scale
        result[f"pred_{target}"] = mean
        result[f"tree_std_{target}"] = std
        result[f"upper_margin_{target}"] = margin
        result[f"upper_95_{target}"] = mean + margin
    return result
