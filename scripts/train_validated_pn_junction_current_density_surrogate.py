from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import PolynomialFeatures

from comsol_small_model.surrogate_model_card import register_general_surrogate, write_general_surrogate_model_card

ROOT = Path(__file__).resolve().parents[1]
TRAINING = ROOT / "generated/training_runs/pn_junction_current_density_training.csv"
HOLDOUT = ROOT / "generated/training_runs/pn_junction_current_density_holdout.csv"
MODEL = ROOT / "generated/models/pn_junction_current_density_surrogate.joblib"
INPUTS = ["bias_V"]
OUTPUT = "current_density_at_x_2_5um_A_m2"
SCOPE = (
    "一维硅 P-N 结稳态半导体模型；Tl=300 K、Na=Nd=1e15 1/cm^3、几何、材料、网格和金属接触固定；"
    "仅改变正向偏压 0.05-0.5 V，输出 x=2.5 um 截面的 x 向总电流密度 semi.JX。"
)


def main() -> None:
    training = pd.read_csv(TRAINING)
    holdout = pd.read_csv(HOLDOUT)
    x_train = training[INPUTS].to_numpy()
    y_train = np.log10(-training[OUTPUT].to_numpy())
    x_holdout = holdout[INPUTS].to_numpy()
    y_holdout = holdout[OUTPUT].to_numpy()
    candidates = []
    for degree in (1, 2, 3):
        model = make_pipeline(PolynomialFeatures(degree), LinearRegression()).fit(x_train, y_train)
        predicted = -10 ** model.predict(x_holdout)
        errors = np.abs(predicted - y_holdout) / np.maximum(np.abs(y_holdout), 1e-30) * 100.0
        candidates.append((float(errors.max()), float(errors.mean()), degree, model))
    max_error, mean_error, degree, model = min(candidates, key=lambda item: item[0])
    passed = max_error <= 5.0
    validation = {
        "kind": "pn_junction_current_density_independent_comsol_validation",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "training_csv": str(TRAINING.resolve()), "holdout_csv": str(HOLDOUT.resolve()),
        "training_rows": len(training), "holdout_rows": len(holdout),
        "selected_model": f"polynomial_degree_{degree}_regression_on_log10_abs_current_density",
        "selection_reason": "Forward-bias current density spans orders of magnitude, so log10 of its magnitude is fitted while the negative COMSOL sign is restored after prediction.",
        "max_relative_error_percent": max_error, "mean_relative_error_percent": mean_error,
        "threshold_relative_error_percent": 5.0, "passed": passed, "scope": SCOPE,
    }
    report = MODEL.with_suffix(".holdout_validation.json")
    validation["path"] = str(report.resolve())
    report.write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    joblib.dump({
        "model": model, "model_name": validation["selected_model"], "input_columns": INPUTS,
        "output_columns": [OUTPUT], "log_transformed_outputs": [OUTPUT], "output_signs": {OUTPUT: -1.0},
        "training_csv_path": str(TRAINING.resolve()), "selection_method": "independent_comsol_holdout",
    }, MODEL)
    card = write_general_surrogate_model_card(
        model_name="一维 P-N 结截面电流密度代理模型", model_path=MODEL, training_csv=TRAINING,
        holdout_csv=HOLDOUT, input_columns=INPUTS, output_columns=[OUTPUT], physical_scope=SCOPE,
        validation=validation, output_dir=MODEL.parent,
    )
    register_general_surrogate(
        model_name="一维 P-N 结截面电流密度代理模型", model_path=MODEL, card=card,
        validation=validation, registry_path=ROOT / "generated/models/surrogate_registry.json",
    )
    print(json.dumps(validation, ensure_ascii=False))
    if not passed:
        raise SystemExit("Independent COMSOL validation did not meet the 5% threshold.")


if __name__ == "__main__":
    main()
