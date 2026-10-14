from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "configs" / "dac2027_p0_protocol.json"
BENCHMARK_DIR = ROOT / "benchmarks" / "dac2027_p0"
GENERATED_DIR = ROOT / "generated" / "dac2027" / "p0"
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from comsol_small_model.dac2027_p0_evaluation import evaluate_method_responses, validate_blind_tasks


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    statuses = ("complete", "missing", "conflict")
    task_rows = []
    for family_index in range(1, 9):
        for status in statuses:
            task_rows.append({
                "id": f"blind-f{family_index:02d}-{status}",
                "family": f"REPLACE_WITH_EXTERNAL_FAMILY_{family_index:02d}",
                "status": status,
                "requirement": "",
                "domains": [],
                "interfaces": [],
                "couplings": [],
                "study": "",
                "expected_blocked": status != "complete",
                "record_status": "template",
                "author_id": "",
                "author_affiliation": "",
                "adjudicator_id": "",
                "independence_attestation": False,
                "authored_at": "",
                "adjudicated_at": "",
                "notes": ""
            })
    task_path = BENCHMARK_DIR / "blind_tasks.template.jsonl"
    if not task_path.exists():
        write_jsonl(task_path, task_rows)

    response_schema = {
        "schema": "dac2027-p0-method-response-row",
        "record_status": "template",
        "required_rows": "one row for every task_id x method (24 x 4 = 96)",
        "methods": protocol["methods"],
        "fields": {
            "task_id": "blind task id",
            "method": "one of methods",
            "predicted_interfaces": [],
            "predicted_couplings": [],
            "predicted_study": "",
            "predicted_blocked": None,
            "completion_seconds": None,
            "interactions": None,
            "human_edits": None,
            "provider": "",
            "model_id": "",
            "model_version": "",
            "operator_id": "",
            "run_at": ""
        }
    }
    schema_path = BENCHMARK_DIR / "method_response_schema.json"
    schema_path.write_text(json.dumps(response_schema, ensure_ascii=False, indent=2), encoding="utf-8")

    blind_path = BENCHMARK_DIR / "blind_tasks.measured.jsonl"
    response_path = BENCHMARK_DIR / "method_responses.measured.jsonl"
    blind_valid = False
    responses_valid = False
    validation_error = ""
    blind_task_count = 0
    measured_response_count = 0
    measured_by_method = {method: 0 for method in protocol["methods"]}
    if blind_path.exists():
        try:
            measured_tasks = load_jsonl(blind_path)
            blind_task_count = sum(row.get("record_status") == "measured" for row in measured_tasks)
            validate_blind_tasks(measured_tasks, protocol)
            blind_valid = True
            if response_path.exists():
                response_rows = load_jsonl(response_path)
                measured_response_count = sum(row.get("record_status") == "measured" for row in response_rows)
                for row in response_rows:
                    if row.get("record_status") == "measured" and row.get("method") in measured_by_method:
                        measured_by_method[row["method"]] += 1
                evaluate_method_responses(measured_tasks, response_rows, protocol)
                responses_valid = True
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            validation_error = str(exc)
    readiness = {
        "schema": "dac2027-p0-readiness",
        "schemaVersion": "1.0.0",
        "protocol_sha256": sha256(PROTOCOL_PATH),
        "infrastructure": {
            "protocol_frozen": True,
            "task_template_ready": True,
            "four_method_schema_ready": True,
            "paired_statistics_ready": True,
            "internal_pilot_ready": True
        },
        "publication_evidence": {
            "blind_tasks_file_present": blind_path.exists(),
            "method_responses_file_present": response_path.exists(),
            "external_blind_task_count": blind_task_count,
            "measured_response_count": measured_response_count,
            "measured_responses_by_method": measured_by_method,
            "external_blind_tasks_valid": blind_valid,
            "all_four_methods_measured": responses_valid,
            "p0_publication_gate_passed": blind_valid and responses_valid
        },
        "next_required_human_action": (
            "Have external authors and separate adjudicators replace all template fields, set record_status=measured, "
            "and save blind_tasks.measured.jsonl. Then run prepare again to create the 96-row method response sheet."
        ),
        "evidence_boundary": "Templates and the project-authored internal pilot are infrastructure/debug evidence, not DAC main-result observations.",
        "validation_error": validation_error
    }
    acquisition_path = GENERATED_DIR / "acquisition_status.json"
    if acquisition_path.exists():
        readiness["acquisition_campaign"] = json.loads(acquisition_path.read_text(encoding="utf-8"))
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    (GENERATED_DIR / "readiness_status.json").write_text(
        json.dumps(readiness, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(readiness, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
