"""Train a scoped circuit-FEM resistor surrogate on independent COMSOL holdout points."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from comsol_small_model.surrogate import train_surrogate_with_comsol_holdout
from comsol_small_model.surrogate_model_card import register_general_surrogate, write_general_surrogate_model_card

ROOT = Path(__file__).resolve().parents[1]
INPUTS = ["sigma_S_m"]
OUTPUTS = ["resistance_circuit_ohm", "resistance_analytic_ohm"]
MAX_RELATIVE_ERROR_PERCENT = {"resistance_circuit_ohm": 1.0, "resistance_analytic_ohm": 1.0}
SCOPE = (
    "电阻 FEM 场路耦合模型；固定圆柱几何、端子、电路拓扑、R1/R2 和稳态研究；"
    "仅改变材料电导率 sigma=800-1200 S/m。"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--training-csv", type=Path, default=ROOT / "generated/training_runs/circuit_fem_resistor_training.csv")
    parser.add_argument("--holdout-csv", type=Path, default=ROOT / "generated/training_runs/circuit_fem_resistor_holdout.csv")
    parser.add_argument("--model", type=Path, default=ROOT / "generated/models/circuit_fem_resistor_multioutput_surrogate.joblib")
    args = parser.parse_args()

    selected = train_surrogate_with_comsol_holdout(args.training_csv, args.holdout_csv, args.model, INPUTS, OUTPUTS)
    payload = joblib.load(args.model)
    holdout = pd.read_csv(args.holdout_csv)
    actual = holdout[OUTPUTS].to_numpy(dtype=float)
    predicted = np.asarray(payload["model"].predict(holdout[INPUTS].to_numpy(dtype=float)))
    if predicted.ndim == 1:
        predicted = predicted.reshape(-1, 1)
    relative = np.abs(predicted - actual) / np.maximum(np.abs(actual), 1e-12) * 100.0
    per_output = {
        name: {
            "max_relative_error_percent": float(relative[:, index].max()),
            "mean_relative_error_percent": float(relative[:, index].mean()),
            "threshold_relative_error_percent": MAX_RELATIVE_ERROR_PERCENT[name],
            "passed": bool(relative[:, index].max() <= MAX_RELATIVE_ERROR_PERCENT[name]),
        }
        for index, name in enumerate(OUTPUTS)
    }
    validation = {
        "kind": "circuit_fem_resistor_independent_comsol_validation",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "training_csv": str(args.training_csv.resolve()),
        "holdout_csv": str(args.holdout_csv.resolve()),
        "training_rows": selected["rows"],
        "holdout_rows": selected["holdout_rows"],
        "candidate_reports": selected["candidate_reports"],
        "selected_model": selected["best_model"],
        "per_output_relative_validation": per_output,
        "passed": all(item["passed"] for item in per_output.values()),
        "scope": SCOPE,
    }
    report_path = args.model.with_suffix(".holdout_validation.json")
    validation["path"] = str(report_path.resolve())
    report_path.write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")
    card = write_general_surrogate_model_card(
        model_name="电阻 FEM 场路耦合多输出代理",
        model_path=args.model,
        training_csv=args.training_csv,
        holdout_csv=args.holdout_csv,
        input_columns=INPUTS,
        output_columns=OUTPUTS,
        physical_scope=SCOPE,
        validation=validation,
        output_dir=args.model.parent,
    )
    registry = register_general_surrogate(
        model_name="电阻 FEM 场路耦合多输出代理",
        model_path=args.model,
        card=card,
        validation=validation,
        registry_path=ROOT / "generated/models/surrogate_registry.json",
    )
    print(json.dumps({"selection": selected, "validation": validation, "model_card": card, "registry": registry}, ensure_ascii=False))
    return 0 if validation["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())