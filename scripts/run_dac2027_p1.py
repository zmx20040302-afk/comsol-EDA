from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from comsol_small_model.dac2027_p1_scenarios import write_p1_report


def main() -> int:
    output = write_p1_report(ROOT)
    report = json.loads(output.read_text(encoding="utf-8"))
    print(json.dumps({
        "output": output.relative_to(ROOT).as_posix(),
        "p1_definition_completed": report["p1_definition_completed"],
        "submission_two_case_experiment_completed": report["submission_two_case_experiment_completed"],
        "definition_ready_count": report["definition_ready_count"],
        "primary_scenario_count": report["primary_scenario_count"],
        "fresh_post_freeze_count": report["fresh_post_freeze_count"],
    }, ensure_ascii=False, indent=2))
    return 0 if report["p1_definition_completed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

