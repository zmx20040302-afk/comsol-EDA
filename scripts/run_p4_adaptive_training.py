from __future__ import annotations

import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd

from comsol_small_model.eda_adaptive import fit_p4_models, select_adaptive_batch
from comsol_small_model.eda_design import independent_domain_design, load_eda_problem, out_of_domain_design
from comsol_small_model.eda_optimization import BASELINE_JMAX, FEATURES, TARGETS


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "generated" / "p4"
ROUNDS = OUTPUT / "adaptive_rounds"
SEALED = OUTPUT / "sealed_final_design"
SOURCE_TEMPLATE = ROOT / "generated" / "p3" / "initial_design" / "run_busbar_p3_initial_design.m"


def q(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prepare_sealed_design(spec: dict, forbidden: pd.DataFrame) -> dict:
    SEALED.mkdir(parents=True, exist_ok=True)
    domain_path = SEALED / "p4_independent_domain_inputs.csv"
    ood_path = SEALED / "p4_out_of_domain_inputs.csv"
    if not domain_path.exists():
        domain = independent_domain_design(spec, count=60, seed=20261119, forbidden=forbidden)
        domain["case_id"] = [f"p4_holdout_{index + 1:03d}" for index in range(len(domain))]
        domain["sample_role"] = "p4_independent_domain_test"
        domain.to_csv(domain_path, index=False)
    if not ood_path.exists():
        ood = out_of_domain_design(spec, count=20, seed=20261129)
        ood["case_id"] = [f"p4_ood_{index + 1:03d}" for index in range(len(ood))]
        ood["sample_role"] = "p4_out_of_domain_test"
        ood.to_csv(ood_path, index=False)
    manifest = {
        "schema": "comsol-p4-sealed-final-design",
        "schemaVersion": "1.0.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "domain_seed": 20261119,
        "ood_seed": 20261129,
        "domain_rows": 60,
        "ood_rows": 20,
        "files": {
            "domain": {"path": str(domain_path.relative_to(ROOT)), "sha256": sha256(domain_path)},
            "ood": {"path": str(ood_path.relative_to(ROOT)), "sha256": sha256(ood_path)},
        },
        "policy": "Inputs were generated before adaptive sampling. They are excluded from model fitting and candidate selection until the P4 model is frozen.",
    }
    manifest_path = SEALED / "sealed_design_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def build_runner(input_path: Path, result_path: Path, mph_path: Path, round_index: int) -> Path:
    template = SOURCE_TEMPLATE.read_text(encoding="utf-8")
    replacements = {
        q(ROOT / "generated" / "p3" / "designs" / "initial_design_inputs.csv"): q(input_path),
        q(ROOT / "generated" / "p3" / "initial_design" / "busbar_p3_initial_design_results.csv"): q(result_path),
        q(ROOT / "generated" / "p3" / "initial_design" / "busbar_p3_initial_design_final.mph"): q(mph_path),
        q(ROOT / "generated" / "p3" / "initial_design" / "busbar_p3_initial_design.error.txt"): q(result_path.with_suffix(".error.txt")),
        "P3_INITIAL": f"P4_ADAPTIVE_R{round_index}",
    }
    for old, new in replacements.items():
        if old not in template:
            raise RuntimeError(f"runner template marker missing: {old}")
        template = template.replace(old, new)
    runner = input_path.with_name(f"run_p4_adaptive_round_{round_index}.m")
    runner.write_text(template, encoding="utf-8")
    return runner


def run_round(node: dict, input_path: Path, result_path: Path, mph_path: Path, round_index: int) -> float:
    runner = build_runner(input_path, result_path, mph_path, round_index)
    started = time.perf_counter()
    process = subprocess.run(
        [str(Path(node["matlab_executable"])), "-batch", f"run('{q(runner)}')"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=int(node.get("timeout_seconds", 3600)),
    )
    input_path.with_name(f"round_{round_index}_matlab_stdout.log").write_text(
        process.stdout + "\n" + process.stderr, encoding="utf-8"
    )
    if process.returncode:
        raise RuntimeError(f"P4 adaptive round {round_index} returned {process.returncode}")
    return time.perf_counter() - started


def evaluate_results(path: Path, round_index: int) -> pd.DataFrame:
    frame = pd.read_csv(path)
    solved = frame["solver_status"].astype(str).eq("solved")
    if len(frame) != 20 or not solved.all():
        raise RuntimeError(f"P4 adaptive round {round_index} did not solve all 20 cases")
    frame["normalized_voltage_at_160A_mV"] = frame["voltage_drop_mV"] * 160.0 / frame["I_load_A"]
    frame["temperature_constraint_passed"] = frame["Tmax_K"] <= 373.15
    frame["voltage_constraint_passed"] = frame["normalized_voltage_at_160A_mV"] <= 20.0
    frame["current_density_constraint_passed"] = (
        frame["Jmax_A_m2"] <= 1.10 * BASELINE_JMAX * frame["I_load_A"] / 160.0
    )
    frame["geometry_constraint_passed"] = frame["bolt_radius_mm"] <= 0.2 * frame["wbb_mm"] + 1e-12
    frame["constraints_passed"] = frame[
        [
            "temperature_constraint_passed",
            "voltage_constraint_passed",
            "current_density_constraint_passed",
            "geometry_constraint_passed",
        ]
    ].all(axis=1)
    frame["comsol_verified"] = True
    frame["training_source"] = f"p4_adaptive_round_{round_index}"
    evaluated = path.with_name(f"round_{round_index}_evaluated.csv")
    frame.to_csv(evaluated, index=False)
    return frame


def base_training() -> pd.DataFrame:
    initial = pd.read_csv(ROOT / "generated" / "p3" / "initial_design" / "busbar_p3_initial_design_evaluated.csv")
    initial["training_source"] = "p3_initial_design"
    opened = pd.read_csv(ROOT / "generated" / "p3" / "final_evaluation" / "final_evaluation_evaluated.csv")
    opened = opened[opened["sample_role"] == "independent_domain_test"].copy()
    opened["training_source"] = "retired_p3_domain_final_set"
    columns = sorted(set(initial.columns) | set(opened.columns))
    return pd.concat([initial.reindex(columns=columns), opened.reindex(columns=columns)], ignore_index=True)


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    ROUNDS.mkdir(parents=True, exist_ok=True)
    spec = load_eda_problem(ROOT / "configs" / "busbar_eda_design_problem.json")
    node = json.loads((ROOT / "configs" / "execution_node.json").read_text(encoding="utf-8"))
    training = base_training()
    prepare_sealed_design(spec, training)
    training.to_csv(OUTPUT / "p4_training_base_140.csv", index=False)
    round_reports = []
    total_wall = 0.0
    for round_index in range(1, 5):
        bundle = fit_p4_models(training, seed=20261110 + round_index)
        input_path = ROUNDS / f"round_{round_index}_inputs.csv"
        result_path = ROUNDS / f"round_{round_index}_results.csv"
        mph_path = ROUNDS / f"round_{round_index}_final.mph"
        if not input_path.exists():
            selected = select_adaptive_batch(
                spec,
                bundle,
                training,
                count=20,
                seed=20261200 + round_index,
            )
            selected["case_id"] = [f"p4_r{round_index}_{index + 1:03d}" for index in range(len(selected))]
            selected["sample_role"] = f"p4_adaptive_round_{round_index}"
            selected.to_csv(input_path, index=False)
        if not result_path.exists() or len(pd.read_csv(result_path)) < 20:
            wall = run_round(node, input_path, result_path, mph_path, round_index)
        else:
            wall = 0.0
        total_wall += wall
        solved = evaluate_results(result_path, round_index)
        training = pd.concat([training, solved], ignore_index=True, sort=False)
        round_reports.append(
            {
                "round": round_index,
                "training_rows_after_round": len(training),
                "selected_models_before_round": {
                    target: detail["selected"] for target, detail in bundle["comparison"].items()
                },
                "cross_validation_before_round": {
                    target: detail["selected_cross_validation"] for target, detail in bundle["comparison"].items()
                },
                "solved_rows": len(solved),
                "feasible_rows": int(solved["constraints_passed"].sum()),
                "wall_seconds": wall,
                "input_sha256": sha256(input_path),
                "result_sha256": sha256(result_path),
            }
        )
    final_bundle = fit_p4_models(training, seed=20261199)
    model_path = OUTPUT / "p4_adaptive_surrogate.joblib"
    joblib.dump(final_bundle, model_path)
    training_path = OUTPUT / "p4_training_220.csv"
    training.to_csv(training_path, index=False)
    report = {
        "schema": "comsol-p4-adaptive-training",
        "schemaVersion": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_rows": 140,
        "adaptive_rounds": 4,
        "cases_per_round": 20,
        "final_training_rows": len(training),
        "rounds": round_reports,
        "final_model_comparison": final_bundle["comparison"],
        "selected_final_models": {
            target: detail["selected"] for target, detail in final_bundle["comparison"].items()
        },
        "execution_checks": {
            "all_80_adaptive_cases_solved": len(training) == 220,
            "terminal_current_within_1_percent": bool(
                ((training["terminal_current_A"] - training["I_load_A"]).abs() <= 0.01 * training["I_load_A"]).all()
            ),
            "energy_imbalance_below_0_1_percent": bool((training["energy_imbalance_percent"] <= 0.1).all()),
            "sealed_final_design_exists": (SEALED / "sealed_design_manifest.json").exists(),
        },
        "wall_seconds_new_comsol": total_wall,
        "artifacts": {
            "model": str(model_path.relative_to(ROOT)),
            "training_data": str(training_path.relative_to(ROOT)),
            "sealed_design_manifest": str((SEALED / "sealed_design_manifest.json").relative_to(ROOT)),
        },
        "policy": "The opened P3 domain set is diagnostic training evidence. P4 release requires the separately seeded sealed final design.",
    }
    report["execution_passed"] = all(report["execution_checks"].values())
    (OUTPUT / "adaptive_training_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["execution_passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
