from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd

from comsol_small_model.eda_conformal import CONSTRAINT_TARGETS, fit_one_sided_calibration, upper_bounds
from comsol_small_model.eda_design import independent_domain_design, load_eda_problem, out_of_domain_design
from comsol_small_model.eda_optimization import BASELINE_JMAX, FEATURES


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "generated" / "p5"
SEALED = OUTPUT / "sealed_final_design"
TRAINING = ROOT / "generated" / "p4" / "p4_training_220.csv"
P4_MODEL = ROOT / "generated" / "p4" / "p4_adaptive_surrogate.joblib"
P4_DIAGNOSTIC = ROOT / "generated" / "p4" / "final_evaluation" / "p4_final_evaluation_evaluated.csv"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def assess_method(bundle: dict, calibration: dict, frame: pd.DataFrame, method: str) -> dict:
    predicted = upper_bounds(bundle, calibration, frame, method=method)
    current_limit = 1.10 * BASELINE_JMAX * predicted["I_load_A"] / 160.0
    predicted["actual_constraints_passed"] = (
        (predicted["Tmax_K"] <= 373.15)
        & (predicted["normalized_voltage_at_160A_mV"] <= 20.0)
        & (predicted["Jmax_A_m2"] <= current_limit)
    )
    predicted["released_safe"] = (
        (predicted["upper_95_Tmax_K"] <= 373.15)
        & (predicted["upper_95_normalized_voltage_at_160A_mV"] <= 20.0)
        & (predicted["upper_95_Jmax_A_m2"] <= current_limit)
    )
    predicted["false_safe"] = predicted["released_safe"] & (~predicted["actual_constraints_passed"])
    released = int(predicted["released_safe"].sum())
    false_safe = int(predicted["false_safe"].sum())
    upper_coverage = {
        target: float((predicted[target] <= predicted[f"upper_95_{target}"]).mean())
        for target in CONSTRAINT_TARGETS
    }
    return {
        "rows": len(predicted),
        "released_safe": released,
        "false_safe": false_safe,
        "false_safe_rate": false_safe / max(released, 1),
        "safe_release_coverage": released / max(len(predicted), 1),
        "upper_coverage": upper_coverage,
        "passes_diagnostic_safety": bool(
            false_safe / max(released, 1) <= 0.05 and min(upper_coverage.values()) >= 0.90
        ),
    }


def prepare_sealed_design(spec: dict, forbidden: pd.DataFrame, frozen_files: dict[str, Path]) -> dict:
    SEALED.mkdir(parents=True, exist_ok=True)
    domain_path = SEALED / "p5_independent_domain_inputs.csv"
    ood_path = SEALED / "p5_out_of_domain_inputs.csv"
    if domain_path.exists() or ood_path.exists():
        raise RuntimeError("P5 sealed inputs already exist; refusing to overwrite an independent design")
    domain = independent_domain_design(spec, count=60, seed=20270119, forbidden=forbidden)
    domain["case_id"] = [f"p5_holdout_{index + 1:03d}" for index in range(len(domain))]
    domain["sample_role"] = "p5_independent_domain_test"
    domain.to_csv(domain_path, index=False)
    ood = out_of_domain_design(spec, count=20, seed=20270129)
    ood["case_id"] = [f"p5_ood_{index + 1:03d}" for index in range(len(ood))]
    ood["sample_role"] = "p5_out_of_domain_test"
    ood.to_csv(ood_path, index=False)
    manifest = {
        "schema": "comsol-p5-sealed-final-design",
        "schemaVersion": "1.0.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "domain_seed": 20270119,
        "ood_seed": 20270129,
        "domain_rows": 60,
        "ood_rows": 20,
        "files": {
            "domain": {"path": str(domain_path.relative_to(ROOT)), "sha256": sha256(domain_path)},
            "ood": {"path": str(ood_path.relative_to(ROOT)), "sha256": sha256(ood_path)},
        },
        "frozen_before_sealing": {
            name: {"path": str(path.relative_to(ROOT)), "sha256": sha256(path)}
            for name, path in frozen_files.items()
        },
        "policy": "P5 inputs were generated only after calibration selection, model packaging and release thresholds were frozen.",
    }
    manifest_path = SEALED / "sealed_design_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    training = pd.read_csv(TRAINING)
    p4_bundle = joblib.load(P4_MODEL)
    calibration = fit_one_sided_calibration(training, p4_bundle, seed=20270110, coverage=0.95)
    diagnostic = pd.read_csv(P4_DIAGNOSTIC)
    diagnostic = diagnostic[diagnostic["sample_role"].eq("p4_independent_domain_test")].copy()
    methods = {
        method: assess_method(p4_bundle, calibration, diagnostic, method)
        for method in calibration["candidate_methods"]
    }
    eligible = [name for name, detail in methods.items() if detail["passes_diagnostic_safety"]]
    if not eligible:
        raise RuntimeError("No P5 calibration candidate passed the retired diagnostic safety gate")
    selected = max(eligible, key=lambda name: (methods[name]["safe_release_coverage"], name))
    calibration["selected_method"] = selected
    model_path = OUTPUT / "p5_one_sided_surrogate.joblib"
    joblib.dump({"p4_bundle": p4_bundle, "calibration": calibration}, model_path)
    report = {
        "schema": "comsol-p5-calibration-selection",
        "schemaVersion": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "training_rows": len(training),
        "diagnostic_rows": len(diagnostic),
        "diagnostic_policy": "The opened P4 final set is retired and is used only to select the P5 calibration method.",
        "candidate_methods": methods,
        "selected_method": selected,
        "calibration": calibration,
        "predeclared_final_release_thresholds": {
            "ood_auroc_min": 0.95,
            "ood_detection_rate_min": 0.95,
            "domain_false_alarm_rate_max": 0.05,
            "false_safe_rate_max": 0.05,
            "safe_release_coverage_min": 0.10,
            "constraint_upper_coverage_min": 0.90,
            "tmax_rmse_max_K": 15.0,
            "power_relative_rmse_max": 0.15,
            "mass_relative_rmse_max": 0.10,
        },
        "artifacts": {"model": str(model_path.relative_to(ROOT))},
    }
    report_path = OUTPUT / "calibration_selection_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    prior_final = pd.read_csv(P4_DIAGNOSTIC)
    forbidden = pd.concat([training[FEATURES], prior_final[FEATURES]], ignore_index=True).drop_duplicates()
    spec = load_eda_problem(ROOT / "configs" / "busbar_eda_design_problem.json")
    manifest = prepare_sealed_design(
        spec,
        forbidden,
        {"model": model_path, "calibration_report": report_path},
    )
    print(json.dumps({"report": report, "sealed_manifest": manifest}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
