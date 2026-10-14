from __future__ import annotations

import json
from datetime import datetime, timezone
from itertools import product
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


THERMAL_INPUTS = ["L_m", "W_m", "k_W_mK", "T_hot_K", "T_cold_K"]


def build_independent_thermal_holdout(
    spec: dict[str, Any],
    *,
    count: int = 18,
    seed: int = 20261008,
) -> dict[str, Any]:
    """Build an untouched, space-filling holdout with boundary, centre, and hot anchors."""
    if count < 8:
        raise ValueError("independent holdout requires at least 8 points")
    sampling = dict(spec.get("sampling", {}))
    missing = [name for name in THERMAL_INPUTS if not sampling.get(name)]
    if missing:
        raise ValueError(f"thermal sampling ranges missing: {', '.join(missing)}")
    ranges = {
        name: (float(min(sampling[name])), float(max(sampling[name])))
        for name in THERMAL_INPUTS
    }
    if any(upper <= lower for lower, upper in ranges.values()):
        raise ValueError("each thermal input must span at least two distinct values")

    rng = np.random.default_rng(seed)
    center_jitter = rng.uniform(-0.035, 0.035, len(THERMAL_INPUTS))
    low_jitter = rng.uniform(0.0, 0.025, len(THERMAL_INPUTS))
    high_jitter = rng.uniform(0.0, 0.025, len(THERMAL_INPUTS))
    anchor_positions = [
        ("center", (np.full(5, 0.5) + center_jitter).tolist()),
        ("boundary_low", (np.asarray([0.04, 0.04, 0.04, 0.09, 0.09]) + low_jitter).tolist()),
        ("boundary_high", (np.asarray([0.96, 0.96, 0.96, 0.91, 0.91]) - high_jitter).tolist()),
        ("high_temperature_gradient", [0.48 + center_jitter[0], 0.52 + center_jitter[1], 0.48 + center_jitter[2], 0.94 - high_jitter[3], 0.06 + low_jitter[4]]),
        ("high_temperature_low_conductivity", [0.72 + center_jitter[0], 0.28 + center_jitter[1], 0.07 + low_jitter[2], 0.94 - high_jitter[3], 0.23 + center_jitter[4]]),
        ("high_temperature_high_conductivity", [0.28 + center_jitter[0], 0.72 + center_jitter[1], 0.93 - high_jitter[2], 0.94 - high_jitter[3], 0.23 + center_jitter[4]]),
    ]
    rows: list[dict[str, Any]] = []
    for region, positions in anchor_positions[:count]:
        rows.append({"region": region, **_denormalize(positions, ranges)})

    remaining = count - len(rows)
    if remaining:
        lhs = np.empty((remaining, len(THERMAL_INPUTS)), dtype=float)
        for dimension in range(len(THERMAL_INPUTS)):
            strata = (np.arange(remaining, dtype=float) + rng.random(remaining)) / remaining
            rng.shuffle(strata)
            lhs[:, dimension] = 0.08 + 0.84 * strata
        for index, positions in enumerate(lhs):
            hot_position = float(positions[3])
            region = "high_temperature" if hot_position >= 0.72 else "space_filling"
            rows.append({"region": region, **_denormalize(positions.tolist(), ranges)})

    training_conditions = {
        tuple(round(float(value), 12) for value in values)
        for values in product(*(sampling[name] for name in THERMAL_INPUTS))
    }
    overlap = [
        row for row in rows
        if tuple(round(float(row[name]), 12) for name in THERMAL_INPUTS) in training_conditions
    ]
    if overlap:
        raise RuntimeError("generated holdout unexpectedly overlaps the training grid")

    return {
        "kind": "independent_thermal_holdout_design",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "method": "deterministic_anchor_plus_latin_hypercube",
        "seed": int(seed),
        "sample_count": len(rows),
        "input_columns": list(THERMAL_INPUTS),
        "validated_ranges": {
            name: {"min": lower, "max": upper} for name, (lower, upper) in ranges.items()
        },
        "coverage": {
            "center": sum(row["region"] == "center" for row in rows),
            "boundary": sum(str(row["region"]).startswith("boundary") for row in rows),
            "high_temperature": sum("high_temperature" in str(row["region"]) for row in rows),
            "space_filling": sum(row["region"] == "space_filling" for row in rows),
        },
        "training_overlap_count": 0,
        "rows": rows,
        "policy": [
            "These points are reserved for validation and must not be merged into fitting data.",
            "Every output must come from a fresh COMSOL solve using the declared physical scope.",
            "A replacement holdout must be generated after any data-driven tuning against this set.",
        ],
    }


def write_independent_thermal_holdout(
    spec: dict[str, Any],
    output_dir: str | Path,
    *,
    count: int = 18,
    seed: int = 20261008,
) -> dict[str, Any]:
    design = build_independent_thermal_holdout(spec, count=count, seed=seed)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    json_path = destination / "thermal_plate_independent_holdout_design.json"
    csv_path = destination / "thermal_plate_independent_holdout_inputs.csv"
    json_path.write_text(json.dumps(design, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(design["rows"])[["region", *THERMAL_INPUTS]].to_csv(csv_path, index=False)
    design["json_path"] = str(json_path)
    design["csv_path"] = str(csv_path)
    return design


def summarize_validation_regions(
    validation: dict[str, Any],
    design: dict[str, Any],
) -> dict[str, Any]:
    """Summarize independent holdout errors for boundary, centre, hot, and space-filling regions."""
    validation_rows = list(validation.get("rows", []))
    design_rows = list(design.get("rows", []))
    if len(validation_rows) != len(design_rows):
        raise ValueError("validation and design row counts must match")
    grouped: dict[str, list[dict[str, Any]]] = {}
    for result, condition in zip(validation_rows, design_rows):
        region = str(condition.get("region", "unclassified"))
        grouped.setdefault(region, []).append(result)
    summaries: dict[str, Any] = {}
    for region, rows in grouped.items():
        output_names = sorted({name for row in rows for name in row.get("absolute_error", {})})
        summaries[region] = {
            "rows": len(rows),
            "outputs": {
                name: {
                    "mae": float(np.mean([float(row["absolute_error"][name]) for row in rows])),
                    "rmse": float(np.sqrt(np.mean([
                        float(row["absolute_error"][name]) ** 2 for row in rows
                    ]))),
                    "max_absolute_error": float(max(
                        float(row["absolute_error"][name]) for row in rows
                    )),
                }
                for name in output_names
            },
        }
    return {
        "kind": "independent_holdout_region_summary",
        "sample_count": len(validation_rows),
        "coverage": design.get("coverage", {}),
        "regions": summaries,
    }


def _denormalize(
    positions: list[float],
    ranges: dict[str, tuple[float, float]],
) -> dict[str, float]:
    return {
        name: lower + float(position) * (upper - lower)
        for name, position, (lower, upper) in zip(
            THERMAL_INPUTS,
            positions,
            (ranges[name] for name in THERMAL_INPUTS),
        )
    }
