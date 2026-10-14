"""Train a geometry-scoped mast mounting stiffness-ratio surrogate on COMSOL holdout points."""

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
INPUTS = ["t_p_mm", "t_m_mm"]
OUTPUTS = ["stiffness_ratio_1"]
MAX_RELATIVE_ERROR_PERCENT = {"stiffness_ratio_1": 2.0}
SCOPE = (
    "通信塔桅零件的灵敏度分析；固定结构钢材料、安装拓扑、约束、载荷定义和稳态固体力学研究；"
    "仅改变板厚 t_p=10-12 mm 与安装厚度 t_m=10-15 mm。"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--training-csv", type=Path, default=ROOT / "generated/training_runs/mast_diagonal_mounting_training.csv")
    parser.add_argument("--holdout-csv", type=Path, default=ROOT / "generated/training_runs/mast_diagonal_mounting_holdout.csv")
    parser.add_argument("--model", type=Path, default=ROOT / "generated/models/mast_diagonal_mounting_stiffness_surrogate.joblib")
    args = parser.parse_args()
    selected = train_surrogate_with_comsol_holdout(args.training_csv, args.holdout_csv, args.model, INPUTS, OUTPUTS)
    payload = joblib.load(args.model)
    holdout = pd.read_csv(args.holdout_csv)
    actual = holdout[OUTPUTS].to_numpy(dtype=float).reshape(-1, 1)
    predicted = np.asarray(payload["model"].predict(holdout[INPUTS].to_numpy(dtype=float)))
    if predicted.ndim == 1:
        predicted = predicted.reshape(-1, 1)
    relative = np.abs(predicted - actual) / np.maximum(np.abs(actual), 1e-12) * 100.0
    per_output = {
        "stiffness_ratio_1": {
            "max_relative_error_percent": float(relative[:, 0].max()),
            "mean_relative_error_percent": float(relative[:, 0].mean()),
            "threshold_relative_error_percent": MAX_RELATIVE_ERROR_PERCENT["stiffness_ratio_1"],
            "passed": bool(relative[:, 0].max() <= MAX_RELATIVE_ERROR_PERCENT["stiffness_ratio_1"]),
        }
    }
    validation = {
        "kind": "mast_diagonal_mounting_independent_comsol_validation",
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
        model_name="通信塔桅刚度比代理模型",
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
        model_name="通信塔桅刚度比代理模型",
        model_path=args.model,
        card=card,
        validation=validation,
        registry_path=ROOT / "generated/models/surrogate_registry.json",
    )
    print(json.dumps({"selection": selected, "validation": validation, "model_card": card, "registry": registry}, ensure_ascii=False))
    return 0 if validation["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())