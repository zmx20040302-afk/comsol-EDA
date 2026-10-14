"""Train and register the narrow Joule-heating surrogate against fresh COMSOL holdout data."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from comsol_small_model.surrogate import train_surrogate_with_comsol_holdout
from comsol_small_model.surrogate_model_card import register_general_surrogate, write_general_surrogate_model_card


ROOT = Path(__file__).resolve().parents[1]
INPUTS = ["Vtot_V"]
OUTPUTS = ["Tmax_K", "Tavg_K"]
RMSE_THRESHOLD_K = 3.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--training-csv", type=Path, default=ROOT / "generated" / "staged_workflows" / "final_code" / "joule_rectangle_auto_solve_results.csv")
    parser.add_argument("--holdout-csv", type=Path, default=ROOT / "generated" / "staged_workflows" / "final_code" / "joule_rectangle_holdout.csv")
    parser.add_argument("--model", type=Path, default=ROOT / "generated" / "models" / "joule_rectangle_validated_surrogate.joblib")
    args = parser.parse_args()

    training_csv = args.training_csv.resolve()
    holdout_csv = args.holdout_csv.resolve()
    model_path = args.model.resolve()
    selected = train_surrogate_with_comsol_holdout(training_csv, holdout_csv, model_path, INPUTS, OUTPUTS)
    best = next(item for item in selected["candidate_reports"] if item["name"] == selected["best_model"])
    validation = {
        "kind": "joule_rectangle_independent_comsol_validation",
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
        "scope": "2D copper rectangle Joule-heating model, 100 mm by 50 mm, fixed material and convection assumptions, Vtot 0.1-1 mV only.",
    }
    report_path = model_path.with_suffix(".holdout_validation.json")
    validation["path"] = str(report_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8")

    card = write_general_surrogate_model_card(
        model_name="二维铜矩形焦耳热温度代理模型",
        model_path=model_path,
        training_csv=training_csv,
        holdout_csv=holdout_csv,
        input_columns=INPUTS,
        output_columns=OUTPUTS,
        physical_scope=validation["scope"],
        validation=validation,
        output_dir=model_path.parent,
    )
    registry = register_general_surrogate(
        model_name="二维铜矩形焦耳热温度代理模型",
        model_path=model_path,
        card=card,
        validation=validation,
        registry_path=ROOT / "generated" / "models" / "surrogate_registry.json",
    )
    output = {"selection": selected, "validation": validation, "model_card": card, "registry": registry}
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if validation["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
