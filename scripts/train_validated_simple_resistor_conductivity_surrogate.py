"""Train a physics-consistent conductivity-to-resistance COMSOL surrogate."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer

from comsol_small_model.surrogate_model_card import register_general_surrogate, write_general_surrogate_model_card

ROOT = Path(__file__).resolve().parents[1]
TRAINING = ROOT / "generated/training_runs/simple_resistor_conductivity_training.csv"
HOLDOUT = ROOT / "generated/training_runs/simple_resistor_conductivity_holdout.csv"
MODEL = ROOT / "generated/models/simple_resistor_conductivity_surrogate.joblib"
INPUTS = ["conductivity_S_m"]
OUTPUTS = ["resistance_ohm"]
SCOPE = "三维铜导线 Conductive Media 模型；固定几何、1 A 端子、接地和网格，仅改变各向同性电导率 sigma=3e7-7e7 S/m。"


def main() -> int:
    training = pd.read_csv(TRAINING)
    holdout = pd.read_csv(HOLDOUT)
    model = Pipeline([("reciprocal_conductivity", FunctionTransformer(np.reciprocal)), ("linear", LinearRegression())])
    model.fit(training[INPUTS].to_numpy(dtype=float), training[OUTPUTS].to_numpy(dtype=float))
    actual = holdout[OUTPUTS].to_numpy(dtype=float)
    predicted = model.predict(holdout[INPUTS].to_numpy(dtype=float))
    relative = np.abs(predicted - actual) / np.maximum(np.abs(actual), 1e-30) * 100.0
    max_error = float(relative.max())
    validation = {
        "kind": "simple_resistor_conductivity_independent_comsol_validation",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "training_csv": str(TRAINING.resolve()),
        "holdout_csv": str(HOLDOUT.resolve()),
        "training_rows": int(len(training)),
        "holdout_rows": int(len(holdout)),
        "selected_model": "reciprocal_conductivity_linear_regression",
        "selection_reason": "Fixed-geometry ohmic resistance follows R proportional to 1/sigma.",
        "per_output_relative_validation": {"resistance_ohm": {"max_relative_error_percent": max_error, "mean_relative_error_percent": float(relative.mean()), "threshold_relative_error_percent": 1.0, "passed": bool(max_error <= 1.0)}},
        "passed": bool(max_error <= 1.0), "scope": SCOPE,
    }
    report_path = MODEL.with_suffix(".holdout_validation.json")
    validation["path"] = str(report_path.resolve())
    report_path.write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    joblib.dump({"model": model, "model_name": "reciprocal_conductivity_linear_regression", "input_columns": INPUTS, "output_columns": OUTPUTS, "selection_method": "physics_consistent_feature_with_independent_comsol_holdout", "training_csv_path": str(TRAINING.resolve()), "holdout_csv_path": str(HOLDOUT.resolve())}, MODEL)
    card = write_general_surrogate_model_card(model_name="三维导线电阻电导率代理模型", model_path=MODEL, training_csv=TRAINING, holdout_csv=HOLDOUT, input_columns=INPUTS, output_columns=OUTPUTS, physical_scope=SCOPE, validation=validation, output_dir=MODEL.parent)
    registry = register_general_surrogate(model_name="三维导线电阻电导率代理模型", model_path=MODEL, card=card, validation=validation, registry_path=ROOT / "generated/models/surrogate_registry.json")
    print(json.dumps({"validation": validation, "registry": registry}, ensure_ascii=False))
    return 0 if validation["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
