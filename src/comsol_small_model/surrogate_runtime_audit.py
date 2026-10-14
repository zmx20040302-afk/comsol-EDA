from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from .surrogate_runtime import load_surrogate_payload, predict_registered_surrogate


ARTIFACT_FIELDS = ("model_path", "model_card", "model_card_json", "validation_report")
VALIDATED_STATUS = "validated_for_declared_scope"


def audit_registered_surrogates(
    registry_path: str | Path,
    *,
    simulate_relocation: bool = False,
) -> dict[str, Any]:
    """Audit registered artifacts and exercise every validated model at its range midpoint."""
    source = Path(registry_path).resolve()
    registry_bytes = source.read_bytes()
    registry = json.loads(registry_bytes.decode("utf-8"))
    entries = registry.get("models", [])
    if not isinstance(entries, list):
        raise ValueError("代理模型注册表的 models 字段必须是列表。")

    rows = [
        _audit_entry(source, entry, simulate_relocation=simulate_relocation)
        for entry in entries
        if isinstance(entry, dict)
    ]
    validated_rows = [row for row in rows if row["eligible_for_prediction"]]
    superseded_rows = [row for row in rows if row["lifecycle_status"] == "superseded"]
    active_unvalidated_rows = [
        row
        for row in rows
        if not row["eligible_for_prediction"] and row["lifecycle_status"] == "active"
    ]
    passed = sum(bool(row["ok"]) for row in validated_rows)
    missing_artifacts = sum(
        len(row["missing_artifacts"])
        for row in rows
    )
    warning_count = sum(int(row["warning_count"]) for row in validated_rows)
    feature_name_warning_count = sum(
        int(row["feature_name_warning_count"])
        for row in validated_rows
    )
    relocation_failures = sum(
        bool(row.get("relocation_tested")) and not bool(row.get("relocation_ok"))
        for row in validated_rows
    )
    compatibility_notices = _dependency_compatibility_notices()
    return {
        "schema": "comsol-surrogate-runtime-audit",
        "schema_version": "1.1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "registry_path": str(source),
        "registry_sha256": hashlib.sha256(registry_bytes).hexdigest(),
        "registered_models": len(rows),
        "validated_models": len(validated_rows),
        "superseded_models": len(superseded_rows),
        "active_unvalidated_models": len(active_unvalidated_rows),
        "skipped_unvalidated_models": len(rows) - len(validated_rows),
        "passed": passed,
        "failed": len(validated_rows) - passed,
        "missing_artifacts": missing_artifacts,
        "warning_count": warning_count,
        "feature_name_warning_count": feature_name_warning_count,
        "compatibility_notices": compatibility_notices,
        "relocation_tested": bool(simulate_relocation),
        "relocation_failures": relocation_failures,
        "overall_passed": (
            passed == len(validated_rows)
            and missing_artifacts == 0
            and relocation_failures == 0
        ),
        "rows": rows,
    }


def write_runtime_audit(report: dict[str, Any], output_path: str | Path) -> Path:
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return destination


def _audit_entry(
    registry_path: Path,
    entry: dict[str, Any],
    *,
    simulate_relocation: bool,
) -> dict[str, Any]:
    model_id = str(entry.get("id", ""))
    status = str(entry.get("status", "unknown"))
    lifecycle_status = str(entry.get("lifecycle_status", "active"))
    artifacts = {
        field: _resolve_artifact(registry_path, str(entry.get(field, "")))
        for field in ARTIFACT_FIELDS
    }
    missing_artifacts = [field for field, path in artifacts.items() if not path.is_file()]
    eligible = (
        status == VALIDATED_STATUS
        and bool(entry.get("validation_passed"))
        and lifecycle_status == "active"
    )
    row: dict[str, Any] = {
        "id": model_id,
        "status": status,
        "lifecycle_status": lifecycle_status,
        "superseded_by": str(entry.get("superseded_by", "")),
        "eligible_for_prediction": eligible,
        "artifacts": {field: str(path) for field, path in artifacts.items()},
        "missing_artifacts": missing_artifacts,
        "midpoint_inputs": {},
        "expected_outputs": [],
        "predicted_outputs": [],
        "warnings": [],
        "warning_count": 0,
        "feature_name_warning_count": 0,
        "ok": False,
        "error": "",
    }
    if not eligible:
        row["skip_reason"] = (
            f"历史模型已由 {entry.get('superseded_by', '')} 替代。"
            if lifecycle_status == "superseded"
            else "模型尚未通过声明范围内的独立 COMSOL 验证。"
        )
        return row
    if missing_artifacts:
        row["error"] = "缺少已验证模型所需文件：" + ", ".join(missing_artifacts)
        return row

    caught: list[Any] = []
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            payload = load_surrogate_payload(artifacts["model_path"])
            expected_outputs = [str(name) for name in payload.get("output_columns", [])]
            midpoint_inputs = _midpoint_inputs(entry, payload, artifacts["model_card_json"])
            row["expected_outputs"] = expected_outputs
            row["midpoint_inputs"] = midpoint_inputs
            result = predict_registered_surrogate(registry_path, model_id, midpoint_inputs)
        predicted_outputs = list(result.get("prediction", {}))
        row["predicted_outputs"] = predicted_outputs
        if not result.get("ok"):
            raise ValueError(str(result.get("guidance", "运行时拒绝预测。")))
        if not expected_outputs:
            raise ValueError("模型载荷没有 output_columns。")
        if set(predicted_outputs) != set(expected_outputs):
            raise ValueError("预测输出列与模型载荷声明不一致。")
        row["validation_evidence_available"] = bool(result.get("validation", {}).get("available"))
        if not row["validation_evidence_available"]:
            raise ValueError("运行时未能读取独立验证报告。")
        row["ok"] = True
        if simulate_relocation:
            relocation = _audit_relocation(registry_path, entry, artifacts, midpoint_inputs)
            row.update(relocation)
            row["ok"] = row["ok"] and bool(relocation["relocation_ok"])
    except Exception as exc:  # The report must retain failures from heterogeneous sklearn payloads.
        row["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        row["warnings"] = _summarize_warnings(caught)
        row["warning_count"] = len(caught)
        row["feature_name_warning_count"] = sum(
            "feature names" in str(item.message).lower()
            for item in caught
        )
    return row


def _midpoint_inputs(
    entry: dict[str, Any],
    payload: dict[str, Any],
    model_card_path: Path,
) -> dict[str, float]:
    ranges = entry.get("validated_input_ranges")
    if not isinstance(ranges, dict):
        ranges = payload.get("validated_input_ranges")
    if not isinstance(ranges, dict) and model_card_path.is_file():
        card = json.loads(model_card_path.read_text(encoding="utf-8"))
        ranges = card.get("validated_input_ranges")
    if not isinstance(ranges, dict):
        raise ValueError("注册表、模型载荷和模型卡均缺少已验证输入范围。")

    midpoint: dict[str, float] = {}
    for name in payload.get("input_columns", []):
        bounds = ranges.get(name)
        if not isinstance(bounds, dict) or "min" not in bounds or "max" not in bounds:
            raise ValueError(f"输入 {name} 缺少 min/max 范围。")
        midpoint[str(name)] = (float(bounds["min"]) + float(bounds["max"])) / 2.0
    if not midpoint:
        raise ValueError("模型载荷没有 input_columns。")
    return midpoint


def _audit_relocation(
    registry_path: Path,
    entry: dict[str, Any],
    artifacts: dict[str, Path],
    midpoint_inputs: dict[str, float],
) -> dict[str, Any]:
    try:
        with tempfile.TemporaryDirectory(prefix="surrogate_runtime_audit_") as directory:
            destination = Path(directory)
            relocated_entry = dict(entry)
            for field, source in artifacts.items():
                target = destination / source.name
                shutil.copy2(source, target)
                relocated_entry[field] = str(Path("Z:/missing/surrogate_bundle") / source.name)
            model_path = destination / artifacts["model_path"].name
            payload = load_surrogate_payload(model_path)
            payload["training_csv_path"] = "Z:/missing/training.csv"
            joblib.dump(payload, model_path)
            relocated_registry = dict(
                schema="comsol-surrogate-registry",
                schemaVersion="1.0.0",
                models=[relocated_entry],
            )
            relocated_registry_path = destination / registry_path.name
            relocated_registry_path.write_text(
                json.dumps(relocated_registry, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            result = predict_registered_surrogate(
                relocated_registry_path,
                str(entry.get("id", "")),
                midpoint_inputs,
            )
        return {
            "relocation_tested": True,
            "relocation_ok": bool(result.get("ok")),
            "relocation_error": "" if result.get("ok") else str(result.get("guidance", "")),
        }
    except Exception as exc:
        return {
            "relocation_tested": True,
            "relocation_ok": False,
            "relocation_error": f"{type(exc).__name__}: {exc}",
        }


def _resolve_artifact(registry_path: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_file():
        return path
    if path.name:
        relocated = registry_path.parent / path.name
        if relocated.is_file():
            return relocated
    return path


def _summarize_warnings(caught: list[Any]) -> list[dict[str, Any]]:
    summary: dict[tuple[str, str], int] = {}
    for item in caught:
        key = (item.category.__name__, str(item.message))
        summary[key] = summary.get(key, 0) + 1
    return [
        {"category": category, "message": message, "count": count}
        for (category, message), count in summary.items()
    ]


def _dependency_compatibility_notices() -> list[dict[str, str]]:
    notices: list[dict[str, str]] = []
    if _version_tuple(np.__version__) >= (2, 5) and _version_tuple(joblib.__version__) < (1, 6):
        notices.append(
            {
                "dependency": "numpy/joblib",
                "installed": f"numpy {np.__version__}, joblib {joblib.__version__}",
                "message": (
                    "joblib 1.5.x 在 NumPy 2.5 下会触发数组 shape 赋值弃用提示；"
                    "运行时已精确过滤该提示，新部署环境应遵循 requirements.txt 的 NumPy 上限。"
                ),
            }
        )
    return notices


def _version_tuple(value: str) -> tuple[int, ...]:
    parts = []
    for item in value.split("."):
        digits = "".join(character for character in item if character.isdigit())
        if not digits:
            break
        parts.append(int(digits))
    return tuple(parts)
