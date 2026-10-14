"""Merge COMSOL power-inductor frequency CSVs with overlap checks."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


REQUIRED_COLUMNS = ["frequency_Hz", "inductance_H", "conductance_S"]


def load_frequency_data(paths: list[Path]) -> pd.DataFrame:
    if not paths:
        raise ValueError("at least one CSV path is required")
    frames: list[pd.DataFrame] = []
    for path in paths:
        if not path.is_file():
            raise FileNotFoundError(path)
        frame = pd.read_csv(path)
        missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
        if missing:
            raise ValueError(f"{path} is missing columns: {missing}")
        frame = frame[REQUIRED_COLUMNS].copy()
        for column in REQUIRED_COLUMNS:
            frame[column] = pd.to_numeric(frame[column], errors="raise")
        if frame.empty:
            raise ValueError(f"{path} contains no rows")
        if not np.isfinite(frame.to_numpy(float)).all():
            raise ValueError(f"{path} contains NaN or infinite values")
        if (frame["frequency_Hz"] <= 0).any():
            raise ValueError(f"{path} contains a non-positive frequency")
        if (frame[["inductance_H", "conductance_S"]] <= 0).any().any():
            raise ValueError(f"{path} contains a non-positive response")
        frames.append(frame)

    merged = pd.concat(frames, ignore_index=True)
    grouped = merged.groupby("frequency_Hz", sort=False)
    conflicting = []
    for frequency, rows in grouped:
        if len(rows.drop_duplicates()) > 1:
            conflicting.append(float(frequency))
    if conflicting:
        raise ValueError(f"conflicting rows share a frequency: {conflicting}")
    return merged.drop_duplicates().sort_values("frequency_Hz").reset_index(drop=True)


def merge_frequency_data(paths: list[Path], output: Path) -> dict[str, object]:
    merged = load_frequency_data(paths)
    output.parent.mkdir(parents=True, exist_ok=True)
    merged.to_csv(output, index=False)
    return {
        "path": str(output.resolve()),
        "source_paths": [str(path.resolve()) for path in paths],
        "rows": len(merged),
        "frequency_min_Hz": float(merged["frequency_Hz"].min()),
        "frequency_max_Hz": float(merged["frequency_Hz"].max()),
        "frequencies_Hz": [float(value) for value in merged["frequency_Hz"]],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument("inputs", type=Path, nargs="+")
    args = parser.parse_args()
    report = {
        "kind": "power_inductor_frequency_dataset_merge",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "merge": merge_frequency_data(args.inputs, args.output),
    }
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
