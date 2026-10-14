from __future__ import annotations

import argparse
import importlib
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "generated" / "p2" / "migration_acceptance.json"


def _check(name: str, passed: bool, evidence: Any, required: bool = True) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "required": required, "evidence": evidence}


def run(run_tests: bool = False, host_role: str = "current") -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    checks.append(_check("python_3_12", sys.version_info[:2] == (3, 12), sys.version))
    versions = {}
    for module_name in ("joblib", "numpy", "pandas", "scipy", "sklearn"):
        try:
            module = importlib.import_module(module_name)
            versions[module_name] = getattr(module, "__version__", "available")
        except Exception as exc:  # noqa: BLE001
            versions[module_name] = f"ERROR: {exc}"
    checks.append(_check("core_python_dependencies", all(not str(value).startswith("ERROR") for value in versions.values()), versions))

    config_path = ROOT / "configs" / "execution_node.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    executable_fields = ("matlab_executable", "comsol_executable", "comsol_server_executable")
    executable_status = {field: {"path": config.get(field), "exists": Path(str(config.get(field, ""))).is_file()} for field in executable_fields}
    checks.append(_check("matlab_comsol_paths", all(item["exists"] for item in executable_status.values()), executable_status))
    livelink = Path(str(config.get("livelink_matlab_path", "")))
    checks.append(_check("livelink_path", livelink.is_dir(), str(livelink)))

    p1_path = ROOT / "generated" / "p1" / "template_maturity.json"
    p1 = json.loads(p1_path.read_text(encoding="utf-8"))
    checks.append(_check("representative_comsol_evidence", p1.get("summary", {}).get("comsol_verified_count") == 6, p1.get("summary")))
    checks.append(_check(
        "template_specific_java_dual_path",
        p1.get("summary", {}).get("template_specific_java_backups_verified") == 6
        and p1.get("summary", {}).get("java_dual_path_gate_passed") is True,
        p1.get("summary"),
    ))
    p2_path = ROOT / "generated" / "p2" / "end_to_end_benchmark.json"
    p2 = json.loads(p2_path.read_text(encoding="utf-8"))
    checks.append(_check("p2_fixed_task_benchmark", p2.get("task_matrix", {}).get("task_count") == 60 and not p2.get("failures"), p2.get("metrics")))

    web_text = (ROOT / "web_app.py").read_text(encoding="utf-8")
    ui_markers = ("stagedProgressCard", "stagedWorkflowSelect", "comsolConnectButton", "offlineModeButton", "apiModeButton")
    checks.append(_check("unified_web_workflow", all(marker in web_text for marker in ui_markers), list(ui_markers)))
    startup_files = [ROOT / "start_windows.bat", ROOT / "scripts" / "start_local_service.py", ROOT / "requirements-lock-windows-py312.txt"]
    checks.append(_check("one_click_startup_assets", all(path.is_file() for path in startup_files), [str(path) for path in startup_files]))

    if run_tests:
        environment = dict(__import__("os").environ)
        environment["PYTHONPATH"] = str(ROOT / "src")
        environment["TEMP"] = str(ROOT / ".tmp")
        environment["TMP"] = str(ROOT / ".tmp")
        completed = subprocess.run(
            [sys.executable, "-m", "unittest", "tests.test_p2_release", "tests.test_p1_modeling_pipeline"],
            cwd=ROOT, env=environment, capture_output=True, text=True, timeout=120,
        )
        checks.append(_check("offline_release_tests", completed.returncode == 0, (completed.stdout + completed.stderr)[-4000:]))
    else:
        checks.append(_check("offline_release_tests", True, "not executed in this preflight; use --run-tests", required=False))

    required_checks = [item for item in checks if item["required"]]
    report = {
        "schema": "comsol-p2-migration-acceptance",
        "schemaVersion": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "host": {"platform": platform.platform(), "python": sys.executable},
        "host_role": host_role,
        "scope": "current-host release preflight; repeat this command on the destination Windows computer and then run one live COMSOL template",
        "passed": all(item["passed"] for item in required_checks),
        "checks": checks,
        "destination_host_remaining_action": "Run this script with --run-tests, start start_windows.bat, connect localhost:2036, and execute the one-dimensional heat template.",
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-tests", action="store_true")
    parser.add_argument("--host-role", choices=("current", "destination"), default="current")
    parser.add_argument("--output", default=str(OUTPUT))
    args = parser.parse_args()
    report = run(run_tests=args.run_tests, host_role=args.host_role)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "passed": report["passed"], "checks": [{"name": row["name"], "passed": row["passed"], "required": row["required"]} for row in report["checks"]]}, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
