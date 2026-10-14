from __future__ import annotations

import hashlib
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

from comsol_small_model.comsol_server import ensure_comsol_server
from comsol_small_model.eda_adaptive import predict_bundle
from comsol_small_model.eda_conformal import CONSTRAINT_TARGETS, upper_bounds
from comsol_small_model.eda_optimization import BASELINE_JMAX, FEATURES, TARGETS


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "generated" / "p5" / "final_evaluation"
SEALED = ROOT / "generated" / "p5" / "sealed_final_design"
MODEL = ROOT / "generated" / "p5" / "p5_one_sided_surrogate.joblib"
CALIBRATION_REPORT = ROOT / "generated" / "p5" / "calibration_selection_report.json"
SOURCE_TEMPLATE = ROOT / "generated" / "p3" / "initial_design" / "run_busbar_p3_initial_design.m"


def q(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prepare_inputs() -> tuple[Path, dict]:
    manifest = json.loads((SEALED / "sealed_design_manifest.json").read_text(encoding="utf-8"))
    for name, detail in manifest["frozen_before_sealing"].items():
        path = ROOT / detail["path"]
        if sha256(path) != detail["sha256"]:
            raise RuntimeError(f"P5 frozen {name} changed before final evaluation")
    domain_path = ROOT / manifest["files"]["domain"]["path"]
    ood_path = ROOT / manifest["files"]["ood"]["path"]
    if sha256(domain_path) != manifest["files"]["domain"]["sha256"]:
        raise RuntimeError("P5 sealed domain design hash changed before final evaluation")
    if sha256(ood_path) != manifest["files"]["ood"]["sha256"]:
        raise RuntimeError("P5 sealed OOD design hash changed before final evaluation")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    combined = pd.concat([pd.read_csv(domain_path), pd.read_csv(ood_path)], ignore_index=True)
    path = OUTPUT / "p5_final_evaluation_inputs.csv"
    combined.to_csv(path, index=False)
    return path, manifest


def build_runner(input_path: Path) -> Path:
    result_path = OUTPUT / "p5_final_evaluation_results.csv"
    mph_path = OUTPUT / "p5_final_evaluation_final.mph"
    template = SOURCE_TEMPLATE.read_text(encoding="utf-8")
    replacements = {
        q(ROOT / "generated" / "p3" / "designs" / "initial_design_inputs.csv"): q(input_path),
        q(ROOT / "generated" / "p3" / "initial_design" / "busbar_p3_initial_design_results.csv"): q(result_path),
        q(ROOT / "generated" / "p3" / "initial_design" / "busbar_p3_initial_design_final.mph"): q(mph_path),
        q(ROOT / "generated" / "p3" / "initial_design" / "busbar_p3_initial_design.error.txt"): q(
            OUTPUT / "p5_final_evaluation.error.txt"
        ),
        "P3_INITIAL": "P5_FINAL_EVAL",
    }
    for old, new in replacements.items():
        if old not in template:
            raise RuntimeError(f"runner template marker missing: {old}")
        template = template.replace(old, new)
    runner = OUTPUT / "run_p5_final_evaluation.m"
    runner.write_text(template, encoding="utf-8")
    return runner


def declared_ranges() -> dict[str, tuple[float, float]]:
    spec = json.loads((ROOT / "configs" / "busbar_eda_design_problem.json").read_text(encoding="utf-8"))
    variables = [*spec["decision_variables"], *spec["operating_variables"]]
    return {item["name"]: (float(item["lower"]), float(item["upper"])) for item in variables}


def range_distance(frame: pd.DataFrame) -> np.ndarray:
    distance = np.zeros(len(frame), dtype=float)
    for name, (low, high) in declared_ranges().items():
        values = frame[name].to_numpy(dtype=float)
        span = high - low
        distance = np.maximum(distance, np.maximum((low - values) / span, (values - high) / span))
    return np.maximum(distance, 0.0)


def evaluate(elapsed: float, manifest: dict | None = None) -> dict:
    inputs = pd.read_csv(OUTPUT / "p5_final_evaluation_inputs.csv")
    actual = pd.read_csv(OUTPUT / "p5_final_evaluation_results.csv")
    frame = inputs.merge(actual.drop(columns=[name for name in FEATURES if name in actual.columns]), on="case_id")
    frame["normalized_voltage_at_160A_mV"] = frame["voltage_drop_mV"] * 160.0 / frame["I_load_A"]
    package = joblib.load(MODEL)
    p4_bundle = package["p4_bundle"]
    calibration = package["calibration"]
    method = str(calibration["selected_method"])
    frame = predict_bundle(p4_bundle, frame)
    bounded = upper_bounds(p4_bundle, calibration, frame, method=method)
    for target in CONSTRAINT_TARGETS:
        frame[f"upper_margin_{target}"] = bounded[f"upper_margin_{target}"]
        frame[f"upper_95_{target}"] = bounded[f"upper_95_{target}"]
        frame[f"inside_upper_95_{target}"] = frame[target] <= frame[f"upper_95_{target}"]
    current_limit = 1.10 * BASELINE_JMAX * frame["I_load_A"] / 160.0
    frame["actual_constraints_passed"] = (
        (frame["Tmax_K"] <= 373.15)
        & (frame["normalized_voltage_at_160A_mV"] <= 20.0)
        & (frame["Jmax_A_m2"] <= current_limit)
    )
    frame["predicted_constraints_mean_passed"] = (
        (frame["pred_Tmax_K"] <= 373.15)
        & (frame["pred_normalized_voltage_at_160A_mV"] <= 20.0)
        & (frame["pred_Jmax_A_m2"] <= current_limit)
    )
    frame["predicted_constraints_upper_95_passed"] = (
        (frame["upper_95_Tmax_K"] <= 373.15)
        & (frame["upper_95_normalized_voltage_at_160A_mV"] <= 20.0)
        & (frame["upper_95_Jmax_A_m2"] <= current_limit)
    )
    frame["ood_score"] = range_distance(frame)
    frame["detected_ood"] = frame["ood_score"] > 0
    frame["released_safe"] = frame["predicted_constraints_upper_95_passed"] & (~frame["detected_ood"])
    frame["false_safe"] = frame["released_safe"] & (~frame["actual_constraints_passed"])
    frame["released_safe_mean_gate"] = frame["predicted_constraints_mean_passed"] & (~frame["detected_ood"])
    frame["false_safe_mean_gate"] = frame["released_safe_mean_gate"] & (~frame["actual_constraints_passed"])
    domain = frame[frame["sample_role"] == "p5_independent_domain_test"].copy()
    ood = frame[frame["sample_role"] == "p5_out_of_domain_test"].copy()
    metrics = {}
    for target in TARGETS:
        truth = domain[target].to_numpy(dtype=float)
        prediction = domain[f"pred_{target}"].to_numpy(dtype=float)
        metrics[target] = {
            "rmse": float(mean_squared_error(truth, prediction) ** 0.5),
            "mae": float(mean_absolute_error(truth, prediction)),
            "r2": float(r2_score(truth, prediction)),
            "maximum_absolute_error": float(np.max(np.abs(truth - prediction))),
        }
        if target in CONSTRAINT_TARGETS:
            metrics[target]["upper_95_coverage"] = float(domain[f"inside_upper_95_{target}"].mean())
            metrics[target]["mean_upper_margin"] = float(domain[f"upper_margin_{target}"].mean())
    released = int(domain["released_safe"].sum())
    false_safe = int(domain["false_safe"].sum())
    mean_released = int(domain["released_safe_mean_gate"].sum())
    mean_false_safe = int(domain["false_safe_mean_gate"].sum())
    labels = frame["sample_role"].eq("p5_out_of_domain_test").astype(int)
    safe_coverage = released / max(len(domain), 1)
    execution_checks = {
        "sealed_and_frozen_hashes_verified_before_opening": manifest is not None,
        "all_60_domain_cases_solved": bool(len(domain) == 60 and domain["solver_status"].eq("solved").all()),
        "all_20_ood_cases_solved": bool(len(ood) == 20 and ood["solver_status"].eq("solved").all()),
        "terminal_current_within_1_percent": bool(
            ((frame["terminal_current_A"] - frame["I_load_A"]).abs() <= 0.01 * frame["I_load_A"]).all()
        ),
        "energy_imbalance_below_0_1_percent": bool((frame["energy_imbalance_percent"] <= 0.1).all()),
    }
    release_checks = {
        "ood_auroc_at_least_0_95": bool(roc_auc_score(labels, frame["ood_score"]) >= 0.95),
        "ood_detection_rate_at_least_0_95": bool(ood["detected_ood"].mean() >= 0.95),
        "domain_false_alarm_at_most_0_05": bool(domain["detected_ood"].mean() <= 0.05),
        "false_safe_rate_at_most_0_05": bool(false_safe / max(released, 1) <= 0.05),
        "safe_release_coverage_at_least_0_10": bool(safe_coverage >= 0.10),
        "all_constraint_upper_coverages_at_least_0_90": bool(
            all(metrics[target]["upper_95_coverage"] >= 0.90 for target in CONSTRAINT_TARGETS)
        ),
        "tmax_rmse_at_most_15_K": bool(metrics["Tmax_K"]["rmse"] <= 15.0),
        "power_relative_rmse_at_most_15_percent": bool(
            metrics["joule_power_W"]["rmse"] / float(domain["joule_power_W"].mean()) <= 0.15
        ),
        "mass_relative_rmse_at_most_10_percent": bool(
            metrics["copper_mass_kg"]["rmse"] / float(domain["copper_mass_kg"].mean()) <= 0.10
        ),
    }
    evaluated_path = OUTPUT / "p5_final_evaluation_evaluated.csv"
    frame.to_csv(evaluated_path, index=False)
    report = {
        "schema": "comsol-p5-final-independent-evaluation",
        "schemaVersion": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "training_rows": int(p4_bundle["training_rows"]),
        "calibration_method": method,
        "counts": {
            "domain_holdout": len(domain),
            "out_of_domain": len(ood),
            "released_safe_upper_95": released,
            "false_safe_upper_95": false_safe,
            "released_safe_mean_gate": mean_released,
            "false_safe_mean_gate": mean_false_safe,
        },
        "execution_checks": execution_checks,
        "execution_passed": all(execution_checks.values()),
        "release_checks": release_checks,
        "surrogate_release_passed": all(release_checks.values()),
        "holdout_metrics": metrics,
        "ood": {
            "auroc": float(roc_auc_score(labels, frame["ood_score"])),
            "detection_rate": float(ood["detected_ood"].mean()),
            "domain_false_alarm_rate": float(domain["detected_ood"].mean()),
        },
        "safe_release_coverage": safe_coverage,
        "false_safe_rate": false_safe / max(released, 1),
        "mean_gate_diagnostic": {
            "released_safe": mean_released,
            "false_safe": mean_false_safe,
            "false_safe_rate": mean_false_safe / max(mean_released, 1),
        },
        "wall_seconds": elapsed,
        "artifacts": {
            "evaluated_results": str(evaluated_path.relative_to(ROOT)),
            "model": str(MODEL.relative_to(ROOT)),
            "calibration_report": str(CALIBRATION_REPORT.relative_to(ROOT)),
            "final_mph": str((OUTPUT / "p5_final_evaluation_final.mph").relative_to(ROOT)),
        },
        "policy": "The P5 set was opened once after the selected calibration, frozen model hashes and thresholds were recorded. It is now retired from independent use.",
    }
    (OUTPUT / "p5_final_evaluation_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return report


def solved_count_and_remove_failures() -> int:
    result_path = OUTPUT / "p5_final_evaluation_results.csv"
    if not result_path.exists():
        return 0
    frame = pd.read_csv(result_path)
    solved = frame[frame["solver_status"].astype(str).eq("solved")].copy()
    if len(solved) != len(frame):
        solved.to_csv(result_path, index=False)
    return len(solved)


def run_with_server_recovery(node: dict, runner: Path, *, maximum_attempts: int = 10) -> float:
    total_started = time.perf_counter()
    log_path = OUTPUT / "matlab_stdout.log"
    for attempt in range(1, maximum_attempts + 1):
        before = solved_count_and_remove_failures()
        connect_config = dict(node)
        connect_config["start_comsol_server"] = True
        server = ensure_comsol_server(
            connect_config,
            log_path=OUTPUT / f"mphserver_recovery_attempt_{attempt}.log",
            detached=True,
        )
        if not server.get("ready"):
            raise RuntimeError(f"P5 recovery could not start mphserver: {server.get('message', '')}")
        process = subprocess.run(
            [str(Path(node["matlab_executable"])), "-batch", f"run('{q(runner)}')"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=int(node.get("timeout_seconds", 3600)),
        )
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"\n===== P5 FINAL ATTEMPT {attempt} STARTED_FROM {before} =====\n")
            handle.write(process.stdout + "\n" + process.stderr)
        after = solved_count_and_remove_failures()
        if process.returncode == 0 and after == 80:
            return time.perf_counter() - total_started
        if after <= before:
            raise RuntimeError(
                f"P5 final evaluation made no progress on recovery attempt {attempt}; "
                f"MATLAB return code {process.returncode}"
            )
    raise RuntimeError(f"P5 final evaluation did not finish after {maximum_attempts} recovery attempts")


def main() -> None:
    if "--evaluate-only" in sys.argv:
        print(json.dumps(evaluate(0.0, {"verified": True}), ensure_ascii=False, indent=2))
        return
    node = json.loads((ROOT / "configs" / "execution_node.json").read_text(encoding="utf-8"))
    input_path, manifest = prepare_inputs()
    runner = build_runner(input_path)
    elapsed = run_with_server_recovery(node, runner)
    report = evaluate(elapsed, manifest)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["execution_passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
