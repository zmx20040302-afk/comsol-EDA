from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from comsol_small_model.p6_baseline_evaluation import evaluate_baselines, prepare_baseline_template  # noqa: E402


def main() -> None:
    config = ROOT / "configs" / "p6_external_evidence.json"
    template = ROOT / "examples" / "p6_fixed_task_baseline_template.csv"
    report = ROOT / "generated" / "p6" / "baseline_evaluation" / "baseline_evaluation_report.json"
    prepare_baseline_template(ROOT / "generated" / "p2" / "end_to_end_benchmark.json", config, template)
    result = evaluate_baselines(template, config, report)
    print(json.dumps({"template": str(template), "report": str(report), "status": result["status"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
