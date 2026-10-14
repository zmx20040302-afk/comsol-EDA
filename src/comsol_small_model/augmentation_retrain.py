from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from .surrogate import find_input_overlap


def prepare_augmentation_retrain(
    training_csv: str | Path,
    augmentation_csv: str | Path,
    previous_holdout_csv: str | Path,
    fresh_holdout_csv: str | Path,
    input_columns: list[str],
    output_csv: str | Path,
) -> dict[str, Any]:
    """Merge new COMSOL samples only when a new independent holdout is supplied."""
    paths = {name: Path(value).resolve() for name, value in {
        "training": training_csv, "augmentation": augmentation_csv,
        "previous_holdout": previous_holdout_csv, "fresh_holdout": fresh_holdout_csv,
    }.items()}
    if paths["previous_holdout"] == paths["fresh_holdout"]:
        raise ValueError("fresh_holdout_csv must not reuse previous_holdout_csv")
    training = pd.read_csv(paths["training"])
    augmentation = pd.read_csv(paths["augmentation"])
    fresh_holdout = pd.read_csv(paths["fresh_holdout"])
    combined = pd.concat([training, augmentation], ignore_index=True)
    missing = [name for name in input_columns if name not in combined.columns or name not in fresh_holdout.columns]
    if missing:
        raise ValueError(f"combined training or fresh holdout CSV missing input columns: {', '.join(sorted(set(missing)))}")
    overlap = find_input_overlap(combined, fresh_holdout, input_columns)
    if overlap["count"]:
        raise ValueError("combined training and fresh holdout share input conditions; collect a new independent COMSOL holdout")
    destination = Path(output_csv)
    destination.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(destination, index=False)
    return {
        "kind": "augmentation_retrain_preparation",
        "merged_training_csv": str(destination),
        "training_rows": int(len(training)),
        "augmentation_rows": int(len(augmentation)),
        "merged_rows": int(len(combined)),
        "fresh_holdout_rows": int(len(fresh_holdout)),
        "fresh_holdout_csv": str(paths["fresh_holdout"]),
        "previous_holdout_csv": str(paths["previous_holdout"]),
        "input_overlap": overlap,
        "next_action": "Call train_surrogate_with_comsol_holdout with merged_training_csv and fresh_holdout_csv; do not substitute the previous holdout.",
    }
