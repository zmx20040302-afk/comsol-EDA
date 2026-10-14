from __future__ import annotations

import json
from pathlib import Path

from comsol_small_model.eda_design import load_eda_problem, write_p3_design_package


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    spec = load_eda_problem(ROOT / "configs" / "busbar_eda_design_problem.json")
    report = write_p3_design_package(spec, ROOT / "generated" / "p3" / "designs")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

