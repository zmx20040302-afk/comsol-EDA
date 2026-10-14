"""Export and execute six template-specific COMSOL Java backups for P6."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
P1_REPORT = ROOT / "generated" / "p1" / "template_maturity.json"
OUTPUT = ROOT / "generated" / "p6" / "java_dual_path"
REPORT = OUTPUT / "java_dual_path_report.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def public_class_name(source: str) -> str:
    match = re.search(r"\bpublic\s+(?:final\s+)?class\s+([A-Za-z_$][A-Za-z0-9_$]*)", source)
    if not match:
        raise ValueError("导出的 Java 源码中找不到 public class。")
    return match.group(1)


def runner_source(exported_class: str, runner_class: str, output_mph: Path) -> str:
    output_text = java_quote(output_mph.as_posix())
    return f'''import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;

public final class {runner_class} {{
    public static void main(String[] args) {{
        Model model = null;
        try {{
            ModelUtil.initStandalone(false);
            model = {exported_class}.run();
            String[] components = model.component().tags();
            String[] studies = model.study().tags();
            String[] solutions = model.sol().tags();
            if (components.length == 0) throw new IllegalStateException("No component was reconstructed");
            if (studies.length == 0) throw new IllegalStateException("No study was reconstructed");
            model.study(studies[0]).run();
            model.save("{output_text}");
            System.out.println("P6_JAVA_OK=1");
            System.out.println("P6_COMPONENT_COUNT=" + components.length);
            System.out.println("P6_STUDY_COUNT=" + studies.length);
            System.out.println("P6_SOLUTION_COUNT=" + model.sol().tags().length);
            System.out.println("P6_OUTPUT_MPH={output_text}");
        }} catch (Throwable error) {{
            error.printStackTrace(System.err);
            System.exit(1);
        }} finally {{
            if (model != null) try {{ ModelUtil.remove(model.tag()); }} catch (Throwable ignored) {{}}
        }}
    }}
}}
'''


def java_quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def matlab_quote(path: Path) -> str:
    return path.as_posix().replace("'", "''")


def matlab_export_script(templates: list[dict[str, Any]], config: dict[str, Any]) -> str:
    lines = [
        f"addpath('{matlab_quote(Path(str(config['livelink_matlab_path'])))}');",
        f"mphstart('{str(config.get('comsol_server_host', 'localhost')).replace("'", "''")}', {int(config.get('comsol_server_port', 2036))});",
        "import com.comsol.model.util.*;",
    ]
    for item in templates:
        source = Path(item["source_mph"])
        target = Path(item["java_path"])
        lines.extend(
            [
                f"model = mphload('{matlab_quote(source)}');",
                "try; model.resetHist(); catch; end;",
                f"model.save('{matlab_quote(target)}', 'java');",
                f"disp('P6_JAVA_EXPORT={item['id']}');",
                "ModelUtil.remove(model.tag());",
                "clear model;",
            ]
        )
    return "\n".join(lines) + "\n"


def run_command(command: list[str], cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
    )


def load_templates() -> list[dict[str, Any]]:
    p1 = json.loads(P1_REPORT.read_text(encoding="utf-8"))
    templates: list[dict[str, Any]] = []
    for row in p1.get("templates", []):
        template_id = str(row["id"])
        workdir = OUTPUT / template_id
        source_mph = ROOT / str(row["artifacts"]["mph"]["path"])
        templates.append(
            {
                "id": template_id,
                "name": row["name"],
                "physics": row.get("physics", ""),
                "source_job_id": row["job_id"],
                "source_mph": str(source_mph.resolve()),
                "source_mph_sha256": sha256(source_mph),
                "java_path": str((workdir / f"{template_id}_backup.java").resolve()),
                "workdir": str(workdir.resolve()),
            }
        )
    if len(templates) != 6:
        raise RuntimeError(f"P6 要求恰好六个代表模板，当前为 {len(templates)} 个。")
    return templates


def parse_marker(text: str, name: str) -> int | None:
    matches = re.findall(rf"(?:^|\n){re.escape(name)}=(\d+)", text)
    return int(matches[-1]) if matches else None


def execute(*, export_timeout: int, template_timeout: int, reuse_export: bool) -> dict[str, Any]:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    templates = load_templates()
    config = json.loads((ROOT / "configs" / "execution_node.json").read_text(encoding="utf-8"))
    matlab = Path(str(config.get("matlab_executable", "")))
    comsol = Path(str(config.get("comsol_executable", "")))
    install_root = comsol.resolve().parents[2]
    javac = install_root / "java" / "win64" / "jre" / "bin" / "javac.exe"
    batch = install_root / "bin" / "win64" / "comsolbatch.exe"
    plugins = install_root / "plugins" / "*"
    missing = [str(path) for path in (matlab, javac, batch) if not path.is_file()]
    if missing:
        raise FileNotFoundError("缺少 P6 Java 执行程序：" + ", ".join(missing))

    for item in templates:
        Path(item["workdir"]).mkdir(parents=True, exist_ok=True)
    export_runner = OUTPUT / "export_six_template_java_backups.m"
    export_runner.write_text(matlab_export_script(templates, config), encoding="utf-8")
    export_started = time.monotonic()
    export_result: subprocess.CompletedProcess[str] | None = None
    if not reuse_export or not all(Path(item["java_path"]).is_file() for item in templates):
        export_result = run_command(
            [str(matlab), "-batch", f"run('{matlab_quote(export_runner)}')"],
            OUTPUT,
            export_timeout,
        )
    exported_count = sum(Path(item["java_path"]).is_file() for item in templates)
    export_ok = exported_count == len(templates) and (export_result is None or export_result.returncode == 0)

    rows: list[dict[str, Any]] = []
    for item in templates:
        source_java = Path(item["java_path"])
        workdir = Path(item["workdir"])
        row: dict[str, Any] = {
            "id": item["id"],
            "name": item["name"],
            "physics": item["physics"],
            "source_job_id": item["source_job_id"],
            "source_mph": item["source_mph"],
            "source_mph_sha256": item["source_mph_sha256"],
            "java_path": str(source_java),
            "java_exported": source_java.is_file(),
        }
        if not source_java.is_file():
            row.update({"compiled": False, "executed": False, "passed": False, "failure": "java_export_missing"})
            rows.append(row)
            continue

        source_text = source_java.read_text(encoding="utf-8", errors="replace")
        exported_class = public_class_name(source_text)
        runner_class = "P6" + "".join(part.capitalize() for part in str(item["id"]).split("_")) + "Runner"
        runner = workdir / f"{runner_class}.java"
        output_mph = workdir / f"{item['id']}_java_rebuilt.mph"
        batch_log = workdir / "comsol_java_execution.log"
        runner.write_text(runner_source(exported_class, runner_class, output_mph), encoding="utf-8")
        output_mph.unlink(missing_ok=True)
        for class_file in workdir.glob("*.class"):
            class_file.unlink(missing_ok=True)
        started = time.monotonic()
        try:
            compile_result = run_command(
                [str(javac), "-encoding", "UTF-8", "-proc:none", "-cp", str(plugins), str(source_java), str(runner)],
                workdir,
                template_timeout,
            )
            runner_class_file = workdir / f"{runner_class}.class"
            compiled = compile_result.returncode == 0 and runner_class_file.is_file()
            if compiled:
                batch_result = run_command(
                    [str(batch), "-inputfile", str(runner_class_file), "-batchlog", str(batch_log)],
                    workdir,
                    template_timeout,
                )
            else:
                batch_result = subprocess.CompletedProcess([], -1, "", "not executed because compilation failed")
        except subprocess.TimeoutExpired as exc:
            row.update({"compiled": False, "executed": False, "passed": False, "failure": f"timeout: {exc}"})
            rows.append(row)
            continue
        log_text = batch_log.read_text(encoding="utf-8", errors="replace") if batch_log.is_file() else ""
        combined = "\n".join([batch_result.stdout or "", batch_result.stderr or "", log_text])
        executed = batch_result.returncode == 0 and "P6_JAVA_OK=1" in combined and output_mph.is_file()
        row.update(
            {
                "java_class": exported_class,
                "java_size_bytes": source_java.stat().st_size,
                "java_sha256": sha256(source_java),
                "runner_path": str(runner),
                "compiled": compiled,
                "compile_exit_code": compile_result.returncode,
                "compile_output_tail": (compile_result.stderr or compile_result.stdout or "")[-3000:],
                "executed": executed,
                "batch_exit_code": batch_result.returncode,
                "batch_log": str(batch_log),
                "execution_output_tail": combined[-4000:],
                "component_count": parse_marker(combined, "P6_COMPONENT_COUNT"),
                "study_count": parse_marker(combined, "P6_STUDY_COUNT"),
                "solution_count": parse_marker(combined, "P6_SOLUTION_COUNT"),
                "output_mph": str(output_mph),
                "output_mph_size_bytes": output_mph.stat().st_size if output_mph.is_file() else 0,
                "output_mph_sha256": sha256(output_mph) if output_mph.is_file() else "",
                "duration_seconds": round(time.monotonic() - started, 3),
                "passed": bool(compiled and executed),
            }
        )
        rows.append(row)

    passed_count = sum(bool(row.get("passed")) for row in rows)
    report = {
        "schema": "comsol-p6-java-dual-path-evidence",
        "schemaVersion": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "host_scope": "current Windows workstation with COMSOL 6.4 Java API",
        "export": {
            "runner": str(export_runner),
            "duration_seconds": round(time.monotonic() - export_started, 3),
            "exit_code": export_result.returncode if export_result is not None else 0,
            "stdout_tail": (export_result.stdout or "")[-4000:] if export_result is not None else "reused existing exports",
            "stderr_tail": (export_result.stderr or "")[-4000:] if export_result is not None else "",
            "passed": export_ok,
        },
        "summary": {
            "template_count": len(rows),
            "java_exported_count": sum(bool(row.get("java_exported")) for row in rows),
            "java_compiled_count": sum(bool(row.get("compiled")) for row in rows),
            "java_executed_count": sum(bool(row.get("executed")) for row in rows),
            "java_verified_count": passed_count,
            "java_dual_path_gate_passed": export_ok and passed_count == len(rows),
        },
        "templates": rows,
        "scope": "The Java path reconstructs each template, runs its first study through COMSOL Java API and saves a fresh MPH artifact.",
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-timeout", type=int, default=900)
    parser.add_argument("--template-timeout", type=int, default=600)
    parser.add_argument("--reuse-export", action="store_true")
    args = parser.parse_args()
    report = execute(
        export_timeout=max(60, args.export_timeout),
        template_timeout=max(60, args.template_timeout),
        reuse_export=args.reuse_export,
    )
    print(json.dumps({"report": str(REPORT), **report["summary"]}, ensure_ascii=False, indent=2))
    return 0 if report["summary"]["java_dual_path_gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
