from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import KFold, cross_val_predict

from .eda_design import latin_hypercube_design, validate_eda_problem


FEATURES = ["L_mm", "wbb_mm", "tbb_mm", "bolt_radius_mm", "I_load_A", "htc_W_m2K", "T_amb_K"]
TARGETS = ["Tmax_K", "Jmax_A_m2", "normalized_voltage_at_160A_mV", "joule_power_W", "copper_mass_kg"]
BASELINE_JMAX = 5_141_738.84968363


def fit_p3_models(frame: pd.DataFrame, *, seed: int = 20261010) -> tuple[dict[str, RandomForestRegressor], dict[str, Any]]:
    missing = [name for name in [*FEATURES, *TARGETS] if name not in frame.columns]
    if missing:
        raise ValueError(f"P3 training table missing columns: {', '.join(missing)}")
    if len(frame) < 40:
        raise ValueError("P3 optimization requires at least 40 solved initial-design rows")
    x = frame[FEATURES].astype(float)
    folds = KFold(n_splits=5, shuffle=True, random_state=seed)
    models: dict[str, RandomForestRegressor] = {}
    metrics: dict[str, Any] = {}
    for offset, target in enumerate(TARGETS):
        estimator = RandomForestRegressor(
            n_estimators=320,
            max_features=0.85,
            min_samples_leaf=1,
            random_state=seed + offset,
            n_jobs=-1,
        )
        predictions = cross_val_predict(estimator, x, frame[target].astype(float), cv=folds, n_jobs=-1)
        truth = frame[target].astype(float).to_numpy()
        metrics[target] = {
            "rmse": float(mean_squared_error(truth, predictions) ** 0.5),
            "mae": float(mean_absolute_error(truth, predictions)),
            "r2": float(r2_score(truth, predictions)),
            "maximum_absolute_error": float(np.max(np.abs(truth - predictions))),
        }
        estimator.fit(x, truth)
        models[target] = estimator
    return models, metrics


def tree_stats(model: RandomForestRegressor, x: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    values = x.to_numpy(dtype=float)
    samples = np.vstack([tree.predict(values) for tree in model.estimators_])
    return samples.mean(axis=0), samples.std(axis=0, ddof=1)


def search_nominal_pareto(
    spec: dict[str, Any],
    models: dict[str, RandomForestRegressor],
    *,
    count: int = 20000,
    seed: int = 20261031,
    z_score: float = 1.645,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    validate_eda_problem(spec)
    candidates = latin_hypercube_design(spec, count=count, seed=seed, include_baseline=True)
    candidates["I_load_A"] = float(spec["drive_definition"]["nominal_current_A"])
    candidates["htc_W_m2K"] = next(float(row["nominal"]) for row in spec["operating_variables"] if row["name"] == "htc_W_m2K")
    candidates["T_amb_K"] = next(float(row["nominal"]) for row in spec["operating_variables"] if row["name"] == "T_amb_K")
    x = candidates[FEATURES].astype(float)
    for target, model in models.items():
        mean, std = tree_stats(model, x)
        candidates[f"pred_{target}"] = mean
        candidates[f"std_{target}"] = std
    candidates["temperature_margin_K"] = 373.15 - (
        candidates["pred_Tmax_K"] + z_score * candidates["std_Tmax_K"]
    )
    candidates["voltage_margin_mV"] = 20.0 - (
        candidates["pred_normalized_voltage_at_160A_mV"] + z_score * candidates["std_normalized_voltage_at_160A_mV"]
    )
    candidates["current_density_margin_A_m2"] = 1.10 * BASELINE_JMAX - (
        candidates["pred_Jmax_A_m2"] + z_score * candidates["std_Jmax_A_m2"]
    )
    candidates["conservative_feasible"] = (
        (candidates["temperature_margin_K"] >= 0)
        & (candidates["voltage_margin_mV"] >= 0)
        & (candidates["current_density_margin_A_m2"] >= 0)
        & (candidates["bolt_radius_mm"] <= 0.2 * candidates["wbb_mm"] + 1e-12)
    )
    candidates["mean_feasible"] = (
        (candidates["pred_Tmax_K"] <= 373.15)
        & (candidates["pred_normalized_voltage_at_160A_mV"] <= 20.0)
        & (candidates["pred_Jmax_A_m2"] <= 1.10 * BASELINE_JMAX)
        & (candidates["bolt_radius_mm"] <= 0.2 * candidates["wbb_mm"] + 1e-12)
    )
    feasible = candidates[candidates["conservative_feasible"]].copy()
    if feasible.empty:
        feasible = candidates[candidates["mean_feasible"]].copy()
        feasible["verification_policy"] = "mean_feasible_fallback_requires_fresh_comsol"
    else:
        feasible["verification_policy"] = "conservative_tree_interval"
    pareto = two_objective_pareto(feasible, "pred_copper_mass_kg", "pred_joule_power_W")
    return candidates, pareto


def two_objective_pareto(frame: pd.DataFrame, first: str, second: str) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    ordered = frame.sort_values([first, second], ascending=[True, True]).reset_index(drop=True)
    keep: list[int] = []
    best_second = float("inf")
    for index, value in enumerate(ordered[second].astype(float)):
        if value < best_second:
            keep.append(index)
            best_second = value
    return ordered.iloc[keep].reset_index(drop=True)


def select_verification_candidates(pareto: pd.DataFrame, *, count: int = 5) -> pd.DataFrame:
    if pareto.empty:
        raise ValueError("no conservative feasible Pareto candidates were found")
    ordered = pareto.sort_values("pred_copper_mass_kg").reset_index(drop=True)
    indexes = np.unique(np.round(np.linspace(0, len(ordered) - 1, min(count, len(ordered)))).astype(int))
    selected = ordered.iloc[indexes].copy().reset_index(drop=True)
    selected["case_id"] = [f"pareto_verify_{index + 1:02d}" for index in range(len(selected))]
    selected["sample_role"] = "fresh_pareto_verification"
    return selected


def run_p3_surrogate_search(
    training_csv: str | Path,
    spec: dict[str, Any],
    output_dir: str | Path,
) -> dict[str, Any]:
    frame = pd.read_csv(training_csv)
    models, cross_validation = fit_p3_models(frame)
    candidates, pareto = search_nominal_pareto(spec, models)
    selected = select_verification_candidates(pareto, count=5)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    model_path = destination / "p3_busbar_surrogate_models.joblib"
    joblib.dump({"models": models, "features": FEATURES, "targets": TARGETS}, model_path)
    candidates_path = destination / "nominal_candidate_predictions.csv"
    pareto_path = destination / "predicted_conservative_pareto.csv"
    verification_path = destination / "fresh_pareto_verification_inputs.csv"
    candidates.to_csv(candidates_path, index=False)
    pareto.to_csv(pareto_path, index=False)
    selected.to_csv(verification_path, index=False)
    report = {
        "schema": "comsol-p3-surrogate-optimization",
        "schemaVersion": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "training_rows": len(frame),
        "features": FEATURES,
        "targets": TARGETS,
        "cross_validation": cross_validation,
        "search": {
            "nominal_candidate_count": len(candidates),
            "conservative_feasible_count": int(candidates["conservative_feasible"].sum()),
            "mean_feasible_count": int(candidates["mean_feasible"].sum()),
            "predicted_pareto_count": len(pareto),
            "fresh_verification_candidate_count": len(selected),
            "operating_condition": {"I_load_A": 160.0, "htc_W_m2K": 5.0, "T_amb_K": 293.15},
            "constraint_confidence_rule": "upper prediction = forest mean + 1.645 tree standard deviations",
            "candidate_policy": str(pareto["verification_policy"].iloc[0]) if len(pareto) else "none",
        },
        "artifacts": {
            "models": str(model_path),
            "candidate_predictions": str(candidates_path),
            "predicted_pareto": str(pareto_path),
            "fresh_verification_inputs": str(verification_path),
        },
        "status": "pending_fresh_comsol_verification",
        "release_gate": "Predicted candidates are proposals. Only fresh COMSOL results can enter the verified Pareto set.",
    }
    report_path = destination / "surrogate_optimization_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    report["report_path"] = str(report_path)
    return report

