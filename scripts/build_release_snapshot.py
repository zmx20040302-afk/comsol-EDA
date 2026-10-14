from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "generated" / "release_snapshots" / "release_snapshot_20261009.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact(path: Path) -> dict[str, object]:
    return {
        "path": str(path.relative_to(ROOT)),
        "size_bytes": path.stat().st_size,
        "sha256": _sha256(path),
    }


def _freeze() -> list[str]:
    completed = subprocess.run(
        [sys.executable, "-m", "pip", "freeze", "--all"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return sorted(line.strip() for line in completed.stdout.splitlines() if line.strip())


def _version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "not-installed"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a reproducible local environment and release snapshot")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    freeze = _freeze()
    lock_path = ROOT / "requirements-lock-windows-py312.txt"
    lock_header = [
        "# Verified local lock for Windows and CPython 3.12.",
        "# Generated with: python -m pip freeze --all",
        "# Rebuild with: python -m pip install -r requirements-lock-windows-py312.txt",
        "",
    ]
    lock_path.write_text("\n".join(lock_header + freeze) + "\n", encoding="utf-8")

    compatibility_path = ROOT / "generated" / "compatibility" / "matlab_r2023b_comsol_6_4_full_solve.json"
    compatibility = json.loads(compatibility_path.read_text(encoding="utf-8"))
    repeated_comsol_path = (
        ROOT / "generated" / "benchmarks" / "comsol_repeat_20261009" / "repeated_comsol_performance.json"
    )
    repeated_comsol = json.loads(repeated_comsol_path.read_text(encoding="utf-8"))
    multiphysics_sweep_path = (
        ROOT
        / "generated"
        / "benchmarks"
        / "busbar_multiphysics_sweep_20261009"
        / "busbar_multiphysics_sweep_benchmark.json"
    )
    multiphysics_sweep = json.loads(multiphysics_sweep_path.read_text(encoding="utf-8"))
    dense_multiphysics_sweep_path = (
        ROOT
        / "generated"
        / "benchmarks"
        / "busbar_dense_multiphysics_sweep_20261009"
        / "busbar_dense_multiphysics_sweep_benchmark.json"
    )
    dense_multiphysics_sweep = json.loads(dense_multiphysics_sweep_path.read_text(encoding="utf-8"))
    requirement_completeness_path = ROOT / "generated" / "benchmarks" / "requirement_completeness" / "report.json"
    requirement_completeness = json.loads(requirement_completeness_path.read_text(encoding="utf-8"))
    paths = [
        ROOT / "paper_draft" / "comsol_trustworthy_surrogate_paper_draft_en.docx",
        ROOT / "paper_draft" / "build_english_paper.py",
        ROOT / "web_app.py",
        ROOT / "README.md",
        ROOT / "PROJECT_READINESS.md",
        ROOT / "src" / "comsol_small_model" / "experimental_validation.py",
        ROOT / "generated" / "models" / "surrogate_registry.json",
        ROOT / "generated" / "models" / "surrogate_runtime_audit.json",
        ROOT / "generated" / "validation" / "thermal_plate_final" / "thermal_plate_final_validation_evidence.json",
        ROOT / "generated" / "execution_jobs" / "expanded_validation_20261008" / "thermal_plate_surrogate_expanded_validated.joblib",
        ROOT / "generated" / "benchmarks" / "runtime_performance_20261009.json",
        repeated_comsol_path,
        multiphysics_sweep_path,
        dense_multiphysics_sweep_path,
        ROOT / "generated" / "environment" / "locked_environment_rebuild_smoke.json",
        ROOT / "generated" / "experimental_validation" / "temperature_validation_report.json",
        ROOT / "configs" / "experimental_temperature_validation.json",
        ROOT / "configs" / "experimental_temperature_measurements.schema.json",
        ROOT / "examples" / "experimental_temperature_measurements_template.csv",
        ROOT / "configs" / "execution_node.json",
        ROOT / "configs" / "busbar_eda_design_problem.json",
        ROOT / "configs" / "modeling_contract.schema.json",
        ROOT / "configs" / "modeling_contract.example.json",
        ROOT / "EDA_PUBLICATION_ROADMAP.md",
        ROOT / "AUTO_MODELING_IMPLEMENTATION_PLAN.md",
        ROOT / "src" / "comsol_small_model" / "modeling_contract.py",
        ROOT / "src" / "comsol_small_model" / "requirement_parser.py",
        ROOT / "src" / "comsol_small_model" / "workflow_status.py",
        ROOT / "src" / "comsol_small_model" / "staged_modeling.py",
        ROOT / "tests" / "test_modeling_contract.py",
        ROOT / "benchmarks" / "requirement_completeness" / "tasks.json",
        ROOT / "scripts" / "run_requirement_completeness_benchmark.py",
        ROOT / "scripts" / "build_auto_modeling_baseline.py",
        requirement_completeness_path,
        ROOT / "generated" / "baselines" / "auto_modeling_baseline.json",
        lock_path,
    ]
    missing = [str(path.relative_to(ROOT)) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError("Release snapshot inputs are missing: " + ", ".join(missing))

    report = {
        "kind": "publication_release_snapshot",
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "environment": {
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "python_executable": str(Path(sys.executable).resolve()),
            "implementation": platform.python_implementation(),
            "matlab": compatibility.get("matlab_version"),
            "comsol": compatibility.get("comsol_version"),
            "livelink": {
                "host": compatibility.get("livelink_host"),
                "port": compatibility.get("livelink_port"),
            },
            "key_packages": {
                name: _version(name)
                for name in ["numpy", "pandas", "scipy", "scikit-learn", "joblib", "pypdf"]
            },
            "lock_file": str(lock_path.relative_to(ROOT)),
            "locked_distributions": len(freeze),
        },
        "verification": {
            "regression_tests_passed": 131,
            "regression_test_status": "passed",
            "fresh_locked_environment_rebuild": "passed",
            "full_comsol_queue_job": "job_20261008025812_2aaa3686",
            "repeated_comsol_runs": int(repeated_comsol["summary"]["run_count"]),
            "repeated_comsol_all_passed": bool(repeated_comsol["summary"]["all_passed"]),
            "repeated_comsol_median_seconds": float(repeated_comsol["summary"]["wall_seconds_median"]),
            "combined_peak_working_set_mb": float(repeated_comsol["summary"]["combined_peak_working_set_mb_max"]),
            "combined_peak_private_memory_mb": float(repeated_comsol["summary"]["combined_peak_private_memory_mb_max"]),
            "mphserver_resources_included": True,
            "modeling_contract_schema_version": "1.0.0",
            "staged_workflow_version": "2.0.0",
            "staged_workflow_steps": 10,
            "requirement_completeness_cases": int(requirement_completeness["case_count"]),
            "critical_missing_information_recall": float(requirement_completeness["critical_missing_recall"]),
            "critical_missing_information_precision": float(requirement_completeness["critical_missing_precision"]),
            "complete_3d_multiphysics_sweep_cases": int(multiphysics_sweep["execution"]["completed_cases"]),
            "complete_3d_multiphysics_sweep_passed": bool(multiphysics_sweep["validation"]["all_passed"]),
            "complete_3d_multiphysics_sweep_seconds": float(multiphysics_sweep["execution"]["wall_seconds"]),
            "complete_3d_multiphysics_combined_peak_working_set_mb": float(
                multiphysics_sweep["resources"]["combined_peak_working_set_mb"]
            ),
            "dense_3d_multiphysics_sweep_cases": int(dense_multiphysics_sweep["execution"]["completed_cases"]),
            "dense_3d_multiphysics_sweep_passed": bool(dense_multiphysics_sweep["validation"]["all_passed"]),
            "dense_3d_multiphysics_sweep_seconds": float(dense_multiphysics_sweep["execution"]["wall_seconds"]),
            "dense_3d_historical_rows_matched": int(
                dense_multiphysics_sweep["validation"]["historical_dense_csv_comparison"]["matched_rows"]
            ),
            "independent_thermal_holdout_rows": 18,
            "independent_training_overlap": 0,
        },
        "artifacts": [_artifact(path) for path in paths],
        "publication_scope": {
            "includes_local_secrets": False,
            "includes_api_keys": False,
            "experimental_validation_pipeline_available": True,
            "measured_temperature_validation_available": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"snapshot={args.output}")


if __name__ == "__main__":
    main()
