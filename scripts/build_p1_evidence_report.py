from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from comsol_small_model.execution_jobs import JobStore


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "generated" / "p1"
TEMPLATES = (
    ("solid_heat", "固体传热", "configs/one_dimensional_heat_conduction.json", "generated/p1_execution_jobs/heat", "job_20261010041936_3505063a"),
    ("electric_current", "电流", "configs/one_dimensional_electric_current.json", "generated/p1_execution_jobs/current", "job_20261010042005_6556125a"),
    ("electrothermal", "电热耦合", "configs/one_dimensional_electrothermal.json", "generated/p1_execution_jobs/electrothermal", "job_20261010042032_b32119c0"),
    ("solid_mechanics", "固体力学", "configs/solid_mechanics_rectangle.json", "generated/p1_execution_jobs/solid", "job_20261010042103_2b649dc4"),
    ("flow_heat", "流热耦合", "configs/flow_heat_channel_2d.json", "generated/p1_execution_jobs/flow_heat_final", "job_20261010041659_beaba35f"),
    ("pressure_acoustics", "压力声学", "configs/one_dimensional_acoustic_tube.json", "generated/p1_execution_jobs/acoustic", "job_20261010040946_abe0631f"),
)


def _artifact(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"path": str(path.relative_to(ROOT)), "exists": False, "size_bytes": 0, "sha256": ""}
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"path": str(path.relative_to(ROOT)), "exists": True, "size_bytes": path.stat().st_size, "sha256": digest}


def build_report() -> dict[str, Any]:
    p6_java_path = ROOT / "generated" / "p6" / "java_dual_path" / "java_dual_path_report.json"
    p6_java = json.loads(p6_java_path.read_text(encoding="utf-8")) if p6_java_path.is_file() else {}
    java_rows = {
        str(item.get("id")): item
        for item in p6_java.get("templates", [])
        if isinstance(item, dict)
    }
    rows: list[dict[str, Any]] = []
    for template_id, name, config_path, store_path, job_id in TEMPLATES:
        store_root = ROOT / store_path
        job = JobStore(store_root).get(job_id)
        result = dict(job.get("result") or {})
        job_root = store_root / job_id
        validation = dict(result.get("result_validation") or {})
        artifacts = {
            "config": _artifact(ROOT / config_path),
            "matlab_builder": _artifact(next(job_root.glob("generated_build_*.m"), job_root / "missing_builder.m")),
            "runner": _artifact(job_root / f"run_{job_id}.m"),
            "mph": _artifact(job_root / f"{job_id}.mph"),
            "results_csv": _artifact(job_root / f"{job_id}_results.csv"),
            "preview_png": _artifact(job_root / f"{job_id}_preview.png"),
            "execution_evidence": _artifact(job_root / "execution_evidence.json"),
            "log": _artifact(store_root / "logs" / f"{job_id}.log"),
        }
        required = ("config", "matlab_builder", "runner", "mph", "results_csv", "preview_png", "execution_evidence")
        passed = job.get("status") == "completed" and validation.get("passed") is True and all(artifacts[key]["exists"] for key in required)
        java_evidence = java_rows.get(template_id, {})
        java_verified = bool(java_evidence.get("passed"))
        rows.append({
            "id": template_id,
            "name": name,
            "config_path": config_path,
            "job_store": store_path,
            "job_id": job_id,
            "job_status": job.get("status"),
            "physics": result.get("constraint_template", {}).get("physics", ""),
            "comsol_verified": passed,
            "result_validation": validation,
            "execution_duration_seconds": result.get("execution", {}).get("duration_seconds"),
            "artifacts": artifacts,
            "java_backup": {
                "status": "comsol_java_verified" if java_verified else "platform_generator_available_not_template_verified",
                "verified": java_verified,
                "source_java": java_evidence.get("java_path", ""),
                "source_java_sha256": java_evidence.get("java_sha256", ""),
                "rebuilt_mph": java_evidence.get("output_mph", ""),
                "rebuilt_mph_sha256": java_evidence.get("output_mph_sha256", ""),
                "compiled": bool(java_evidence.get("compiled")),
                "executed": bool(java_evidence.get("executed")),
                "note": (
                    "模板专用 Java 已由 COMSOL Java API 编译、重建、求解并保存新的 MPH。"
                    if java_verified
                    else "模板实机主路径为 MATLAB LiveLink；Java 备份尚未形成完整执行证据。"
                ),
            },
        })
    verified = sum(int(row["comsol_verified"]) for row in rows)
    java_verified = sum(int(row["java_backup"]["verified"]) for row in rows)
    return {
        "schema": "comsol-p1-template-maturity-report",
        "schemaVersion": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "host_scope": "current Windows workstation with MATLAB R2023b Update 6 and COMSOL 6.4 LiveLink",
        "summary": {
            "template_count": len(rows),
            "comsol_verified_count": verified,
            "runtime_gate_passed": verified == len(rows),
            "template_specific_java_backups_verified": java_verified,
            "java_dual_path_gate_passed": java_verified == len(rows),
        },
        "templates": rows,
        "remaining_delivery_gap": (
            "六类 MATLAB LiveLink 与模板专用 Java 双路径均已通过本机 COMSOL 6.4 实机验证。"
            if java_verified == len(rows)
            else "六类 MATLAB LiveLink 模板已实机通过；仍有模板专用 Java 备份未通过 COMSOL Java API 验证。"
        ),
    }


def write_report(report: dict[str, Any]) -> tuple[Path, Path]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUT_DIR / "template_maturity.json"
    md_path = OUTPUT_DIR / "template_maturity.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# P1 六类 COMSOL 模板成熟度报告",
        "",
        f"生成时间：{report['generated_at']}",
        "",
        f"实机运行门：{'通过' if report['summary']['runtime_gate_passed'] else '未通过'}（{report['summary']['comsol_verified_count']}/{report['summary']['template_count']}）",
        f"Java 双路径门：{'通过' if report['summary']['java_dual_path_gate_passed'] else '未通过'}（{report['summary']['template_specific_java_backups_verified']}/{report['summary']['template_count']}）",
        "",
        "| 类别 | Job | MATLAB/物理验收 | Java 重建求解 | 耗时 s | MPH 字节 | 预览 |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in report["templates"]:
        lines.append(
            f"| {row['name']} | `{row['job_id']}` | "
            f"{'通过' if row['result_validation'].get('passed') else '未通过'} | "
            f"{'通过' if row['java_backup'].get('verified') else '未通过'} | "
            f"{row['execution_duration_seconds']} | {row['artifacts']['mph']['size_bytes']} | "
            f"{'有' if row['artifacts']['preview_png']['exists'] else '无'} |"
        )
    lines.extend(["", "## 当前缺口", "", report["remaining_delivery_gap"], ""])
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


if __name__ == "__main__":
    report = build_report()
    paths = write_report(report)
    print(json.dumps({"summary": report["summary"], "paths": [str(path) for path in paths]}, ensure_ascii=False, indent=2))
