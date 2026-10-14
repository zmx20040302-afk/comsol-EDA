"""Train the declared-scope capacitor surrogate from independent COMSOL permittivity points."""
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
TRAINING = ROOT / "generated/training_runs/capacitor_dc_permittivity_training.csv"
HOLDOUT = ROOT / "generated/training_runs/capacitor_dc_permittivity_holdout.csv"
MODEL = ROOT / "generated/models/capacitor_dc_permittivity_surrogate.joblib"
INPUTS = ["relative_permittivity"]
OUTPUTS = ["capacitance_F"]
SCOPE = "三维电容器静电模型；固定几何、金属端子、接地和网格，仅改变石英域相对介电常数 epsilon_r=2-8。"


def main() -> int:
    training = pd.read_csv(TRAINING)
    holdout = pd.read_csv(HOLDOUT)
    model = LinearRegression().fit(training[INPUTS], training[OUTPUTS])
    actual = holdout[OUTPUTS].to_numpy(dtype=float)
    predicted = model.predict(holdout[INPUTS].to_numpy(dtype=float))
    relative = np.abs(predicted - actual) / np.maximum(np.abs(actual), 1e-30) * 100.0
    max_error = float(relative.max())
    validation = {
        "kind": "capacitor_dc_permittivity_independent_comsol_validation",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "training_csv": str(TRAINING.resolve()),
        "holdout_csv": str(HOLDOUT.resolve()),
        "training_rows": int(len(training)),
        "holdout_rows": int(len(holdout)),
        "selected_model": "linear_regression",
        "per_output_relative_validation": {
            "capacitance_F": {
                "max_relative_error_percent": max_error,
                "mean_relative_error_percent": float(relative.mean()),
                "threshold_relative_error_percent": 1.0,
                "passed": bool(max_error <= 1.0),
            }
        },
        "passed": bool(max_error <= 1.0),
        "scope": SCOPE,
    }
    report_path = MODEL.with_suffix(".holdout_validation.json")
    validation["path"] = str(report_path.resolve())
    report_path.write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    joblib.dump({"model": model, "model_name": "linear_regression", "input_columns": INPUTS, "output_columns": OUTPUTS, "selection_method": "independent_comsol_holdout", "training_csv_path": str(TRAINING.resolve()), "holdout_csv_path": str(HOLDOUT.resolve())}, MODEL)
    card = write_general_surrogate_model_card(model_name="三维电容介电常数代理模型", model_path=MODEL, training_csv=TRAINING, holdout_csv=HOLDOUT, input_columns=INPUTS, output_columns=OUTPUTS, physical_scope=SCOPE, validation=validation, output_dir=MODEL.parent)
    registry = register_general_surrogate(model_name="三维电容介电常数代理模型", model_path=MODEL, card=card, validation=validation, registry_path=ROOT / "generated/models/surrogate_registry.json")
    print(json.dumps({"validation": validation, "registry": registry}, ensure_ascii=False))
    return 0 if validation["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
