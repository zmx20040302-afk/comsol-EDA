"""Select a compact nonlinear surrogate for one-dimensional steady radiation heat transfer."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import PolynomialFeatures
from comsol_small_model.surrogate_model_card import register_general_surrogate, write_general_surrogate_model_card

ROOT = Path(__file__).resolve().parents[1]
TRAINING = ROOT / "generated/training_runs/heat_radiation_1d_emissivity_training.csv"
HOLDOUT = ROOT / "generated/training_runs/heat_radiation_1d_emissivity_holdout.csv"
MODEL = ROOT / "generated/models/heat_radiation_1d_emissivity_surrogate.joblib"
INPUTS, OUTPUTS = ["emissivity"], ["radiating_end_temperature_K"]
SCOPE = "一维稳态传热模型；左端固定 1000 K、右端向 300 K 环境表面对环境辐射，仅改变右端发射率 epsilon=0.2-0.98。"

def main() -> int:
    training, holdout = pd.read_csv(TRAINING), pd.read_csv(HOLDOUT)
    x_train, y_train = training[INPUTS].to_numpy(float), training[OUTPUTS].to_numpy(float)
    x_holdout, actual = holdout[INPUTS].to_numpy(float), holdout[OUTPUTS].to_numpy(float)
    candidates = [("linear", LinearRegression()), ("polynomial_degree2", Pipeline([("poly", PolynomialFeatures(2)), ("linear", LinearRegression())])), ("polynomial_degree3", Pipeline([("poly", PolynomialFeatures(3)), ("linear", LinearRegression())]))]
    reports, fitted = [], {}
    for name, candidate in candidates:
        candidate.fit(x_train, y_train)
        prediction = candidate.predict(x_holdout)
        error = np.abs(prediction - actual) / actual * 100.0
        reports.append({"name": name, "max_relative_error_percent": float(error.max()), "mean_relative_error_percent": float(error.mean())})
        fitted[name] = candidate
    best = min(reports, key=lambda item: item["max_relative_error_percent"])
    selected = fitted[best["name"]]
    passed = best["max_relative_error_percent"] <= 1.0
    validation = {"kind": "heat_radiation_1d_independent_comsol_validation", "created_at": datetime.now(timezone.utc).isoformat(), "training_csv": str(TRAINING.resolve()), "holdout_csv": str(HOLDOUT.resolve()), "training_rows": len(training), "holdout_rows": len(holdout), "candidate_reports": reports, "selected_model": best["name"], "per_output_relative_validation": {OUTPUTS[0]: {"max_relative_error_percent": best["max_relative_error_percent"], "mean_relative_error_percent": best["mean_relative_error_percent"], "threshold_relative_error_percent": 1.0, "passed": passed}}, "passed": passed, "scope": SCOPE}
    report_path = MODEL.with_suffix(".holdout_validation.json"); validation["path"] = str(report_path.resolve()); report_path.write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    joblib.dump({"model": selected, "model_name": best["name"], "input_columns": INPUTS, "output_columns": OUTPUTS, "selection_method": "independent_comsol_holdout", "training_csv_path": str(TRAINING.resolve()), "holdout_csv_path": str(HOLDOUT.resolve())}, MODEL)
    card = write_general_surrogate_model_card(model_name="一维稳态辐射传热代理模型", model_path=MODEL, training_csv=TRAINING, holdout_csv=HOLDOUT, input_columns=INPUTS, output_columns=OUTPUTS, physical_scope=SCOPE, validation=validation, output_dir=MODEL.parent)
    registry = register_general_surrogate(model_name="一维稳态辐射传热代理模型", model_path=MODEL, card=card, validation=validation, registry_path=ROOT / "generated/models/surrogate_registry.json")
    print(json.dumps({"validation": validation, "registry": registry}, ensure_ascii=False)); return 0 if passed else 1
if __name__ == "__main__": raise SystemExit(main())
