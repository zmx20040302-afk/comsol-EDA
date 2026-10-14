from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from comsol_small_model.dac2027_p0_evaluation import exact_mcnemar, wilson
from comsol_small_model.dac2027_p2_comparison import (
    evaluate_p2,
    load_jsonl,
    parse_llm_output,
    sha256,
    validate_frozen_inputs,
    validate_internal_tasks,
)
from comsol_small_model.physics_dependency_graph import compile_physics_dependency_plan
from comsol_small_model.physics_dependency_graph_v11 import compile_physics_dependency_plan_v11
from comsol_small_model.physics_selection import select_modeling_intent


PROTOCOL_PATH = ROOT / "configs" / "dac2027_p2_protocol.json"
OUTPUT_DIR = ROOT / "generated" / "dac2027" / "p2"
RESPONSES_PATH = OUTPUT_DIR / "method_responses.jsonl"
REPORT_PATH = OUTPUT_DIR / "controlled_comparison_report.json"
STATUS_PATH = OUTPUT_DIR / "readiness_status.json"
RAW_DIR = OUTPUT_DIR / "raw_llm_outputs"
WRITE_LOCK = threading.Lock()
INFRASTRUCTURE_RETRY_LIMIT = 3
INFRASTRUCTURE_RETRY_DELAY_SECONDS = 15


OUTPUT_INSTRUCTION = """只输出一个 JSON 对象，不要输出 Markdown、解释或额外文字。必须严格包含：
{"predicted_interfaces":["接口ID"],"predicted_couplings":["耦合ID"],"predicted_study":"Stationary|TimeDependent|Frequency|Eigenfrequency","predicted_blocked":true或false}
允许的接口 ID：heat_transfer_solids, electric_currents, solid_mechanics, laminar_flow, heat_transfer_fluids, pressure_acoustics, transport_diluted_species。
允许的耦合 ID：electromagnetic_heating, nonisothermal_flow, thermal_expansion, acoustic_structure_boundary。没有耦合时返回空数组。
如果关键信息缺失、需求有明确冲突或无法安全形成模型，predicted_blocked 必须为 true。不得补造用户没有提供的关键边界、激励、材料、单位或工况。"""


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    method_order = {name: index for index, name in enumerate(json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))["methods"])}
    ordered = sorted(rows, key=lambda row: (str(row["task_id"]), method_order[str(row["method"])]))
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in ordered), encoding="utf-8")
    temporary.replace(path)


def _now() -> str:
    return datetime.now().astimezone().isoformat()


def _local_row(task: dict[str, Any], method: str) -> dict[str, Any]:
    started = time.perf_counter()
    if method == "existing_selector":
        result = select_modeling_intent(task["requirement"], task.get("domains", []))
        values = {
            "predicted_interfaces": result["selected_interface_ids"],
            "predicted_couplings": result["coupling_ids"],
            "predicted_study": result["study"]["type"],
            "predicted_blocked": bool(result["abstained"] or result["missing_information"]),
        }
        version = str(result["schemaVersion"])
    else:
        result = compile_physics_dependency_plan_v11(task["requirement"], task.get("domains", []))
        values = {
            "predicted_interfaces": result["interface_ids"],
            "predicted_couplings": result["coupling_ids"],
            "predicted_study": result["study"]["type"],
            "predicted_blocked": bool(result["decision"]["blocked"]),
        }
        version = str(result["schemaVersion"])
    elapsed = time.perf_counter() - started
    return {
        "task_id": task["id"],
        "method": method,
        "record_status": "measured",
        "parse_valid": True,
        **values,
        "completion_seconds": round(elapsed, 6),
        "interactions": 0,
        "human_edits": 0,
        "provider": "local_deterministic",
        "model_id": method,
        "model_version": version,
        "operator_id": "automated-p2-runner",
        "run_at": _now(),
        "raw_output_path": "",
        "diagnostic_path": "",
        "parse_error": "",
    }


def _codex_executable() -> Path:
    direct = shutil.which("codex")
    if direct:
        return Path(direct)
    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    candidates = sorted(
        (Path(local_app_data) / "OpenAI" / "Codex" / "bin").glob("*/codex.exe"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    ) if local_app_data else []
    if not candidates:
        raise RuntimeError("Codex executable was not found")
    return candidates[0]


def _prompt(task: dict[str, Any], method: str, corpus: str) -> str:
    retrieval = "" if method == "direct_llm" else f"\n\n冻结检索资料如下。只把它作为接口与合同词典，不要复制其中无关内容：\n{corpus}"
    return (
        "你是一个受控 COMSOL 建模意图编译器。本次运行禁止调用工具、读取文件、搜索网络或询问用户，"
        "只能使用本提示中提供的工程需求和检索资料。\n\n"
        f"工程需求：\n{task['requirement']}\n\n{OUTPUT_INSTRUCTION}{retrieval}\n"
    )


def _run_llm(task: dict[str, Any], method: str, protocol: dict[str, Any], corpus: str) -> dict[str, Any]:
    config = protocol["llm_control"]
    task_dir = RAW_DIR / method / str(task["id"])
    session_dir = task_dir / "empty_session"
    session_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = task_dir / "prompt.txt"
    raw_path = task_dir / "response.txt"
    diagnostic_path = task_dir / "diagnostic.log"
    prompt_text = _prompt(task, method, corpus)
    prompt_path.write_text(prompt_text, encoding="utf-8")
    temporary = tempfile.NamedTemporaryFile(prefix="dac_p2_codex_", suffix=".txt", delete=False)
    output_path = Path(temporary.name)
    temporary.close()
    command = [
        str(_codex_executable()),
        "exec",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--skip-git-repo-check",
        "--color",
        "never",
        "-C",
        str(session_dir),
        "-o",
        str(output_path),
        "-m",
        str(config["model"]),
        "-c",
        f'model_reasoning_effort="{config["reasoning_effort"]}"',
        "-",
    ]
    environment = os.environ.copy()
    environment.setdefault("CODEX_HOME", str(Path.home() / ".codex"))
    started = time.perf_counter()
    return_code = -1
    diagnostic = ""
    raw = ""
    parse_error = ""
    values: dict[str, Any] = {
        "predicted_interfaces": [],
        "predicted_couplings": [],
        "predicted_study": "__invalid__",
        "predicted_blocked": True,
    }
    attempts = 0
    try:
        diagnostic_parts: list[str] = []
        for attempt in range(1, INFRASTRUCTURE_RETRY_LIMIT + 1):
            attempts = attempt
            output_path.write_text("", encoding="utf-8")
            completed = subprocess.run(
                command,
                input=prompt_text,
                text=True,
                encoding="utf-8",
                errors="replace",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=int(config["timeout_seconds"]) + 15,
                check=False,
                env=environment,
            )
            return_code = completed.returncode
            attempt_diagnostic = f"{completed.stdout}\n{completed.stderr}".strip()
            diagnostic_parts.append(f"=== infrastructure attempt {attempt}/{INFRASTRUCTURE_RETRY_LIMIT} ===\n{attempt_diagnostic}")
            raw = output_path.read_text(encoding="utf-8", errors="replace").strip() if output_path.is_file() else ""
            if return_code == 0:
                break
            if attempt < INFRASTRUCTURE_RETRY_LIMIT:
                time.sleep(INFRASTRUCTURE_RETRY_DELAY_SECONDS * attempt)
        diagnostic = "\n\n".join(diagnostic_parts)
        if return_code != 0:
            parse_error = f"codex infrastructure exit code {return_code} after {attempts} attempts"
        else:
            try:
                values = parse_llm_output(raw)
            except (ValueError, json.JSONDecodeError) as exc:
                parse_error = str(exc)
    except subprocess.TimeoutExpired as exc:
        diagnostic = f"timeout: {exc}"
        parse_error = "timeout"
    except OSError as exc:
        diagnostic = str(exc)
        parse_error = f"launch error: {exc}"
    finally:
        output_path.unlink(missing_ok=True)
    elapsed = time.perf_counter() - started
    raw_path.write_text(raw, encoding="utf-8")
    diagnostic_path.write_text(diagnostic, encoding="utf-8")
    model_match = re.search(r"(?m)^model:\s*([^\s]+)", diagnostic)
    actual_model = model_match.group(1) if model_match else str(config["model"])
    return {
        "task_id": task["id"],
        "method": method,
        "record_status": "measured" if return_code == 0 else "infrastructure_failure",
        "parse_valid": not parse_error,
        **values,
        "completion_seconds": round(elapsed, 6),
        "interactions": 1,
        "human_edits": 0,
        "provider": str(config["provider"]),
        "model_id": actual_model,
        "model_version": actual_model,
        "operator_id": "automated-p2-runner",
        "run_at": _now(),
        "raw_output_path": raw_path.relative_to(ROOT).as_posix(),
        "diagnostic_path": diagnostic_path.relative_to(ROOT).as_posix(),
        "prompt_sha256": sha256(prompt_path),
        "raw_output_sha256": sha256(raw_path),
        "return_code": return_code,
        "infrastructure_attempts": attempts,
        "parse_error": parse_error,
    }


def _ablation_score(task: dict[str, Any], prediction: dict[str, Any]) -> dict[str, Any]:
    return {
        "selection_ok": set(prediction["interfaces"]) == set(task["interfaces"])
        and set(prediction["couplings"]) == set(task["couplings"]),
        "study_ok": prediction["study"] == task["study"],
        "gate_ok": prediction["blocked"] == bool(task["expected_blocked"]),
        "blocked": prediction["blocked"],
    }


def _ablation_summary(details: list[dict[str, Any]], method: str) -> dict[str, Any]:
    rows = [row[method] for row in details]
    blocked = [(task, task[method]) for task in details if task["expected_blocked"]]
    complete = [(task, task[method]) for task in details if not task["expected_blocked"]]
    exact = sum(row["selection_ok"] for row in rows)
    study = sum(row["study_ok"] for row in rows)
    gate = sum(row["gate_ok"] for row in rows)
    false_safe = sum(not row["blocked"] for _, row in blocked)
    false_block = sum(row["blocked"] for _, row in complete)
    total = len(rows)
    return {
        "task_count": total,
        "selection_exact": exact,
        "selection_accuracy": round(exact / total, 4),
        "selection_wilson95": wilson(exact, total),
        "study_exact": study,
        "study_accuracy": round(study / total, 4),
        "study_wilson95": wilson(study, total),
        "gate_correct": gate,
        "gate_accuracy": round(gate / total, 4),
        "gate_wilson95": wilson(gate, total),
        "false_safe_count": false_safe,
        "false_safe_rate": round(false_safe / len(blocked), 4),
        "false_block_count": false_block,
        "false_block_rate": round(false_block / len(complete), 4),
    }


def _run_ablations(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    details = []
    for task in tasks:
        existing = select_modeling_intent(task["requirement"], task.get("domains", []))
        v10 = compile_physics_dependency_plan(task["requirement"], task.get("domains", []))
        v11 = compile_physics_dependency_plan_v11(task["requirement"], task.get("domains", []))
        predictions = {
            "existing_selector": {
                "interfaces": existing["selected_interface_ids"], "couplings": existing["coupling_ids"],
                "study": existing["study"]["type"], "blocked": bool(existing["abstained"] or existing["missing_information"]),
            },
            "dependency_v10": {
                "interfaces": v10["interface_ids"], "couplings": v10["coupling_ids"],
                "study": v10["study"]["type"], "blocked": bool(v10["decision"]["blocked"] or v10["clarification_questions"]),
            },
            "contract_dependency_v11": {
                "interfaces": v11["interface_ids"], "couplings": v11["coupling_ids"],
                "study": v11["study"]["type"], "blocked": bool(v11["decision"]["blocked"]),
            },
            "no_safety_gate": {
                "interfaces": v11["interface_ids"], "couplings": v11["coupling_ids"],
                "study": v11["study"]["type"], "blocked": False,
            },
        }
        details.append({
            "task_id": task["id"], "family": task["family"], "status": task["status"],
            "expected_blocked": bool(task["expected_blocked"]),
            **{name: _ablation_score(task, value) for name, value in predictions.items()},
        })
    methods = ["existing_selector", "dependency_v10", "contract_dependency_v11", "no_safety_gate"]
    summaries = {method: _ablation_summary(details, method) for method in methods}
    full = "contract_dependency_v11"
    comparisons = {}
    for method in methods:
        if method == full:
            continue
        comparisons[method] = {
            "selection_mcnemar": exact_mcnemar(
                [row[full]["selection_ok"] for row in details], [row[method]["selection_ok"] for row in details]
            ),
            "gate_mcnemar": exact_mcnemar(
                [row[full]["gate_ok"] for row in details], [row[method]["gate_ok"] for row in details]
            ),
        }
    return {
        "generated_at": _now(),
        "methods": summaries,
        "paired_comparisons_against_full_method": comparisons,
        "mapping": {
            "without_dependency_graph": "existing_selector",
            "without_negation_aware_completeness": "dependency_v10",
            "without_safety_gate": "no_safety_gate",
        },
        "details": details,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the frozen DAC 2027 P2 controlled method comparison.")
    parser.add_argument("--local-only", action="store_true", help="Run deterministic methods and ablations without LLM calls.")
    parser.add_argument("--llm-workers", type=int, default=4)
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    input_validation = validate_frozen_inputs(ROOT, protocol)
    tasks = load_jsonl(ROOT / protocol["task_set"]["path"])
    task_validation = validate_internal_tasks(tasks, protocol)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    existing_rows = load_jsonl(RESPONSES_PATH) if RESPONSES_PATH.is_file() else []
    # Transport, capacity, authentication and timeout failures are not method
    # predictions. Drop them from the resumable checkpoint so a later run can
    # measure the same frozen task without counting infrastructure as an error.
    existing_rows = [
        row for row in existing_rows
        if not (
            row.get("method") in {"direct_llm", "retrieval_llm"}
            and (row.get("record_status") == "infrastructure_failure" or int(row.get("return_code", 0)) != 0)
        )
    ]
    by_key = {(str(row["task_id"]), str(row["method"])): row for row in existing_rows}
    for task in tasks:
        for method in ("existing_selector", "contract_dependency_v11"):
            key = (str(task["id"]), method)
            if key not in by_key:
                by_key[key] = _local_row(task, method)
    with WRITE_LOCK:
        _write_jsonl(RESPONSES_PATH, list(by_key.values()))
    ablations = _run_ablations(tasks)
    ablation_path = OUTPUT_DIR / "ablation_report.json"
    ablation_path.write_text(json.dumps(ablations, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if not args.local_only:
        corpus = "\n\n".join(
            f"### {item['path']}\n{(ROOT / item['path']).read_text(encoding='utf-8')}" for item in protocol["retrieval_corpus"]
        )
        pending = [
            (task, method)
            for task in tasks
            for method in ("direct_llm", "retrieval_llm")
            if (str(task["id"]), method) not in by_key
        ]
        print(f"p2_llm_pending={len(pending)} workers={max(1, args.llm_workers)}", flush=True)
        with ThreadPoolExecutor(max_workers=max(1, args.llm_workers)) as executor:
            future_map = {
                executor.submit(_run_llm, task, method, protocol, corpus): (task["id"], method)
                for task, method in pending
            }
            completed_count = 0
            for future in as_completed(future_map):
                task_id, method = future_map[future]
                row = future.result()
                completed_count += 1
                if row["record_status"] == "measured":
                    by_key[(str(task_id), method)] = row
                    with WRITE_LOCK:
                        _write_jsonl(RESPONSES_PATH, list(by_key.values()))
                print(
                    f"p2_llm_completed={completed_count}/{len(pending)} task={task_id} method={method} "
                    f"status={row['record_status']} parse_valid={str(bool(row['parse_valid'])).lower()} "
                    f"attempts={row['infrastructure_attempts']} seconds={row['completion_seconds']}",
                    flush=True,
                )
    methods = list(protocol["methods"])
    counts = {method: sum(row["method"] == method for row in by_key.values()) for method in methods}
    complete = all(counts[method] == len(tasks) for method in methods)
    report: dict[str, Any] | None = None
    if complete:
        report = evaluate_p2(tasks, list(by_key.values()), protocol)
        report["generated_at"] = _now()
        report["protocol_path"] = PROTOCOL_PATH.relative_to(ROOT).as_posix()
        report["protocol_sha256"] = sha256(PROTOCOL_PATH)
        report["frozen_input_validation"] = input_validation
        report["ablation"] = ablations
        REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    status = {
        "schema": "dac2027-p2-readiness",
        "schemaVersion": "1.0.0",
        "generated_at": _now(),
        "phase": "DAC2027-P2",
        "title": "同任务四方法对照与消融",
        "status": "completed_development_evidence" if complete else "llm_measurement_pending",
        "frozen_inputs_valid": input_validation["valid"],
        "task_set_valid": task_validation["valid"],
        "task_count": len(tasks),
        "method_count": len(methods),
        "measured_response_count": len(by_key),
        "measured_responses_by_method": counts,
        "controlled_comparison_completed": complete,
        "ablation_completed": True,
        "all_llm_outputs_parse_valid": bool(
            complete and all(row["parse_valid"] for row in by_key.values() if row["method"] in {"direct_llm", "retrieval_llm"})
        ),
        "p2_development_gate_passed": complete,
        "publication_external_gate_passed": False,
        "report_path": REPORT_PATH.relative_to(ROOT).as_posix() if report else "",
        "report_sha256": sha256(REPORT_PATH) if report else "",
        "ablation_report_path": ablation_path.relative_to(ROOT).as_posix(),
        "ablation_report_sha256": sha256(ablation_path),
        "next_action": "Repeat the frozen four-method protocol on the sealed P0 independently authored blind tasks; do not promote this project-authored comparison to the DAC main result.",
        "evidence_boundary": protocol["evidence_boundary"],
    }
    STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(status, ensure_ascii=False, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

