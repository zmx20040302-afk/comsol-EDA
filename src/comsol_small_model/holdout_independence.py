from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .surrogate import find_input_overlap


def build_holdout_independence_report(
    training_csv: str | Path,
    holdout_csv: str | Path,
    input_columns: list[str],
    *,
    training_manifest: str | Path | None = None,
    holdout_manifest: str | Path | None = None,
) -> dict[str, Any]:
    """Document whether a declared COMSOL holdout is independent of training conditions."""
    if not input_columns:
        raise ValueError("input_columns are required")
    training_path, holdout_path = Path(training_csv), Path(holdout_csv)
    training, holdout = pd.read_csv(training_path), pd.read_csv(holdout_path)
    missing = [name for name in input_columns if name not in training.columns or name not in holdout.columns]
    if missing:
        raise ValueError(f"training or holdout CSV missing input columns: {', '.join(sorted(set(missing)))}")
    overlap = find_input_overlap(training, holdout, input_columns)
    manifest_roles = _manifest_roles(training_manifest, holdout_manifest)
    compatible_columns = set(training.columns) == set(holdout.columns)
    passed = overlap["count"] == 0 and manifest_roles["passed"]
    return {
        "kind": "comsol_holdout_independence_report",
        "training_csv": str(training_path),
        "holdout_csv": str(holdout_path),
        "training_rows": int(len(training)),
        "holdout_rows": int(len(holdout)),
        "input_columns": input_columns,
        "input_overlap": overlap,
        "same_column_set": compatible_columns,
        "manifest_roles": manifest_roles,
        "passed": passed,
        "guidance": "No identical input conditions is a minimum independence check. It does not establish independence when points are near duplicates, simulations share a calibration loop, or the declared physical scope differs.",
    }


def _manifest_roles(training_manifest: str | Path | None, holdout_manifest: str | Path | None) -> dict[str, Any]:
    if training_manifest is None and holdout_manifest is None:
        return {"checked": False, "passed": True, "reason": "manifests not supplied"}
    if training_manifest is None or holdout_manifest is None:
        return {"checked": True, "passed": False, "reason": "both training and holdout manifests are required when either is supplied"}
    train = json.loads(Path(training_manifest).read_text(encoding="utf-8"))
    holdout = json.loads(Path(holdout_manifest).read_text(encoding="utf-8"))
    passed = train.get("role") == "training" and holdout.get("role") == "holdout"
    return {"checked": True, "passed": passed, "training_role": train.get("role"), "holdout_role": holdout.get("role")}
