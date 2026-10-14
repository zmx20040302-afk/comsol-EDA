from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from comsol_small_model.problem1_publication_evidence import validate_blind_task_submission  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("submission")
    args = parser.parse_args()
    report = validate_blind_task_submission(ROOT / args.submission)
    output = ROOT / "generated" / "dac" / "problem1_publication" / "blind_task_validation_report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
