from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


def write_thermal_plate_model_card(
    *,
    spec: dict[str, Any],
    training_csv: str | Path,
    model_path: str | Path,
    validation: dict[str, Any],
    output_dir: str | Path,
) -> dict[str, Any]:
    """Persist the physical scope and evidence behind a trained thermal surrogate."""
    csv_path = Path(training_csv)
    data = pd.read_csv(csv_path)
    inputs = list(spec.get("inputs", []))
    ranges = {
        name: {"min": float(data[name].min()), "max": float(data[name].max()), "unit": _unit(name)}
        for name in inputs
    }
    card = {
        "kind": "comsol_surrogate_model_card",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "name": "二维稳态导热板代理模型",
        "model_path": str(Path(model_path)),
        "training_data": {"path": str(csv_path), "rows": int(len(data)), "inputs": inputs, "outputs": list(spec.get("outputs", []))},
        "physical_model": {
            "comsol_interface": "Heat Transfer in Solids (2D, stationary)",
            "governing_equation": "∇·(k∇T)=0",
            "geometry": "二维矩形板，长度 L_m、宽度 W_m",
            "material": "各向同性常数导热系数 k_W_mK",
            "boundary_conditions": ["左侧边界：恒温 T_hot_K", "右侧边界：恒温 T_cold_K", "其余边界：默认绝热"],
            "outputs": ["Tmax_K：域内最高温度", "Tavg_K：域内平均温度"],
        },
        "validated_input_ranges": ranges,
        "independent_comsol_validation": validation,
        "use_policy": {
            "allowed": "仅用于上述物理模型、几何拓扑、材料假设和输入范围内的快速比较。",
            "requires_comsol": "输入越界、材料随温度变化、边界类型改变、几何拓扑改变或最终设计定稿。",
        },
    }
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    json_path = destination / "thermal_plate_surrogate_model_card.json"
    markdown_path = destination / "thermal_plate_surrogate_model_card.md"
    json_path.write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_to_markdown(card), encoding="utf-8")
    return {"json_path": str(json_path), "markdown_path": str(markdown_path), "card": card}


def write_general_surrogate_model_card(
    *,
    model_name: str,
    model_path: str | Path,
    training_csv: str | Path,
    holdout_csv: str | Path,
    input_columns: list[str],
    output_columns: list[str],
    physical_scope: str,
    validation: dict[str, Any],
    output_dir: str | Path,
) -> dict[str, Any]:
    """Write a portable evidence card for a user-defined COMSOL surrogate."""
    training_path = Path(training_csv)
    data = pd.read_csv(training_path)
    ranges = {
        name: {"min": float(data[name].min()), "max": float(data[name].max())}
        for name in input_columns
    }
    card = {
        "kind": "comsol_general_surrogate_model_card",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "name": model_name,
        "model_path": str(Path(model_path)),
        "training_data": {"path": str(training_path), "rows": int(len(data)), "inputs": input_columns, "outputs": output_columns},
        "holdout_data": {"path": str(Path(holdout_csv)), "rows": int(len(pd.read_csv(holdout_csv)))},
        "physical_scope": physical_scope,
        "validated_input_ranges": ranges,
        "independent_comsol_validation": validation,
        "use_policy": {
            "allowed": "仅在模型卡所述物理范围、几何拓扑、边界条件和输入范围内用于快速比较。",
            "requires_comsol": "输入越界、输出为零需绝对误差判据、物理范围不完整或最终设计定稿时必须回到 COMSOL。",
        },
    }
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    stem = Path(model_path).stem
    json_path = destination / f"{stem}_model_card.json"
    markdown_path = destination / f"{stem}_model_card.md"
    json_path.write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        f"# {model_name} 模型卡", "", "## 物理适用范围", physical_scope or "未填写；不得作为工程决策依据。", "",
        "## 训练与独立验证", f"- 训练数据：{training_path}，{len(data)} 行", f"- 独立 COMSOL 留出集：{holdout_csv}", f"- 验证通过：{validation.get('passed', False)}", f"- 最大相对误差：{validation.get('max_relative_error_percent', {})}", f"- 阈值：{validation.get('threshold_relative_error_percent', '')}%", "",
        "## 已验证输入范围", *[f"- {name}: {item['min']} 到 {item['max']}" for name, item in ranges.items()], "",
        "## 使用限制", f"- 可用：{card['use_policy']['allowed']}", f"- 必须回到 COMSOL：{card['use_policy']['requires_comsol']}",
    ]
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json_path": str(json_path), "markdown_path": str(markdown_path), "card": card}


def register_general_surrogate(
    *,
    model_name: str,
    model_path: str | Path,
    card: dict[str, Any],
    validation: dict[str, Any],
    registry_path: str | Path,
) -> dict[str, Any]:
    """Register a scoped surrogate without treating data validation as engineering certification."""
    destination = Path(registry_path)
    if destination.is_file():
        registry = json.loads(destination.read_text(encoding="utf-8"))
    else:
        registry = {"schema": "comsol-surrogate-registry", "schemaVersion": "1.0.0", "models": []}
    models = list(registry.get("models", []))
    status = "validated_for_declared_scope" if validation.get("passed") else "needs_more_comsol_evidence"
    entry = {
        "id": Path(model_path).stem,
        "name": model_name,
        "status": status,
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "model_path": str(Path(model_path)),
        "model_card": card.get("markdown_path", ""),
        "model_card_json": card.get("json_path", ""),
        "validation_report": validation.get("path", ""),
        "physical_scope": card.get("card", {}).get("physical_scope", ""),
        "validated_input_ranges": card.get("card", {}).get("validated_input_ranges", {}),
        "validation_passed": bool(validation.get("passed")),
        "release_note": "Data-validated only within the declared scope; this is not experimental or engineering certification.",
    }
    models = [item for item in models if item.get("id") != entry["id"]]
    models.append(entry)
    registry["models"] = models
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"path": str(destination), "entry": entry, "models": models}


def mark_surrogates_superseded(
    registry_path: str | Path,
    model_ids: list[str],
    *,
    replacement_id: str,
    reason: str,
) -> dict[str, Any]:
    """Record explicit model lineage without rewriting historical validation status."""
    destination = Path(registry_path)
    registry = json.loads(destination.read_text(encoding="utf-8"))
    models = [dict(item) for item in registry.get("models", []) if isinstance(item, dict)]
    by_id = {str(item.get("id", "")): item for item in models}
    replacement = by_id.get(replacement_id)
    if replacement is None:
        raise ValueError(f"replacement model is not registered: {replacement_id}")
    if (
        replacement.get("status") != "validated_for_declared_scope"
        or not replacement.get("validation_passed")
    ):
        raise ValueError("replacement model must have passed independent COMSOL validation")

    targets = [str(model_id).strip() for model_id in model_ids if str(model_id).strip()]
    if not targets:
        raise ValueError("at least one superseded model id is required")
    missing = [model_id for model_id in targets if model_id not in by_id]
    if missing:
        raise ValueError("superseded models are not registered: " + ", ".join(missing))
    if replacement_id in targets:
        raise ValueError("replacement model cannot supersede itself")
    clean_reason = " ".join(str(reason or "").split())
    if not clean_reason:
        raise ValueError("supersession reason is required")

    timestamp = datetime.now(timezone.utc).isoformat()
    for model_id in targets:
        item = by_id[model_id]
        unchanged_lineage = (
            item.get("lifecycle_status") == "superseded"
            and item.get("superseded_by") == replacement_id
            and item.get("supersession_reason") == clean_reason
        )
        item["lifecycle_status"] = "superseded"
        item["superseded_by"] = replacement_id
        if not unchanged_lineage or not item.get("superseded_at"):
            item["superseded_at"] = timestamp
        item["supersession_reason"] = clean_reason
    replacement["lifecycle_status"] = "active"
    existing_supersedes = replacement.get("supersedes", [])
    if not isinstance(existing_supersedes, list):
        existing_supersedes = []
    replacement["supersedes"] = sorted(set([*existing_supersedes, *targets]))

    registry["models"] = models
    destination.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "path": str(destination),
        "replacement_id": replacement_id,
        "superseded_ids": targets,
        "superseded_at": timestamp,
        "reason": clean_reason,
    }


def consolidate_surrogate_registries(
    canonical_path: str | Path,
    legacy_path: str | Path,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Copy legacy-only entries into the canonical registry without resolving conflicts implicitly."""
    canonical_destination = Path(canonical_path)
    legacy_source = Path(legacy_path)
    if not legacy_source.is_file():
        return {
            "ok": True,
            "changed": False,
            "dry_run": dry_run,
            "canonical_path": str(canonical_destination),
            "legacy_path": str(legacy_source),
            "imported_ids": [],
            "duplicate_ids": [],
            "conflicting_ids": [],
        }
    if canonical_destination.is_file():
        canonical = json.loads(canonical_destination.read_text(encoding="utf-8"))
    else:
        canonical = {
            "schema": "comsol-surrogate-registry",
            "schemaVersion": "1.0.0",
            "models": [],
        }
    legacy = json.loads(legacy_source.read_text(encoding="utf-8"))
    canonical_models = [
        dict(item) for item in canonical.get("models", []) if isinstance(item, dict)
    ]
    canonical_by_id = {str(item.get("id", "")): item for item in canonical_models}
    imported: list[str] = []
    duplicates: list[str] = []
    conflicts: list[str] = []
    pending: list[dict[str, Any]] = []
    for item in legacy.get("models", []):
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("id", ""))
        existing = canonical_by_id.get(model_id)
        if existing is None:
            imported.append(model_id)
            pending.append(dict(item))
        elif existing == item:
            duplicates.append(model_id)
        else:
            conflicts.append(model_id)
    if conflicts:
        return {
            "ok": False,
            "changed": False,
            "dry_run": dry_run,
            "canonical_path": str(canonical_destination),
            "legacy_path": str(legacy_source),
            "imported_ids": [],
            "pending_import_ids": imported,
            "duplicate_ids": sorted(duplicates),
            "conflicting_ids": sorted(conflicts),
            "guidance": "存在同 ID 但内容不同的条目；请人工核对模型卡与验证证据，不能自动覆盖正式注册表。",
        }
    if pending and not dry_run:
        canonical["models"] = [*canonical_models, *pending]
        canonical_destination.parent.mkdir(parents=True, exist_ok=True)
        canonical_destination.write_text(
            json.dumps(canonical, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return {
        "ok": True,
        "changed": bool(pending) and not dry_run,
        "dry_run": dry_run,
        "canonical_path": str(canonical_destination),
        "legacy_path": str(legacy_source),
        "imported_ids": sorted(imported),
        "duplicate_ids": sorted(duplicates),
        "conflicting_ids": [],
    }


def _unit(name: str) -> str:
    return {"L_m": "m", "W_m": "m", "k_W_mK": "W/(m·K)", "T_hot_K": "K", "T_cold_K": "K"}.get(name, "")


def _to_markdown(card: dict[str, Any]) -> str:
    physical = card["physical_model"]
    ranges = card["validated_input_ranges"]
    validation = card.get("independent_comsol_validation", {})
    lines = [
        "# 二维稳态导热板代理模型卡片",
        "",
        "## 物理模型",
        f"- COMSOL 接口：{physical['comsol_interface']}",
        f"- 控制方程：{physical['governing_equation']}",
        f"- 几何：{physical['geometry']}",
        f"- 材料：{physical['material']}",
        *[f"- 边界：{item}" for item in physical["boundary_conditions"]],
        "",
        "## 已验证输入范围",
        *[f"- {name}: {item['min']} 到 {item['max']} {item['unit']}" for name, item in ranges.items()],
        "",
        "## 独立 COMSOL 验证",
        f"- 通过：{validation.get('passed', False)}",
        f"- 最大绝对误差：{validation.get('max_absolute_error', {})}",
        "",
        "## 使用限制",
        f"- 可用：{card['use_policy']['allowed']}",
        f"- 必须回到 COMSOL：{card['use_policy']['requires_comsol']}",
    ]
    return "\n".join(lines) + "\n"
