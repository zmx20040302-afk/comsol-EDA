from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from comsol_small_model.problem1_publication_evidence import evaluate_external_regeneration  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--responses", default="generated/dac/problem1_publication/external_regeneration_responses.jsonl")
    args = parser.parse_args()
    report = evaluate_external_regeneration(
        ROOT / "benchmarks" / "dac_problem1_publication" / "external_regeneration_tasks.jsonl",
        ROOT / args.responses,
        ROOT / "generated" / "dac" / "problem1_publication" / "external_regeneration_report.json",
    )
    print(json.dumps({key: value for key, value in report.items() if key != "results"}, ensure_ascii=False, indent=2))
    return 0 if report.get("passed") else 2


if __name__ == "__main__":
    raise SystemExit(main())
