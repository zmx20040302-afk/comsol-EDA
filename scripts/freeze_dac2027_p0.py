from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FILES = (
    "configs/dac2027_p0_protocol.json",
    "src/comsol_small_model/dac2027_p0_evaluation.py",
    "scripts/prepare_dac2027_p0.py",
    "scripts/evaluate_dac2027_p0.py",
    "scripts/run_dac2027_p0_internal_pilot.py",
    "scripts/run_dac2027_p0_local_methods.py",
    "scripts/prepare_dac2027_p0_llm_prompts.py",
    "scripts/start_dac2027_p0_blind_campaign.py",
    "scripts/dac2027_p0_intake_server.py",
    "benchmarks/dac2027_p0/blind_tasks.template.jsonl",
    "benchmarks/dac2027_p0/method_response_schema.json",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    missing = [item for item in FILES if not (ROOT / item).is_file()]
    if missing:
        raise FileNotFoundError(f"P0 freeze inputs missing: {missing}")
    manifest = {
        "schema": "dac2027-p0-freeze-manifest",
        "schemaVersion": "1.0.0",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Evaluator, acquisition schemas, local runners, and frozen prompt generator. Measured blind data are deliberately excluded until acquisition.",
        "files_sha256": {item: sha256(ROOT / item) for item in FILES},
        "publication_evidence_included": False,
    }
    output = ROOT / "generated" / "dac2027" / "p0" / "freeze_manifest.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "frozen_file_count": len(FILES)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
