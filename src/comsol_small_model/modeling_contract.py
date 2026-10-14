from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .workflow_status import (
    EVIDENCE_LEVEL_SET,
    RISK_LEVEL_SET,
    WORKFLOW_STATUS_SET,
    evidence_rank,
    normalize_workflow_status,
    validate_evidence_level,
)


CONTRACT_SCHEMA = "comsol-modeling-contract"
CONTRACT_VERSION = "1.0.0"

TOP_LEVEL_FIELDS = (
    "schema",
    "schemaVersion",
    "contract_id",
    "created_at",
    "updated_at",
    "status",
    "evidence_level",
    "raw_requirement",
    "task",
    "geometry",
    "materials",
    "physics",
    "boundary_conditions",
    "initial_conditions",
    "mesh",
    "study",
    "solver",
    "outputs",
    "validation",
    "evidence",
    "missing_information",
    "execution_policy",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_empty_contract(requirement: str, name: str = "") -> dict[str, Any]:
    requirement = " ".join(str(requirement or "").split())
    if not requirement:
        raise ValueError("requirement is empty")
    timestamp = now_iso()
    contract_id = _contract_id(requirement)
    return {
        "schema": CONTRACT_SCHEMA,
        "schemaVersion": CONTRACT_VERSION,
        "contract_id": contract_id,
        "created_at": timestamp,
        "updated_at": timestamp,
        "status": "draft",
        "evidence_level": "proposed",
        "raw_requirement": requirement,
        "task": {
            "name": name.strip() or contract_id,
            "goal": requirement,
            "completion_criteria": [],
            "language": "zh-CN" if re.search(r"[\u4e00-\u9fff]", requirement) else "en",
        },
        "geometry": {
            "dimension": "unknown",
            "source": "natural_language_requirement",
            "objects": [],
            "parameters": [],
            "named_selections": [],
        },
        "materials": [],
        "physics": {"interfaces": [], "couplings": [], "dependent_variables": []},
        "boundary_conditions": [],
        "initial_conditions": [],
        "mesh": {"strategy": [], "local_refinements": [], "independence_check": []},
        "study": {"types": [], "steps": []},
        "solver": {"strategy": [], "checks": []},
        "outputs": [],
        "validation": [],
        "evidence": [],
        "missing_information": [],
        "execution_policy": {
            "risk_level": "C",
            "allow_automatic_generation": False,
            "allow_automatic_solve": False,
            "max_retries": 0,
            "allowed_automatic_changes": [
                "api_label_reference",
                "result_dataset_reference",
            ],
        },
    }


def load_modeling_contract(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return migrate_modeling_contract(payload)


def save_modeling_contract(contract: dict[str, Any], path: str | Path) -> Path:
    normalized = migrate_modeling_contract(contract)
    normalized["updated_at"] = now_iso()
    report = validate_modeling_contract(normalized)
    if not report["valid"]:
        raise ValueError("invalid modeling contract: " + "; ".join(report["errors"]))
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    contract.clear()
    contract.update(normalized)
    return destination


def migrate_modeling_contract(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("modeling contract must be an object")
    if payload.get("schema") == CONTRACT_SCHEMA and payload.get("schemaVersion") == CONTRACT_VERSION:
        result = copy.deepcopy(payload)
        result["status"] = normalize_workflow_status(result.get("status"))
        return result

    requirement = str(payload.get("raw_requirement") or payload.get("requirement") or payload.get("task", {}).get("goal") or "").strip()
    if not requirement:
        raise ValueError("legacy contract has no requirement")
    result = create_empty_contract(requirement, str(payload.get("name", "")))
    for key in (
        "task",
        "geometry",
        "materials",
        "physics",
        "boundary_conditions",
        "initial_conditions",
        "mesh",
        "study",
        "solver",
        "outputs",
        "validation",
        "evidence",
        "missing_information",
        "execution_policy",
    ):
        if key in payload and isinstance(payload[key], type(result[key])):
            result[key] = copy.deepcopy(payload[key])
    result["status"] = normalize_workflow_status(payload.get("status"))
    if str(payload.get("evidence_level", "")) in EVIDENCE_LEVEL_SET:
        result["evidence_level"] = str(payload["evidence_level"])
    result["migration"] = {
        "source_schema": str(payload.get("schema", "legacy")),
        "source_version": str(payload.get("schemaVersion", "unversioned")),
        "migrated_at": now_iso(),
    }
    return result


def validate_modeling_contract(contract: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(contract, dict):
        return {"valid": False, "errors": ["contract must be an object"], "warnings": [], "ready_for_generation": False, "ready_for_solve": False}

    for field in TOP_LEVEL_FIELDS:
        if field not in contract:
            errors.append(f"missing top-level field: {field}")
    if contract.get("schema") != CONTRACT_SCHEMA:
        errors.append(f"schema must be {CONTRACT_SCHEMA}")
    if contract.get("schemaVersion") != CONTRACT_VERSION:
        errors.append(f"schemaVersion must be {CONTRACT_VERSION}")
    if str(contract.get("status", "")) not in WORKFLOW_STATUS_SET:
        errors.append("unsupported workflow status")
    if str(contract.get("evidence_level", "")) not in EVIDENCE_LEVEL_SET:
        errors.append("unsupported contract evidence_level")
    if not str(contract.get("raw_requirement", "")).strip():
        errors.append("raw_requirement is empty")

    task = contract.get("task", {})
    if not isinstance(task, dict):
        errors.append("task must be an object")
    elif not str(task.get("goal", "")).strip():
        errors.append("task.goal is empty")

    geometry = contract.get("geometry", {})
    if not isinstance(geometry, dict):
        errors.append("geometry must be an object")
    else:
        if geometry.get("dimension") not in {"unknown", "0D", "1D", "2D", "2D_axisymmetric", "3D"}:
            errors.append("geometry.dimension is invalid")
        _validate_quantities(geometry.get("parameters", []), "geometry.parameters", errors, warnings)

    materials = contract.get("materials", [])
    if not isinstance(materials, list):
        errors.append("materials must be a list")
    else:
        for index, material in enumerate(materials):
            if not isinstance(material, dict):
                errors.append(f"materials[{index}] must be an object")
                continue
            _validate_evidence(material, f"materials[{index}]", errors)
            if not str(material.get("selection", "")).strip():
                warnings.append(f"materials[{index}].selection is unresolved")
            _validate_quantities(material.get("properties", []), f"materials[{index}].properties", errors, warnings)

    physics = contract.get("physics", {})
    if not isinstance(physics, dict):
        errors.append("physics must be an object")
    else:
        _validate_tagged_items(physics.get("interfaces", []), "physics.interfaces", errors)
        _validate_tagged_items(physics.get("couplings", []), "physics.couplings", errors)

    for collection_name in ("boundary_conditions", "initial_conditions"):
        collection = contract.get(collection_name, [])
        if not isinstance(collection, list):
            errors.append(f"{collection_name} must be a list")
            continue
        for index, item in enumerate(collection):
            path = f"{collection_name}[{index}]"
            if not isinstance(item, dict):
                errors.append(f"{path} must be an object")
                continue
            _validate_evidence(item, path, errors)
            if not str(item.get("target", "")).strip():
                errors.append(f"{path}.target is empty")
            _validate_quantities(item.get("values", []), path + ".values", errors, warnings)

    _validate_unique_tags(contract, errors)

    study = contract.get("study", {})
    if not isinstance(study, dict) or not isinstance(study.get("types", []), list):
        errors.append("study.types must be a list")

    outputs = contract.get("outputs", [])
    if not isinstance(outputs, list):
        errors.append("outputs must be a list")

    missing = contract.get("missing_information", [])
    if not isinstance(missing, list):
        errors.append("missing_information must be a list")
        missing = []
    critical_missing = [item for item in missing if isinstance(item, dict) and item.get("severity") == "critical"]
    for index, item in enumerate(missing):
        if not isinstance(item, dict):
            errors.append(f"missing_information[{index}] must be an object")
            continue
        for field in ("category", "field", "severity", "question", "blocks_stage"):
            if not str(item.get(field, "")).strip():
                errors.append(f"missing_information[{index}].{field} is empty")
        if item.get("severity") not in {"critical", "warning"}:
            errors.append(f"missing_information[{index}].severity is invalid")

    policy = contract.get("execution_policy", {})
    if not isinstance(policy, dict):
        errors.append("execution_policy must be an object")
        policy = {}
    if policy.get("risk_level") not in RISK_LEVEL_SET:
        errors.append("execution_policy.risk_level is invalid")
    if bool(policy.get("allow_automatic_solve")) and critical_missing:
        errors.append("automatic solve cannot be enabled while critical information is missing")
    if bool(policy.get("allow_automatic_solve")) and policy.get("risk_level") != "A":
        errors.append("automatic solve is only allowed for risk level A")

    ready_for_generation = not errors and not critical_missing and bool((physics if isinstance(physics, dict) else {}).get("interfaces"))
    ready_for_solve = ready_for_generation and policy.get("risk_level") == "A" and bool(policy.get("allow_automatic_solve"))
    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "critical_missing_count": len(critical_missing),
        "ready_for_generation": ready_for_generation,
        "ready_for_solve": ready_for_solve,
    }


def add_missing_information(
    contract: dict[str, Any],
    category: str,
    field: str,
    question: str,
    blocks_stage: str,
    severity: str = "critical",
) -> None:
    if severity not in {"critical", "warning"}:
        raise ValueError("severity must be critical or warning")
    item = {
        "category": str(category),
        "field": str(field),
        "severity": severity,
        "question": str(question),
        "blocks_stage": str(blocks_stage),
    }
    rows = contract.setdefault("missing_information", [])
    key = (item["category"], item["field"])
    for index, current in enumerate(rows):
        if (current.get("category"), current.get("field")) == key:
            rows[index] = item
            break
    else:
        rows.append(item)
    if severity == "critical":
        contract["status"] = "missing_information"
        contract.setdefault("execution_policy", {})["allow_automatic_solve"] = False
    contract["updated_at"] = now_iso()


def resolve_missing_information(contract: dict[str, Any], category: str, field: str) -> bool:
    before = list(contract.get("missing_information", []))
    after = [item for item in before if (item.get("category"), item.get("field")) != (category, field)]
    contract["missing_information"] = after
    contract["updated_at"] = now_iso()
    if not any(item.get("severity") == "critical" for item in after):
        contract["status"] = "ready_for_review"
    return len(before) != len(after)


def update_field_evidence(contract: dict[str, Any], field: str, level: str, source: str) -> None:
    validate_evidence_level(level)
    timestamp = now_iso()
    rows = contract.setdefault("evidence", [])
    record = {"field": field, "level": level, "source": str(source), "timestamp": timestamp}
    for index, current in enumerate(rows):
        if current.get("field") == field:
            if evidence_rank(level) >= evidence_rank(current.get("level")):
                rows[index] = record
            break
    else:
        rows.append(record)
    contract["updated_at"] = timestamp


def compare_contracts(before: dict[str, Any], after: dict[str, Any]) -> list[dict[str, Any]]:
    changes: list[dict[str, Any]] = []
    _compare_values(before, after, "", changes)
    return changes


def contract_summary(contract: dict[str, Any]) -> dict[str, Any]:
    report = validate_modeling_contract(contract)
    return {
        "contract_id": contract.get("contract_id"),
        "status": contract.get("status"),
        "risk_level": contract.get("execution_policy", {}).get("risk_level"),
        "physics_interfaces": [item.get("name") for item in contract.get("physics", {}).get("interfaces", [])],
        "couplings": [item.get("name") for item in contract.get("physics", {}).get("couplings", [])],
        "geometry_dimension": contract.get("geometry", {}).get("dimension"),
        "material_count": len(contract.get("materials", [])),
        "boundary_count": len(contract.get("boundary_conditions", [])),
        "output_count": len(contract.get("outputs", [])),
        "missing_information": list(contract.get("missing_information", [])),
        "validation": report,
    }


def _validate_quantities(
    quantities: object,
    path: str,
    errors: list[str],
    warnings: list[str],
) -> None:
    if not isinstance(quantities, list):
        errors.append(f"{path} must be a list")
        return
    for index, item in enumerate(quantities):
        item_path = f"{path}[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{item_path} must be an object")
            continue
        if not str(item.get("name", "")).strip():
            errors.append(f"{item_path}.name is empty")
        _validate_evidence(item, item_path, errors)
        value = item.get("value")
        unit = str(item.get("unit", "")).strip()
        if isinstance(value, (int, float)) and not unit:
            errors.append(f"{item_path}.unit is required for numeric values")
        if value in (None, ""):
            warnings.append(f"{item_path}.value is unresolved")


def _validate_evidence(item: dict[str, Any], path: str, errors: list[str]) -> None:
    if str(item.get("evidence_level", "")) not in EVIDENCE_LEVEL_SET:
        errors.append(f"{path}.evidence_level is invalid")
    if "source" not in item:
        errors.append(f"{path}.source is missing")


def _validate_tagged_items(items: object, path: str, errors: list[str]) -> None:
    if not isinstance(items, list):
        errors.append(f"{path} must be a list")
        return
    for index, item in enumerate(items):
        item_path = f"{path}[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{item_path} must be an object")
            continue
        if not str(item.get("name", "")).strip():
            errors.append(f"{item_path}.name is empty")
        if not str(item.get("tag", "")).strip():
            errors.append(f"{item_path}.tag is empty")
        _validate_evidence(item, item_path, errors)


def _validate_unique_tags(contract: dict[str, Any], errors: list[str]) -> None:
    tagged_paths: list[tuple[str, list[Any]]] = [
        ("materials", contract.get("materials", [])),
        ("physics.interfaces", contract.get("physics", {}).get("interfaces", [])),
        ("physics.couplings", contract.get("physics", {}).get("couplings", [])),
        ("boundary_conditions", contract.get("boundary_conditions", [])),
        ("initial_conditions", contract.get("initial_conditions", [])),
    ]
    seen: dict[str, str] = {}
    for path, rows in tagged_paths:
        if not isinstance(rows, list):
            continue
        for index, row in enumerate(rows):
            if not isinstance(row, dict):
                continue
            tag = str(row.get("tag", "")).strip()
            if not tag:
                continue
            current_path = f"{path}[{index}]"
            if tag in seen:
                errors.append(f"duplicate COMSOL tag {tag}: {seen[tag]} and {current_path}")
            else:
                seen[tag] = current_path


def _compare_values(before: Any, after: Any, path: str, changes: list[dict[str, Any]]) -> None:
    if isinstance(before, dict) and isinstance(after, dict):
        for key in sorted(set(before) | set(after)):
            child = f"{path}.{key}" if path else key
            if key not in before:
                changes.append({"path": child, "change": "added", "before": None, "after": after[key]})
            elif key not in after:
                changes.append({"path": child, "change": "removed", "before": before[key], "after": None})
            else:
                _compare_values(before[key], after[key], child, changes)
        return
    if before != after:
        changes.append({"path": path, "change": "changed", "before": before, "after": after})


def _contract_id(requirement: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", requirement.lower()).strip("_")[:40] or "model"
    digest = hashlib.sha256(requirement.encode("utf-8")).hexdigest()[:10]
    return f"{normalized}_{digest}"
