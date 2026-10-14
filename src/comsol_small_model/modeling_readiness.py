from __future__ import annotations

from typing import Any

from .geometry_parameter_knowledge import validate_geometry_readiness
from .boundary_knowledge import infer_boundary_conditions
from .material_property_knowledge import validate_material_readiness
from .mesh_knowledge import infer_mesh_strategy
from .result_knowledge import infer_result_exports
from .solver_knowledge import infer_study_solver


def assess_modeling_readiness(
    requirement: str,
    plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    plan = plan or {}
    domains = list(plan.get("inferred_domains", []))
    parameters = list(plan.get("candidate_parameters", []))
    materials = validate_material_readiness(requirement, domains, parameters)
    geometry = validate_geometry_readiness(requirement, domains, parameters)
    mesh = infer_mesh_strategy(requirement, domains)
    solver = infer_study_solver(requirement, domains)
    results = infer_result_exports(requirement, domains, plan.get("candidate_outputs", []))
    boundary = infer_boundary_conditions(requirement, domains)
    blockers: list[str] = []
    blockers.extend(
        "材料：" + str(item.get("name", item.get("comsol_key", "未命名物性")))
        for item in materials.get("missing_required_properties", [])
    )
    blockers.extend("几何：" + str(item) for item in geometry.get("missing_geometry_evidence", []))
    if not results.get("outputs"):
        blockers.append("结果：尚未确定输出量")
    if not domains:
        blockers.append("物理场：尚未从需求中识别出可靠的物理场")
    if not boundary.get("matches"):
        blockers.append("边界条件：尚未识别出足够明确的边界条件依据")
    return {
        "ready_for_modeling": not blockers,
        "blockers": blockers,
        "materials": materials,
        "geometry": geometry,
        "mesh": mesh,
        "solver": solver,
        "results": results,
        "boundary": boundary,
        "next_action": "review_blockers" if blockers else "approve_and_generate_code",
    }
