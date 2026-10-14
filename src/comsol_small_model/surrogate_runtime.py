from __future__ import annotations

import json
import math
import re
import warnings
from datetime import datetime, timezone
from pathlib import Path
from statistics import NormalDist
from typing import Any

import joblib
import numpy as np
import pandas as pd


JOBLIB_NUMPY_SHAPE_WARNING = (
    r"Setting the shape on a NumPy array has been deprecated in NumPy 2\.5\."
)


def extract_thermal_plate_prediction_inputs(text: str) -> dict[str, float] | None:
    """Recognize a complete thermal-plate prediction request from a Chinese prompt."""
    source = str(text or "")
    values = {
        "L_m": _find_value(source, [r"板长", r"长度", r"\bL\s*[=:：]"], _length_to_m),
        "W_m": _find_value(source, [r"板宽", r"宽度", r"\bW\s*[=:：]"], _length_to_m),
        "k_W_mK": _find_value(source, [r"导热系数", r"\bk\s*[=:：]"], _identity),
        "T_hot_K": _find_value(source, [r"高温端", r"热端", r"热侧", r"T_hot", r"Thot"], _temperature_to_k),
        "T_cold_K": _find_value(source, [r"低温端", r"冷端", r"冷侧", r"T_cold", r"Tcold"], _temperature_to_k),
    }
    if any(value is None for value in values.values()):
        return None
    return {name: float(value) for name, value in values.items()}


def extract_joule_rectangle_prediction_inputs(text: str) -> dict[str, float] | None:
    """Recognize the declared-scope rectangle Joule-heating prediction request."""
    source = str(text or "")
    if not is_joule_rectangle_prediction_request(source):
        return None
    voltage = _find_value(source, [r"端电压", r"电压", r"\bv(?:tot)?\s*[=:：]"], _voltage_to_v)
    if voltage is None:
        match = re.search(r"([-+]?\d+(?:\.\d+)?)\s*(mV|mv|毫伏|V|v|伏)", source)
        if match:
            voltage = _voltage_to_v(float(match.group(1)), match.group(2))
    return {"Vtot_V": float(voltage)} if voltage is not None else None


def extract_thermal_actuator_prediction_inputs(text: str) -> dict[str, float] | None:
    """Recognize a bounded micro-actuator Joule-heating prediction request."""
    source = str(text or "")
    if not (is_thermal_actuator_prediction_request(source) or is_thermal_actuator_augmentation_request(source)):
        return None
    values = {
        "DV_V": _find_value(source, [r"\bDV\s*[=:：]", r"驱动电压", r"电压"], _voltage_to_v),
        "htc_s_W_m2K": _find_value(source, [r"\bhtc_s\s*[=:：]", r"表面换热系数"], _identity),
        "htc_us_W_m2K": _find_value(source, [r"\bhtc_us\s*[=:：]", r"下表面换热系数", r"底部换热系数"], _identity),
    }
    if any(value is None for value in values.values()):
        return None
    return {name: float(value) for name, value in values.items()}


def is_thermal_actuator_prediction_request(text: str) -> bool:
    """Return true only for the validated distributed-parameter actuator scope."""
    lowered = str(text or "").lower()
    is_actuator = any(token in lowered for token in ("微执行器", "热执行器", "thermal actuator", "thermal_actuator"))
    asks_for_temperature = any(
        token in lowered for token in ("温度预测", "预测温度", "预测最高温", "预测", "tmax", "predict")
    )
    return is_actuator and asks_for_temperature


def is_thermal_actuator_augmentation_request(text: str) -> bool:
    """Recognize a request to expand the validated actuator surrogate with COMSOL data."""
    lowered = str(text or "").lower()
    is_actuator = any(token in lowered for token in ("微执行器", "热执行器", "thermal actuator", "thermal_actuator"))
    asks_to_expand = any(token in lowered for token in ("扩展训练", "补充训练", "补样", "补充样本", "扩展范围", "augmentation"))
    return is_actuator and asks_to_expand

def is_joule_rectangle_prediction_request(text: str) -> bool:
    """Return true only when the user asks for a Joule-heating temperature prediction."""
    lowered = str(text or "").lower()
    is_joule_request = any(
        token in lowered
        for token in ("焦耳热", "joule", "通电发热", "通电加热", "电阻发热", "电热")
    )
    asks_for_temperature = any(
        token in lowered
        for token in ("温度预测", "预测温度", "预测最高温", "预测平均温", "预测", "tmax", "tavg", "predict")
    )
    return is_joule_request and asks_for_temperature


def detect_joule_rectangle_scope_changes(text: str) -> list[str]:
    """Identify explicit conditions that differ from the validated Joule benchmark."""
    source = str(text or "")
    lowered = source.lower()
    changes: list[str] = []
    length = _find_value(source, [r"板长", r"长度", r"\bL\s*[=:：]"], _length_to_m)
    width = _find_value(source, [r"板宽", r"宽度", r"\bW\s*[=:：]"], _length_to_m)
    if length is not None and abs(length - 0.1) > 1e-9:
        changes.append("长度不是已验证的 100 mm")
    if width is not None and abs(width - 0.05) > 1e-9:
        changes.append("宽度不是已验证的 50 mm")
    if any(token in lowered for token in ("铝", "钢", "aluminum", "aluminium", "steel")):
        changes.append("材料不是已验证的铜")
    if any(token in lowered for token in ("对流换热系数", "换热系数", "htc")):
        changes.append("显式给出了对流边界参数，可能不同于标杆固定条件")
    if any(token in lowered for token in ("三维", "3d", "轴对称", "一维", "1d")):
        changes.append("模型维度不是已验证的二维矩形")
    return changes


def latest_validated_thermal_model(jobs_root: str | Path) -> Path:
    """Return the most recently written COMSOL-validated thermal surrogate."""
    root = Path(jobs_root)
    models = sorted(
        root.glob("*/thermal_plate_surrogate*validated.joblib"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    if not models:
        raise FileNotFoundError("未找到已经通过 COMSOL 独立验证的二维传热代理模型。请先执行传热扫描训练。")
    return models[0]


def predict_validated_surrogate(model_path: str | Path, supplied_inputs: dict[str, Any]) -> dict[str, Any]:
    """Predict only within the training envelope, retaining the validation evidence."""
    path = Path(model_path)
    payload = load_surrogate_payload(path)
    input_columns = list(payload["input_columns"])
    output_columns = list(payload["output_columns"])
    missing = [name for name in input_columns if name not in supplied_inputs]
    if missing:
        raise ValueError(f"缺少代理模型输入参数：{', '.join(missing)}")

    values: dict[str, float] = {}
    for name in input_columns:
        try:
            values[name] = float(supplied_inputs[name])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"参数 {name} 必须是数值。") from exc

    training_csv = Path(str(payload.get("training_csv_path", "")))
    # The training data can be wider than the region covered by the final
    # independent COMSOL validation.  A declared validated envelope therefore
    # takes precedence over raw training minima/maxima; the CSV remains useful
    # for nearest-sample distance and as a fallback for legacy payloads.
    embedded_ranges = payload.get("validated_input_ranges")
    if not isinstance(embedded_ranges, dict):
        embedded_ranges = _validated_ranges_from_model_card(path)
    if isinstance(embedded_ranges, dict):
        ranges = {
            name: {
                "min": float(embedded_ranges[name]["min"]),
                "max": float(embedded_ranges[name]["max"]),
            }
            for name in input_columns
            if isinstance(embedded_ranges.get(name), dict)
            and "min" in embedded_ranges[name]
            and "max" in embedded_ranges[name]
        }
        if len(ranges) != len(input_columns):
            raise ValueError("代理模型载荷中的已验证输入范围不完整。")
    elif training_csv.is_file():
        data = pd.read_csv(training_csv)
        ranges = {
            name: {"min": float(data[name].min()), "max": float(data[name].max())}
            for name in input_columns
        }
    else:
        raise FileNotFoundError(f"代理模型缺少训练数据范围记录：{training_csv}")
    out_of_range = {
        name: {"value": value, **ranges[name]}
        for name, value in values.items()
        if value < ranges[name]["min"] or value > ranges[name]["max"]
    }
    validation = _load_holdout_validation(path)
    model_card = _load_model_card(path)
    training_data = _load_training_data(path, payload, input_columns)
    if out_of_range:
        quality = assess_prediction_quality(
            inputs=values,
            validated_ranges=ranges,
            prediction={},
            validation=validation,
            training_data=training_data,
        )
        return {
            "ok": False,
            "model_path": str(path),
            "model_name": payload.get("model_name", "unknown"),
            "inputs": values,
            "validated_ranges": ranges,
            "out_of_range": out_of_range,
            "validation": validation,
            "model_card": model_card,
            **quality,
            "guidance": "输入超出训练和独立 COMSOL 验证覆盖范围。本次不输出代理预测，请改用 COMSOL 真实求解，并把新结果补入训练集。",
        }

    feature_values = [values[name] for name in input_columns]
    if "model" in payload:
        estimator = payload["model"]
        predicted = estimator.predict(
            _prediction_features(estimator, feature_values, input_columns)
        )[0]
        if getattr(predicted, "ndim", 0) == 0:
            predicted = [predicted]
    elif isinstance(payload.get("models"), dict):
        # Some validated cases train one estimator per output so each response
        # can use its own cross-validated model family.
        predicted = []
        missing_models = []
        for name in output_columns:
            estimator = payload["models"].get(name)
            if estimator is None:
                missing_models.append(name)
                continue
            value = estimator.predict(
                _prediction_features(estimator, feature_values, input_columns)
            )[0]
            predicted.append(value.item() if hasattr(value, "item") else value)
        if missing_models:
            raise ValueError(
                "多输出代理模型缺少输出估计器：" + ", ".join(missing_models)
            )
    else:
        raise ValueError("代理模型载荷缺少 model 或 models 输出估计器。")
    log_transformed_outputs = set(payload.get("log_transformed_outputs", []))
    output_signs = payload.get("output_signs", {})
    prediction = {
        name: float(10 ** value) * float(output_signs.get(name, 1.0))
        if name in log_transformed_outputs else float(value)
        for name, value in zip(output_columns, predicted)
    }
    quality = assess_prediction_quality(
        inputs=values,
        validated_ranges=ranges,
        prediction=prediction,
        validation=validation,
        training_data=training_data,
    )
    return {
        "ok": True,
        "model_path": str(path),
        "model_name": payload.get("model_name", "unknown"),
        "inputs": values,
        "prediction": prediction,
        "validated_ranges": ranges,
        "validation": validation,
        "model_card": model_card,
        **quality,
        "guidance": "预测位于当前训练范围内。该结果可用于快速方案比较；定稿、外推或边界条件变化时仍应执行 COMSOL 真实求解。",
    }


def load_surrogate_payload(model_path: str | Path) -> dict[str, Any]:
    """Load a joblib payload while isolating one known NumPy 2.5 compatibility warning."""
    with warnings.catch_warnings():
        warnings.filterwarnings(
            "ignore",
            message=JOBLIB_NUMPY_SHAPE_WARNING,
            category=DeprecationWarning,
            module=r"joblib\.numpy_pickle",
        )
        payload = joblib.load(Path(model_path))
    if not isinstance(payload, dict):
        raise ValueError("代理模型载荷必须是字典。")
    return payload


def predict_registered_surrogate(
    registry_path: str | Path,
    model_id: str,
    supplied_inputs: dict[str, Any],
) -> dict[str, Any]:
    """Allow prediction only for a registry entry that passed its declared-scope validation."""
    source = Path(registry_path)
    if not source.is_file():
        raise FileNotFoundError("尚未创建代理模型注册表。请先完成独立 COMSOL 验证训练。")
    registry = json.loads(source.read_text(encoding="utf-8"))
    entry = next((item for item in registry.get("models", []) if item.get("id") == model_id), None)
    if entry is None:
        raise ValueError(f"注册表中没有模型：{model_id}")
    if entry.get("status") != "validated_for_declared_scope" or not entry.get("validation_passed"):
        return {
            "ok": False,
            "model_id": model_id,
            "registry_status": entry.get("status", "unknown"),
            "guidance": "该模型没有通过独立 COMSOL 留出集验证，不能用于代理预测。请补充真实 COMSOL 样本并重新验证。",
        }
    resolved_entry = dict(entry)
    for field in ("model_path", "model_card", "model_card_json", "validation_report"):
        resolved_entry[field] = str(_resolve_registry_artifact(source, str(entry.get(field, ""))))
    result = predict_validated_surrogate(Path(resolved_entry["model_path"]), supplied_inputs)
    result["model_id"] = model_id
    result["registry_status"] = entry["status"]
    result["declared_scope"] = entry.get("physical_scope", "")
    result["validation"] = _load_registered_validation(resolved_entry)
    result["model_card"] = _load_registered_model_card(resolved_entry)
    payload = load_surrogate_payload(Path(resolved_entry["model_path"]))
    result.update(
        assess_prediction_quality(
            inputs=dict(result.get("inputs", {})),
            validated_ranges=dict(result.get("validated_ranges", {})),
            prediction=dict(result.get("prediction", {})),
            validation=result["validation"],
            training_data=_load_training_data(
                Path(resolved_entry["model_path"]),
                payload,
                list(payload.get("input_columns", [])),
            ),
        )
    )
    return result


def assess_prediction_quality(
    *,
    inputs: dict[str, float],
    validated_ranges: dict[str, dict[str, float]],
    prediction: dict[str, float],
    validation: dict[str, Any],
    training_data: pd.DataFrame | None = None,
    confidence_level: float = 0.95,
) -> dict[str, Any]:
    """Return domain checks, calibrated intervals, and a user-facing confidence grade."""
    if not 0.5 < confidence_level < 1.0:
        raise ValueError("confidence_level must be between 0.5 and 1.0")

    out_of_range: dict[str, dict[str, float]] = {}
    normalized_position: dict[str, float] = {}
    margins: list[float] = []
    for name, value in inputs.items():
        limits = validated_ranges.get(name, {})
        if "min" not in limits or "max" not in limits:
            continue
        lower, upper = float(limits["min"]), float(limits["max"])
        if value < lower or value > upper:
            out_of_range[name] = {"value": float(value), "min": lower, "max": upper}
            continue
        span = upper - lower
        position = 0.5 if abs(span) < 1e-15 else (float(value) - lower) / span
        normalized_position[name] = float(position)
        margins.append(min(position, 1.0 - position))

    domain_status = "outside" if out_of_range else "inside"
    boundary_margin = min(margins) if margins else None
    nearest_distance = _nearest_training_distance(inputs, validated_ranges, training_data)
    domain = {
        "status": domain_status,
        "out_of_range": out_of_range,
        "normalized_position": normalized_position,
        "minimum_boundary_margin_fraction": boundary_margin,
        "near_boundary": bool(boundary_margin is not None and boundary_margin < 0.1),
        "nearest_training_distance_normalized": nearest_distance,
    }

    intervals: dict[str, dict[str, Any]] = {}
    for name, estimate in prediction.items():
        half_width, method, evidence = _prediction_half_width(
            name,
            float(estimate),
            validation,
            confidence_level,
        )
        if half_width is None or not math.isfinite(half_width):
            intervals[name] = {
                "available": False,
                "confidence_level": confidence_level,
                "reason": "独立留出集没有提供可用于校准区间的残差或误差指标。",
            }
            continue
        intervals[name] = {
            "available": True,
            "confidence_level": confidence_level,
            "lower": float(estimate) - half_width,
            "upper": float(estimate) + half_width,
            "half_width": half_width,
            "method": method,
            "calibration_evidence": evidence,
        }

    score = 100
    reasons: list[str] = []
    if out_of_range:
        score = 0
        reasons.append("至少一个输入超出已验证训练范围")
    else:
        if boundary_margin is not None and boundary_margin < 0.05:
            score -= 25
            reasons.append("输入接近训练范围边界")
        elif boundary_margin is not None and boundary_margin < 0.15:
            score -= 12
            reasons.append("输入位于训练范围的边缘区域")
        if nearest_distance is not None and nearest_distance > 0.75:
            score -= 25
            reasons.append("当前参数组合远离已有训练样本")
        elif nearest_distance is not None and nearest_distance > 0.4:
            score -= 12
            reasons.append("当前参数组合附近的训练样本较稀疏")

    if not validation.get("available", False):
        score -= 30
        reasons.append("没有可用的独立 COMSOL 留出验证")
    elif not validation.get("passed", False):
        score -= 55
        reasons.append("独立 COMSOL 留出验证未通过")

    available_intervals = [item for item in intervals.values() if item.get("available")]
    if prediction and not available_intervals:
        score -= 20
        reasons.append("无法从留出误差校准预测区间")
    relative_widths = []
    for name, item in intervals.items():
        if item.get("available"):
            denominator = max(abs(float(prediction.get(name, 0.0))), 1e-12)
            relative_widths.append(2.0 * float(item["half_width"]) / denominator)
    if relative_widths and max(relative_widths) > 0.5:
        score -= 25
        reasons.append("预测区间相对预测值较宽")
    elif relative_widths and max(relative_widths) > 0.2:
        score -= 12
        reasons.append("预测区间存在明显宽度")

    score = max(0, min(100, score))
    level = "high" if score >= 85 else "medium" if score >= 60 else "low"
    labels = {"high": "高", "medium": "中", "low": "低"}
    if not reasons:
        reasons.append("输入位于已验证范围内部，且独立留出误差支持当前预测区间")
    return {
        "input_domain": domain,
        "uncertainty": {
            "confidence_level": confidence_level,
            "intervals": intervals,
            "calibrated_from_holdout": bool(available_intervals),
        },
        "confidence": {
            "level": level,
            "label": labels[level],
            "score": score,
            "reasons": reasons,
            "requires_comsol": level == "low" or bool(out_of_range),
            "reminder": (
                "可信度较低，建议提交 COMSOL 高保真求解并将结果加入新的训练/留出设计。"
                if level == "low" or out_of_range
                else "可用于当前已验证范围内的快速比较；最终设计仍建议由 COMSOL 复核。"
            ),
        },
    }


def write_registered_augmentation_plan(
    registry_path: str | Path,
    model_id: str,
    supplied_inputs: dict[str, Any],
    output_dir: str | Path,
) -> dict[str, Any]:
    """Turn a registered-model extrapolation request into traceable COMSOL sample conditions."""
    prediction = predict_registered_surrogate(registry_path, model_id, supplied_inputs)
    if prediction.get("ok"):
        raise ValueError("输入已在已验证范围内，不需要生成补充 COMSOL 扫描计划。")
    if "out_of_range" not in prediction:
        raise ValueError(str(prediction.get("guidance", "当前模型不能生成补充扫描计划。")))
    center = dict(prediction["inputs"])
    ranges = dict(prediction["validated_ranges"])
    samples = [center]
    for name, item in prediction["out_of_range"].items():
        span = float(item["max"]) - float(item["min"])
        value = float(item["value"])
        delta = max(span * 0.2, abs(value) * 0.05, 1e-9)
        for candidate in (value - delta, value + delta):
            row = dict(center)
            row[name] = candidate
            samples.append(row)
    unique_samples: list[dict[str, float]] = []
    for row in samples:
        if row not in unique_samples:
            unique_samples.append(row)
    plan = {
        "kind": "comsol-registered-surrogate-augmentation-plan",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model_id": model_id,
        "model_path": prediction.get("model_path", ""),
        "physical_scope": prediction.get("declared_scope", ""),
        "reason": "请求输入超出已验证代理模型范围；必须先使用相同物理范围的 COMSOL 模型获得真实补充样本。",
        "requested_inputs": center,
        "out_of_range": prediction["out_of_range"],
        "existing_validated_ranges": ranges,
        "recommended_comsol_samples": unique_samples,
        "sample_count": len(unique_samples),
        "required_follow_up": [
            "用模型卡声明的同一物理场、几何、材料、边界条件和研究类型逐点执行 COMSOL。",
            "为新 CSV 创建 augmentation 数据清单，记录 COMSOL 版本、研究和网格来源。",
            "合并训练数据后使用未参与训练的新 COMSOL 留出集重新验证，不能复用旧留出集。"
        ]
    }
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    path = destination / f"{model_id}_augmentation_{stamp}.json"
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    plan["path"] = str(path)
    return plan


def write_thermal_augmentation_plan(
    model_path: str | Path,
    supplied_inputs: dict[str, Any],
    output_dir: str | Path,
) -> dict[str, Any]:
    """Create a compact COMSOL sampling plan around an out-of-range request."""
    prediction = predict_validated_surrogate(model_path, supplied_inputs)
    if prediction["ok"]:
        raise ValueError("输入已在验证范围内，不需要创建补充扫描计划。")
    center = dict(prediction["inputs"])
    ranges = dict(prediction["validated_ranges"])
    out_of_range = dict(prediction["out_of_range"])
    samples = [center]
    for name, item in out_of_range.items():
        span = float(item["max"]) - float(item["min"])
        value = float(item["value"])
        delta = max(span * 0.2, abs(value) * 0.05, 1.0 if name.startswith("T_") else 0.001)
        for candidate in (value - delta, value + delta):
            row = dict(center)
            row[name] = candidate
            samples.append(row)
    deduplicated: list[dict[str, float]] = []
    for row in samples:
        if row not in deduplicated:
            deduplicated.append(row)
    plan = {
        "kind": "comsol_thermal_surrogate_augmentation_plan",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "model_path": str(Path(model_path)),
        "reason": "用户请求超出已验证代理模型范围，需要先由 COMSOL 生成真实补充样本。",
        "requested_inputs": center,
        "out_of_range": out_of_range,
        "existing_validated_ranges": ranges,
        "recommended_comsol_samples": deduplicated,
        "sample_count": len(deduplicated),
        "execution_order": [
            "用 Heat Transfer in Solids 的同一二维矩形板模型逐点求解。",
            "导出 L_m、W_m、k_W_mK、T_hot_K、T_cold_K、Tmax_K、Tavg_K 到 CSV。",
            "将新 CSV 与原训练集汇合，并使用新的独立 COMSOL 工况重新验证。",
        ],
    }
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    path = destination / f"thermal_plate_augmentation_{stamp}.json"
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    plan["path"] = str(path)
    return plan


def _load_holdout_validation(model_path: Path) -> dict[str, Any]:
    candidates = [
        model_path.with_name(f"{model_path.stem}.holdout_validation.json"),
        model_path.with_name("thermal_sweep_holdout_validation.json"),
        model_path.with_name("thermal_augmentation_holdout_validation.json"),
    ]
    report_path = next((path for path in candidates if path.is_file()), None)
    if report_path is None:
        return {"available": False}
    report = json.loads(report_path.read_text(encoding="utf-8"))
    return {
        "available": True,
        "path": str(report_path),
        "passed": bool(report.get("passed")),
        "criterion": report.get("criterion", ""),
        "max_absolute_error": report.get("max_absolute_error", {}),
        "rows": len(report.get("rows", [])),
        "error_quantile_95": _absolute_error_quantiles(report.get("rows", [])),
    }


def _load_model_card(model_path: Path) -> dict[str, Any]:
    card_path = _model_card_path(model_path)
    if card_path is None:
        return {"available": False}
    card = json.loads(card_path.read_text(encoding="utf-8"))
    return {
        "available": True,
        "path": str(card_path),
        "name": card.get("name", ""),
        "physical_scope": card.get("physical_scope", ""),
        "validated_input_ranges": card.get("validated_input_ranges", {}),
        "use_policy": card.get("use_policy", {}),
    }


def _model_card_path(model_path: Path) -> Path | None:
    candidates = [
        model_path.with_name(f"{model_path.stem}_model_card.json"),
        model_path.with_name("thermal_plate_surrogate_model_card.json"),
    ]
    return next((candidate for candidate in candidates if candidate.is_file()), None)


def _validated_ranges_from_model_card(model_path: Path) -> dict[str, Any] | None:
    card_path = _model_card_path(model_path)
    if card_path is None:
        return None
    card = json.loads(card_path.read_text(encoding="utf-8"))
    ranges = card.get("validated_input_ranges")
    return ranges if isinstance(ranges, dict) else None


def _resolve_registry_artifact(registry_path: Path, raw_path: str) -> Path:
    path = Path(raw_path)
    if path.is_file():
        return path
    if path.name:
        relocated = registry_path.parent / path.name
        if relocated.is_file():
            return relocated
    return path


def _load_registered_validation(entry: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(entry.get("validation_report", "")))
    if not path.is_file():
        return {"available": False}
    report = json.loads(path.read_text(encoding="utf-8"))
    raw_metrics = report.get("max_absolute_error", {})
    per_output = {
        str(name): {key: float(value) for key, value in values.items() if key in {"rmse", "mae", "r2"}}
        for name, values in raw_metrics.items()
        if isinstance(values, dict)
    }
    return {
        "available": True,
        "path": str(path),
        "passed": bool(report.get("passed")),
        "selected_model": report.get("selected_model", ""),
        "training_rows": report.get("training_rows", 0),
        "holdout_rows": report.get("holdout_rows", 0),
        "rmse_threshold_k": report.get("rmse_threshold_k"),
        "threshold_relative_error_percent": report.get("threshold_relative_error_percent"),
        "candidate_reports": report.get("candidate_reports", {}),
        "per_output": per_output,
        "per_output_relative_validation": report.get("per_output_relative_validation", {}),
        "error_quantile_95": _absolute_error_quantiles(report.get("rows", [])),
    }


def _absolute_error_quantiles(rows: Any) -> dict[str, float]:
    if not isinstance(rows, list):
        return {}
    errors: dict[str, list[float]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw = row.get("absolute_error", {})
        if not isinstance(raw, dict):
            continue
        for name, value in raw.items():
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            if math.isfinite(numeric):
                errors.setdefault(str(name), []).append(abs(numeric))
    return {
        name: float(np.quantile(values, 0.95, method="higher"))
        for name, values in errors.items()
        if values
    }


def _prediction_half_width(
    output_name: str,
    estimate: float,
    validation: dict[str, Any],
    confidence_level: float,
) -> tuple[float | None, str, dict[str, Any]]:
    empirical = validation.get("error_quantile_95", {})
    if isinstance(empirical, dict) and output_name in empirical:
        value = abs(float(empirical[output_name]))
        return value, "empirical_holdout_absolute_error_quantile", {"quantile": 0.95, "value": value}

    per_output = validation.get("per_output", {})
    metrics = per_output.get(output_name, {}) if isinstance(per_output, dict) else {}
    if isinstance(metrics, dict) and metrics.get("rmse") is not None:
        rmse = abs(float(metrics["rmse"]))
        z_value = NormalDist().inv_cdf((1.0 + confidence_level) / 2.0)
        return z_value * rmse, "holdout_rmse_normal_approximation", {"rmse": rmse, "z": z_value}

    absolute = validation.get("max_absolute_error", {})
    if isinstance(absolute, dict) and output_name in absolute:
        raw = absolute[output_name]
        if isinstance(raw, dict):
            raw = raw.get("rmse", raw.get("mae"))
        try:
            value = abs(float(raw))
        except (TypeError, ValueError):
            value = float("nan")
        if math.isfinite(value):
            return value, "holdout_reported_absolute_error", {"value": value}

    relative = validation.get("per_output_relative_validation", {})
    relative_metrics = relative.get(output_name, {}) if isinstance(relative, dict) else {}
    if isinstance(relative_metrics, dict):
        percentage = relative_metrics.get("max_relative_error_percent")
        if percentage is None:
            percentage = relative_metrics.get("rmse_relative_error_percent")
        try:
            fraction = abs(float(percentage)) / 100.0
        except (TypeError, ValueError):
            fraction = float("nan")
        if math.isfinite(fraction):
            return abs(estimate) * fraction, "holdout_relative_error_bound", {"relative_error_percent": fraction * 100.0}
    return None, "unavailable", {}


def _load_training_data(
    model_path: Path,
    payload: dict[str, Any],
    input_columns: list[str],
) -> pd.DataFrame | None:
    raw = Path(str(payload.get("training_csv_path", "")))
    candidates = [raw, model_path.parent / raw.name, model_path.parent.parent / raw.name]
    source = next((candidate for candidate in candidates if candidate.name and candidate.is_file()), None)
    if source is None or not input_columns:
        return None
    try:
        data = pd.read_csv(source)
    except Exception:  # noqa: BLE001
        return None
    return data if all(name in data.columns for name in input_columns) else None


def _nearest_training_distance(
    inputs: dict[str, float],
    validated_ranges: dict[str, dict[str, float]],
    training_data: pd.DataFrame | None,
) -> float | None:
    if training_data is None or training_data.empty:
        return None
    names = [name for name in inputs if name in training_data.columns and name in validated_ranges]
    if not names:
        return None
    query: list[float] = []
    matrix_columns: list[np.ndarray] = []
    for name in names:
        lower = float(validated_ranges[name]["min"])
        upper = float(validated_ranges[name]["max"])
        span = upper - lower
        if abs(span) < 1e-15:
            continue
        query.append((float(inputs[name]) - lower) / span)
        matrix_columns.append((training_data[name].to_numpy(dtype=float) - lower) / span)
    if not matrix_columns:
        return None
    matrix = np.column_stack(matrix_columns)
    distances = np.linalg.norm(matrix - np.asarray(query, dtype=float), axis=1)
    return float(np.min(distances)) if len(distances) else None


def _load_registered_model_card(entry: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(entry.get("model_card_json", "")))
    if not path.is_file():
        return {"available": False}
    card = json.loads(path.read_text(encoding="utf-8"))
    return {
        "available": True,
        "path": str(path),
        "name": card.get("name", ""),
        "physical_scope": card.get("physical_scope", ""),
        "validated_input_ranges": card.get("validated_input_ranges", {}),
    }


def _prediction_features(
    estimator: Any,
    feature_values: list[float],
    input_columns: list[str],
) -> Any:
    """Preserve feature names only for estimators that were fitted with them."""
    if hasattr(estimator, "feature_names_in_"):
        return pd.DataFrame([feature_values], columns=input_columns)
    return [feature_values]


def _find_value(source: str, names: list[str], converter: Any) -> float | None:
    number = r"([-+]?\d+(?:\.\d+)?)"
    unit = r"\s*([A-Za-z/()²^·]+|毫米|厘米|米|摄氏度|度|℃)?"
    for name in names:
        match = re.search(rf"(?:{name})\s*(?:为|是|=|:|：)?\s*{number}{unit}", source, flags=re.IGNORECASE)
        if match:
            return converter(float(match.group(1)), (match.group(2) or "").strip())
    return None


def _length_to_m(value: float, unit: str) -> float:
    normalized = unit.lower()
    if normalized in {"mm", "毫米"}:
        return value / 1000.0
    if normalized in {"cm", "厘米"}:
        return value / 100.0
    return value


def _temperature_to_k(value: float, unit: str) -> float:
    if unit.lower() in {"c", "°c", "℃", "摄氏度", "度"}:
        return value + 273.15
    return value


def _voltage_to_v(value: float, unit: str) -> float:
    if unit.lower() in {"mv", "毫伏"}:
        return value / 1000.0
    return value


def _identity(value: float, unit: str) -> float:
    return value
