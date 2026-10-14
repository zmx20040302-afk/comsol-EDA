from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from comsol_small_model.problem1_publication_evidence import (  # noqa: E402
    prepare_external_regeneration_template,
    sha256_file,
    validate_blind_task_submission,
)


def main() -> int:
    base = ROOT / "benchmarks" / "dac_problem1_publication"
    generated = ROOT / "generated" / "dac" / "problem1_publication"
    protocol_path = ROOT / "configs" / "dac_problem1_publication_evidence_protocol.json"
    protocol = json.loads(protocol_path.read_text(encoding="utf-8"))
    external = prepare_external_regeneration_template(
        base / "external_regeneration_tasks.jsonl",
        generated / "external_regeneration_responses.jsonl",
    )
    blind_template = base / "blind_task_submission_template.jsonl"
    blind = validate_blind_task_submission(blind_template)
    blind_path = generated / "blind_task_validation_report.json"
    blind_path.parent.mkdir(parents=True, exist_ok=True)
    blind_path.write_text(json.dumps(blind, ensure_ascii=False, indent=2), encoding="utf-8")
    end_to_end_path = generated / "end_to_end_contract_report.json"
    end_to_end = json.loads(end_to_end_path.read_text(encoding="utf-8")) if end_to_end_path.is_file() else {}
    e2e_passed = bool(end_to_end.get("summary", {}).get("gate_passed"))
    external_report_path = generated / "external_regeneration_report.json"
    external_report = json.loads(external_report_path.read_text(encoding="utf-8")) if external_report_path.is_file() else {}
    external_passed = bool(external_report.get("passed"))
    status = {
        "schema": "dac-problem1-publication-evidence-readiness",
        "schemaVersion": "1.0.0",
        "external_regeneration": external,
        "external_regeneration_evaluation": {
            "status": external_report.get("status", "not_evaluated"),
            "passed": external_passed,
            "report": str(external_report_path),
            "report_sha256": sha256_file(external_report_path) if external_report_path.is_file() else "",
        },
        "independent_blind_tasks": blind,
        "representative_end_to_end": {
            "status": "complete" if e2e_passed else "pending",
            "passed": e2e_passed,
            "report": str(end_to_end_path),
            "report_sha256": sha256_file(end_to_end_path) if end_to_end_path.is_file() else "",
            "summary": end_to_end.get("summary", {}),
        },
        "protocol_sha256": sha256_file(protocol_path),
        "frozen_artifact_sha256": {
            relative: sha256_file(ROOT / relative)
            for relative in protocol.get("frozen_artifacts", [])
        },
        "local_end_to_end_gate_passed": e2e_passed,
        "publication_gate_passed": bool(e2e_passed and external_passed and blind.get("passed")),
        "policy": "Prepared acquisition assets are infrastructure, not observed evidence.",
    }
    status_path = generated / "readiness_status.json"
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": str(status_path), "external": external["status"], "blind": blind["status"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
