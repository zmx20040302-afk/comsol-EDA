from __future__ import annotations

import math
from typing import Any


PHYSICS_CATALOG: tuple[dict[str, Any], ...] = (
    {
        "id": "heat_transfer_solids",
        "display_name": "Heat Transfer in Solids",
        "matlab_interface": "HeatTransfer",
        "interface_tag": "ht",
        "module": "Heat Transfer Module",
        "dimensions": [1, 2, 3],
        "studies": ["Stationary", "TimeDependent"],
        "material_properties": ["thermalconductivity", "density", "heatcapacity"],
        "keywords": ["固体传热", "热传导", "导热", "温度场", "散热", "heat conduction", "heat transfer in solid"],
        "domains": ["heat_transfer"],
        "validation_level": "verified_on_current_host",
    },
    {
        "id": "electric_currents",
        "display_name": "Electric Currents",
        "matlab_interface": "ConductiveMedia",
        "interface_tag": "ec",
        "module": "AC/DC Module",
        "dimensions": [1, 2, 3],
        "studies": ["Stationary", "Frequency"],
        "material_properties": ["electricconductivity", "relpermittivity"],
        "keywords": ["电流", "电势", "电压", "端子", "接地", "电阻", "electric current", "conductive media"],
        "domains": ["electromagnetics"],
        "validation_level": "verified_on_current_host",
    },
    {
        "id": "solid_mechanics",
        "display_name": "Solid Mechanics",
        "matlab_interface": "SolidMechanics",
        "interface_tag": "solid",
        "module": "Structural Mechanics Module",
        "dimensions": [1, 2, 3],
        "studies": ["Stationary", "TimeDependent", "Eigenfrequency", "Frequency"],
        "material_properties": ["youngsmodulus", "poissonsratio", "density"],
        "keywords": ["固体力学", "应力", "应变", "位移", "载荷", "结构", "悬臂梁", "solid mechanics", "stress"],
        "domains": ["structural", "geomechanics"],
        "validation_level": "verified_on_current_host",
    },
    {
        "id": "laminar_flow",
        "display_name": "Laminar Flow",
        "matlab_interface": "LaminarFlow",
        "interface_tag": "spf",
        "module": "CFD Module",
        "dimensions": [2, 3],
        "studies": ["Stationary", "TimeDependent"],
        "material_properties": ["density", "dynamicviscosity"],
        "keywords": ["层流", "流体", "流道", "入口速度", "质量流量", "压力降", "laminar flow", "channel flow"],
        "domains": ["fluid"],
        "validation_level": "verified_on_current_host",
    },
    {
        "id": "heat_transfer_fluids",
        "display_name": "Heat Transfer in Fluids",
        "matlab_interface": "HeatTransferInFluids",
        "interface_tag": "ht",
        "module": "Heat Transfer Module",
        "dimensions": [2, 3],
        "studies": ["Stationary", "TimeDependent"],
        "material_properties": ["thermalconductivity", "density", "heatcapacity"],
        "keywords": ["流体传热", "流热", "流道冷却", "对流换热", "出口温度", "heat transfer in fluid", "nonisothermal"],
        "domains": ["fluid", "heat_transfer"],
        "validation_level": "verified_on_current_host",
    },
    {
        "id": "pressure_acoustics",
        "display_name": "Pressure Acoustics",
        "matlab_interface": "PressureAcoustics",
        "interface_tag": "acpr",
        "module": "Acoustics Module",
        "dimensions": [1, 2, 3],
        "studies": ["Eigenfrequency", "Frequency", "TimeDependent"],
        "material_properties": ["density", "soundspeed"],
        "keywords": ["压力声学", "声学", "声压", "声场", "共振", "驻波", "管道声学", "pressure acoustics", "acoustic"],
        "domains": ["acoustics"],
        "validation_level": "verified_on_current_host",
    },
    {
        "id": "transport_diluted_species",
        "display_name": "Transport of Diluted Species",
        "matlab_interface": "DilutedSpecies",
        "interface_tag": "tds",
        "module": "Chemical Reaction Engineering Module",
        "dimensions": [1, 2, 3],
        "studies": ["Stationary", "TimeDependent"],
        "material_properties": ["diffusivity"],
        "keywords": ["稀物质", "扩散", "浓度", "传质", "diffusion", "diluted species"],
        "domains": ["mass_transfer"],
        "validation_level": "verified_on_current_host",
    },
)


COUPLING_CATALOG: tuple[dict[str, Any], ...] = (
    {
        "id": "electromagnetic_heating",
        "display_name": "Electromagnetic Heating (Joule Heating)",
        "node_type": "ElectromagneticHeating",
        "requires": ["electric_currents", "heat_transfer_solids"],
        "keywords": ["焦耳热", "电热", "通电发热", "joule", "electrothermal"],
        "validation_level": "verified_on_current_host",
    },
    {
        "id": "nonisothermal_flow",
        "display_name": "Nonisothermal Flow",
        "node_type": "NonisothermalFlow",
        "requires": ["laminar_flow", "heat_transfer_fluids"],
        "keywords": ["流热", "非等温流", "流道冷却", "共轭传热", "nonisothermal", "conjugate heat"],
        "validation_level": "one_way_baseline_verified_explicit_multiphysics_node_unsupported",
    },
    {
        "id": "thermal_expansion",
        "display_name": "Thermal Expansion",
        "node_type": "ThermalExpansion",
        "requires": ["heat_transfer_solids", "solid_mechanics"],
        "keywords": ["热应力", "热膨胀", "温差变形", "thermal stress", "thermal expansion"],
        "validation_level": "verified_on_current_host",
    },
    {
        "id": "acoustic_structure_boundary",
        "display_name": "Acoustic-Structure Boundary",
        "node_type": "AcousticStructureBoundary",
        "requires": ["pressure_acoustics", "solid_mechanics"],
        "keywords": ["声固耦合", "声学结构", "流固声", "acoustic structure"],
        "validation_level": "reference_only_pending_host_execution",
    },
)


def select_modeling_intent(
    requirement: str,
    domains: list[str] | tuple[str, ...] | None = None,
    *,
    confidence_floor: float = 0.55,
) -> dict[str, Any]:
    """Select COMSOL interfaces, couplings, and study with evidence and abstention."""
    text = str(requirement or "").strip()
    if not text:
        raise ValueError("requirement is empty")
    lowered = text.lower()
    domain_set = {str(item).lower() for item in (domains or [])}
    ranked: list[dict[str, Any]] = []
    for row in PHYSICS_CATALOG:
        hits = [word for word in row["keywords"] if word.lower() in lowered]
        domain_hits = [item for item in row["domains"] if item.lower() in domain_set]
        score = 2.0 * len(hits) + 1.5 * len(domain_hits)
        ranked.append({**row, "matched_keywords": hits, "matched_domains": domain_hits, "score": score})

    selected_ids = {row["id"] for row in ranked if row["score"] >= 2.0}
    # Domain-only hints are useful when upstream classification already supplied
    # intent, but a generic heat request must not select both solid and fluid heat.
    selected_ids.update(row["id"] for row in ranked if row["score"] >= 1.5 and row["matched_domains"])
    if "heat_transfer_fluids" in selected_ids and "laminar_flow" not in selected_ids:
        selected_ids.discard("heat_transfer_fluids")
    if "heat_transfer_fluids" in selected_ids and not any(
        token in lowered for token in ("传热", "温度", "冷却", "换热", "热流", "heat", "thermal", "nonisothermal")
    ):
        selected_ids.discard("heat_transfer_fluids")
    if "laminar_flow" in selected_ids and any(token in lowered for token in ("传热", "温度", "冷却", "换热", "heat")):
        selected_ids.add("heat_transfer_fluids")
    if "heat_transfer_fluids" in selected_ids and not any(
        token in lowered for token in ("固体", "固壁导热", "solid conduction")
    ):
        selected_ids.discard("heat_transfer_solids")
    if "electric_currents" in selected_ids and any(token in lowered for token in ("焦耳", "电热", "发热", "温升", "joule", "electrothermal")):
        selected_ids.add("heat_transfer_solids")
    if "solid_mechanics" in selected_ids and any(token in lowered for token in ("热应力", "热膨胀", "温差变形", "thermal stress")):
        selected_ids.add("heat_transfer_solids")

    couplings: list[dict[str, Any]] = []
    for row in COUPLING_CATALOG:
        keyword_hits = [word for word in row["keywords"] if word.lower() in lowered]
        if set(row["requires"]).issubset(selected_ids) and keyword_hits:
            couplings.append({**row, "matched_keywords": keyword_hits})

    selected = [row for row in ranked if row["id"] in selected_ids]
    selected.sort(key=lambda row: (-float(row["score"]), str(row["id"])))
    top_score = max((float(row["score"]) for row in ranked), default=0.0)
    evidence_count = sum(len(row["matched_keywords"]) + len(row["matched_domains"]) for row in selected)
    confidence = min(0.98, 0.3 + 0.12 * evidence_count + 0.05 * math.log1p(top_score)) if selected else 0.0
    study = infer_study_type(text, selected_ids)
    missing: list[str] = []
    if not selected:
        missing.append("目标物理量或激励不足，无法选择物理接口")
    if study["confidence"] < 0.6:
        missing.append("研究类型未明确，当前仅给出保守默认值")
    if couplings and any(row["validation_level"].startswith("reference_only") for row in couplings):
        missing.append("所选耦合仍缺少当前电脑上的实机模板证据")
    abstained = not selected or confidence < confidence_floor
    return {
        "schema": "comsol-modeling-intent-decision",
        "schemaVersion": "1.0.0",
        "requirement": text,
        "selected_interfaces": [_public_physics(row) for row in selected],
        "selected_interface_ids": [row["id"] for row in selected],
        "couplings": couplings,
        "coupling_ids": [row["id"] for row in couplings],
        "study": study,
        "confidence": round(confidence, 4),
        "abstained": abstained,
        "missing_information": missing,
        "alternatives": [_public_physics(row) for row in sorted(ranked, key=lambda item: -item["score"]) if row["id"] not in selected_ids and row["score"] > 0][:3],
        "evidence": [
            {"interface_id": row["id"], "keywords": row["matched_keywords"], "domains": row["matched_domains"], "score": row["score"]}
            for row in selected
        ],
    }


def infer_study_type(requirement: str, interface_ids: set[str] | None = None) -> dict[str, Any]:
    text = str(requirement or "").lower()
    rules = (
        ("Eigenfrequency", ("特征频率", "固有频率", "模态", "共振频率", "eigenfrequency", "eigenmode")),
        ("Frequency", ("频域", "扫频", "谐波", "frequency domain", "frequency sweep")),
        ("TimeDependent", ("瞬态", "随时间", "时间历程", "脉冲", "time dependent", "transient")),
        ("Stationary", ("稳态", "静态", "stationary", "steady state")),
    )
    for study, keywords in rules:
        hits = [word for word in keywords if word in text]
        if hits:
            return {"type": study, "confidence": 0.95, "matched_keywords": hits, "defaulted": False}
    if interface_ids and interface_ids == {"pressure_acoustics"} and any(token in text for token in ("腔体", "驻波", "管道")):
        return {"type": "Eigenfrequency", "confidence": 0.7, "matched_keywords": ["声学模态默认"], "defaulted": True}
    return {"type": "Stationary", "confidence": 0.45, "matched_keywords": [], "defaulted": True}


def _public_physics(row: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "id", "display_name", "matlab_interface", "interface_tag", "module",
        "dimensions", "studies", "material_properties", "validation_level", "score",
    )
    return {key: row[key] for key in keys if key in row}
