"""Refit the concentric-cylinder electrostatic surrogate with a physics-consistent linear model."""
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
TRAINING = ROOT / "generated/training_runs/electric_field_concentric_cylinders_training.csv"
HOLDOUT = ROOT / "generated/training_runs/electric_field_concentric_cylinders_holdout.csv"
MODEL = ROOT / "generated/models/electric_field_concentric_cylinders_surrogate.joblib"
INPUTS = ["voltage_V"]
OUTPUTS = ["potential_mid_V", "electric_field_mid_V_m"]
SCOPE = "同心圆柱一维轴对称静电模型；ri=0.1 m、ro=1 m、外圆柱接地，仅改变内圆柱 V0=50-150 V。"


def relative_errors(model: LinearRegression, data: pd.DataFrame) -> dict[str, dict[str, float | bool]]:
    actual = data[OUTPUTS].to_numpy(dtype=float)
    predicted = model.predict(data[INPUTS].to_numpy(dtype=float))
    relative = np.abs(predicted - actual) / np.maximum(np.abs(actual), 1e-12) * 100.0
    return {
        name: {
            "max_relative_error_percent": float(relative[:, index].max()),
            "mean_relative_error_percent": float(relative[:, index].mean()),
            "threshold_relative_error_percent": 1.0,
            "passed": bool(relative[:, index].max() <= 1.0),
        }
        for index, name in enumerate(OUTPUTS)
    }


def main() -> int:
    training = pd.read_csv(TRAINING)
    holdout = pd.read_csv(HOLDOUT)
    model = LinearRegression().fit(training[INPUTS], training[OUTPUTS])
    per_output = relative_errors(model, holdout)
    validation = {
        "kind": "electric_field_concentric_cylinders_independent_comsol_validation",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "training_csv": str(TRAINING.resolve()),
        "holdout_csv": str(HOLDOUT.resolve()),
        "training_rows": int(len(training)),
        "holdout_rows": int(len(holdout)),
        "selected_model": "linear_regression_physics_consistent",
        "selection_reason": "The governing electrostatic response is linear in V0 for fixed geometry, materials, and grounded outer boundary.",
        "per_output_relative_validation": per_output,
        "passed": all(item["passed"] for item in per_output.values()),
        "scope": SCOPE,
    }
    report_path = MODEL.with_suffix(".holdout_validation.json")
    validation["path"] = str(report_path.resolve())
    report_path.write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    joblib.dump({
        "model": model,
        "model_name": "linear_regression_physics_consistent",
        "input_columns": INPUTS,
        "output_columns": OUTPUTS,
        "selection_method": "governing_equation_consistent_linear_refit_with_independent_comsol_holdout",
        "training_csv_path": str(TRAINING.resolve()),
        "holdout_csv_path": str(HOLDOUT.resolve()),
    }, MODEL)
    card = write_general_surrogate_model_card(
        model_name="同心圆柱静电场代理模型", model_path=MODEL, training_csv=TRAINING, holdout_csv=HOLDOUT,
        input_columns=INPUTS, output_columns=OUTPUTS, physical_scope=SCOPE, validation=validation, output_dir=MODEL.parent,
    )
    registry = register_general_surrogate(
        model_name="同心圆柱静电场代理模型", model_path=MODEL, card=card, validation=validation,
        registry_path=ROOT / "generated/models/surrogate_registry.json",
    )
    print(json.dumps({"validation": validation, "registry": registry}, ensure_ascii=False))
    return 0 if validation["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
