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

from comsol_small_model.dac2027_p0_evaluation import validate_blind_tasks
from comsol_small_model.dac2027_p3_evaluation import (
    evaluate_p3,
    expected_response_keys,
    historical_families,
    load_jsonl,
    prepare_response_rows,
    sha256,
    validate_case_isolation,
    validate_frozen_assets,
)


PROTOCOL_PATH = ROOT / "configs" / "dac2027_p3_protocol.json"
OUTPUT_DIR = ROOT / "generated" / "dac2027" / "p3"
BENCHMARK_DIR = ROOT / "benchmarks" / "dac2027_p3"
RESPONSES_PATH = BENCHMARK_DIR / "method_responses.measured.jsonl"
TEMPLATE_PATH = BENCHMARK_DIR / "method_responses.template.jsonl"
REPORT_PATH = OUTPUT_DIR / "prospective_multicase_report.json"
STATUS_PATH = OUTPUT_DIR / "readiness_status.json"
SEAL_PATH = OUTPUT_DIR / "sealed_task_manifest.json"
INFRASTRUCTURE_FREEZE_PATH = OUTPUT_DIR / "infrastructure_freeze_manifest.json"


def _now() -> str:
    return datetime.now().astimezone().isoformat()


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def _task_protocol(protocol: dict) -> dict:
    source = protocol["task_source"]
    return {
        "blind_task_policy": {
            "task_count": source["required_task_count"],
            "family_count": source["required_family_count"],
            "status_counts": source["required_status_counts"],
        }
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare or refresh DAC 2027 P3 prospective evaluation status.")
    parser.add_argument("--seal", action="store_true", help="Seal an accepted external task file by SHA-256.")
    parser.add_argument("--tasks", type=Path)
    parser.add_argument("--responses", type=Path, default=RESPONSES_PATH)
    args = parser.parse_args()

    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    assets = validate_frozen_assets(ROOT, protocol)
    task_path = args.tasks or ROOT / str(protocol["task_source"]["path"])
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)
    infrastructure_manifest_valid = False
    if INFRASTRUCTURE_FREEZE_PATH.is_file():
        try:
            frozen = json.loads(INFRASTRUCTURE_FREEZE_PATH.read_text(encoding="utf-8"))
            files = frozen.get("files_sha256", {})
            infrastructure_manifest_valid = bool(files) and all(
                (ROOT / path).is_file() and sha256(ROOT / path) == expected
                for path, expected in files.items()
            )
        except (OSError, json.JSONDecodeError, TypeError):
            infrastructure_manifest_valid = False

    status = {
        "schema": "dac2027-p3-readiness",
        "schemaVersion": "1.0.0",
        "generated_at": _now(),
        "phase": "DAC2027-P3",
        "title": "前瞻独立多案例评测与统计",
        "status": "awaiting_external_blind_tasks",
        "protocol_frozen": infrastructure_manifest_valid,
        "infrastructure_manifest_valid": infrastructure_manifest_valid,
        "frozen_assets_valid": bool(assets["valid"]),
        "statistics_pipeline_ready": True,
        "case_isolation_check_ready": True,
        "repeat_protocol_ready": True,
        "required_task_count": int(protocol["task_source"]["required_task_count"]),
        "required_family_count": int(protocol["task_source"]["required_family_count"]),
        "required_observation_count": int(protocol["task_source"]["required_task_count"])
        * sum(int(value) for value in protocol["repetitions"].values()),
        "accepted_task_count": 0,
        "accepted_family_count": 0,
        "sealed_external_tasks": False,
        "case_family_disjoint": False,
        "measured_observation_count": 0,
        "repeat_stability_available": False,
        "per_family_statistics_available": False,
        "failure_taxonomy_available": False,
        "p3_infrastructure_gate_passed": infrastructure_manifest_valid,
        "p3_main_result_gate_passed": False,
        "task_path": task_path.relative_to(ROOT).as_posix() if task_path.is_absolute() and ROOT in task_path.parents else str(task_path),
        "response_path": args.responses.relative_to(ROOT).as_posix() if args.responses.is_absolute() and ROOT in args.responses.parents else str(args.responses),
        "report_path": "",
        "next_action": "先通过 P0 采集并裁决 24 条外部盲测任务，覆盖 8 个新器件族；在运行任何方法前完成密封。",
        "evidence_boundary": protocol["evidence_boundary"],
        "validation_error": "",
    }

    if task_path.is_file():
        try:
            tasks = load_jsonl(task_path)
            task_validation = validate_blind_tasks(tasks, _task_protocol(protocol))
            isolation = validate_case_isolation(tasks, historical_families(ROOT, protocol))
            status.update({
                "accepted_task_count": int(task_validation["task_count"]),
                "accepted_family_count": int(task_validation["family_count"]),
                "case_family_disjoint": bool(isolation["valid"]),
                "status": "external_tasks_valid_unsealed",
                "next_action": "在运行任何方法前，使用 --seal 密封已经通过校验的任务文件。",
            })
            if args.seal:
                seal = {
                    "schema": "dac2027-p3-sealed-task-manifest",
                    "schemaVersion": "1.0.0",
                    "sealed_at": _now(),
                    "task_path": task_path.relative_to(ROOT).as_posix(),
                    "task_sha256": sha256(task_path),
                    "protocol_path": PROTOCOL_PATH.relative_to(ROOT).as_posix(),
                    "protocol_sha256": sha256(PROTOCOL_PATH),
                    "task_count": len(tasks),
                    "family_count": task_validation["family_count"],
                    "case_isolation": isolation,
                    "method_sources": protocol["local_method_sources"],
                    "post_unseal_method_changes_allowed": False,
                }
                SEAL_PATH.write_text(json.dumps(seal, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            if SEAL_PATH.is_file():
                seal = json.loads(SEAL_PATH.read_text(encoding="utf-8"))
                sealed = (
                    seal.get("task_sha256") == sha256(task_path)
                    and seal.get("protocol_sha256") == sha256(PROTOCOL_PATH)
                    and bool(seal.get("case_isolation", {}).get("valid"))
                )
                status["sealed_external_tasks"] = sealed
                if not sealed:
                    raise ValueError("P3 sealed task manifest no longer matches the accepted task file or protocol")
                template_rows = prepare_response_rows(tasks, protocol)
                _write_jsonl(TEMPLATE_PATH, template_rows)
                status.update({
                    "status": "sealed_measurements_pending",
                    "next_action": "保持密封任务和方法源文件不变，完成协议规定的全部方法与重复运行。",
                })
                if args.responses.is_file():
                    responses = load_jsonl(args.responses)
                    status["measured_observation_count"] = sum(row.get("record_status") == "measured" for row in responses)
                    expected_count = len(expected_response_keys(tasks, protocol))
                    if len(responses) == expected_count and all(row.get("record_status") == "measured" for row in responses):
                        report = evaluate_p3(ROOT, tasks, responses, protocol)
                        report.update({
                            "generated_at": _now(),
                            "protocol_sha256": sha256(PROTOCOL_PATH),
                            "task_sha256": sha256(task_path),
                            "sealed_manifest_sha256": sha256(SEAL_PATH),
                        })
                        REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                        status.update({
                            "status": "completed_external_prospective_evaluation",
                            "repeat_stability_available": True,
                            "per_family_statistics_available": True,
                            "failure_taxonomy_available": True,
                            "p3_main_result_gate_passed": True,
                            "report_path": REPORT_PATH.relative_to(ROOT).as_posix(),
                            "report_sha256": sha256(REPORT_PATH),
                            "next_action": "人工复核作者身份和单位后，将冻结的 P3 结果表同步进 DAC 稿件，不再调参。",
                        })
        except (ValueError, TypeError, KeyError, json.JSONDecodeError, OSError) as exc:
            status.update({
                "status": "invalid_external_evidence",
                "p3_main_result_gate_passed": False,
                "validation_error": str(exc),
                "next_action": "修正外部采集或密封错误；任务解封后不得修改方法行为。",
            })

    STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
