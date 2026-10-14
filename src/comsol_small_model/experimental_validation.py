from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .surrogate_runtime import load_surrogate_payload, predict_validated_surrogate


DEFAULT_CONFIG: dict[str, Any] = {
    "schema": "comsol-temperature-experiment-validation-config",
    "schemaVersion": "1.0.0",
    "minimum_measured_samples": 5,
    "required_outputs": ["Tmax_K", "Tavg_K"],
    "absolute_tolerance_K": {"Tmax_K": 5.0, "Tavg_K": 5.0},
    "require_comsol_values": True,
    "require_all_rows_in_validated_domain": True,
}


def validate_temperature_experiment(
    csv_path: str | Path,
    model_path: str | Path,
    *,
    config_path: str | Path | None = None,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Compare measured temperatures with COMSOL and a validated surrogate.

    Measurement uncertainty is an expanded 95% uncertainty (``u95``).  A
    comparison passes when the absolute deviation is no larger than the
    declared engineering tolerance plus the measurement uncertainty.  The
    surrogate interval is also tested for overlap with the measurement
    interval, but it is reported separately and does not replace the error
    gate.
    """
    csv_file = Path(csv_path)
    model_file = Path(model_path)
    config = _load_config(config_path)
    payload = load_surrogate_payload(model_file)
    inputs = [str(value) for value in payload.get("input_columns", [])]
    model_outputs = [str(value) for value in payload.get("output_columns", [])]
    required_outputs = [str(value) for value in config["required_outputs"]]
    unknown_outputs = [name for name in required_outputs if name not in model_outputs]
    if unknown_outputs:
        raise ValueError("配置要求的输出不在代理模型中：" + ", ".join(unknown_outputs))

    frame = pd.read_csv(csv_file, dtype={"sample_id": "string", "record_status": "string"})
    required_columns = ["sample_id", "record_status", *inputs]
    for name in required_outputs:
        required_columns.extend((f"measured_{name}", f"measurement_u95_{name}"))
        if bool(config["require_comsol_values"]):
            required_columns.append(f"comsol_{name}")
    missing_columns = [name for name in required_columns if name not in frame.columns]
    if missing_columns:
        raise ValueError("实验 CSV 缺少列：" + ", ".join(missing_columns))

    active = frame[
        frame["record_status"].fillna("").str.strip().str.lower().isin({"measured", "valid"})
    ].copy()
    if active.empty:
        report = _pending_report(csv_file, model_file, config, inputs, required_outputs)
        return _write_report(report, output_path)

    active["sample_id"] = active["sample_id"].fillna("").str.strip()
    if (active["sample_id"] == "").any():
        raise ValueError("每条 measured 记录都必须有 sample_id。")
    duplicates = active.loc[active["sample_id"].duplicated(), "sample_id"].tolist()
    if duplicates:
        raise ValueError("sample_id 重复：" + ", ".join(sorted(set(duplicates))))

    rows: list[dict[str, Any]] = []
    for _, source in active.iterrows():
        supplied = {name: _finite(source[name], name) for name in inputs}
        prediction = predict_validated_surrogate(model_file, supplied)
        row: dict[str, Any] = {
            "sample_id": str(source["sample_id"]),
            "inputs": supplied,
            "in_validated_domain": bool(prediction.get("ok")),
            "confidence": prediction.get("confidence", {}),
            "outputs": {},
        }
        for name in required_outputs:
            measured = _finite(source[f"measured_{name}"], f"measured_{name}")
            u95 = _finite(source[f"measurement_u95_{name}"], f"measurement_u95_{name}")
            if u95 < 0:
                raise ValueError(f"measurement_u95_{name} 不能为负数。")
            tolerance = _tolerance(config, name)
            output: dict[str, Any] = {
                "measured": measured,
                "measurement_u95": u95,
                "measurement_interval_95": [measured - u95, measured + u95],
                "engineering_tolerance": tolerance,
            }

            comsol_column = f"comsol_{name}"
            comsol = _optional_finite(source.get(comsol_column), comsol_column)
            output["comsol"] = _comparison(measured, u95, comsol, tolerance)

            surrogate_value = None
            if prediction.get("ok"):
                surrogate_value = _optional_finite(
                    dict(prediction.get("prediction", {})).get(name), f"surrogate_{name}"
                )
            surrogate = _comparison(measured, u95, surrogate_value, tolerance)
            interval = (
                dict(dict(prediction.get("uncertainty", {})).get("intervals", {})).get(name, {})
                if prediction.get("ok")
                else {}
            )
            lower = _optional_finite(dict(interval).get("lower"), f"interval_lower_{name}")
            upper = _optional_finite(dict(interval).get("upper"), f"interval_upper_{name}")
            surrogate["prediction_interval_95"] = [lower, upper] if lower is not None and upper is not None else None
            surrogate["measurement_interval_overlaps_prediction_interval"] = (
                max(measured - u95, lower) <= min(measured + u95, upper)
                if lower is not None and upper is not None
                else None
            )
            output["surrogate"] = surrogate
            row["outputs"][name] = output
        rows.append(row)

    metrics = {
        name: {
            "comsol_vs_measurement": _aggregate(rows, name, "comsol"),
            "surrogate_vs_measurement": _aggregate(rows, name, "surrogate"),
        }
        for name in required_outputs
    }
    minimum = int(config["minimum_measured_samples"])
    enough_samples = len(rows) >= minimum
    all_in_domain = all(bool(row["in_validated_domain"]) for row in rows)
    all_comparisons = all(
        bool(row["outputs"][name][source]["passed"])
        for row in rows
        for name in required_outputs
        for source in ("comsol", "surrogate")
        if source != "comsol" or bool(config["require_comsol_values"])
    )
    passed = enough_samples and all_comparisons and (
        all_in_domain or not bool(config["require_all_rows_in_validated_domain"])
    )
    report = {
        "schema": "comsol-temperature-experiment-validation-report",
        "schemaVersion": "1.0.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "passed" if passed else "failed",
        "passed": passed,
        "source_csv": str(csv_file),
        "model_path": str(model_file),
        "policy": config,
        "sample_count": len(rows),
        "minimum_sample_count_met": enough_samples,
        "all_rows_in_validated_domain": all_in_domain,
        "metrics": metrics,
        "rows": rows,
        "interpretation": (
            "实验、COMSOL 与代理模型满足当前样本量、适用域和误差门槛。"
            if passed
            else "现有实验证据未满足发布门槛；请根据逐行结果补测、校准物理模型或回到 COMSOL。"
        ),
    }
    return _write_report(report, output_path)


def _load_config(config_path: str | Path | None) -> dict[str, Any]:
    config = json.loads(json.dumps(DEFAULT_CONFIG))
    if config_path is not None:
        supplied = json.loads(Path(config_path).read_text(encoding="utf-8"))
        if not isinstance(supplied, dict):
            raise ValueError("实验验证配置必须是 JSON 对象。")
        config.update(supplied)
    minimum = int(config["minimum_measured_samples"])
    if minimum < 1:
        raise ValueError("minimum_measured_samples 必须至少为 1。")
    if not isinstance(config.get("required_outputs"), list) or not config["required_outputs"]:
        raise ValueError("required_outputs 必须是非空数组。")
    return config


def _pending_report(
    csv_file: Path,
    model_file: Path,
    config: dict[str, Any],
    inputs: list[str],
    outputs: list[str],
) -> dict[str, Any]:
    return {
        "schema": "comsol-temperature-experiment-validation-report",
        "schemaVersion": "1.0.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "awaiting_measurements",
        "passed": False,
        "source_csv": str(csv_file),
        "model_path": str(model_file),
        "policy": config,
        "sample_count": 0,
        "required_input_columns": inputs,
        "required_output_columns": outputs,
        "rows": [],
        "interpretation": "模板中尚无 record_status=measured 的真实测量记录，不能声明物理实验验证通过。",
    }


def _comparison(measured: float, u95: float, value: float | None, tolerance: float) -> dict[str, Any]:
    if value is None:
        return {"available": False, "value": None, "passed": False, "reason": "missing_value"}
    error = value - measured
    limit = tolerance + u95
    return {
        "available": True,
        "value": value,
        "error": error,
        "absolute_error": abs(error),
        "acceptance_limit": limit,
        "passed": abs(error) <= limit,
    }


def _aggregate(rows: list[dict[str, Any]], output: str, source: str) -> dict[str, Any]:
    comparisons = [row["outputs"][output][source] for row in rows]
    available = [item for item in comparisons if item["available"]]
    if not available:
        return {"available_count": 0, "pass_count": 0, "pass_rate": 0.0}
    errors = np.asarray([float(item["error"]) for item in available], dtype=float)
    passed = sum(bool(item["passed"]) for item in available)
    return {
        "available_count": len(available),
        "pass_count": passed,
        "pass_rate": passed / len(available),
        "bias_K": float(np.mean(errors)),
        "mae_K": float(np.mean(np.abs(errors))),
        "rmse_K": float(np.sqrt(np.mean(errors**2))),
        "max_absolute_error_K": float(np.max(np.abs(errors))),
    }


def _tolerance(config: dict[str, Any], output: str) -> float:
    values = config.get("absolute_tolerance_K", {})
    value = float(values.get(output, 5.0) if isinstance(values, dict) else values)
    if value < 0 or not math.isfinite(value):
        raise ValueError(f"{output} 的 absolute_tolerance_K 必须是非负有限数。")
    return value


def _finite(value: Any, name: str) -> float:
    result = _optional_finite(value, name)
    if result is None:
        raise ValueError(f"{name} 必须是有限数值。")
    return result


def _optional_finite(value: Any, name: str) -> float | None:
    if value is None or (isinstance(value, str) and not value.strip()) or pd.isna(value):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} 必须是有限数值。") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} 必须是有限数值。")
    return number


def _write_report(report: dict[str, Any], output_path: str | Path | None) -> dict[str, Any]:
    if output_path is not None:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        report["report_path"] = str(path)
    return report
