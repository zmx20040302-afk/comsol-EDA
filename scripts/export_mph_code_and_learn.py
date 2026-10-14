"""Export a COMSOL MPH model as MATLAB/Java code and learn the exported evidence."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from comsol_small_model.case_knowledge import build_case_card, write_case_card  # noqa: E402
from comsol_small_model.case_memory import remember_case  # noqa: E402
from comsol_small_model.comsol_server import ensure_comsol_server  # noqa: E402
from comsol_small_model.file_reader import build_learning_summary, summarize_files  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mph", type=Path, required=True, help="Source COMSOL MPH model.")
    parser.add_argument("--output-dir", type=Path, help="Directory for exported M/Java/JSON files.")
    parser.add_argument("--knowledge-dir", type=Path, default=ROOT / "generated" / "case_knowledge")
    parser.add_argument("--memory-path", type=Path, default=ROOT / "generated" / "case_memory" / "case_memory.json")
    parser.add_argument("--timeout", type=int, default=300)
    args = parser.parse_args()

    mph_path = args.mph.resolve()
    if not mph_path.is_file() or mph_path.suffix.lower() != ".mph":
        raise FileNotFoundError(f"MPH model not found: {mph_path}")
    output_dir = (args.output_dir or mph_path.with_name(f"{mph_path.stem}_exports")).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    config = json.loads((ROOT / "configs" / "execution_node.json").read_text(encoding="utf-8"))
    report: dict[str, object] = {
        "kind": "mph_code_export_and_learning",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_mph": str(mph_path),
        "output_dir": str(output_dir),
    }

    server = _ensure_server(config)
    report["server"] = server
    if not server["ready"]:
        return _finish(report, False, str(server["message"]))

    matlab = Path(str(config.get("matlab_executable", "")))
    mli = Path(str(config.get("livelink_matlab_path", "")))
    if not matlab.is_file() or not mli.is_dir():
        return _finish(report, False, "MATLAB executable or LiveLink for MATLAB path is unavailable.")

    runner = output_dir / "run_mph_code_export.m"
    runner.write_text(_matlab_runner(mph_path, output_dir, mli, ROOT / "matlab", config), encoding="utf-8")
    completed = subprocess.run(
        [str(matlab), "-batch", f"run('{_matlab_quote(runner)}')"],
        cwd=output_dir,
        capture_output=True,
        text=True,
        timeout=args.timeout,
        check=False,
    )
    matlab_path = output_dir / f"{mph_path.stem}.m"
    java_path = output_dir / f"{mph_path.stem}.java"
    summary_path = output_dir / f"{mph_path.stem}_summary.json"
    report.update(
        {
            "matlab_exit_code": completed.returncode,
            "stdout_tail": completed.stdout[-4000:],
            "stderr_tail": completed.stderr[-4000:],
            "matlab_path": str(matlab_path),
            "java_path": str(java_path),
            "summary_path": str(summary_path),
        }
    )
    artifacts = [path for path in (mph_path, matlab_path, java_path, summary_path) if path.is_file()]
    artifacts.extend(sorted(mph_path.parent.glob("*.pptx")))
    artifacts.extend(sorted(mph_path.parent.glob("*.pdf")))
    if completed.returncode != 0 or not all(path.is_file() for path in (matlab_path, java_path, summary_path)):
        report["failure"] = _classify_export_failure(completed.stdout, completed.stderr)
        return _finish(report, False, "COMSOL export did not produce all expected MATLAB, Java, and JSON files.")

    collection = summarize_files(artifacts)
    learning = build_learning_summary(collection)
    card = build_case_card(mph_path.parent, collection, learning, title=mph_path.stem)
    outputs = write_case_card(card, args.knowledge_dir)
    memory = remember_case(card, args.memory_path)
    report.update({"learning_outputs": outputs, "memory": {"path": memory["memory_path"], "case_count": memory["case_count"]}})
    return _finish(report, True, "MATLAB and Java code exported and learned successfully.")


def _ensure_server(config: dict[str, object]) -> dict[str, object]:
    log_path = ROOT / "generated" / "training_runs" / "comsol_mphserver_export.log"
    result = ensure_comsol_server(config, log_path=log_path, detached=True)
    result["started_by_exporter"] = bool(result.pop("started", False))
    return result


def _matlab_runner(mph_path: Path, output_dir: Path, mli: Path, helper_dir: Path, config: dict[str, object]) -> str:
    host = str(config.get("comsol_server_host", "localhost"))
    port = int(config.get("comsol_server_port", 2036))
    return "\n".join(
        [
            f"addpath('{_matlab_quote(mli)}');",
            f"addpath('{_matlab_quote(helper_dir)}');",
            f"mphstart('{host}', {port});",
            f"result = export_mph_code_bundle('{_matlab_quote(mph_path)}', '{_matlab_quote(output_dir)}');",
            "disp(['MATLAB_EXPORT=' result.matlab_path]);",
            "disp(['JAVA_EXPORT=' result.java_path]);",
            "disp(['SUMMARY_EXPORT=' result.summary_path]);",
        ]
    )


def _matlab_quote(path: Path) -> str:
    return path.as_posix().replace("'", "''")


def _classify_export_failure(stdout: str, stderr: str) -> dict[str, object]:
    """Turn COMSOL/MATLAB output into a machine-readable retry decision."""
    text = f"{stdout}\n{stderr}"
    lowered = text.lower()
    modules = list(dict.fromkeys(re.findall(r"所需产品为：\s*([^。\r\n]+)", text)))
    if "licenseexception" in lowered or "许可证" in text or "license" in lowered:
        return {
            "category": "license",
            "retry_recommended": True,
            "required_modules": modules,
            "message": "COMSOL 或所需模块许可证不可用；恢复许可证后可直接重试导出。",
        }
    if "mphload" in lowered:
        return {
            "category": "model_load",
            "retry_recommended": True,
            "required_modules": modules,
            "message": "COMSOL 未能加载 MPH 模型；请检查模型版本、模块和许可证。",
        }
    if "mphsave" in lowered or "model.save" in lowered:
        return {
            "category": "code_export",
            "retry_recommended": True,
            "required_modules": modules,
            "message": "模型已加载但代码导出失败；可在压缩模型历史后重试。",
        }
    return {
        "category": "unknown",
        "retry_recommended": True,
        "required_modules": modules,
        "message": "导出失败，需查看 MATLAB/COMSOL 日志进一步诊断。",
    }


def _finish(report: dict[str, object], ok: bool, message: str) -> int:
    report["ok"] = ok
    report["message"] = message
    report_path = Path(str(report["output_dir"])) / "export_and_learning_report.json"
    report["report_path"] = str(report_path)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
