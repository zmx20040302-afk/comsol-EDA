from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from comsol_small_model.requirement_parser import missing_categories, parse_modeling_requirement


def run_benchmark(cases_path: str | Path) -> dict:
    path = Path(cases_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    results = []
    true_positive = 0
    false_negative = 0
    false_positive = 0
    exact = 0
    for case in payload.get("cases", []):
        contract = parse_modeling_requirement(str(case["requirement"]))
        expected = set(str(item) for item in case.get("expected_missing_categories", []))
        predicted = missing_categories(contract, critical_only=True)
        true_positive += len(expected & predicted)
        false_negative += len(expected - predicted)
        false_positive += len(predicted - expected)
        exact += expected == predicted
        results.append(
            {
                "id": case["id"],
                "expected": sorted(expected),
                "predicted": sorted(predicted),
                "missed": sorted(expected - predicted),
                "unexpected": sorted(predicted - expected),
                "passed": expected.issubset(predicted),
            }
        )
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 1.0
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 1.0
    return {
        "schema": "comsol-requirement-completeness-benchmark-report",
        "schemaVersion": "1.0.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "case_count": len(results),
        "passed_required_recall": sum(item["passed"] for item in results),
        "exact_match_count": exact,
        "true_positive": true_positive,
        "false_negative": false_negative,
        "false_positive": false_positive,
        "critical_missing_recall": recall,
        "critical_missing_precision": precision,
        "target_recall": 0.95,
        "target_passed": recall >= 0.95,
        "cases": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default=str(ROOT / "benchmarks" / "requirement_completeness" / "tasks.json"))
    parser.add_argument("--output", default=str(ROOT / "generated" / "benchmarks" / "requirement_completeness" / "report.json"))
    args = parser.parse_args()
    report = run_benchmark(args.cases)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("case_count", "critical_missing_recall", "critical_missing_precision", "target_passed")}, ensure_ascii=False))
    return 0 if report["target_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
