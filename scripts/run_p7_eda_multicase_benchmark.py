from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from comsol_small_model.p7_eda_multicase import write_p7_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit the frozen P7 multi-case EDA evidence set.")
    parser.add_argument("--config", type=Path, default=ROOT / "configs" / "p7_eda_multicase_benchmark.json")
    parser.add_argument("--output", type=Path, default=ROOT / "generated" / "p7" / "p7_eda_multicase_report.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = write_p7_report(ROOT, output_path=args.output, config_path=args.config)
    summary = {
        "phase": report["phase"],
        "status": report["status"],
        "passed_main_cases": f"{report['passed_main_case_count']}/{report['main_case_count']}",
        "passed_extension_cases": f"{report['passed_extension_case_count']}/{report['extension_case_count']}",
        "physics_families": report["physics_family_count"],
        "report_path": report["report_path"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if report["p7_completed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
