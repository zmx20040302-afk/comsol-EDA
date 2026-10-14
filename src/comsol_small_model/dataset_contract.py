from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd


REQUIRED_PROVENANCE = ("comsol_version", "model_reference", "study", "mesh_reference")


def validate_dataset_manifest(path: str | Path) -> dict[str, Any]:
    """Validate the portable metadata needed to interpret a COMSOL training CSV."""
    source = Path(path)
    manifest = json.loads(source.read_text(encoding="utf-8"))
    errors: list[str] = []
    if manifest.get("kind") != "comsol-training-dataset-manifest":
        errors.append("kind must be comsol-training-dataset-manifest")
    if manifest.get("schemaVersion") != "1.0.0":
        errors.append("schemaVersion must be 1.0.0")
    if manifest.get("role") not in {"training", "holdout", "augmentation"}:
        errors.append("role must be training, holdout, or augmentation")
    if not str(manifest.get("physical_scope", "")).strip():
        errors.append("physical_scope is required")
    csv_path = Path(str(manifest.get("dataset_csv", "")))
    if not csv_path.is_absolute():
        csv_path = (source.parent / csv_path).resolve()
    if not csv_path.is_file():
        errors.append(f"dataset_csv not found: {csv_path}")
        data_columns: list[str] = []
        rows = 0
    else:
        data = pd.read_csv(csv_path)
        data_columns = list(data.columns)
        rows = int(len(data))
    columns = list(manifest.get("inputs", [])) + list(manifest.get("outputs", []))
    names = [str(item.get("name", "")).strip() for item in columns if isinstance(item, dict)]
    if not manifest.get("inputs") or not manifest.get("outputs"):
        errors.append("inputs and outputs must both contain at least one column")
    if len(names) != len(set(names)):
        errors.append("input and output column names must be unique")
    for item in columns:
        if not isinstance(item, dict) or not str(item.get("name", "")).strip() or not str(item.get("unit", "")).strip():
            errors.append("each input/output requires a nonempty name and unit")
            break
    missing_columns = [name for name in names if name not in data_columns]
    if missing_columns:
        errors.append(f"CSV missing declared columns: {', '.join(missing_columns)}")
    provenance = manifest.get("provenance", {})
    for name in REQUIRED_PROVENANCE:
        if not isinstance(provenance, dict) or not str(provenance.get(name, "")).strip():
            errors.append(f"provenance.{name} is required")
    return {"ok": not errors, "manifest_path": str(source), "dataset_csv": str(csv_path), "rows": rows, "input_columns": [str(item.get("name")) for item in manifest.get("inputs", []) if isinstance(item, dict)], "output_columns": [str(item.get("name")) for item in manifest.get("outputs", []) if isinstance(item, dict)], "errors": errors}
