from __future__ import annotations

from pathlib import Path
from typing import Any

from .modeling_contract import add_missing_information, contract_summary
from .physics_dependency_graph_v11 import compile_physics_dependency_plan_v11
from .physics_selection import COUPLING_CATALOG, PHYSICS_CATALOG
from .requirement_parser import clarification_questions
from .staged_modeling import (
    approve_current_step,
    create_staged_workflow,
    final_modeling_package,
    load_workflow,
    save_workflow,
)


_FIELD_TARGETS = {
    "objective": ("outputs", "outputs.quantities", "task_definition"),
    "thermal_boundary": ("boundary_conditions", "boundary_conditions.thermal", "boundary_initial"),
    "electrical_boundary": ("boundary_conditions", "boundary_conditions.electrical", "boundary_initial"),
    "structural_boundary": ("boundary_conditions", "boundary_conditions.structural", "boundary_initial"),
    "flow_boundary": ("boundary_conditions", "boundary_conditions.flow", "boundary_initial"),
    "acoustic_boundary": ("boundary_conditions", "boundary_conditions.acoustic", "boundary_initial"),
    "species_boundary": ("boundary_conditions", "boundary_conditions.species", "boundary_initial"),
    "study": ("study", "study.types", "physics_study"),
}


def create_staged_workflow_v11(
    requirement: str,
    memory_path: str | Path = "generated/case_memory/case_memory.json",
    output_dir: str | Path = "generated/staged_workflows",
    top_k: int = 5,
) -> dict[str, Any]:
    workflow = create_staged_workflow(requirement, memory_path, output_dir, top_k)
    _apply_v11_gate(workflow)
    workflow["outputs"] = save_workflow(workflow, output_dir)
    return workflow


def approve_current_step_v11(
    workflow_path: str | Path,
    approved: bool,
    comment: str = "",
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    workflow = load_workflow(workflow_path)
    gate = workflow.get("requirement_gate_v11", {})
    if approved and isinstance(gate, dict) and gate.get("blocked"):
        reasons = ", ".join(str(item) for item in gate.get("reason_codes", []))
        raise ValueError(f"v1.1 requirement completeness gate is blocked: {reasons}")
    return approve_current_step(workflow_path, approved, comment, output_dir)


def final_modeling_package_v11(
    workflow_path: str | Path,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    workflow = load_workflow(workflow_path)
    gate = workflow.get("requirement_gate_v11", {})
    if isinstance(gate, dict) and gate.get("blocked"):
        raise ValueError("v1.1 requirement completeness gate must pass before code generation")
    return final_modeling_package(workflow_path, output_dir)


def _apply_v11_gate(workflow: dict[str, Any]) -> None:
    requirement = str(workflow.get("requirement", ""))
    domains = workflow.get("plan", {}).get("inferred_domains", [])
    dependency = compile_physics_dependency_plan_v11(requirement, domains)
    effective_questions = list(dependency["completeness"]["clarification_questions"])
    if "UNVERIFIED_COUPLING" in dependency["decision"]["reason_codes"]:
        effective_questions.append("当前耦合缺少本机已验证执行模板，请选择已验证替代方案或转人工建模。")
    dependency["clarification_questions"] = effective_questions
    gate = {
        "schemaVersion": "1.1.0",
        "blocked": bool(dependency["decision"]["blocked"]),
        "reason_codes": list(dependency["decision"]["reason_codes"]),
        "missing_fields": list(dependency["completeness"]["missing_fields"]),
        "clarification_questions": effective_questions,
    }
    workflow["requirement_gate_v11"] = gate
    contract = workflow.get("modeling_contract")
    if not isinstance(contract, dict):
        return
    contract.setdefault("decision_support", {})["physics_dependency_graph"] = dependency
    _replace_contract_physics(contract, dependency)
    question_by_field = dict(zip(
        dependency["completeness"]["missing_fields"],
        dependency["completeness"]["clarification_questions"],
    ))
    for field in dependency["completeness"]["missing_fields"]:
        category, target, stage = _FIELD_TARGETS[field]
        add_missing_information(contract, category, target, question_by_field[field], stage)
    if gate["blocked"]:
        policy = contract.setdefault("execution_policy", {})
        policy.update({"risk_level": "C", "allow_automatic_generation": False, "allow_automatic_solve": False, "max_retries": 0})
        workflow["status"] = "blocked_missing_information"
        workflow["current_step"] = 0
        if workflow.get("steps"):
            first = workflow["steps"][0]
            first["status"] = "needs_revision"
            first["proposal"] = [
                "v1.1 需求完整性门已阻断：" + "、".join(gate["reason_codes"]),
                *gate["clarification_questions"],
            ]
            first["approval_questions"] = gate["clarification_questions"]
    for step in workflow.get("steps", []):
        if step.get("id") == "physics_study":
            summary = "v1.1 依赖图：接口=" + ("、".join(dependency["interface_ids"]) or "未可靠选择")
            summary += "；耦合=" + ("、".join(dependency["coupling_ids"]) or "无")
            summary += "；决定=" + ("阻断" if gate["blocked"] else "可继续审查")
            step.setdefault("proposal", []).insert(0, summary)
            break
    contract["clarifying_questions"] = clarification_questions(contract)
    workflow["contract_summary"] = contract_summary(contract)


def _replace_contract_physics(contract: dict[str, Any], dependency: dict[str, Any]) -> None:
    physics_catalog = {row["id"]: row for row in PHYSICS_CATALOG}
    coupling_catalog = {row["id"]: row for row in COUPLING_CATALOG}
    variables = {
        "heat_transfer_solids": ["T"], "heat_transfer_fluids": ["T"],
        "electric_currents": ["V", "J"], "solid_mechanics": ["u", "stress"],
        "laminar_flow": ["u", "p"], "pressure_acoustics": ["p"],
        "transport_diluted_species": ["c"],
    }
    interfaces = []
    dependent_variables: list[str] = []
    sources = {row["id"]: row.get("source", "physics_dependency_graph_v11") for row in dependency["interfaces"]}
    for interface_id in dependency["interface_ids"]:
        spec = physics_catalog[interface_id]
        interfaces.append({
            "id": interface_id, "name": spec["display_name"], "tag": spec["interface_tag"],
            "evidence_level": "proposed", "source": sources[interface_id],
        })
        dependent_variables.extend(variables.get(interface_id, []))
    couplings = [
        {
            "id": coupling_id, "name": coupling_catalog[coupling_id]["display_name"],
            "tag": f"multiphysics_{index}_{coupling_id}", "evidence_level": "proposed",
            "source": "physics_dependency_graph_v11",
        }
        for index, coupling_id in enumerate(dependency["coupling_ids"], start=1)
    ]
    contract.setdefault("physics", {}).update({
        "interfaces": interfaces,
        "couplings": couplings,
        "dependent_variables": list(dict.fromkeys(dependent_variables)),
    })
