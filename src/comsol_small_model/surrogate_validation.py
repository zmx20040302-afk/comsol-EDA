from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .surrogate_runtime import load_surrogate_payload


def validate_surrogate_holdout(
    model_path: str | Path,
    csv_path: str | Path,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Compare a saved surrogate against fresh COMSOL rows not used for fitting."""
    payload = load_surrogate_payload(model_path)
    inputs = list(payload["input_columns"])
    outputs = list(payload["output_columns"])
    data = pd.read_csv(csv_path)
    missing = [name for name in inputs + outputs if name not in data.columns]
    if missing:
        raise ValueError(f"holdout CSV missing columns: {', '.join(missing)}")
    predicted = payload["model"].predict(data[inputs].to_numpy(dtype=float))
    if getattr(predicted, "ndim", 1) == 1:
        predicted = [[value] for value in predicted]
    rows: list[dict[str, Any]] = []
    for row_index, (_, row) in enumerate(data.iterrows()):
        actual = {name: float(row[name]) for name in outputs}
        estimate = {name: float(predicted[row_index][column_index]) for column_index, name in enumerate(outputs)}
        errors = {name: abs(actual[name] - estimate[name]) for name in outputs}
        rows.append({"inputs": {name: float(row[name]) for name in inputs}, "actual": actual, "predicted": estimate, "absolute_error": errors})
    max_error = {name: max(row["absolute_error"][name] for row in rows) for name in outputs}
    report = {
        "kind": "comsol_surrogate_holdout_validation",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model_path": str(Path(model_path)),
        "csv_path": str(Path(csv_path)),
        "rows": rows,
        "max_absolute_error": max_error,
        "passed": bool(rows) and all(value < 5.0 for value in max_error.values()),
        "criterion": "Each fresh-COMSOL holdout output must have absolute error below 5 K.",
    }
    if output_path:
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        report["path"] = str(destination)
    return report


def validate_surrogate_holdout_relative(
    model_path: str | Path,
    csv_path: str | Path,
    *,
    max_relative_error_percent: float,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Validate a general surrogate on untouched COMSOL rows using a stated relative-error gate."""
    if not max_relative_error_percent > 0:
        raise ValueError("max_relative_error_percent must be greater than zero")
    payload = load_surrogate_payload(model_path)
    inputs = list(payload["input_columns"])
    outputs = list(payload["output_columns"])
    data = pd.read_csv(csv_path)
    missing = [name for name in inputs + outputs if name not in data.columns]
    if missing:
        raise ValueError(f"holdout CSV missing columns: {', '.join(missing)}")

    predicted = payload["model"].predict(data[inputs].to_numpy(dtype=float))
    if getattr(predicted, "ndim", 1) == 1:
        predicted = [[value] for value in predicted]
    rows: list[dict[str, Any]] = []
    unscored_outputs: set[str] = set()
    for row_index, (_, row) in enumerate(data.iterrows()):
        actual = {name: float(row[name]) for name in outputs}
        estimate = {name: float(predicted[row_index][column_index]) for column_index, name in enumerate(outputs)}
        absolute = {name: abs(actual[name] - estimate[name]) for name in outputs}
        relative: dict[str, float | None] = {}
        for name in outputs:
            if abs(actual[name]) < 1e-12:
                relative[name] = None
                unscored_outputs.add(name)
            else:
                relative[name] = absolute[name] / abs(actual[name]) * 100.0
        rows.append({"inputs": {name: float(row[name]) for name in inputs}, "actual": actual, "predicted": estimate, "absolute_error": absolute, "relative_error_percent": relative})

    max_relative = {
        name: max(float(row["relative_error_percent"][name]) for row in rows if row["relative_error_percent"][name] is not None)
        for name in outputs
        if name not in unscored_outputs
    }
    passed = bool(rows) and not unscored_outputs and all(value <= max_relative_error_percent for value in max_relative.values())
    report = {
        "kind": "comsol_surrogate_relative_holdout_validation",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model_path": str(Path(model_path)),
        "csv_path": str(Path(csv_path)),
        "rows": rows,
        "max_relative_error_percent": max_relative,
        "threshold_relative_error_percent": float(max_relative_error_percent),
        "unscored_outputs": sorted(unscored_outputs),
        "passed": passed,
        "criterion": "Each nonzero holdout output must stay within the user-defined relative-error threshold. Zero-valued outputs require an explicit absolute-error criterion.",
    }
    if output_path:
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        report["path"] = str(destination)
    return report
