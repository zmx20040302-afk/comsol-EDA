from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from comsol_small_model.dac2027_p0_evaluation import (
    evaluate_method_responses,
    prepare_method_response_rows,
    validate_blind_tasks,
)


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate DAC 2027 P0 blind tasks or score complete four-method observations.")
    parser.add_argument("--tasks", type=Path, default=ROOT / "benchmarks" / "dac2027_p0" / "blind_tasks.measured.jsonl")
    parser.add_argument("--responses", type=Path)
    parser.add_argument("--prepare-responses", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "generated" / "dac2027" / "p0" / "blind_evaluation.json")
    args = parser.parse_args()
    protocol = json.loads((ROOT / "configs" / "dac2027_p0_protocol.json").read_text(encoding="utf-8"))
    tasks = load_jsonl(args.tasks)
    validation = validate_blind_tasks(tasks, protocol)
    if args.prepare_responses:
        output = args.responses or ROOT / "benchmarks" / "dac2027_p0" / "method_responses.measured.jsonl"
        if output.exists():
            raise RuntimeError(f"refusing to overwrite existing response file: {output}")
        write_jsonl(output, prepare_method_response_rows(tasks, protocol))
        print(json.dumps({"validation": validation, "response_rows": 96, "output": str(output)}, ensure_ascii=False, indent=2))
        return 0
    if not args.responses:
        print(json.dumps(validation, ensure_ascii=False, indent=2))
        return 0
    report = evaluate_method_responses(tasks, load_jsonl(args.responses), protocol)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"methods": report["methods"], "comparisons": report["paired_comparisons_against_full_method"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
