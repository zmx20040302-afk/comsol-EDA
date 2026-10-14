from __future__ import annotations

import json
from pathlib import Path

from comsol_small_model.eda_design import load_eda_problem
from comsol_small_model.eda_optimization import run_p3_surrogate_search


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    spec = load_eda_problem(ROOT / "configs" / "busbar_eda_design_problem.json")
    report = run_p3_surrogate_search(
        ROOT / "generated" / "p3" / "initial_design" / "busbar_p3_initial_design_evaluated.csv",
        spec,
        ROOT / "generated" / "p3" / "optimization",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

