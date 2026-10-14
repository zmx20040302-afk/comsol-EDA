from __future__ import annotations

import argparse
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from comsol_small_model.workflow_status import EVIDENCE_LEVELS, WORKFLOW_STATUSES
from comsol_small_model.validated_templates import load_validated_templates


def _read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def build_baseline(test_count: int, test_status: str) -> dict:
    compatibility_path = ROOT / "generated" / "compatibility" / "matlab_r2023b_comsol_6_4_full_solve.json"
    sweep9_path = ROOT / "generated" / "benchmarks" / "busbar_multiphysics_sweep_20261009" / "busbar_multiphysics_sweep_benchmark.json"
    sweep49_path = ROOT / "generated" / "benchmarks" / "busbar_dense_multiphysics_sweep_20261009" / "busbar_dense_multiphysics_sweep_benchmark.json"
    completeness_path = ROOT / "generated" / "benchmarks" / "requirement_completeness" / "report.json"
    memory_path = ROOT / "generated" / "case_memory" / "case_memory.json"
    compatibility = _read_json(compatibility_path)
    sweep9 = _read_json(sweep9_path)
    sweep49 = _read_json(sweep49_path)
    completeness = _read_json(completeness_path)
    memory = _read_json(memory_path)
    templates = load_validated_templates()
    mph_files = list(ROOT.glob("generated/**/*.mph"))
    return {
        "schema": "comsol-auto-modeling-baseline",
        "schemaVersion": "1.0.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_root": str(ROOT),
        "runtime": {
            "platform": platform.platform(),
            "python": sys.version.split()[0],
            "python_executable": sys.executable,
            "matlab": compatibility.get("matlab_version", "unknown"),
            "comsol": compatibility.get("comsol_version", "unknown"),
            "mphserver_host": compatibility.get("livelink_host", "localhost"),
            "mphserver_port": compatibility.get("livelink_port", 2036),
            "livelink_full_solve_passed": bool(compatibility.get("test", {}).get("passed", False)),
        },
        "workflow_contract": {
            "workflow_version": "2.0.0",
            "contract_schema": "configs/modeling_contract.schema.json",
            "contract_schema_version": "1.0.0",
            "stage_count": 10,
            "workflow_statuses": list(WORKFLOW_STATUSES),
            "evidence_levels": list(EVIDENCE_LEVELS),
        },
        "assets": {
            "validated_template_count": len(templates),
            "validated_template_ids": [item.get("id") for item in templates],
            "case_memory_count": len(memory.get("cases", [])),
            "generated_mph_count": len(mph_files),
        },
        "tests": {"count": int(test_count), "status": str(test_status)},
        "benchmarks": {
            "livelink_compatibility": {
                "path": str(compatibility_path.relative_to(ROOT)),
                "passed": bool(compatibility.get("test", {}).get("passed", False)),
            },
            "busbar_9_case": {
                "path": str(sweep9_path.relative_to(ROOT)),
                "completed_cases": sweep9.get("execution", {}).get("completed_cases"),
                "wall_seconds": sweep9.get("execution", {}).get("wall_seconds"),
                "passed": sweep9.get("validation", {}).get("all_passed"),
            },
            "busbar_49_case": {
                "path": str(sweep49_path.relative_to(ROOT)),
                "completed_cases": sweep49.get("execution", {}).get("completed_cases"),
                "wall_seconds": sweep49.get("execution", {}).get("wall_seconds"),
                "passed": sweep49.get("validation", {}).get("all_passed"),
            },
            "requirement_completeness": {
                "path": str(completeness_path.relative_to(ROOT)),
                "case_count": completeness.get("case_count"),
                "critical_missing_recall": completeness.get("critical_missing_recall"),
                "critical_missing_precision": completeness.get("critical_missing_precision"),
                "passed": completeness.get("target_passed"),
            },
        },
        "evidence_paths": [
            str(path.relative_to(ROOT))
            for path in (compatibility_path, sweep9_path, sweep49_path, completeness_path, memory_path)
            if path.is_file()
        ],
    }


def _markdown(report: dict) -> str:
    runtime = report["runtime"]
    assets = report["assets"]
    tests = report["tests"]
    benchmarks = report["benchmarks"]
    lines = [
        "# 自动建模平台 P0 基线",
        "",
        f"生成时间：{report['created_at']}",
        "",
        "## 环境",
        "",
        f"- Python：`{runtime['python']}`",
        f"- MATLAB：`{runtime['matlab']}`",
        f"- COMSOL：`{runtime['comsol']}`",
        f"- mphserver：`{runtime['mphserver_host']}:{runtime['mphserver_port']}`",
        f"- LiveLink 完整求解兼容性：`{runtime['livelink_full_solve_passed']}`",
        "",
        "## 资产",
        "",
        f"- 已登记模板：`{assets['validated_template_count']}`",
        f"- 案例记忆：`{assets['case_memory_count']}`",
        f"- generated 下 MPH：`{assets['generated_mph_count']}`",
        "",
        "## P0 工作流",
        "",
        "- 工作流版本：`2.0.0`",
        "- 建模合同版本：`1.0.0`",
        "- 分阶段数量：`10`",
        f"- 测试：`{tests['count']}`，状态：`{tests['status']}`",
        "",
        "## 基准",
        "",
    ]
    for name, row in benchmarks.items():
        lines.append(f"- {name}：`{row.get('passed')}`，证据：`{row.get('path')}`")
    lines.extend(["", "## 证据路径", ""])
    lines.extend(f"- `{path}`" for path in report.get("evidence_paths", []))
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-count", type=int, default=0)
    parser.add_argument("--test-status", default="not_run")
    parser.add_argument("--output-dir", default=str(ROOT / "generated" / "baselines"))
    args = parser.parse_args()
    report = build_baseline(args.test_count, args.test_status)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "auto_modeling_baseline.json"
    md_path = output_dir / "auto_modeling_baseline.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_markdown(report), encoding="utf-8")
    print(json.dumps({"json": str(json_path), "markdown": str(md_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
