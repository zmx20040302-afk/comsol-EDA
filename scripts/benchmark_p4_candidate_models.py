from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from comsol_small_model.eda_adaptive import diagnostic_metrics, fit_p4_models


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    initial = pd.read_csv(ROOT / "generated" / "p3" / "initial_design" / "busbar_p3_initial_design_evaluated.csv")
    consumed = pd.read_csv(ROOT / "generated" / "p3" / "final_evaluation" / "final_evaluation_evaluated.csv")
    diagnostic = consumed[consumed["sample_role"] == "independent_domain_test"].copy()
    bundle_80 = fit_p4_models(initial)
    report = {
        "training_rows": len(initial),
        "diagnostic_rows": len(diagnostic),
        "diagnostic_policy": "The P3 final domain set has been opened and is used only for P4 model selection. It is permanently retired as independent evidence.",
        "selected_models": {target: item["selected"] for target, item in bundle_80["comparison"].items()},
        "cross_validation": {target: item["selected_cross_validation"] for target, item in bundle_80["comparison"].items()},
        "retired_p3_diagnostic_metrics": diagnostic_metrics(bundle_80, diagnostic),
        "candidate_comparison": bundle_80["comparison"],
    }
    output = ROOT / "generated" / "p4" / "model_selection"
    output.mkdir(parents=True, exist_ok=True)
    (output / "candidate_model_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
