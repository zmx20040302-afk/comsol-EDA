from __future__ import annotations

import re
from typing import Any

from .physics_selection import COUPLING_CATALOG, PHYSICS_CATALOG, select_modeling_intent
from .requirement_conflicts import detect_requirement_conflicts


GRAPH_SCHEMA = "comsol-physics-dependency-plan"
GRAPH_VERSION = "0.1.0"


def _contains(text: str, terms: tuple[str, ...]) -> list[str]:
    lower = text.lower()
    return [term for term in terms if term.lower() in lower]


def _fluid_context(text: str) -> bool:
    return bool(_contains(text, ("流体", "流道", "通道", "入口速度", "质量流量", "fluid", "channel", "flow")))


def _goal_rules(text: str) -> list[dict[str, Any]]:
    """Map requested observables and mechanisms to required interfaces.

    These rules intentionally expose their evidence. They are a research
    prototype for testing output-driven dependency completion, not a claim of
    universal COMSOL coverage.
    """
    fluid = _fluid_context(text)
    rules: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = [
        ("temperature", ("温度", "温升", "热流", "散热", "temperature", "heat flux"),
         ("heat_transfer_fluids",) if fluid else ("heat_transfer_solids",)),
        ("electrical_response", ("电流", "电压", "电势", "电阻", "焦耳损耗", "功率", "current", "voltage", "resistance", "joule loss"),
         ("electric_currents",)),
        ("structural_response", ("位移", "变形", "应力", "应变", "反力", "displacement", "deformation", "stress", "strain"),
         ("solid_mechanics",)),
        ("flow_response", ("压降", "入口速度", "出口速度", "质量流量", "pressure drop", "mass flow"),
         ("laminar_flow",)),
        ("acoustic_response", ("声压", "声场", "声学", "共振频率", "驻波", "sound pressure", "acoustic"),
         ("pressure_acoustics",)),
        ("species_response", ("浓度", "扩散", "传质", "concentration", "diffusion"),
         ("transport_diluted_species",)),
    ]
    goals: list[dict[str, Any]] = []
    for goal_id, terms, interfaces in rules:
        evidence = _contains(text, terms)
        if goal_id == "electrical_response" and re.search(r"(?<![\d.])\d+(?:\.\d+)?\s*(?:m?v|a)(?![a-z])", text, re.I):
            evidence.append("numeric electrical excitation")
        # "电压降" contains the Chinese substring "压降" but is not a fluid
        # pressure drop. A flow observable only has meaning in a fluid context.
        if goal_id == "flow_response" and not fluid:
            evidence = []
        if evidence:
            goals.append({"id": goal_id, "evidence": evidence, "requires_interfaces": list(interfaces)})
    return goals


def _coupling_rules(text: str, interfaces: set[str], goals: set[str]) -> list[dict[str, Any]]:
    lower = text.lower()
    coupling_ids: list[tuple[str, str, list[str]]] = []
    if {"electric_currents", "heat_transfer_solids"}.issubset(interfaces):
        evidence = _contains(text, ("焦耳热", "电热", "通电发热", "温升", "温度", "joule", "electrothermal"))
        if evidence and "electrical_response" in goals and "temperature" in goals:
            coupling_ids.append(("electromagnetic_heating", "electrical excitation supplies the heat source", evidence))
    if {"heat_transfer_solids", "solid_mechanics"}.issubset(interfaces):
        evidence = _contains(text, ("热执行器", "热致", "热膨胀", "热应力", "温度", "温升", "thermal actuator", "thermal expansion", "thermal stress"))
        if evidence and "temperature" in goals and "structural_response" in goals:
            coupling_ids.append(("thermal_expansion", "temperature field drives structural strain", evidence))
    if {"laminar_flow", "heat_transfer_fluids"}.issubset(interfaces):
        evidence = _contains(text, ("流热", "冷却", "出口温度", "非等温", "换热", "cooling", "outlet temperature", "nonisothermal"))
        if evidence and "temperature" in goals:
            coupling_ids.append(("nonisothermal_flow", "flow transports thermal energy", evidence))
    if {"pressure_acoustics", "solid_mechanics"}.issubset(interfaces):
        evidence = _contains(text, ("声固耦合", "声致振动", "振动辐射", "acoustic structure", "vibroacoustic"))
        if evidence:
            coupling_ids.append(("acoustic_structure_boundary", "acoustic pressure and structural motion interact", evidence))

    catalog = {row["id"]: row for row in COUPLING_CATALOG}
    return [
        {
            "id": coupling_id,
            "requires": list(catalog[coupling_id]["requires"]),
            "reason": reason,
            "evidence": evidence,
            "validation_level": catalog[coupling_id]["validation_level"],
        }
        for coupling_id, reason, evidence in coupling_ids
    ]


def compile_physics_dependency_plan(
    requirement: str,
    domains: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """Compile an auditable requirement-to-physics dependency plan."""
    text = " ".join(str(requirement or "").split())
    if not text:
        raise ValueError("requirement is empty")

    base = select_modeling_intent(text, domains)
    goals = _goal_rules(text)
    interface_ids = set(base["selected_interface_ids"])
    for goal in goals:
        interface_ids.update(goal["requires_interfaces"])

    # A requested fluid temperature requires both the velocity and thermal
    # fields; the observable alone must not silently create a conduction model.
    if _fluid_context(text) and any(goal["id"] == "temperature" for goal in goals):
        interface_ids.update(("laminar_flow", "heat_transfer_fluids"))
        interface_ids.discard("heat_transfer_solids")

    goal_ids = {goal["id"] for goal in goals}
    couplings = _coupling_rules(text, interface_ids, goal_ids)
    coupling_ids = {row["id"] for row in couplings}
    # Preserve an explicit base coupling when all of its prerequisites remain.
    catalog_couplings = {row["id"]: row for row in COUPLING_CATALOG}
    for coupling_id in base["coupling_ids"]:
        row = catalog_couplings[coupling_id]
        if set(row["requires"]).issubset(interface_ids) and coupling_id not in coupling_ids:
            couplings.append({
                "id": coupling_id,
                "requires": list(row["requires"]),
                "reason": "explicit coupling phrase selected by the base selector",
                "evidence": next((item.get("matched_keywords", []) for item in base["couplings"] if item["id"] == coupling_id), []),
                "validation_level": row["validation_level"],
            })
            coupling_ids.add(coupling_id)

    physics_catalog = {row["id"]: row for row in PHYSICS_CATALOG}
    interface_nodes = [
        {
            "id": interface_id,
            "display_name": physics_catalog[interface_id]["display_name"],
            "validation_level": physics_catalog[interface_id]["validation_level"],
            "source": "base_selector" if interface_id in base["selected_interface_ids"] else "output_dependency_completion",
        }
        for interface_id in sorted(interface_ids)
    ]
    edges: list[dict[str, str]] = []
    for goal in goals:
        for interface_id in goal["requires_interfaces"]:
            if interface_id in interface_ids:
                edges.append({"from": f"goal:{goal['id']}", "to": f"interface:{interface_id}", "type": "requires"})
    for coupling in couplings:
        for interface_id in coupling["requires"]:
            edges.append({"from": f"coupling:{coupling['id']}", "to": f"interface:{interface_id}", "type": "requires"})

    conflicts = detect_requirement_conflicts(text)
    unsupported = [row for row in couplings if row["validation_level"].startswith("reference_only")]
    questions: list[str] = []
    if not goals:
        questions.append("请明确需要计算或验证的目标物理量。")
    if "temperature" in goal_ids and not re.search(r"(?:边界|环境|初始|入口|壁面|固定温度|对流|ambient|boundary|inlet|wall)", text, re.I):
        questions.append("请补充热边界或环境散热条件。")
    if "structural_response" in goal_ids and not re.search(r"(?:固定|约束|支撑|载荷|自由端|fixed|constraint|support|load)", text, re.I):
        questions.append("请补充结构约束及载荷或热驱动条件。")

    return {
        "schema": GRAPH_SCHEMA,
        "schemaVersion": GRAPH_VERSION,
        "requirement": text,
        "goals": goals,
        "interfaces": interface_nodes,
        "interface_ids": sorted(interface_ids),
        "couplings": couplings,
        "coupling_ids": sorted(coupling_ids),
        "study": base["study"],
        "edges": edges,
        "conflicts": conflicts,
        "clarification_questions": questions,
        "decision": {
            "blocked": bool(conflicts or unsupported or not goals),
            "reason_codes": (
                (["REQUIREMENT_CONFLICT"] if conflicts else [])
                + (["UNVERIFIED_COUPLING"] if unsupported else [])
                + (["OBJECTIVE_MISSING"] if not goals else [])
            ),
        },
        "base_selector": {
            "interface_ids": base["selected_interface_ids"],
            "coupling_ids": base["coupling_ids"],
            "confidence": base["confidence"],
            "abstained": base["abstained"],
        },
        "scope_note": "Development prototype covering seven interfaces and four declared couplings; unsupported physics must abstain.",
    }
