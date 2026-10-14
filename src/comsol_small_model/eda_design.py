from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


def load_eda_problem(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_eda_problem(data)
    return data


def validate_eda_problem(spec: dict[str, Any]) -> None:
    if spec.get("kind") != "busbar_electrothermal_eda_design_problem":
        raise ValueError("unsupported EDA design problem")
    if spec.get("drive_definition", {}).get("optimization_mode") != "fixed_terminal_current":
        raise ValueError("busbar design comparison must use fixed terminal current")
    variables = [*spec.get("decision_variables", []), *spec.get("operating_variables", [])]
    if not variables:
        raise ValueError("EDA problem has no variables")
    names = [str(item.get("name", "")) for item in variables]
    if len(names) != len(set(names)) or any(not name for name in names):
        raise ValueError("EDA variable names must be present and unique")
    for item in variables:
        if "lower" not in item or "upper" not in item:
            raise ValueError(f"variable {item['name']} is missing a range")
        if float(item["upper"]) <= float(item["lower"]):
            raise ValueError(f"variable {item['name']} has an invalid range")
        if not item.get("unit"):
            raise ValueError(f"variable {item['name']} is missing a unit")
    objective_names = {str(item.get("name", "")) for item in spec.get("objectives", [])}
    if objective_names != {"copper_mass_kg", "joule_power_W"}:
        raise ValueError("P3 busbar problem requires mass and Joule-power objectives")
    assumptions = set(map(str, spec.get("fixed_assumptions", [])))
    if "All final Pareto candidates require fresh COMSOL verification" not in assumptions:
        raise ValueError("fresh COMSOL verification gate is missing")


def variable_rows(spec: dict[str, Any]) -> list[dict[str, Any]]:
    return [*spec.get("decision_variables", []), *spec.get("operating_variables", [])]


def latin_hypercube_design(
    spec: dict[str, Any], *, count: int, seed: int, include_baseline: bool = False
) -> pd.DataFrame:
    validate_eda_problem(spec)
    if count < 2:
        raise ValueError("Latin hypercube design requires at least two rows")
    variables = variable_rows(spec)
    rng = np.random.default_rng(seed)
    matrix = np.empty((count, len(variables)), dtype=float)
    for column in range(len(variables)):
        strata = (np.arange(count, dtype=float) + rng.random(count)) / count
        rng.shuffle(strata)
        matrix[:, column] = strata
    rows: list[dict[str, float]] = []
    for values in matrix:
        row = {
            str(item["name"]): float(item["lower"]) + float(value) * (
                float(item["upper"]) - float(item["lower"])
            )
            for item, value in zip(variables, values)
        }
        rows.append(_repair_geometry(row))
    if include_baseline:
        rows[0] = {
            str(item["name"]): float(
                item.get("baseline", item.get("nominal", (float(item["lower"]) + float(item["upper"])) / 2))
            )
            for item in variables
        }
    frame = pd.DataFrame(rows)
    frame.insert(0, "case_id", [f"design_{index + 1:03d}" for index in range(count)])
    frame.insert(1, "sample_role", "initial_design")
    return frame


def independent_domain_design(
    spec: dict[str, Any], *, count: int, seed: int, forbidden: pd.DataFrame
) -> pd.DataFrame:
    design = latin_hypercube_design(spec, count=count, seed=seed, include_baseline=False)
    design["case_id"] = [f"holdout_{index + 1:03d}" for index in range(count)]
    design["sample_role"] = "independent_domain_test"
    names = [str(item["name"]) for item in variable_rows(spec)]
    forbidden_keys = {_row_key(row, names) for row in forbidden.to_dict("records")}
    if any(_row_key(row, names) in forbidden_keys for row in design.to_dict("records")):
        raise RuntimeError("independent design overlaps the initial design")
    return design


def out_of_domain_design(spec: dict[str, Any], *, count: int, seed: int) -> pd.DataFrame:
    validate_eda_problem(spec)
    variables = variable_rows(spec)
    rng = np.random.default_rng(seed)
    rows: list[dict[str, Any]] = []
    for index in range(count):
        row = {
            str(item["name"]): rng.uniform(float(item["lower"]), float(item["upper"]))
            for item in variables
        }
        variable = variables[index % len(variables)]
        name = str(variable["name"])
        span = float(variable["upper"]) - float(variable["lower"])
        side = "below" if (index // len(variables)) % 2 == 0 else "above"
        row[name] = (
            float(variable["lower"]) - rng.uniform(0.05, 0.15) * span
            if side == "below"
            else float(variable["upper"]) + rng.uniform(0.05, 0.15) * span
        )
        row = _repair_geometry(row, preserve=name)
        row.update({
            "case_id": f"ood_{index + 1:03d}",
            "sample_role": "out_of_domain_test",
            "violated_variable": name,
            "violation_side": side,
        })
        rows.append(row)
    columns = ["case_id", "sample_role", *[str(item["name"]) for item in variables], "violated_variable", "violation_side"]
    return pd.DataFrame(rows)[columns]


def design_readiness(
    frame: pd.DataFrame, spec: dict[str, Any], *, require_verified: bool = True
) -> dict[str, Any]:
    required_outputs = list(map(str, spec.get("required_outputs", [])))
    missing_columns = [name for name in required_outputs if name not in frame.columns]
    missing_values = {
        name: int(frame[name].isna().sum())
        for name in required_outputs if name in frame.columns and frame[name].isna().any()
    }
    verified_count = 0
    if "comsol_verified" in frame.columns:
        verified_count = int(frame["comsol_verified"].fillna(False).astype(bool).sum())
    ready = not missing_columns and not missing_values
    if require_verified:
        ready = ready and verified_count == len(frame)
    return {
        "row_count": int(len(frame)),
        "required_outputs": required_outputs,
        "missing_output_columns": missing_columns,
        "missing_output_values": missing_values,
        "comsol_verified_rows": verified_count,
        "ready_for_optimization": bool(ready),
        "decision": "ready" if ready else "blocked_pending_comsol_evidence",
    }


def pareto_front(
    frame: pd.DataFrame,
    objectives: Iterable[str] = ("copper_mass_kg", "joule_power_W"),
    *,
    feasible_column: str = "constraints_passed",
) -> pd.DataFrame:
    objective_names = list(objectives)
    required = [*objective_names, feasible_column, "comsol_verified"]
    missing = [name for name in required if name not in frame.columns]
    if missing:
        raise ValueError(f"Pareto analysis missing columns: {', '.join(missing)}")
    candidates = frame[
        frame[feasible_column].fillna(False).astype(bool)
        & frame["comsol_verified"].fillna(False).astype(bool)
    ].copy()
    if candidates.empty:
        return candidates
    values = candidates[objective_names].astype(float).to_numpy()
    keep = np.ones(len(candidates), dtype=bool)
    for index, candidate in enumerate(values):
        dominated = np.any(np.all(values <= candidate, axis=1) & np.any(values < candidate, axis=1))
        keep[index] = not bool(dominated)
    return candidates.loc[keep].sort_values(objective_names).reset_index(drop=True)


def write_p3_design_package(
    spec: dict[str, Any], output_dir: str | Path
) -> dict[str, Any]:
    plan = spec.get("evaluation_plan", {})
    initial_count = int(plan.get("initial_design", {}).get("cases", 80))
    holdout_count = int(plan.get("independent_domain_test_cases", 60))
    ood_count = int(plan.get("independent_out_of_domain_cases", 20))
    seeds = list(plan.get("random_seeds", [20261009, 20261019, 20261029]))
    initial = latin_hypercube_design(spec, count=initial_count, seed=int(seeds[0]), include_baseline=True)
    holdout = independent_domain_design(spec, count=holdout_count, seed=int(seeds[1]), forbidden=initial)
    ood = out_of_domain_design(spec, count=ood_count, seed=int(seeds[2]))
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    paths = {
        "initial_design": destination / "initial_design_inputs.csv",
        "independent_domain_test": destination / "independent_domain_test_inputs.csv",
        "out_of_domain_test": destination / "out_of_domain_test_inputs.csv",
    }
    initial.to_csv(paths["initial_design"], index=False)
    holdout.to_csv(paths["independent_domain_test"], index=False)
    ood.to_csv(paths["out_of_domain_test"], index=False)
    manifest = {
        "schema": "comsol-p3-eda-design-package",
        "schemaVersion": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "problem_kind": spec["kind"],
        "drive_mode": spec["drive_definition"]["optimization_mode"],
        "variable_names": [str(item["name"]) for item in variable_rows(spec)],
        "counts": {"initial_design": len(initial), "independent_domain_test": len(holdout), "out_of_domain_test": len(ood)},
        "files": {name: str(path) for name, path in paths.items()},
        "initial_design_readiness": design_readiness(initial, spec),
        "release_gate": "No Pareto candidate can be released until all objective and constraint outputs come from fresh COMSOL solves and comsol_verified=true.",
    }
    manifest_path = destination / "design_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest["manifest_path"] = str(manifest_path)
    return manifest


def _repair_geometry(row: dict[str, float], preserve: str = "") -> dict[str, float]:
    if "bolt_radius_mm" not in row or "wbb_mm" not in row:
        return row
    maximum = 0.20 * float(row["wbb_mm"])
    if preserve != "bolt_radius_mm" and float(row["bolt_radius_mm"]) > maximum:
        row["bolt_radius_mm"] = maximum * 0.995
    return row


def _row_key(row: dict[str, Any], names: list[str]) -> tuple[float, ...]:
    return tuple(round(float(row[name]), 10) for name in names)

