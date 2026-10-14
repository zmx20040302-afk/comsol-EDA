from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from comsol_small_model.dac2027_p3_evaluation import evaluate_p3, load_jsonl, sha256


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate complete sealed DAC 2027 P3 repeated observations.")
    parser.add_argument("--tasks", type=Path, default=ROOT / "benchmarks" / "dac2027_p0" / "blind_tasks.measured.jsonl")
    parser.add_argument("--responses", type=Path, default=ROOT / "benchmarks" / "dac2027_p3" / "method_responses.measured.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "generated" / "dac2027" / "p3" / "prospective_multicase_report.json")
    args = parser.parse_args()
    protocol_path = ROOT / "configs" / "dac2027_p3_protocol.json"
    seal_path = ROOT / "generated" / "dac2027" / "p3" / "sealed_task_manifest.json"
    if not seal_path.is_file():
        raise RuntimeError("P3 tasks are not sealed; run prepare_dac2027_p3.py --seal first")
    seal = json.loads(seal_path.read_text(encoding="utf-8"))
    if seal.get("task_sha256") != sha256(args.tasks) or seal.get("protocol_sha256") != sha256(protocol_path):
        raise RuntimeError("P3 task or protocol hash differs from the sealed manifest")
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    report = evaluate_p3(ROOT, load_jsonl(args.tasks), load_jsonl(args.responses), protocol)
    report.update({
        "generated_at": datetime.now().astimezone().isoformat(),
        "protocol_sha256": sha256(protocol_path),
        "task_sha256": sha256(args.tasks),
        "sealed_manifest_sha256": sha256(seal_path),
    })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "task_count": report["task_count"],
        "family_count": report["family_count"],
        "observation_count": report["measured_observation_count"],
        "methods": report["methods"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
