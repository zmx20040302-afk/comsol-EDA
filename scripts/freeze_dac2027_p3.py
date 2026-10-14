from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from comsol_small_model.dac2027_p3_evaluation import sha256, validate_frozen_assets


FILES = (
    "configs/dac2027_p3_protocol.json",
    "src/comsol_small_model/dac2027_p0_evaluation.py",
    "src/comsol_small_model/dac2027_p2_comparison.py",
    "src/comsol_small_model/dac2027_p3_evaluation.py",
    "scripts/prepare_dac2027_p3.py",
    "scripts/run_dac2027_p3.py",
    "scripts/evaluate_dac2027_p3.py",
    "tests/test_dac2027_p3.py",
)


def main() -> int:
    protocol = json.loads((ROOT / FILES[0]).read_text(encoding="utf-8"))
    validate_frozen_assets(ROOT, protocol)
    missing = [path for path in FILES if not (ROOT / path).is_file()]
    if missing:
        raise FileNotFoundError(f"P3 infrastructure file missing: {missing}")
    manifest = {
        "schema": "dac2027-p3-infrastructure-freeze",
        "schemaVersion": "1.0.0",
        "created_at": datetime.now().astimezone().isoformat(),
        "files_sha256": {path: sha256(ROOT / path) for path in FILES},
        "external_task_data_included": False,
        "main_result_available": False,
        "evidence_boundary": protocol["evidence_boundary"],
    }
    output = ROOT / "generated" / "dac2027" / "p3" / "infrastructure_freeze_manifest.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "frozen_file_count": len(FILES)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
