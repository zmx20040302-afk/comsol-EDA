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
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from comsol_small_model.dac2027_p0_evaluation import validate_blind_tasks
from comsol_small_model.dac2027_p2_comparison import parse_llm_output
from comsol_small_model.dac2027_p3_evaluation import (
    expected_response_keys,
    historical_families,
    load_jsonl,
    sha256,
    validate_case_isolation,
    validate_frozen_assets,
)
from comsol_small_model.physics_dependency_graph_v11 import compile_physics_dependency_plan_v11
from comsol_small_model.physics_selection import select_modeling_intent


PROTOCOL_PATH = ROOT / "configs" / "dac2027_p3_protocol.json"
TASK_PATH = ROOT / "benchmarks" / "dac2027_p0" / "blind_tasks.measured.jsonl"
RESPONSES_PATH = ROOT / "benchmarks" / "dac2027_p3" / "method_responses.measured.jsonl"
OUTPUT_DIR = ROOT / "generated" / "dac2027" / "p3"
RAW_DIR = OUTPUT_DIR / "raw_llm_outputs"
SEAL_PATH = OUTPUT_DIR / "sealed_task_manifest.json"
WRITE_LOCK = threading.Lock()
INFRASTRUCTURE_RETRY_LIMIT = 3
INFRASTRUCTURE_RETRY_DELAY_SECONDS = 15


OUTPUT_INSTRUCTION = """只输出一个 JSON 对象，不要输出 Markdown、解释或额外文字。必须严格包含：
{"predicted_interfaces":["接口ID"],"predicted_couplings":["耦合ID"],"predicted_study":"Stationary|TimeDependent|Frequency|Eigenfrequency","predicted_blocked":true或false}
允许的接口 ID：heat_transfer_solids, electric_currents, solid_mechanics, laminar_flow, heat_transfer_fluids, pressure_acoustics, transport_diluted_species。
允许的耦合 ID：electromagnetic_heating, nonisothermal_flow, thermal_expansion, acoustic_structure_boundary。没有耦合时返回空数组。
如果关键信息缺失、需求有明确冲突或无法安全形成模型，predicted_blocked 必须为 true。不得补造用户没有提供的关键边界、激励、材料、单位或工况。"""


def _now() -> str:
    return datetime.now().astimezone().isoformat()


def _write_jsonl(rows: list[dict[str, Any]]) -> None:
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    method_order = {name: index for index, name in enumerate(protocol["methods"])}
    ordered = sorted(rows, key=lambda row: (str(row["task_id"]), method_order[str(row["method"])], int(row["repeat_index"])))
    RESPONSES_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = RESPONSES_PATH.with_suffix(RESPONSES_PATH.suffix + ".tmp")
    temporary.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in ordered), encoding="utf-8")
    temporary.replace(RESPONSES_PATH)


def _task_protocol(protocol: dict[str, Any]) -> dict[str, Any]:
    source = protocol["task_source"]
    return {
        "blind_task_policy": {
            "task_count": source["required_task_count"],
            "family_count": source["required_family_count"],
            "status_counts": source["required_status_counts"],
        }
    }


def _validate_seal(protocol: dict[str, Any], tasks: list[dict[str, Any]]) -> None:
    if not SEAL_PATH.is_file():
        raise RuntimeError("P3 task manifest is missing; run prepare_dac2027_p3.py --seal first")
    seal = json.loads(SEAL_PATH.read_text(encoding="utf-8"))
    if seal.get("task_sha256") != sha256(TASK_PATH) or seal.get("protocol_sha256") != sha256(PROTOCOL_PATH):
        raise RuntimeError("P3 task or protocol hash differs from the sealed manifest")
    validate_frozen_assets(ROOT, protocol)
    validate_blind_tasks(tasks, _task_protocol(protocol))
    validate_case_isolation(tasks, historical_families(ROOT, protocol))


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
    return {
        "task_id": task["id"], "method": method, "repeat_index": 1,
        "record_status": "measured", "parse_valid": True, **values,
        "completion_seconds": round(time.perf_counter() - started, 6),
        "interactions": 0, "human_edits": 0, "provider": "local_deterministic",
        "model_id": method, "model_version": version,
        "operator_id": "automated-p3-runner", "run_at": _now(),
        "raw_output_path": "", "diagnostic_path": "", "parse_error": "",
        "return_code": 0, "infrastructure_attempts": 1,
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


def _run_llm(task: dict[str, Any], method: str, repeat_index: int, protocol: dict[str, Any], corpus: str) -> dict[str, Any]:
    config = protocol["llm_control"]
    run_dir = RAW_DIR / method / str(task["id"]) / f"repeat-{repeat_index}"
    session_dir = run_dir / "empty_session"
    session_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = run_dir / "prompt.txt"
    raw_path = run_dir / "response.txt"
    diagnostic_path = run_dir / "diagnostic.log"
    prompt_text = _prompt(task, method, corpus)
    prompt_path.write_text(prompt_text, encoding="utf-8")
    temporary = tempfile.NamedTemporaryFile(prefix="dac_p3_codex_", suffix=".txt", delete=False)
    output_path = Path(temporary.name)
    temporary.close()
    command = [
        str(_codex_executable()), "exec", "--ephemeral", "--sandbox", "read-only",
        "--skip-git-repo-check", "--color", "never", "-C", str(session_dir),
        "-o", str(output_path), "-m", str(config["model"]),
        "-c", f'model_reasoning_effort="{config["reasoning_effort"]}"', "-",
    ]
    environment = os.environ.copy()
    environment.setdefault("CODEX_HOME", str(Path.home() / ".codex"))
    started = time.perf_counter()
    return_code = -1
    raw = ""
    parse_error = ""
    diagnostic_parts: list[str] = []
    attempts = 0
    values: dict[str, Any] = {
        "predicted_interfaces": [], "predicted_couplings": [],
        "predicted_study": "__invalid__", "predicted_blocked": True,
    }
    try:
        for attempt in range(1, INFRASTRUCTURE_RETRY_LIMIT + 1):
            attempts = attempt
            output_path.write_text("", encoding="utf-8")
            completed = subprocess.run(
                command, input=prompt_text, text=True, encoding="utf-8", errors="replace",
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=int(config["timeout_seconds"]) + 15, check=False, env=environment,
            )
            return_code = completed.returncode
            diagnostic_parts.append(
                f"=== infrastructure attempt {attempt}/{INFRASTRUCTURE_RETRY_LIMIT} ===\n"
                f"{completed.stdout}\n{completed.stderr}".strip()
            )
            raw = output_path.read_text(encoding="utf-8", errors="replace").strip() if output_path.is_file() else ""
            if return_code == 0:
                break
            if attempt < INFRASTRUCTURE_RETRY_LIMIT:
                time.sleep(INFRASTRUCTURE_RETRY_DELAY_SECONDS * attempt)
        if return_code != 0:
            parse_error = f"codex infrastructure exit code {return_code} after {attempts} attempts"
        else:
            try:
                values = parse_llm_output(raw)
            except (ValueError, json.JSONDecodeError) as exc:
                parse_error = str(exc)
    except subprocess.TimeoutExpired as exc:
        diagnostic_parts.append(f"timeout: {exc}")
        parse_error = "timeout"
    except OSError as exc:
        diagnostic_parts.append(str(exc))
        parse_error = f"launch error: {exc}"
    finally:
        output_path.unlink(missing_ok=True)
    diagnostic = "\n\n".join(diagnostic_parts)
    raw_path.write_text(raw, encoding="utf-8")
    diagnostic_path.write_text(diagnostic, encoding="utf-8")
    model_match = re.search(r"(?m)^model:\s*([^\s]+)", diagnostic)
    actual_model = model_match.group(1) if model_match else str(config["model"])
    return {
        "task_id": task["id"], "method": method, "repeat_index": repeat_index,
        "record_status": "measured" if return_code == 0 else "infrastructure_failure",
        "parse_valid": not parse_error, **values,
        "completion_seconds": round(time.perf_counter() - started, 6),
        "interactions": 1, "human_edits": 0, "provider": str(config["provider"]),
        "model_id": actual_model, "model_version": actual_model,
        "operator_id": "automated-p3-runner", "run_at": _now(),
        "raw_output_path": raw_path.relative_to(ROOT).as_posix(),
        "diagnostic_path": diagnostic_path.relative_to(ROOT).as_posix(),
        "prompt_sha256": sha256(prompt_path), "raw_output_sha256": sha256(raw_path),
        "return_code": return_code, "infrastructure_attempts": attempts, "parse_error": parse_error,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run sealed DAC 2027 P3 repeated method observations.")
    parser.add_argument("--local-only", action="store_true")
    parser.add_argument("--llm-workers", type=int, default=4)
    args = parser.parse_args()
    protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
    if not TASK_PATH.is_file():
        raise FileNotFoundError("P3 external tasks are not available; complete the P0 acquisition campaign first")
    tasks = load_jsonl(TASK_PATH)
    _validate_seal(protocol, tasks)
    existing = load_jsonl(RESPONSES_PATH) if RESPONSES_PATH.is_file() else []
    existing = [row for row in existing if row.get("record_status") == "measured" and int(row.get("return_code", 0)) == 0]
    by_key = {(str(row["task_id"]), str(row["method"]), int(row["repeat_index"])): row for row in existing}
    for task in tasks:
        for method in ("existing_selector", "contract_dependency_v11"):
            key = (str(task["id"]), method, 1)
            if key not in by_key:
                by_key[key] = _local_row(task, method)
    _write_jsonl(list(by_key.values()))
    if not args.local_only:
        corpus = "\n\n".join(
            f"### {item['path']}\n{(ROOT / item['path']).read_text(encoding='utf-8')}"
            for item in protocol["retrieval_corpus"]
        )
        pending = [
            (task, method, repeat_index)
            for task in tasks
            for method in ("direct_llm", "retrieval_llm")
            for repeat_index in range(1, int(protocol["repetitions"][method]) + 1)
            if (str(task["id"]), method, repeat_index) not in by_key
        ]
        print(f"p3_llm_pending={len(pending)} workers={max(1, args.llm_workers)}", flush=True)
        with ThreadPoolExecutor(max_workers=max(1, args.llm_workers)) as executor:
            futures = {
                executor.submit(_run_llm, task, method, repeat_index, protocol, corpus):
                (str(task["id"]), method, repeat_index)
                for task, method, repeat_index in pending
            }
            for completed_count, future in enumerate(as_completed(futures), 1):
                key = futures[future]
                row = future.result()
                if row["record_status"] == "measured":
                    by_key[key] = row
                    with WRITE_LOCK:
                        _write_jsonl(list(by_key.values()))
                print(
                    f"p3_llm_completed={completed_count}/{len(pending)} task={key[0]} method={key[1]} "
                    f"repeat={key[2]} status={row['record_status']} parse_valid={str(bool(row['parse_valid'])).lower()} "
                    f"attempts={row['infrastructure_attempts']} seconds={row['completion_seconds']}",
                    flush=True,
                )
    expected = expected_response_keys(tasks, protocol)
    measured_keys = set(by_key)
    print(json.dumps({
        "response_path": RESPONSES_PATH.relative_to(ROOT).as_posix(),
        "measured_observation_count": len(measured_keys),
        "required_observation_count": len(expected),
        "complete": measured_keys == expected,
        "remaining": len(expected - measured_keys),
    }, ensure_ascii=False, indent=2), flush=True)
    subprocess.run([sys.executable, str(ROOT / "scripts" / "prepare_dac2027_p3.py")], cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
