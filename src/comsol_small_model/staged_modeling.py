from __future__ import annotations

import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .boundary_knowledge import infer_boundary_conditions
from .case_memory import generate_model_plan
from .code_generator import generate_comsol_code_from_memory
from .coupled_physics_knowledge import analyze_coupled_physics
from .geometry_parameter_knowledge import analyze_geometry_parameters, validate_geometry_readiness
from .instruction_agent import _select_physics_from_requirement
from .material_property_knowledge import analyze_material_properties, validate_material_readiness
from .mesh_knowledge import infer_mesh_strategy
from .solver_knowledge import infer_study_solver
from .result_knowledge import infer_result_exports
from .modeling_readiness import assess_modeling_readiness
from .modeling_contract import contract_summary
from .physics_selection import select_modeling_intent
from .physics_dependency_graph import compile_physics_dependency_plan
from .static_model_audit import audit_generated_model_files
from .requirement_parser import parse_modeling_requirement
from .requirement_conflicts import detect_requirement_conflicts
from .workflow_status import normalize_workflow_status


DEFAULT_WORKFLOW_DIR = Path("generated/staged_workflows")


STAGE_DEFINITIONS = [
    (
        "task_definition",
        "需求目标与完成标准",
        "Confirm the engineering goal, quantity of interest, scope, and evidence required to mark the task complete.",
    ),
    (
        "physics_study",
        "物理场、耦合与研究类型",
        "Confirm physics interfaces, coupling assumptions, dependent variables, and stationary/transient/frequency intent.",
    ),
    (
        "geometry",
        "几何与参数",
        "Confirm geometry source, dimensionality, selections, imported data, parameters, and units.",
    ),
    (
        "materials",
        "确定材料",
        "Confirm material groups, property sources, units, nonlinear/anisotropic assumptions, and parameterization.",
    ),
    (
        "boundary_initial",
        "边界条件与初始条件",
        "Confirm excitation, constraints, dissipation boundaries, initial fields, values, units, and named selections.",
    ),
    (
        "mesh",
        "网格策略",
        "Confirm global/local mesh size, boundary layers, refinement targets, and mesh-independence checks.",
    ),
    (
        "solver",
        "研究步骤与求解器",
        "Confirm study sequence, solver settings, parameter sweeps, convergence checks, and numerical risks.",
    ),
    (
        "results_validation",
        "结果、派生量与物理验收",
        "Confirm derived values, plots, exports, conservation checks, analytical references, and acceptance thresholds.",
    ),
    (
        "code_generation",
        "代码生成与静态审计",
        "Generate COMSOL MATLAB/Java code and audit parameters, tags, selections, materials, studies, and outputs.",
    ),
    (
        "execution_validation",
        "COMSOL 执行、验证与受控修正",
        "Build, mesh, solve, export, validate, and retain auditable evidence for any allowed repair.",
    ),
]

WORKFLOW_VERSION = "2.0.0"


def create_staged_workflow(
    requirement: str,
    memory_path: str | Path = "generated/case_memory/case_memory.json",
    output_dir: str | Path = DEFAULT_WORKFLOW_DIR,
    top_k: int = 5,
) -> dict[str, Any]:
    requirement = requirement.strip()
    if not requirement:
        raise ValueError("requirement is empty")
    plan = generate_model_plan(requirement, memory_path=memory_path, top_k=top_k)
    contract = parse_modeling_requirement(requirement, plan)
    intent = select_modeling_intent(requirement, plan.get("inferred_domains", []))
    conflicts = detect_requirement_conflicts(requirement)
    workflow_id = _workflow_id(requirement)
    workflow = {
        "kind": "comsol_staged_modeling_workflow",
        "workflow_version": WORKFLOW_VERSION,
        "workflow_id": workflow_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "requirement": requirement,
        "memory_path": str(memory_path),
        "status": "blocked_conflict" if conflicts else "ready_for_review",
        "current_step": 0,
        "plan": plan,
        "modeling_contract": contract,
        "modeling_intent": intent,
        "conflicts": conflicts,
        "contract_summary": contract_summary(contract),
        "steps": [_build_step(index, stage, plan, requirement, contract) for index, stage in enumerate(STAGE_DEFINITIONS)],
        "approval_log": [],
    }
    if conflicts:
        workflow["steps"][0]["status"] = "needs_revision"
        workflow["steps"][0]["proposal"] = [item["message"] for item in conflicts]
        workflow["steps"][0]["approval_questions"] = ["请修改冲突条件后重新创建或退回修订该任务。"]
    outputs = save_workflow(workflow, output_dir)
    workflow["outputs"] = outputs
    return workflow


def approve_current_step(
    workflow_path: str | Path,
    approved: bool,
    comment: str = "",
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    workflow = load_workflow(workflow_path)
    if approved and workflow.get("conflicts"):
        raise ValueError("requirement contains unresolved conflicts and cannot be approved")
    step_index = int(workflow.get("current_step", 0))
    steps = workflow.get("steps", [])
    if step_index >= len(steps):
        workflow["status"] = "complete"
        return workflow

    step = steps[step_index]
    if step.get("id") == "execution_validation":
        raise ValueError("execution_validation requires COMSOL execution evidence and cannot be approved manually")
    step["status"] = "approved" if approved else "needs_revision"
    step["approval"] = {
        "approved": approved,
        "comment": comment,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    workflow.setdefault("approval_log", []).append(
        {
            "step_id": step.get("id"),
            "approved": approved,
            "comment": comment,
            "timestamp": step["approval"]["timestamp"],
        }
    )
    if approved:
        workflow["current_step"] = min(step_index + 1, len(steps))
        workflow["status"] = "completed" if workflow["current_step"] >= len(steps) else "ready_for_review"
        if workflow["current_step"] < len(steps):
            next_step = steps[workflow["current_step"]]
            if next_step.get("id") == "execution_validation":
                next_step["status"] = "pending_execution"
                workflow["status"] = "approved_for_generation"
            else:
                next_step["status"] = "active"
    else:
        revision = _apply_step_revision(workflow, step, comment)
        step["status"] = "active"
        step["proposal"] = revision["proposal"]
        step["revision_guidance"] = revision["guidance"]
        step.setdefault("revision_history", []).append(revision["record"])
        workflow["status"] = "ready_for_review"
    workflow["updated_at"] = datetime.now(timezone.utc).isoformat()
    outputs = save_workflow(workflow, output_dir or Path(workflow_path).parent)
    workflow["outputs"] = outputs
    return workflow


def record_execution_validation(
    workflow_path: str | Path,
    evidence: dict[str, Any],
    passed: bool,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Close the final stage only when runtime and physics evidence are present."""
    workflow = load_workflow(workflow_path)
    execution_step = next(
        (step for step in workflow.get("steps", []) if step.get("id") == "execution_validation"),
        None,
    )
    if execution_step is None:
        raise ValueError("workflow has no execution_validation stage")
    required = ("mph_model", "result_data", "execution_log", "physics_validation_report")
    missing = [name for name in required if not str(evidence.get(name, "")).strip()]
    if passed and missing:
        raise ValueError("completed execution evidence is missing: " + ", ".join(missing))
    timestamp = datetime.now(timezone.utc).isoformat()
    execution_step["status"] = "approved" if passed else "validation_failed"
    execution_step["execution_evidence"] = dict(evidence)
    execution_step["validation_record"] = {"passed": bool(passed), "timestamp": timestamp}
    workflow["status"] = "completed" if passed else "validation_failed"
    workflow["current_step"] = len(workflow.get("steps", [])) if passed else len(workflow.get("steps", [])) - 1
    workflow["updated_at"] = timestamp
    contract = workflow.get("modeling_contract", {})
    if isinstance(contract, dict):
        contract["status"] = workflow["status"]
        contract["updated_at"] = timestamp
        workflow["contract_summary"] = contract_summary(contract)
    outputs = save_workflow(workflow, output_dir or Path(workflow_path).parent)
    workflow["outputs"] = outputs
    return workflow


def final_modeling_package(workflow_path: str | Path, output_dir: str | Path | None = None) -> dict[str, Any]:
    workflow = load_workflow(workflow_path)
    unapproved = [step for step in workflow.get("steps", [])[:-1] if step.get("status") != "approved"]
    if unapproved:
        raise ValueError("All modeling steps must be approved before final generation")
    destination = Path(output_dir or Path(workflow_path).parent)
    destination.mkdir(parents=True, exist_ok=True)
    approved_context = _approved_generation_context(workflow)
    generated = generate_comsol_code_from_memory(
        requirement=approved_context,
        memory_path=workflow.get("memory_path", "generated/case_memory/case_memory.json"),
        output_dir=destination / "final_code",
        output_prefix=str(workflow.get("workflow_id", "generated_comsol_model")),
        top_k=5,
        approved_domains=workflow.get("plan", {}).get("inferred_domains", []),
        approved_requirement=str(workflow.get("requirement", "")),
    )
    static_audit = audit_generated_model_files(
        workflow.get("modeling_contract", {}),
        generated.matlab_path,
        generated.java_path,
        destination / "final_code" / f"{workflow.get('workflow_id', 'workflow')}.static_audit.json",
    )
    code_step = next((step for step in workflow.get("steps", []) if step.get("id") == "code_generation"), None)
    if isinstance(code_step, dict):
        code_step["status"] = "approved"
        code_step["generation_status"] = "generated"
        code_step["generated_outputs"] = {**generated.as_dict()["outputs"], "static_audit": static_audit["path"]}
        code_step["static_audit"] = static_audit
        code_step["generation_record"] = {
            "approved": True,
            "comment": "Final MATLAB and Java files generated from approved workflow decisions.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    execution_step = next((step for step in workflow.get("steps", []) if step.get("id") == "execution_validation"), None)
    if isinstance(execution_step, dict):
        execution_step["status"] = "pending_execution"
    workflow["current_step"] = max(0, len(workflow.get("steps", [])) - 1)
    workflow["status"] = "generated"
    workflow["updated_at"] = datetime.now(timezone.utc).isoformat()
    save_workflow(workflow, Path(workflow_path).parent)
    package = {
        "kind": "approved_comsol_modeling_package",
        "workflow_id": workflow.get("workflow_id"),
        "requirement": workflow.get("requirement"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "approved_steps": workflow.get("steps", []),
        "approved_decisions": _approved_decisions(workflow),
        "modeling_contract": workflow.get("modeling_contract", {}),
        "contract_summary": workflow.get("contract_summary", {}),
        "modeling_sequence": _final_sequence(workflow),
        "matlab_generation_requirements": _matlab_requirements(workflow),
        "java_generation_requirements": _java_requirements(workflow),
        "verification_checklist": _verification_checklist(workflow),
        "material_readiness": validate_material_readiness(
            str(workflow.get("requirement", "")),
            workflow.get("plan", {}).get("inferred_domains", []),
            workflow.get("plan", {}).get("candidate_parameters", []),
        ),
        "modeling_readiness": assess_modeling_readiness(
            str(workflow.get("requirement", "")), workflow.get("plan", {})
        ),
        "generated_code": generated.as_dict(),
        "static_model_audit": static_audit,
    }
    package["execution_handoff"] = _execution_handoff(package)
    _append_execution_handoff_to_guidance(
        Path(str(generated.guidance_path)),
        package["execution_handoff"],
        Path(str(generated.verification_path)),
        package["generated_code"].get("generation_readiness", {}).get("approved_domains", []),
    )
    json_path = destination / f"{workflow.get('workflow_id', 'workflow')}.final_modeling_package.json"
    md_path = destination / f"{workflow.get('workflow_id', 'workflow')}.final_modeling_package.md"
    json_path.write_text(json.dumps(package, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_package_markdown(package), encoding="utf-8")
    return {
        "package": package,
        "outputs": {
            "json": str(json_path),
            "markdown": str(md_path),
            **generated.as_dict()["outputs"],
            "static_audit": static_audit["path"],
        },
    }


def load_workflow(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return migrate_workflow(payload)


def list_staged_workflows(output_dir: str | Path = DEFAULT_WORKFLOW_DIR, limit: int = 30) -> list[dict[str, Any]]:
    destination = Path(output_dir)
    rows: list[dict[str, Any]] = []
    for path in sorted(destination.glob("*.workflow.json"), key=lambda item: item.stat().st_mtime, reverse=True)[: max(1, limit)]:
        try:
            workflow = load_workflow(path)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        steps = workflow.get("steps", [])
        current = int(workflow.get("current_step", 0))
        rows.append({
            "workflow_id": workflow.get("workflow_id"),
            "requirement": workflow.get("requirement"),
            "status": workflow.get("status"),
            "risk_level": workflow.get("contract_summary", {}).get("risk_level"),
            "current_step": current,
            "step_count": len(steps),
            "completed_steps": sum(1 for step in steps if step.get("status") == "approved"),
            "updated_at": workflow.get("updated_at"),
            "path": str(path),
        })
    return rows


def retry_failed_stage(workflow_path: str | Path, output_dir: str | Path | None = None) -> dict[str, Any]:
    workflow = load_workflow(workflow_path)
    if workflow.get("conflicts"):
        raise ValueError("requirement conflicts must be resolved before retry")
    steps = workflow.get("steps", [])
    failed_statuses = {"failed", "error", "build_failed", "mesh_failed", "solve_failed", "validation_failed"}
    index = next((i for i, step in enumerate(steps) if step.get("status") in failed_statuses), None)
    if index is None and workflow.get("status") in failed_statuses:
        index = max(0, len(steps) - 1)
    if index is None:
        raise ValueError("workflow has no failed stage to retry")
    step = steps[index]
    step.setdefault("retry_history", []).append({
        "previous_status": step.get("status"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    step["status"] = "pending_execution" if step.get("id") == "execution_validation" else "active"
    workflow["current_step"] = index
    workflow["status"] = "generated" if step.get("id") == "execution_validation" else "ready_for_review"
    workflow["updated_at"] = datetime.now(timezone.utc).isoformat()
    workflow["outputs"] = save_workflow(workflow, output_dir or Path(workflow_path).parent)
    return workflow


def build_workflow_download_archive(workflow_path: str | Path, output_dir: str | Path | None = None) -> Path:
    path = Path(workflow_path).resolve()
    workflow = load_workflow(path)
    destination = Path(output_dir or path.parent / "downloads")
    destination.mkdir(parents=True, exist_ok=True)
    workflow_id = str(workflow.get("workflow_id") or path.stem)
    archive = destination / f"{workflow_id}.task_package.zip"
    candidates = [path]
    candidates.extend(path.parent.glob(f"{workflow_id}.*"))
    candidates.extend((path.parent / "final_code").glob(f"{workflow_id}*"))
    unique = sorted({item.resolve() for item in candidates if item.is_file()})
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as handle:
        for item in unique:
            handle.write(item, item.relative_to(path.parent).as_posix())
    return archive


def save_workflow(workflow: dict[str, Any], output_dir: str | Path = DEFAULT_WORKFLOW_DIR) -> dict[str, str]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / f"{workflow.get('workflow_id', 'workflow')}.workflow.json"
    path.write_text(json.dumps(workflow, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"workflow": str(path)}


def migrate_workflow(workflow: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(workflow, dict):
        raise ValueError("workflow must be an object")
    requirement = str(workflow.get("requirement", "")).strip()
    plan = workflow.get("plan", {}) if isinstance(workflow.get("plan"), dict) else {}
    if not requirement:
        raise ValueError("workflow requirement is empty")
    if workflow.get("workflow_version") == WORKFLOW_VERSION and len(workflow.get("steps", [])) == len(STAGE_DEFINITIONS):
        result = dict(workflow)
        result["status"] = normalize_workflow_status(result.get("status"), "ready_for_review")
        if not isinstance(result.get("modeling_contract"), dict):
            result["modeling_contract"] = parse_modeling_requirement(requirement, plan)
        if not isinstance(result.get("modeling_intent"), dict):
            result["modeling_intent"] = select_modeling_intent(requirement, plan.get("inferred_domains", []))
        result["contract_summary"] = contract_summary(result["modeling_contract"])
        return result

    contract = parse_modeling_requirement(requirement, plan)
    old_steps = {
        str(step.get("id", "")): step
        for step in workflow.get("steps", [])
        if isinstance(step, dict)
    }
    legacy_map = {
        "task_definition": "physics",
        "physics_study": "physics",
        "geometry": "data_structure",
        "materials": "materials",
        "boundary_initial": "physics",
        "mesh": "mesh",
        "solver": "study_solver",
        "results_validation": "results_export",
        "code_generation": "final_generation",
    }
    steps = [_build_step(index, stage, plan, requirement, contract) for index, stage in enumerate(STAGE_DEFINITIONS)]
    for step in steps:
        source = old_steps.get(legacy_map.get(str(step.get("id")), ""))
        if not source:
            continue
        if source.get("status") == "approved":
            step["status"] = "approved"
            if isinstance(source.get("approval"), dict):
                step["approval"] = dict(source["approval"])
        if source.get("revision_history"):
            step["revision_history"] = list(source["revision_history"])
    next_index = next((index for index, step in enumerate(steps[:-1]) if step.get("status") != "approved"), len(steps) - 1)
    if next_index < len(steps) - 1:
        steps[next_index]["status"] = "active"
        status = "ready_for_review"
    else:
        steps[-1]["status"] = "pending_execution"
        status = "approved_for_generation"
    migrated = dict(workflow)
    migrated.update(
        {
            "workflow_version": WORKFLOW_VERSION,
            "status": status,
            "current_step": next_index,
            "modeling_contract": contract,
            "modeling_intent": select_modeling_intent(requirement, plan.get("inferred_domains", [])),
            "contract_summary": contract_summary(contract),
            "steps": steps,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "migration": {
                "source_version": str(workflow.get("workflow_version", "1.0.0")),
                "migrated_at": datetime.now(timezone.utc).isoformat(),
                "approval_log_preserved": True,
            },
        }
    )
    return migrated


def _build_step(
    index: int,
    stage: tuple[str, str, str],
    plan: dict[str, Any],
    requirement: str,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    step_id, title, purpose = stage
    status = "active" if index == 0 else "pending"
    return {
        "index": index,
        "id": step_id,
        "title": title,
        "purpose": purpose,
        "status": status,
        "proposal": _stage_proposal(step_id, plan, requirement, contract),
        "evidence": _stage_evidence(step_id, plan),
        "approval_questions": _approval_questions(step_id),
        "approved_outputs": _approved_outputs(step_id),
    }


def _stage_proposal(
    step_id: str,
    plan: dict[str, Any],
    requirement: str,
    contract: dict[str, Any] | None = None,
) -> list[str]:
    domains = plan.get("inferred_domains", [])
    outputs = plan.get("candidate_outputs", [])
    parameters = [item.get("name", "") for item in plan.get("candidate_parameters", [])[:10]]
    matched = [item.get("title", "") for item in plan.get("matched_cases", [])[:5]]
    contract = contract or parse_modeling_requirement(requirement, plan)
    if step_id == "task_definition":
        missing = contract.get("missing_information", [])
        critical = [item for item in missing if item.get("severity") == "critical"]
        criteria = contract.get("task", {}).get("completion_criteria", [])
        return [
            "任务目标：" + str(contract.get("task", {}).get("goal", requirement)),
            "完成标准：" + "；".join(str(item) for item in criteria),
            f"当前风险等级：{contract.get('execution_policy', {}).get('risk_level', 'C')}。",
            f"关键信息缺口：{len(critical)} 项；总待确认项：{len(missing)} 项。",
            "集中追问：" + ("；".join(contract.get("clarifying_questions", [])[:8]) or "当前未发现阻断性问题。"),
        ]
    if step_id == "physics_study":
        selection = _select_physics_from_requirement(requirement, domains)
        coupling = analyze_coupled_physics(requirement, domains)
        solver = infer_study_solver(requirement, domains)
        decision = select_modeling_intent(requirement, domains)
        dependency_plan = compile_physics_dependency_plan(requirement, domains)
        interfaces = "、".join(item["display_name"] for item in dependency_plan["interfaces"]) or "未能可靠选择"
        coupling_names = "、".join(item["id"] for item in dependency_plan["couplings"]) or "无"
        completed = [item["display_name"] for item in dependency_plan["interfaces"] if item["source"] == "output_dependency_completion"]
        return [
            "选择结果：" + selection["result"],
            "COMSOL 接口建议：" + selection["interfaces"],
            f"标准化决策：接口={interfaces}；耦合={coupling_names}；研究={decision['study']['type']}；置信度={decision['confidence']:.2f}。",
            "输出目标反推补全：" + ("、".join(completed) if completed else "无需补全；显式证据已覆盖必要接口。"),
            "依赖图执行决定：" + ("阻断；" + "、".join(dependency_plan["decision"]["reason_codes"]) if dependency_plan["decision"]["blocked"] else "可继续进入合同完整性审查。"),
            "理论依据：" + selection["theory"],
            "复合场检查：" + _coupling_summary(coupling),
            "研究类型：" + "、".join(solver["studies"]),
            "需要确认：" + selection["checks"],
            "相似案例参考：" + ", ".join(matched or ["暂无直接匹配案例"]) + "。",
        ]
    if step_id == "materials":
        material = analyze_material_properties(requirement, domains, plan.get("candidate_parameters", []))
        readiness = validate_material_readiness(requirement, domains, plan.get("candidate_parameters", []))
        recognized = material.get("recognized_materials", [])
        recognized_text = "; ".join(
            f"{item['name']}: " + ", ".join(f"{key}={value}" for key, value in item["properties"].items())
            for item in recognized
        )
        required = "；".join(
            f"{row['name']}({row['symbol']}, {row['unit']})" for row in material["required_properties"][:8]
        )
        optional = "；".join(
            f"{row['name']}({row['symbol']})" for row in material["optional_properties"][:6]
        )
        return [
            "材料与物性结论：" + material["summary"],
            "物性就绪检查：" + ("可以进入材料配置" if readiness["ready_for_model_generation"] else "暂不能进入最终求解模型，需先补充物性"),
            "物性联动风险：" + ("；".join(readiness["risks"]) or "未发现明显物性联动风险"),
            "默认物性假设：" + ("；".join(readiness["assumptions"]) or "未使用材料档案默认值"),
            "已识别材料配置：" + (recognized_text or "需求未明确材料名称，需要人工确认材料库条目。"),
            "必填物性参数：" + required,
            "可选/耦合物性：" + (optional or "暂无"),
            "温度/频率/方向依赖：" + "；".join(material["dependencies"][:5]),
            "待补充物性：" + ("、".join(row["name"] for row in material["missing_required_properties"][:8]) or "当前候选参数已覆盖主要必填项"),
            "MATLAB 材料设置应使用 material.propertyGroup('def').set(...)，并先用 model.param.set(...) 定义带单位参数。",
        ]
    if step_id == "geometry":
        analysis = analyze_geometry_parameters(requirement, domains, plan.get("candidate_parameters", []))
        readiness = validate_geometry_readiness(requirement, domains, plan.get("candidate_parameters", []))
        parameter_text = ", ".join(
            f"{item['name']}={item['value']}" for item in analysis["parameters"][:8]
        )
        return [
            "几何与参数结论：" + analysis["summary"],
            "几何就绪检查：" + ("可以进入网格划分" if readiness["ready_for_meshing"] else "暂不能进入网格划分，需先补充几何证据"),
            "待补充几何信息：" + ("、".join(readiness["missing_geometry_evidence"]) or "当前几何证据基本完整"),
            "维度建议：" + analysis["dimension"],
            "几何要点：" + "；".join(analysis["geometry"][:6]),
            "关键参数：" + (parameter_text or ", ".join(parameters or ["需要人工补充尺寸、材料和载荷参数"])),
            "选择集建议：" + "；".join(analysis["selection_advice"][:6]),
            "后续扫描变量：" + "、".join(analysis["sweep_advice"][:6]),
        ]
    if step_id == "boundary_initial":
        boundary = infer_boundary_conditions(requirement, domains)
        missing = [
            item for item in contract.get("missing_information", [])
            if item.get("category") == "boundary_conditions"
        ]
        return [
            "边界条件判断：" + boundary["summary"],
            "建议边界类型：" + "、".join(boundary["boundary_types"][:8]) + "。",
            "初始条件建议：" + "、".join(boundary["initial_conditions"][:8]) + "。",
            "边界选择原则：为激励、约束和散逸边界建立命名选择，并核对期望实体数。",
            "待确认：" + ("；".join(str(item.get("question", "")) for item in missing) or "边界类型已有依据，仍需在 COMSOL 中核对具体实体。"),
        ]
    if step_id == "mesh":
        mesh = infer_mesh_strategy(requirement, domains)
        return [
            "网格策略：" + "；".join(mesh["strategy"]),
            "局部加密区域：" + ("、".join(mesh["local_refinements"]) or "需根据几何和结果梯度确认"),
            "网格参数：" + mesh["mesh_parameter"] + "，建议先做基准网格再做加密对比",
            "网格检查：" + "；".join(mesh["checks"]),
        ]
    if step_id == "solver":
        solver = infer_study_solver(requirement, domains)
        return [
            "研究类型：" + "、".join(solver["studies"]),
            "判断依据：" + "；".join(solver["reasons"]),
            "求解器检查：" + "；".join(solver["solver_checks"]),
            "案例库建议路径：" + ", ".join(plan.get("analysis_path", [])[:6]),
        ]
    if step_id == "results_validation":
        result_plan = infer_result_exports(requirement, domains, outputs)
        return [
            "结果输出量：" + "、".join(result_plan["outputs"]),
            "导出格式：" + "、".join(result_plan["export_format"]),
            "结果校验：" + "；".join(result_plan["validation"]),
            "是否需要实验/现场对比：" + ("是" if result_plan["requires_reference_comparison"] else "暂未识别"),
        ]
    if step_id == "code_generation":
        return [
            "从已批准的建模任务合同生成 COMSOL LiveLink MATLAB 和 Java 文件。",
            "静态审计参数定义、单位、标签唯一性、材料分配、命名选择、研究步骤和结果表达式。",
            "所有未解决选择、物性和边界必须保留为阻断项，不能被代码注释掩盖。",
        ]
    return [
        "连接 mphserver 后分阶段执行构建、几何、选择、网格、研究、导出和保存。",
        "只有 MPH、结果数据和物理验证证据齐全时，任务状态才能变为 completed。",
        "自动修正限定为标签引用、结果数据集引用和可证明等价的命名选择；物理修改需要用户确认。",
    ]


def _coupling_summary(coupling: dict[str, Any]) -> str:
    if not coupling.get("is_coupled"):
        return str(coupling.get("summary", "暂未识别复合场。"))
    return (
        f"{coupling['summary']} 主物理场={coupling['primary_physics']}；"
        f"耦合物理场={'、'.join(coupling['coupled_physics'][:6])}；"
        f"多物理场节点={'、'.join(coupling['multiphysics_nodes'][:6])}；"
        f"耦合变量={'、'.join(coupling['coupling_variables'][:8])}。"
    )


def _stage_evidence(step_id: str, plan: dict[str, Any]) -> list[str]:
    evidence = [
        f"案例记忆数量：{plan.get('case_count', 0)}。",
        "匹配案例：" + ", ".join(item.get("title", "") for item in plan.get("matched_cases", [])[:5]),
    ]
    context = plan.get("knowledge_system_context", {})
    if context.get("available"):
        evidence.append("本地知识库已可用于相似案例检索、物理场判断、参数/输出量提取和建模步骤复用。")
    if step_id in {"physics_study", "solver", "results_validation"}:
        evidence.extend(str(item) for item in plan.get("analysis_path", [])[:5])
    return [item for item in evidence if item]


def _approval_questions(step_id: str) -> list[str]:
    questions = {
        "task_definition": ["任务目标和完成标准是否完整？", "集中列出的关键信息缺口是否正确？"],
        "physics_study": ["物理场和耦合是否正确？", "稳态、瞬态、频域或特征频率研究类型是否正确？"],
        "geometry": ["几何来源、维度、尺寸和单位是否完整？", "参数和命名选择是否符合建模对象？"],
        "materials": ["材料属性和单位是否可靠？", "是否需要非线性、各向异性或温度相关材料？"],
        "boundary_initial": ["激励、约束和散逸边界是否明确？", "边界数值、单位、方向和作用实体是否确认？"],
        "mesh": ["网格尺度和局部加密区域是否合理？", "是否需要边界层或网格无关性检查？"],
        "solver": ["求解顺序是否合理？", "是否先做基准求解再做参数扫描？"],
        "results_validation": ["输出量是否能验证模型？", "守恒、范围、趋势和网格检查是否充分？"],
        "code_generation": ["所有物理决策是否已确认？", "是否可以生成并静态审计 MATLAB/Java 建模包？"],
        "execution_validation": ["COMSOL 是否完成构建、网格、求解和导出？", "物理验证和修正记录是否齐全？"],
    }
    return questions.get(step_id, ["该步骤是否正确？"])


def _approved_outputs(step_id: str) -> list[str]:
    return {
        "task_definition": ["approved_goal", "completion_criteria", "resolved_information_requirements"],
        "physics_study": ["approved_physics_interfaces", "approved_couplings", "approved_study_type"],
        "geometry": ["approved_geometry", "geometry_parameters", "named_selections"],
        "materials": ["approved_materials", "material_parameters", "unit_checks"],
        "boundary_initial": ["approved_boundary_conditions", "approved_initial_conditions", "selection_targets"],
        "mesh": ["approved_mesh_strategy", "refinement_targets", "mesh_validation_plan"],
        "solver": ["approved_study_sequence", "solver_settings", "parameter_sweep_plan"],
        "results_validation": ["approved_outputs", "export_columns", "physics_validation_targets"],
        "code_generation": ["final_matlab_script", "final_java_script", "static_audit_report"],
        "execution_validation": ["mph_model", "result_data", "preview", "execution_log", "physics_validation_report"],
    }.get(step_id, [])


def _revision_guidance(step: dict[str, Any], comment: str) -> list[str]:
    return [
        f"Revise step `{step.get('title', '')}` before continuing.",
        "User comment: " + (comment or "No comment provided."),
        "Update the proposal, then request approval again.",
    ]


def _apply_step_revision(
    workflow: dict[str, Any],
    step: dict[str, Any],
    comment: str,
) -> dict[str, Any]:
    clean_comment = " ".join(str(comment or "").split())
    if not clean_comment:
        clean_comment = "用户要求重新检查当前步骤，但尚未提供具体修改内容。"
    revised_requirement = (
        f"{workflow.get('requirement', '')}\n"
        f"用户对“{step.get('title', '')}”的修正意见（优先采用）：{clean_comment}"
    )
    regenerated = _stage_proposal(
        str(step.get("id", "")),
        workflow.get("plan", {}),
        revised_requirement,
        workflow.get("modeling_contract", {}),
    )
    proposal = [
        f"已应用本轮修正意见：{clean_comment}",
        *regenerated,
    ]
    timestamp = datetime.now(timezone.utc).isoformat()
    return {
        "proposal": proposal,
        "guidance": [
            "系统已根据用户意见重建当前步骤，请检查新方案后再次批准。",
            f"本轮修正：{clean_comment}",
        ],
        "record": {
            "comment": clean_comment,
            "timestamp": timestamp,
            "proposal": proposal,
        },
    }


def _approved_generation_context(workflow: dict[str, Any]) -> str:
    lines = [str(workflow.get("requirement", "")).strip(), "", "已批准建模决策："]
    for step in workflow.get("steps", [])[:-1]:
        if step.get("status") != "approved":
            continue
        lines.append(f"[{step.get('title', step.get('id', 'step'))}]")
        lines.extend(str(item) for item in step.get("proposal", [])[:12])
        comment = step.get("approval", {}).get("comment")
        if comment:
            lines.append("用户确认：" + str(comment))
    return "\n".join(item for item in lines if item is not None).strip()


def _approved_decisions(workflow: dict[str, Any]) -> dict[str, dict[str, Any]]:
    decisions: dict[str, dict[str, Any]] = {}
    for step in workflow.get("steps", [])[:-1]:
        if step.get("status") != "approved":
            continue
        step_id = str(step.get("id", "step"))
        approval = step.get("approval", {})
        decisions[step_id] = {
            "title": step.get("title", step_id),
            "proposal": list(step.get("proposal", [])),
            "approved_outputs": list(step.get("approved_outputs", [])),
            "approval_comment": str(approval.get("comment", "")),
            "approved_at": approval.get("timestamp"),
        }
    return decisions


def _execution_handoff(package: dict[str, Any]) -> dict[str, Any]:
    readiness = package.get("generated_code", {}).get("generation_readiness", {})
    unresolved = list(readiness.get("unresolved_requirements", []))
    material = package.get("material_readiness", {})
    overall = package.get("modeling_readiness", {})
    static_audit = package.get("static_model_audit", {})
    material_ready = bool(material.get("ready_for_model_generation", False))
    if not material_ready:
        unresolved.extend(
            "缺少材料物性：" + str(row.get("name", "未命名物性"))
            for row in material.get("missing_required_properties", [])
        )
    for blocker in overall.get("blockers", []):
        if blocker not in unresolved:
            unresolved.append(str(blocker))
    if not static_audit.get("passed", False):
        unresolved.extend(
            "静态审计：" + str(row.get("message", "未命名错误"))
            for row in static_audit.get("findings", [])
            if row.get("severity") == "error"
        )
    unresolved = _dedupe_handoff_items(unresolved)
    solve_ready = bool(readiness.get("ready_to_solve", False)) and material_ready and bool(overall.get("ready_for_modeling", False)) and bool(static_audit.get("passed", False))
    return {
        "kind": "comsol_execution_handoff",
        "workflow_id": package.get("workflow_id"),
        "approved_step_ids": list(package.get("approved_decisions", {}).keys()),
        "ready_to_open": bool(readiness.get("ready_to_open", False)),
        "ready_to_solve": solve_ready,
        "next_action": "start_baseline_solve" if solve_ready else (str(overall.get("next_action", "review_blockers")) if overall.get("blockers") else ("review_material_properties" if not material_ready else "review_named_selections_and_boundaries")),
        "unresolved_requirements": unresolved,
        "contract_sha256": static_audit.get("contract_sha256", ""),
        "static_audit_path": static_audit.get("path", ""),
    }


def _append_execution_handoff_to_guidance(
    path: Path, handoff: dict[str, Any], verification_path: Path, approved_domains: list[str]
) -> None:
    """Keep the standalone guidance file aligned with the final package handoff."""
    next_action = str(handoff.get("next_action", "review_blockers"))
    unresolved = list(handoff.get("unresolved_requirements", []))
    lines = [
        "",
        "## 执行前确认",
        "",
        f"- 可打开模型：`{handoff.get('ready_to_open', False)}`",
        f"- 可直接求解：`{handoff.get('ready_to_solve', False)}`",
        f"- 下一步：`{next_action}`",
        f"- 操作说明：{_handoff_action_guidance(next_action)}",
        f"- 待核对项数量：`{len(unresolved)}`",
        f"- 完成条件：{_handoff_completion_guidance(handoff, unresolved)}",
        f"- 验证记录：`{verification_path}`",
        f"- 实际采用物理场：{_domain_labels(approved_domains)}",
    ]
    if unresolved:
        lines.append(f"- 优先处理：{unresolved[0]}")
    for item in unresolved:
        lines.append(f"- 求解前核对：{item}")
    path.write_text(path.read_text(encoding="utf-8") + "\n".join(lines) + "\n", encoding="utf-8")


def _domain_labels(domains: list[str]) -> str:
    labels = {
        "heat_transfer": "传热",
        "electromagnetics": "电流/电磁",
        "structural": "结构力学",
        "geomechanics": "岩土力学",
        "fluid": "流体流动",
        "electrochemistry": "电化学",
        "acoustics": "声学",
        "optimization": "优化",
        "geometry": "几何",
    }
    return " + ".join(labels.get(str(domain), str(domain)) for domain in domains) or "待确认"


def _handoff_action_guidance(action: str) -> str:
    guidance = {
        "start_baseline_solve": "在 COMSOL 中先运行一个基准工况，再检查求解日志和结果是否合理。",
        "review_named_selections_and_boundaries": "在 COMSOL 中核对端子、接地、对流面等命名选择集及其边界条件，然后再运行基准工况。",
        "review_material_properties": "补充或确认材料物性、单位及其温度或频率依赖关系，再运行基准工况。",
        "review_blockers": "逐项处理下方列出的未解决条件，完成后再生成或求解模型。",
    }
    return guidance.get(action, "根据下方未解决项完成核对后，再运行基准工况。")


def _handoff_completion_guidance(handoff: dict[str, Any], unresolved: list[str]) -> str:
    if handoff.get("ready_to_solve", False):
        return "当前模型已通过生成阶段检查，可执行一个基准工况求解并检查结果。"
    if unresolved:
        return "逐项完成下方核对内容，并重新生成最终模型包；确认可直接求解后再运行基准工况。"
    return "在 COMSOL 中复核当前设置后，重新生成最终模型包以确认求解状态。"


def _dedupe_handoff_items(items: list[str]) -> list[str]:
    """Remove repeated material variants while preserving the first explanation."""
    result: list[str] = []
    material_names: set[str] = set()
    for raw in items:
        item = str(raw)
        if item.startswith("补充材料物性：") or item.startswith("材料：") or item.startswith("缺少材料物性："):
            name = item.split("：", 1)[1].strip()
            if name in material_names:
                continue
            material_names.add(name)
        if item not in result:
            result.append(item)
    return result


def _final_sequence(workflow: dict[str, Any]) -> list[str]:
    return [
        "Define parameters and units.",
        "Build/import geometry and selections.",
        "Assign materials.",
        "Create approved physics interfaces and boundary conditions.",
        "Create mesh and refinement settings.",
        "Create study and solver sequence.",
        "Export approved results and CSV training columns.",
        "Save model and report verification checklist.",
    ]


def _matlab_requirements(workflow: dict[str, Any]) -> list[str]:
    requirements = [
        "Use LiveLink MATLAB API in the approved sequence.",
        "Keep boundary IDs and named selections as explicit review comments.",
        "Add table export for approved outputs.",
        f"Requirement: {workflow.get('requirement', '')}",
    ]
    requirement = str(workflow.get("requirement", "")).lower()
    if any(token in requirement for token in ("不同电压", "比较不同", "参数扫描", "sweep", "parametric", "compare different", "different voltage")):
        requirements.append("Voltage sweep uses the review-only default range 0.1-1 mV with 37 sample points; replace it with approved values before solving.")
    return requirements


def _java_requirements(workflow: dict[str, Any]) -> list[str]:
    return [
        "Use COMSOL Java API equivalents for parameters, geometry, physics, mesh, study, and results.",
        "Keep comments where COMSOL entity IDs must be verified.",
        "Save the final model as MPH after baseline solve settings are reviewed.",
    ]


def _verification_checklist(workflow: dict[str, Any]) -> list[str]:
    checklist = [
        "Confirm material units and property sources.",
        "Confirm boundary selections after geometry generation.",
        "Run one baseline solve before parameter sweeps.",
        "Run mesh refinement checks for key outputs.",
        "Export CSV only after derived values are verified.",
    ]
    readiness = validate_material_readiness(
        str(workflow.get("requirement", "")),
        workflow.get("plan", {}).get("inferred_domains", []),
        workflow.get("plan", {}).get("candidate_parameters", []),
    )
    if not readiness["ready_for_model_generation"]:
        checklist.insert(1, "补充材料物性后再进行最终求解；当前缺少：" + "、".join(row["name"] for row in readiness["missing_required_properties"]))
    return checklist


def _package_markdown(package: dict[str, Any]) -> str:
    lines = [
        "# Approved COMSOL Modeling Package",
        "",
        f"- Workflow: `{package.get('workflow_id', '')}`",
        f"- Requirement: {package.get('requirement', '')}",
        "",
        "## Modeling Sequence",
        "",
    ]
    lines.extend(f"- {item}" for item in package.get("modeling_sequence", []))
    lines.extend(["", "## MATLAB Requirements", ""])
    lines.extend(f"- {item}" for item in package.get("matlab_generation_requirements", []))
    lines.extend(["", "## Java Requirements", ""])
    lines.extend(f"- {item}" for item in package.get("java_generation_requirements", []))
    lines.extend(["", "## Verification Checklist", ""])
    lines.extend(f"- {item}" for item in package.get("verification_checklist", []))
    material = package.get("material_readiness", {})
    lines.extend(["", "## Material Readiness", ""])
    lines.append(f"- ready_for_model_generation: `{material.get('ready_for_model_generation', False)}`")
    for item in material.get("risks", []):
        lines.append(f"- risk: {item}")
    overall = package.get("modeling_readiness", {})
    lines.extend(["", "## Overall Modeling Readiness", ""])
    lines.append(f"- ready_for_modeling: `{overall.get('ready_for_modeling', False)}`")
    lines.append(f"- next_action: `{overall.get('next_action', 'review_blockers')}`")
    for item in overall.get("blockers", []):
        lines.append(f"- blocker: {item}")
    generated = package.get("generated_code", {})
    outputs = generated.get("outputs", {}) if isinstance(generated, dict) else {}
    readiness = generated.get("generation_readiness", {}) if isinstance(generated, dict) else {}
    handoff = package.get("execution_handoff", {})
    lines.extend(["", "## Generated Files", ""])
    for name, path in outputs.items():
        lines.append(f"- {name}: `{path}`")
    lines.extend(["", "## Generation Readiness", ""])
    lines.append(f"- status: `{readiness.get('status', 'unknown')}`")
    lines.append(f"- ready_to_open: `{handoff.get('ready_to_open', readiness.get('ready_to_open', False))}`")
    lines.append(f"- ready_to_solve: `{handoff.get('ready_to_solve', False)}`")
    for item in readiness.get("unresolved_requirements", []):
        lines.append(f"- unresolved: {item}")
    lines.extend(["", "## Execution Handoff", ""])
    lines.append(f"- next_action: `{handoff.get('next_action', 'unknown')}`")
    lines.append(f"- approved_steps: `{', '.join(handoff.get('approved_step_ids', []))}`")
    for item in handoff.get("unresolved_requirements", []):
        lines.append(f"- review_before_execution: {item}")
    return "\n".join(lines) + "\n"


def _workflow_id(requirement: str) -> str:
    slug = re.sub(r"[^\w\u4e00-\u9fff]+", "_", requirement.strip(), flags=re.UNICODE).strip("_")
    slug = slug[:40] or "comsol_workflow"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return f"{slug}_{stamp}"
