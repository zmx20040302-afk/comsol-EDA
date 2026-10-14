"""Train the bounded thermal-actuator temperature surrogate with COMSOL holdout data."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from comsol_small_model.surrogate import train_surrogate_with_comsol_holdout
from comsol_small_model.surrogate_model_card import register_general_surrogate, write_general_surrogate_model_card


ROOT = Path(__file__).resolve().parents[1]
INPUTS = ["DV_V", "htc_s_W_m2K", "htc_us_W_m2K"]
OUTPUTS = ["Tmax_K"]
RMSE_THRESHOLD_K = 8.0
DEFAULT_SCOPE = (
    "微执行器焦耳热分布参数案例；DV=2-5 V，"
    "htc_s=15000-25000 W/(m^2*K)，htc_us=300-500 W/(m^2*K)。"
    "模型只用于该已验证工作区内的最高温度预测，不外推至高温失控区。"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--training-csv",
        type=Path,
        default=ROOT / "generated" / "training_runs" / "thermal_actuator_safe_training.csv",
    )
    parser.add_argument(
        "--holdout-csv",
        type=Path,
        default=ROOT / "generated" / "training_runs" / "thermal_actuator_safe_holdout.csv",
    )
    parser.add_argument(
        "--model",
        type=Path,
        default=ROOT / "generated" / "models" / "thermal_actuator_safe_tmax_surrogate.joblib",
    )
    parser.add_argument("--scope", default=DEFAULT_SCOPE)
    args = parser.parse_args()

    training_csv = args.training_csv.resolve()
    holdout_csv = args.holdout_csv.resolve()
    model_path = args.model.resolve()
    scope = str(args.scope)
    selected = train_surrogate_with_comsol_holdout(training_csv, holdout_csv, model_path, INPUTS, OUTPUTS)
    best = next(item for item in selected["candidate_reports"] if item["name"] == selected["best_model"])
    validation = {
        "kind": "thermal_actuator_independent_comsol_validation",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "training_csv": str(training_csv),
        "holdout_csv": str(holdout_csv),
        "training_rows": selected["rows"],
        "holdout_rows": selected["holdout_rows"],
        "candidate_reports": selected["candidate_reports"],
        "selected_model": selected["best_model"],
        "max_absolute_error": best["per_output"],
        "rmse_threshold_k": RMSE_THRESHOLD_K,
        "passed": best["holdout_rmse"] <= RMSE_THRESHOLD_K,
        "scope": scope,
    }
    report_path = model_path.with_suffix(".holdout_validation.json")
    validation["path"] = str(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")

    card = write_general_surrogate_model_card(
        model_name="微执行器焦耳热最高温度代理模型",
        model_path=model_path,
        training_csv=training_csv,
        holdout_csv=holdout_csv,
        input_columns=INPUTS,
        output_columns=OUTPUTS,
        physical_scope=scope,
        validation=validation,
        output_dir=model_path.parent,
    )
    registry = register_general_surrogate(
        model_name="微执行器焦耳热最高温度代理模型",
        model_path=model_path,
        card=card,
        validation=validation,
        registry_path=ROOT / "generated" / "models" / "surrogate_registry.json",
    )
    print(json.dumps({"selection": selected, "validation": validation, "model_card": card, "registry": registry}, ensure_ascii=False, indent=2))
    return 0 if validation["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
