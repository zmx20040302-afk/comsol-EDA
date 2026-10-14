from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from comsol_small_model.problem1_publication_evidence import write_jsonl  # noqa: E402
from run_dac_problem1_repair_benchmark import _fixtures  # noqa: E402


def main() -> int:
    output = ROOT / "benchmarks" / "dac_problem1_publication" / "external_regeneration_tasks.jsonl"
    if output.exists():
        raise SystemExit("冻结任务已存在；拒绝覆盖。")
    contract = {
        "schemaVersion": "1.0.0",
        "task": {"name": "frozen complete-code regeneration fixture"},
        "physics": {"interfaces": ["heat_transfer_solids"]},
    }
    markers = [
        "ModelUtil.create",
        ".geom.create",
        ".material.create",
        ".physics.create",
        ".study.create",
        "Stationary",
        ".result.numerical.create",
        "mphsave",
    ]
    rows = []
    for fixture in _fixtures():
        rows.append({
            "id": fixture["id"],
            "contract": contract,
            "failure_message": fixture["error"],
            "broken_code": fixture["broken"],
            "required_markers": markers,
            "max_output_tokens": 8000,
        })
    write_jsonl(output, rows)
    print(json.dumps({"output": str(output), "task_count": len(rows)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
