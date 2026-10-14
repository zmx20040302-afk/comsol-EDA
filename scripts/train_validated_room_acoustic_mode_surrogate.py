"""Train a sound-speed-to-tracked-acoustic-mode surrogate for the room model."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from comsol_small_model.surrogate_model_card import register_general_surrogate, write_general_surrogate_model_card


ROOT = Path(__file__).resolve().parents[1]
TRAINING = ROOT / "generated/training_runs/eigenmodes_of_room_target_mode_training.csv"
HOLDOUT = ROOT / "generated/training_runs/eigenmodes_of_room_target_mode_holdout.csv"
MODEL = ROOT / "generated/models/room_acoustic_target_mode_surrogate.joblib"
INPUTS = ["sound_speed_m_s"]
OUTPUTS = ["tracked_eigenfrequency_Hz"]
SCOPE = (
    "固定房间几何、空气密度、网格和压力声学特征频率研究；"
    "仅改变声速 300-380 m/s，追踪基准声速 343 m/s 时靠近 90 Hz 的同一目标模态。"
)


def main() -> int:
    training = pd.read_csv(TRAINING)
    holdout = pd.read_csv(HOLDOUT)
    model = LinearRegression().fit(training[INPUTS].to_numpy(float), training[OUTPUTS].to_numpy(float))
    predicted = model.predict(holdout[INPUTS].to_numpy(float))
    actual = holdout[OUTPUTS].to_numpy(float)
    relative = np.abs(predicted - actual) / np.maximum(np.abs(actual), 1e-30) * 100.0
    maximum = float(relative.max())
    validation = {
        "kind": "room_acoustic_target_mode_independent_comsol_validation",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "training_csv": str(TRAINING.resolve()),
        "holdout_csv": str(HOLDOUT.resolve()),
        "training_rows": len(training),
        "holdout_rows": len(holdout),
        "selected_model": "linear_regression",
        "selection_reason": "For fixed geometry and boundary conditions, the tracked acoustic eigenfrequency is proportional to sound speed.",
        "per_output_relative_validation": {OUTPUTS[0]: {"max_relative_error_percent": maximum, "mean_relative_error_percent": float(relative.mean()), "threshold_relative_error_percent": 1.0, "passed": maximum <= 1.0}},
        "passed": maximum <= 1.0,
        "scope": SCOPE,
    }
    report_path = MODEL.with_suffix(".holdout_validation.json")
    validation["path"] = str(report_path.resolve())
    report_path.write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    joblib.dump({"model": model, "model_name": "linear_regression", "input_columns": INPUTS, "output_columns": OUTPUTS, "selection_method": "physics_consistent_linear_with_independent_comsol_holdout", "training_csv_path": str(TRAINING.resolve()), "holdout_csv_path": str(HOLDOUT.resolve())}, MODEL)
    card = write_general_surrogate_model_card(model_name="房间声学目标模态频率代理模型", model_path=MODEL, training_csv=TRAINING, holdout_csv=HOLDOUT, input_columns=INPUTS, output_columns=OUTPUTS, physical_scope=SCOPE, validation=validation, output_dir=MODEL.parent)
    registry = register_general_surrogate(model_name="房间声学目标模态频率代理模型", model_path=MODEL, card=card, validation=validation, registry_path=ROOT / "generated/models/surrogate_registry.json")
    print(json.dumps({"validation": validation, "registry": registry}, ensure_ascii=False))
    return 0 if validation["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
