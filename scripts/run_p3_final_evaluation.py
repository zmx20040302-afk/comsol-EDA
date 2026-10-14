from __future__ import annotations

import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, roc_auc_score

from comsol_small_model.eda_optimization import BASELINE_JMAX, FEATURES, TARGETS, tree_stats


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "generated" / "p3" / "final_evaluation"
HOLDOUT = ROOT / "generated" / "p3" / "designs" / "independent_domain_test_inputs.csv"
OOD = ROOT / "generated" / "p3" / "designs" / "out_of_domain_test_inputs.csv"
MODELS = ROOT / "generated" / "p3" / "optimization" / "p3_busbar_surrogate_models.joblib"


def q(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


def prepare_inputs() -> Path:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    holdout = pd.read_csv(HOLDOUT)
    ood = pd.read_csv(OOD)
    columns = ["case_id", "sample_role", *FEATURES]
    combined = pd.concat([holdout[columns], ood[columns]], ignore_index=True)
    path = OUTPUT / "final_evaluation_inputs.csv"
    combined.to_csv(path, index=False)
    return path


def build_runner(input_path: Path) -> Path:
    template = (ROOT / "generated" / "p3" / "initial_design" / "run_busbar_p3_initial_design.m").read_text(encoding="utf-8")
    replacements = {
        q(ROOT / "generated" / "p3" / "designs" / "initial_design_inputs.csv"): q(input_path),
        q(ROOT / "generated" / "p3" / "initial_design" / "busbar_p3_initial_design_results.csv"): q(OUTPUT / "final_evaluation_results.csv"),
        q(ROOT / "generated" / "p3" / "initial_design" / "busbar_p3_initial_design_final.mph"): q(OUTPUT / "final_evaluation_final.mph"),
        q(ROOT / "generated" / "p3" / "initial_design" / "busbar_p3_initial_design.error.txt"): q(OUTPUT / "final_evaluation.error.txt"),
        "P3_INITIAL": "P3_FINAL_EVAL",
    }
    for old, new in replacements.items():
        if old not in template:
            raise RuntimeError(f"runner template marker missing: {old}")
        template = template.replace(old, new)
    runner = OUTPUT / "run_p3_final_evaluation.m"
    runner.write_text(template, encoding="utf-8")
    return runner


def declared_ranges() -> dict[str, tuple[float, float]]:
    problem = json.loads((ROOT / "configs" / "busbar_eda_design_problem.json").read_text(encoding="utf-8"))
    variables = [*problem["decision_variables"], *problem["operating_variables"]]
    return {item["name"]: (float(item["lower"]), float(item["upper"])) for item in variables}


def normalized_range_distance(frame: pd.DataFrame, ranges: dict[str, tuple[float, float]]) -> np.ndarray:
    distances = np.zeros(len(frame), dtype=float)
    for name in FEATURES:
        low, high = ranges[name]
        span = max(high - low, 1e-12)
        values = frame[name].astype(float).to_numpy()
        distances = np.maximum(distances, np.maximum((low - values) / span, (values - high) / span))
    return np.maximum(distances, 0.0)


def evaluate(elapsed: float) -> dict:
    inputs = pd.read_csv(OUTPUT / "final_evaluation_inputs.csv")
    actual = pd.read_csv(OUTPUT / "final_evaluation_results.csv")
    frame = inputs.merge(actual.drop(columns=[name for name in FEATURES if name in actual.columns]), on="case_id", how="left")
    frame["normalized_voltage_at_160A_mV"] = frame["voltage_drop_mV"] * 160.0 / frame["I_load_A"]
    frame["actual_temperature_passed"] = frame["Tmax_K"] <= 373.15
    frame["actual_voltage_passed"] = frame["normalized_voltage_at_160A_mV"] <= 20.0
    frame["actual_current_density_passed"] = frame["Jmax_A_m2"] <= 1.10 * BASELINE_JMAX * frame["I_load_A"] / 160.0
    frame["actual_constraints_passed"] = frame[["actual_temperature_passed", "actual_voltage_passed", "actual_current_density_passed"]].all(axis=1)
    bundle = joblib.load(MODELS)
    models = bundle["models"]
    x = frame[FEATURES].astype(float)
    for target in TARGETS:
        mean, std = tree_stats(models[target], x)
        frame[f"pred_{target}"] = mean
        frame[f"std_{target}"] = std
        frame[f"inside_95_{target}"] = (frame[target] >= mean - 1.96 * std) & (frame[target] <= mean + 1.96 * std)
    frame["predicted_constraints_mean_passed"] = (
        (frame["pred_Tmax_K"] <= 373.15)
        & (frame["pred_normalized_voltage_at_160A_mV"] <= 20.0)
        & (frame["pred_Jmax_A_m2"] <= 1.10 * BASELINE_JMAX * frame["I_load_A"] / 160.0)
    )
    frame["predicted_constraints_conservative_95_passed"] = (
        (frame["pred_Tmax_K"] + 1.96 * frame["std_Tmax_K"] <= 373.15)
        & (frame["pred_normalized_voltage_at_160A_mV"] + 1.96 * frame["std_normalized_voltage_at_160A_mV"] <= 20.0)
        & (frame["pred_Jmax_A_m2"] + 1.96 * frame["std_Jmax_A_m2"] <= 1.10 * BASELINE_JMAX * frame["I_load_A"] / 160.0)
    )
    frame["ood_score"] = normalized_range_distance(frame, declared_ranges())
    frame["detected_ood"] = frame["ood_score"] > 0
    frame["released_safe_mean_gate"] = frame["predicted_constraints_mean_passed"] & (~frame["detected_ood"])
    frame["false_safe_mean_gate"] = frame["released_safe_mean_gate"] & (~frame["actual_constraints_passed"])
    frame["released_safe"] = frame["predicted_constraints_conservative_95_passed"] & (~frame["detected_ood"])
    frame["false_safe"] = frame["released_safe"] & (~frame["actual_constraints_passed"])
    holdout = frame[frame["sample_role"] == "independent_domain_test"].copy()
    ood = frame[frame["sample_role"] == "out_of_domain_test"].copy()
    metrics = {}
    for target in TARGETS:
        truth = holdout[target].astype(float)
        pred = holdout[f"pred_{target}"].astype(float)
        metrics[target] = {
            "rmse": float(mean_squared_error(truth, pred) ** 0.5),
            "mae": float(mean_absolute_error(truth, pred)),
            "r2": float(r2_score(truth, pred)),
            "maximum_absolute_error": float((truth - pred).abs().max()),
            "picp_95_tree_interval": float(holdout[f"inside_95_{target}"].mean()),
            "mpiw_95_tree_interval": float((3.92 * holdout[f"std_{target}"]).mean()),
        }
    labels = frame["sample_role"].eq("out_of_domain_test").astype(int)
    released_count = int(frame["released_safe"].sum())
    false_safe_count = int(frame["false_safe"].sum())
    mean_released_count = int(frame["released_safe_mean_gate"].sum())
    mean_false_safe_count = int(frame["false_safe_mean_gate"].sum())
    execution_checks = {
        "all_80_final_evaluation_cases_recorded": len(frame) == 80,
        "all_60_domain_cases_solved": bool(len(holdout) == 60 and holdout["solver_status"].eq("solved").all()),
        "all_20_ood_cases_solved": bool(len(ood) == 20 and ood["solver_status"].eq("solved").all()),
        "energy_imbalance_below_0_1_percent": bool((frame["energy_imbalance_percent"] <= 0.1).all()),
        "terminal_current_within_1_percent": bool(((frame["terminal_current_A"] - frame["I_load_A"]).abs() <= 0.01 * frame["I_load_A"]).all()),
    }
    release_checks = {
        "ood_auroc_at_least_0_95": bool(roc_auc_score(labels, frame["ood_score"]) >= 0.95),
        "false_safe_rate_at_most_0_05": bool((false_safe_count / max(released_count, 1)) <= 0.05),
        "tmax_rmse_at_most_15_K": bool(metrics["Tmax_K"]["rmse"] <= 15.0),
        "power_relative_rmse_at_most_15_percent": bool(metrics["joule_power_W"]["rmse"] / max(float(holdout["joule_power_W"].mean()), 1e-12) <= 0.15),
        "mass_relative_rmse_at_most_10_percent": bool(metrics["copper_mass_kg"]["rmse"] / max(float(holdout["copper_mass_kg"].mean()), 1e-12) <= 0.10),
    }
    evaluated_path = OUTPUT / "final_evaluation_evaluated.csv"
    frame.to_csv(evaluated_path, index=False)
    report = {
        "schema": "comsol-p3-final-independent-evaluation",
        "schemaVersion": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "counts": {
            "domain_holdout": len(holdout),
            "out_of_domain": len(ood),
            "released_safe_conservative_95": released_count,
            "false_safe_conservative_95": false_safe_count,
            "released_safe_mean_gate": mean_released_count,
            "false_safe_mean_gate": mean_false_safe_count,
        },
        "execution_checks": execution_checks,
        "execution_passed": all(execution_checks.values()),
        "release_checks": release_checks,
        "surrogate_release_passed": all(release_checks.values()),
        "holdout_metrics": metrics,
        "ood": {
            "auroc": float(roc_auc_score(labels, frame["ood_score"])),
            "detection_rate": float(ood["detected_ood"].mean()),
            "domain_false_alarm_rate": float(holdout["detected_ood"].mean()),
        },
        "false_safe_rate": false_safe_count / max(released_count, 1),
        "mean_gate_diagnostic": {
            "released_safe": mean_released_count,
            "false_safe": mean_false_safe_count,
            "false_safe_rate": mean_false_safe_count / max(mean_released_count, 1),
            "status": "diagnostic_only; runtime release uses the conservative 95 percent upper bound gate",
        },
        "wall_seconds": elapsed,
        "artifacts": {"inputs": str((OUTPUT / "final_evaluation_inputs.csv").relative_to(ROOT)), "evaluated_results": str(evaluated_path.relative_to(ROOT)), "final_mph": str((OUTPUT / "final_evaluation_final.mph").relative_to(ROOT))},
        "policy": "The frozen 80-row model was evaluated once on reserved 60-row domain and 20-row OOD sets. These results must not be used for tuning unless a new final holdout is generated.",
    }
    (OUTPUT / "final_evaluation_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    if "--evaluate-only" in sys.argv:
        print(json.dumps(evaluate(0.0), ensure_ascii=False, indent=2))
        return
    node = json.loads((ROOT / "configs" / "execution_node.json").read_text(encoding="utf-8"))
    input_path = prepare_inputs()
    runner = build_runner(input_path)
    started = time.perf_counter()
    result = subprocess.run([str(Path(node["matlab_executable"])), "-batch", f"run('{q(runner)}')"], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=int(node.get("timeout_seconds", 3600)))
    (OUTPUT / "matlab_stdout.log").write_text(result.stdout + "\n" + result.stderr, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"MATLAB returned {result.returncode}; see {OUTPUT / 'matlab_stdout.log'}")
    report = evaluate(time.perf_counter() - started)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["execution_passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()

