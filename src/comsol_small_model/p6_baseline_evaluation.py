from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


BOOLEAN_COLUMNS = (
    "completed",
    "physics_correct",
    "build_passed",
    "solve_passed",
    "validation_passed",
    "false_safe",
)


def prepare_baseline_template(task_report: str | Path, config_path: str | Path, output_path: str | Path) -> Path:
    task_data = json.loads(Path(task_report).read_text(encoding="utf-8"))
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    tasks = [row for row in task_data.get("rows", []) if isinstance(row, dict)]
    expected = int(config["required_task_count_per_method"])
    if len(tasks) != expected:
        raise ValueError(f"固定任务必须为 {expected} 条，当前为 {len(tasks)} 条。")
    rows: list[dict[str, Any]] = []
    for method in config["comparison_methods"]:
        for task in tasks:
            rows.append(
                {
                    "task_id": task["id"],
                    "domain": task.get("domain", ""),
                    "category": task.get("category", ""),
                    "method": method,
                    "record_status": "template",
                    "completed": "",
                    "physics_correct": "",
                    "build_passed": "",
                    "solve_passed": "",
                    "validation_passed": "",
                    "false_safe": "",
                    "completion_seconds": "",
                    "human_edits": "",
                    "interactions": "",
                    "evaluator_id": "",
                    "run_id": "",
                    "notes": "填写真实观测后将 record_status 改为 measured",
                }
            )
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(output, index=False, encoding="utf-8-sig")
    return output


def evaluate_baselines(csv_path: str | Path, config_path: str | Path, output_path: str | Path | None = None) -> dict[str, Any]:
    csv_file = Path(csv_path)
    config = json.loads(Path(config_path).read_text(encoding="utf-8"))
    fixed = json.loads(Path(config["fixed_task_report"]).read_text(encoding="utf-8"))
    expected_ids = {str(row["id"]) for row in fixed.get("rows", []) if isinstance(row, dict)}
    frame = pd.read_csv(csv_file, dtype="string")
    required = {
        "task_id", "method", "record_status", *BOOLEAN_COLUMNS,
        "completion_seconds", "human_edits", "interactions", "evaluator_id", "run_id",
    }
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError("P6 对照 CSV 缺少列：" + ", ".join(missing))
    active = frame[frame["record_status"].fillna("").str.strip().str.lower().isin({"measured", "valid"})].copy()
    methods = [str(value) for value in config["comparison_methods"]]
    expected_count = int(config["required_task_count_per_method"])
    if active.empty:
        report = _base_report(csv_file, "awaiting_measurements", False)
        report.update({"required_methods": methods, "required_task_count_per_method": expected_count, "methods": {}})
        return _write(report, output_path)

    active["task_id"] = active["task_id"].fillna("").str.strip()
    active["method"] = active["method"].fillna("").str.strip()
    unknown_methods = sorted(set(active["method"]).difference(methods))
    unknown_tasks = sorted(set(active["task_id"]).difference(expected_ids))
    if unknown_methods:
        raise ValueError("存在未声明的对照方法：" + ", ".join(unknown_methods))
    if unknown_tasks:
        raise ValueError("存在固定任务集之外的 task_id：" + ", ".join(unknown_tasks))
    if active.duplicated(["method", "task_id"]).any():
        raise ValueError("同一方法和 task_id 只能有一条 measured 记录。")

    for column in BOOLEAN_COLUMNS:
        active[column] = active[column].map(lambda value: _boolean(value, column))
    for column in ("completion_seconds", "human_edits", "interactions"):
        active[column] = active[column].map(lambda value: _nonnegative(value, column))
    if active["evaluator_id"].fillna("").str.strip().eq("").any():
        raise ValueError("每条 measured 记录必须填写 evaluator_id。")
    if active["run_id"].fillna("").str.strip().eq("").any():
        raise ValueError("每条 measured 记录必须填写 run_id。")

    method_reports: dict[str, Any] = {}
    for method in methods:
        subset = active[active["method"] == method]
        success = (
            subset["completed"]
            & subset["physics_correct"]
            & subset["build_passed"]
            & subset["solve_passed"]
            & subset["validation_passed"]
            & ~subset["false_safe"]
        )
        ids = set(subset["task_id"])
        coverage_complete = len(subset) == expected_count and ids == expected_ids
        method_reports[method] = {
            "measured_count": int(len(subset)),
            "coverage_complete": coverage_complete,
            "success_count": int(success.sum()),
            "success_rate": float(success.mean()) if len(subset) else 0.0,
            "false_safe_count": int(subset["false_safe"].sum()),
            "completion_seconds_median": float(subset["completion_seconds"].median()) if len(subset) else None,
            "human_edits_median": float(subset["human_edits"].median()) if len(subset) else None,
            "interactions_median": float(subset["interactions"].median()) if len(subset) else None,
        }
    complete = all(row["coverage_complete"] for row in method_reports.values())
    report = _base_report(csv_file, "complete" if complete else "collecting", complete)
    report.update(
        {
            "required_methods": methods,
            "required_task_count_per_method": expected_count,
            "measured_row_count": int(len(active)),
            "methods": method_reports,
            "interpretation": (
                "三种方法已在同一固定 60 任务集上形成完整外部对照证据。"
                if complete
                else "已有部分真实记录，但尚未覆盖三种方法的全部固定任务。"
            ),
        }
    )
    return _write(report, output_path)


def _base_report(source: Path, status: str, passed: bool) -> dict[str, Any]:
    return {
        "schema": "comsol-p6-baseline-evaluation-report",
        "schemaVersion": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_csv": str(source),
        "status": status,
        "passed": passed,
        "policy": "Only measured or valid rows count. Template rows never count as experimental evidence.",
    }


def _boolean(value: Any, name: str) -> bool:
    normalized = str(value).strip().lower()
    if normalized in {"true", "1", "yes", "y", "是"}:
        return True
    if normalized in {"false", "0", "no", "n", "否"}:
        return False
    raise ValueError(f"{name} 必须是明确的布尔值。")


def _nonnegative(value: Any, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} 必须是非负有限数。") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{name} 必须是非负有限数。")
    return number


def _write(report: dict[str, Any], output_path: str | Path | None) -> dict[str, Any]:
    if output_path is not None:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        report["report_path"] = str(output)
    return report
