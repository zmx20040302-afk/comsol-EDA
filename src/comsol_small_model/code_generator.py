from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .boundary_knowledge import infer_boundary_conditions
from .case_memory import generate_model_plan, query_memory
from .coupled_physics_knowledge import analyze_coupled_physics
from .geometry_parameter_knowledge import analyze_geometry_parameters, validate_geometry_readiness
from .material_property_knowledge import analyze_material_properties, validate_material_readiness


@dataclass(frozen=True)
class GeneratedComsolCode:
    requirement: str
    plan: dict[str, Any]
    matlab_code: str
    java_code: str
    theory_guidance: list[str]
    refinement_suggestions: list[str]
    existing_content_review: dict[str, Any]
    generation_readiness: dict[str, Any]
    matlab_path: str
    java_path: str
    guidance_path: str
    verification_path: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "requirement": self.requirement,
            "plan": self.plan,
            "matlab_code": self.matlab_code,
            "java_code": self.java_code,
            "theory_guidance": self.theory_guidance,
            "refinement_suggestions": self.refinement_suggestions,
            "existing_content_review": self.existing_content_review,
            "generation_readiness": self.generation_readiness,
            "outputs": {
                "matlab": self.matlab_path,
                "java": self.java_path,
                "guidance": self.guidance_path,
                "verification": self.verification_path,
            },
        }


def generate_comsol_code_from_memory(
    requirement: str,
    memory_path: str | Path = "generated/case_memory/case_memory.json",
    output_dir: str | Path = "generated/code",
    output_prefix: str = "generated_comsol_model",
    top_k: int = 5,
    existing_content: str = "",
    approved_domains: list[str] | None = None,
    approved_requirement: str | None = None,
) -> GeneratedComsolCode:
    requirement = requirement.strip()
    if not requirement:
        raise ValueError("requirement is empty")

    plan = generate_model_plan(requirement, memory_path=memory_path, top_k=top_k)
    plan.setdefault("requirement", requirement)
    if approved_domains:
        plan["inferred_domains"] = list(dict.fromkeys(str(domain) for domain in approved_domains))
    if approved_requirement:
        plan["dimension_requirement"] = str(approved_requirement)
        plan["study_requirement"] = str(approved_requirement)
    retrieval = query_memory(requirement, memory_path=memory_path, top_k=top_k)
    matched_cases = [item.get("case", {}) for item in retrieval.get("matches", [])]
    model_id = _safe_identifier(output_prefix or "generated_comsol_model")
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    matlab_path = destination / f"{model_id}.m"
    java_path = destination / f"{_java_class_name(model_id)}.java"
    guidance_path = destination / f"{model_id}_guidance.md"
    verification_path = destination / f"{model_id}_verification.json"
    matlab_code = build_matlab_code(requirement, plan, model_id)
    java_code = build_java_code(requirement, plan, model_id)
    theory_guidance = build_theory_guidance(requirement, plan, matched_cases)
    existing_content_review = review_existing_content(existing_content, plan, matched_cases)
    refinement_suggestions = build_refinement_suggestions(existing_content_review, plan, matched_cases)
    generation_readiness = assess_generation_readiness(requirement, plan, matlab_code, java_code)
    matlab_path.write_text(matlab_code, encoding="utf-8")
    java_path.write_text(java_code, encoding="utf-8")
    guidance_path.write_text(
        build_guidance_markdown(
            requirement,
            plan,
            matched_cases,
            theory_guidance,
            refinement_suggestions,
            existing_content_review,
            matlab_path,
            java_path,
        ),
        encoding="utf-8",
    )
    verification_path.write_text(
        json.dumps(generation_readiness, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return GeneratedComsolCode(
        requirement=requirement,
        plan=plan,
        matlab_code=matlab_code,
        java_code=java_code,
        theory_guidance=theory_guidance,
        refinement_suggestions=refinement_suggestions,
        existing_content_review=existing_content_review,
        generation_readiness=generation_readiness,
        matlab_path=str(matlab_path),
        java_path=str(java_path),
        guidance_path=str(guidance_path),
        verification_path=str(verification_path),
    )


def build_matlab_code(requirement: str, plan: dict[str, Any], model_id: str = "generated_comsol_model") -> str:
    # MATLAB requires a public function to have the same name as its .m file.
    # The generated builder is written to <model_id>.m by the caller.
    function_name = _safe_identifier(model_id)
    lines = [
        f"function model = {function_name}()",
        f"%{function_name.upper()} Memory-assisted COMSOL LiveLink builder.",
        "% 由 comsol_training_small_model 生成。",
        f"% Requirement: {_comment_text(requirement)}",
        "% GENERATION STATUS: REVIEW_REQUIRED until verification JSON reports ready_to_solve=true.",
        "",
        "import com.comsol.model.*",
        "import com.comsol.model.util.*",
        "",
        "model = ModelUtil.create('Model');",
        f"model.label('{model_id}.mph');",
        "model.modelNode.create('mod1');",
        "",
        *_matlab_parameters(plan, requirement),
        "",
        "model.component.create('comp1', true);",
        f"model.component('comp1').geom.create('geom1', {_dimension(plan)});",
        "model.component('comp1').geom('geom1').lengthUnit('m');",
        "% REVIEW REQUIRED: confirm that the selected geometry pattern matches the approved dimensions.",
        *_matlab_geometry(plan),
        "",
        *_matlab_material(plan, requirement),
        "",
        *_matlab_physics(plan),
        "",
        "model.component('comp1').mesh.create('mesh1');",
        "model.component('comp1').mesh('mesh1').create('size1', 'Size');",
        "model.component('comp1').mesh('mesh1').feature('size1').set('custom', true);",
        "model.component('comp1').mesh('mesh1').feature('size1').set('hmax', 'hmax');",
        *_matlab_mesh_elements(plan),
        "model.component('comp1').mesh('mesh1').run;",
        *_matlab_result_operators(plan),
        "",
        *_matlab_study(plan),
        "",
        *_matlab_outputs(plan),
        "",
        "% Saving is handled by the execution wrapper with mphsave(model, output_path).",
        "end",
        "",
    ]
    return "\n".join(lines)


def build_java_code(requirement: str, plan: dict[str, Any], model_id: str = "generated_comsol_model") -> str:
    class_name = _java_class_name(model_id)
    lines = [
        "import com.comsol.model.*;",
        "import com.comsol.model.util.*;",
        "",
        f"public class {class_name} {{",
        "  public static Model run() {",
        "    Model model = ModelUtil.create(\"Model\");",
        f"    model.label(\"{model_id}.mph\");",
        "    model.modelNode().create(\"mod1\");",
        f"    // Requirement: {_comment_text(requirement)}",
        "    // GENERATION STATUS: REVIEW_REQUIRED until verification JSON reports ready_to_solve=true.",
        "",
        *_java_parameters(plan, requirement),
        "",
        "    model.component().create(\"comp1\", true);",
        f"    model.component(\"comp1\").geom().create(\"geom1\", {_dimension(plan)});",
        "    model.component(\"comp1\").geom(\"geom1\").lengthUnit(\"m\");",
        "    // REVIEW REQUIRED: confirm that the selected geometry pattern matches the approved dimensions.",
        *_java_geometry(plan),
        "",
        *_java_material(plan, requirement),
        "",
        *_java_physics(plan),
        "",
        "    model.component(\"comp1\").mesh().create(\"mesh1\");",
        "    model.component(\"comp1\").mesh(\"mesh1\").create(\"size1\", \"Size\");",
        "    model.component(\"comp1\").mesh(\"mesh1\").feature(\"size1\").set(\"custom\", true);",
        "    model.component(\"comp1\").mesh(\"mesh1\").feature(\"size1\").set(\"hmax\", \"hmax\");",
        *_java_mesh_elements(plan),
        "    model.component(\"comp1\").mesh(\"mesh1\").run();",
        *_java_result_operators(plan),
        "",
        *_java_study(plan),
        "",
        *_java_outputs(plan),
        "",
        "    return model;",
        "  }",
        "",
        "  public static void main(String[] args) {",
        "    Model model = run();",
        f"    model.save(\"{model_id}.mph\");",
        "  }",
        "}",
        "",
    ]
    return "\n".join(lines)


def build_theory_guidance(requirement: str, plan: dict[str, Any], matched_cases: list[dict[str, Any]]) -> list[str]:
    domains = set(plan.get("inferred_domains", []))
    content_physics = _merged_case_content(matched_cases, "physics")
    theory_keywords = _merged_case_content(matched_cases, "theory_keywords")
    geometry_analysis = analyze_geometry_parameters(
        requirement,
        list(domains),
        plan.get("candidate_parameters", []),
    )
    material_analysis = analyze_material_properties(
        requirement,
        list(domains),
        plan.get("candidate_parameters", []),
    )
    boundary_analysis = infer_boundary_conditions(requirement, list(domains))
    coupling_analysis = analyze_coupled_physics(requirement, list(domains))
    guidance = [
        "建模顺序应保持为：参数 -> 几何 -> 选择集 -> 材料 -> 物理场 -> 边界/初始条件 -> 网格 -> 研究/求解 -> 结果导出。",
        "生成代码中的边界编号和选择集必须在 COMSOL 中复核；学习库只能提供案例模式和 API 结构，不能替代几何实体编号确认。",
        "几何模型与参数指导：" + geometry_analysis["summary"] + " " + geometry_analysis["dimension"],
        "几何要点：" + "；".join(geometry_analysis["geometry"][:6]) + "。",
        "关键参数建议：" + "；".join(
            f"{item['name']}={item['value']}（{item['description']}）"
            for item in geometry_analysis["parameters"][:8]
        ) + "。",
        "选择集与扫描建议：选择集=" + "；".join(geometry_analysis["selection_advice"][:6])
        + "；扫描变量=" + "、".join(geometry_analysis["sweep_advice"][:6]) + "。",
        "材料与物性参数指导：" + material_analysis["summary"],
        "必填物性：" + "；".join(
            f"{row['name']}({row['symbol']}, {row['unit']})"
            for row in material_analysis["required_properties"][:8]
        ) + "。",
        "物性变化关系：" + "；".join(material_analysis["dependencies"][:4]) + "。",
        "边界条件与初始条件指导：" + boundary_analysis["summary"],
        "建议边界：" + "；".join(boundary_analysis["boundary_types"][:8]) + "。",
        "建议初始条件：" + "；".join(boundary_analysis["initial_conditions"][:6]) + "。",
        "物理场复合场检查：" + (
            f"{coupling_analysis['summary']} 主物理场={coupling_analysis['primary_physics']}；"
            f"耦合物理场={'、'.join(coupling_analysis['coupled_physics'][:6])}；"
            f"多物理场节点={'、'.join(coupling_analysis['multiphysics_nodes'][:6])}。"
            if coupling_analysis.get("is_coupled")
            else coupling_analysis["summary"]
        ),
    ]
    if "heat_transfer" in domains or any("HeatTransfer" in item for item in content_physics):
        guidance.append("传热模型需要确认热源、温度边界、热通量或对流换热条件，并检查材料的导热系数、密度和热容。")
    if "electromagnetics" in domains or any("ConductiveMedia" in item or "Electric" in item for item in content_physics):
        guidance.append("电流/电磁模型需要确认端子、电势、接地和绝缘边界；若与传热耦合，应把焦耳热或损耗项传递到热场。")
    if _needs_parametric_sweep(plan):
        guidance.append(
            "参数扫描说明：代码中的 "
            + _voltage_sweep_expression(plan).replace("range(", "").replace(")", "").replace(",", " 至 ")
            + " 仅为待审核默认范围，必须按已确认的工况替换后再求解。"
        )
    if "fluid" in domains or any("LaminarFlow" in item for item in content_physics):
        guidance.append("流体模型需要确认入口、出口、壁面和压力条件；微流动案例通常还要同时检查稀物质传递或扩散系数。")
    if "structural" in domains or any("SolidMechanics" in item for item in content_physics):
        guidance.append("结构力学模型需要确认固定约束、载荷、接触/对称条件和材料弹性参数；特征频率问题应使用 Eigenfrequency 研究。")
    if "acoustics" in domains or any("PressureAcoustics" in item for item in content_physics):
        guidance.append("声学模型需要确认声硬边界、声源、压力条件和频域/特征频率研究设置。")
    if theory_keywords:
        guidance.append("已学习案例中的理论关键词包括：" + "，".join(theory_keywords[:12]) + "。")
    if matched_cases:
        names = "，".join(str(case.get("title", "案例")) for case in matched_cases[:5])
        guidance.append(f"本次生成优先参考以下已学习案例：{names}。")
    return guidance


def review_existing_content(existing_content: str, plan: dict[str, Any], matched_cases: list[dict[str, Any]]) -> dict[str, Any]:
    text = existing_content or ""
    lowered = text.lower()
    checks = {
        "has_parameters": "model.param" in lowered or ".param()" in lowered,
        "has_geometry": ".geom" in lowered,
        "has_physics": ".physics" in lowered,
        "has_material": ".material" in lowered,
        "has_mesh": ".mesh" in lowered,
        "has_study": ".study" in lowered,
        "has_results": ".result" in lowered,
        "has_boundary_selection": ".selection" in lowered,
    }
    expected_physics = [item["interface"] for item in _physics_specs(plan)]
    present_expected = [physics for physics in expected_physics if physics.lower() in lowered]
    missing_expected = [physics for physics in expected_physics if physics.lower() not in lowered]
    matched_content = {
        "physics": _merged_case_content(matched_cases, "physics")[:20],
        "geometry": _merged_case_content(matched_cases, "geometry")[:20],
        "studies": _merged_case_content(matched_cases, "studies")[:20],
        "results": _merged_case_content(matched_cases, "results")[:20],
    }
    return {
        "kind": "existing_comsol_content_review",
        "provided": bool(text.strip()),
        "length": len(text),
        "checks": checks,
        "expected_physics": expected_physics,
        "present_expected_physics": present_expected,
        "missing_expected_physics": missing_expected,
        "matched_case_content": matched_content,
    }


def assess_generation_readiness(
    requirement: str,
    plan: dict[str, Any],
    matlab_code: str,
    java_code: str,
) -> dict[str, Any]:
    domains = list(plan.get("inferred_domains", []))
    boundary = infer_boundary_conditions(requirement, domains)
    material = validate_material_readiness(requirement, domains, plan.get("candidate_parameters", []))
    geometry = validate_geometry_readiness(requirement, domains, plan.get("candidate_parameters", []))
    unresolved = [
        "确认生成几何中的材料域和边界选择集。",
        "在 COMSOL 中核对物理接口名称是否与已安装模块一致。",
    ]
    if boundary.get("matches"):
        unresolved.append("把已批准边界条件绑定到经过核对的命名选择集。")
    else:
        unresolved.append("需求尚不足以唯一确定边界和初始条件。")
    if "水力压裂" in requirement or "裂缝" in requirement or "裂纹" in requirement:
        unresolved.append("确认裂缝表示方法、断裂参数和裂纹起始区域。")
    if any("terminal current" in str(item).lower() or "端子电流" in str(item) for item in plan.get("candidate_outputs", [])):
        unresolved.append("将端子电流导出绑定到经过核对的端子边界积分选择集。")
    if any(
        any(token in str(item).lower() for token in ("pressure drop", "压降", "flow rate", "流量"))
        for item in plan.get("candidate_outputs", [])
    ):
        unresolved.append("将压力降或流量导出绑定到经过核对的入口、出口或截面选择集。")
    unresolved.extend(
        "补充材料物性：" + str(row.get("name", "未命名物性"))
        for row in material.get("missing_required_properties", [])
    )
    unresolved.extend(
        "补充几何信息：" + str(item)
        for item in geometry.get("missing_geometry_evidence", [])
    )
    checks = {
        "matlab_has_model_creation": "ModelUtil.create" in matlab_code,
        "matlab_has_geometry": ".geom" in matlab_code,
        "matlab_has_material": ".material" in matlab_code,
        "matlab_has_physics": ".physics" in matlab_code,
        "matlab_has_mesh": ".mesh" in matlab_code,
        "matlab_has_study": ".study" in matlab_code,
        "java_has_model_creation": "ModelUtil.create" in java_code,
        "java_has_geometry": ".geom()" in java_code or ".geom(" in java_code,
        "java_has_physics": ".physics()" in java_code or ".physics(" in java_code,
    }
    study_tag, study_type = _study_spec(plan)
    checks.update(
        {
            "matlab_has_expected_study": f"'{study_tag}', '{study_type}'" in matlab_code,
            "java_has_expected_study": f'"{study_tag}", "{study_type}"' in java_code,
        }
    )
    if _is_joule_heating_plan(plan):
        checks.update(
            {
                "matlab_has_conductive_media": "'ConductiveMedia'" in matlab_code,
                "matlab_has_heat_transfer": "'HeatTransfer'" in matlab_code,
                "matlab_has_joule_heating_coupling": "ElectromagneticHeating" in matlab_code,
                "matlab_has_electrothermal_parameters": all(
                    token in matlab_code for token in ("'Vtot'", "'T_amb'", "'htc'", "'sigma_ref'")
                ),
                "matlab_has_electrical_material_property": "'electricconductivity', 'sigma_ref'" in matlab_code,
                "matlab_has_boundary_review_template": all(
                    token in matlab_code
                    for token in ("'sel_terminal'", "'sel_ground'", "'sel_convection'", "'ElectricPotential'", "'V0', 'Vtot'", "'HeatFluxBoundary'")
                ),
                "java_has_joule_heating_coupling": "ElectromagneticHeating" in java_code,
                "java_has_boundary_selection_template": all(
                    token in java_code
                    for token in ('\"sel_terminal\"', '\"sel_ground\"', '\"sel_convection\"')
                ),
            }
        )
    structural_complete = all(checks.values())
    return {
        "kind": "generated_comsol_code_verification",
        "status": "review_required" if unresolved else "ready",
        "ready_to_open": structural_complete,
        "ready_to_solve": structural_complete and not unresolved and material["ready_for_model_generation"] and geometry["ready_for_meshing"],
        "structural_checks": checks,
        "unresolved_requirements": unresolved,
        "material_readiness": material,
        "geometry_readiness": geometry,
        "approved_domains": domains,
        "boundary_families": boundary.get("boundary_types", []),
        "instructions": [
            "先在 COMSOL with MATLAB 或 COMSOL Java 环境中运行到几何构建结束。",
            "核对命名选择集、材料域、边界条件和单位。",
            "清空 unresolved_requirements 后再启用基准求解。",
        ],
    }


def build_refinement_suggestions(
    review: dict[str, Any],
    plan: dict[str, Any],
    matched_cases: list[dict[str, Any]],
) -> list[str]:
    suggestions = []
    if not review.get("provided"):
        suggestions.append("未提供现有脚本或模型摘要；本次输出为基于学习库的新建模型模板，可作为后续修正基线。")
    checks = review.get("checks", {})
    missing_steps = [
        ("has_parameters", "补充参数定义，并把关键尺寸、材料参数和载荷写成可扫描参数。"),
        ("has_geometry", "补充或替换几何构建段，优先复用相似案例中的几何序列。"),
        ("has_physics", "补充物理场接口，并与需求和已学习案例中的物理场保持一致。"),
        ("has_material", "补充材料节点，至少包含密度、弹性参数、导热或电学参数等必要属性。"),
        ("has_mesh", "补充网格设置，并在孔、裂纹、边界层或高梯度区域局部加密。"),
        ("has_study", "补充研究/求解器设置，按稳态、瞬态、频域、特征频率或参数扫描选择。"),
        ("has_results", "补充结果导出，保存关键全局量、场图和用于训练的 CSV。"),
        ("has_boundary_selection", "补充选择集或边界编号复核步骤，避免边界条件施加到错误实体。"),
    ]
    for key, message in missing_steps:
        if not checks.get(key, False):
            suggestions.append(message)
    for physics in review.get("missing_expected_physics", []):
        suggestions.append(f"根据需求和学习库，应补充或复核 `{physics}` 物理接口。")
    if matched_cases:
        best = matched_cases[0]
        content = best.get("case_content", {})
        if content.get("physics"):
            suggestions.append(f"可参考 `{best.get('title')}` 中的物理场设置：{', '.join(content.get('physics', [])[:5])}。")
        if content.get("studies"):
            suggestions.append(f"可参考 `{best.get('title')}` 中的研究设置：{', '.join(content.get('studies', [])[:5])}。")
    if not suggestions:
        suggestions.append("现有内容包含主要 COMSOL 建模段；下一步应在 COMSOL 中运行基准求解，并根据报错修正边界编号、材料属性和求解器设置。")
    return suggestions[:16]


def build_guidance_markdown(
    requirement: str,
    plan: dict[str, Any],
    matched_cases: list[dict[str, Any]],
    theory_guidance: list[str],
    refinement_suggestions: list[str],
    existing_content_review: dict[str, Any],
    matlab_path: Path,
    java_path: Path,
) -> str:
    lines = [
        "# COMSOL 建模代码与理论指导",
        "",
        f"- 需求: {requirement}",
        f"- MATLAB 输出: `{matlab_path}`",
        f"- Java 输出: `{java_path}`",
        "",
        "## 理论与建模指导",
        "",
    ]
    lines.extend(f"- {item}" for item in theory_guidance)
    lines.extend(["", "## 已学习案例证据", ""])
    for case in matched_cases[:8]:
        content = case.get("case_content", {})
        totals = content.get("totals", {})
        lines.append(
            f"- `{case.get('title', '案例')}`: 内容证据 {totals.get('model_tree_items', 0)} 条；"
            f"物理场={', '.join(content.get('physics', [])[:5]) or '未抽取'}"
        )
    lines.extend(["", "## 现有内容检查", ""])
    checks = existing_content_review.get("checks", {})
    if existing_content_review.get("provided"):
        for key, value in checks.items():
            lines.append(f"- {key}: {'已包含' if value else '缺失或未识别'}")
    else:
        lines.append("- 未提供现有内容，本次按新建模型模板处理。")
    lines.extend(["", "## 调整和完善建议", ""])
    lines.extend(f"- {item}" for item in refinement_suggestions)
    lines.extend(["", "## 后续验证路径", ""])
    lines.extend(
        [
            "- 在 COMSOL 中打开生成脚本，先不批量扫描，只运行一个基准模型。",
            "- 核对所有选择集、边界编号和材料参数。",
            "- 求解通过后，再添加参数扫描并导出 CSV。",
            "- 把修正后的 MATLAB/Java 脚本重新放回案例库，继续学习和完善记忆库。",
        ]
    )
    return "\n".join(lines) + "\n"


def _matlab_parameters(plan: dict[str, Any], requirement: str = "") -> list[str]:
    defaults = _material_parameter_defaults(requirement, plan)
    lines = [
        "% Parameters merged from matched case memory and defaults.",
        f"model.param.set('rho_ref', '{defaults['density']}', 'Material density');",
        f"model.param.set('k_ref', '{defaults['thermalconductivity']}', 'Material thermal conductivity');",
        f"model.param.set('Cp_ref', '{defaults['heatcapacity']}', 'Material heat capacity');",
        f"model.param.set('sigma_ref', '{defaults['electricconductivity']}', 'Material electrical conductivity');",
        "model.param.set('hmax', '0.02[m]', 'Maximum mesh size');",
    ]
    if {"structural", "geomechanics"}.intersection(plan.get("inferred_domains", [])):
        lines.extend(
            [
                "model.param.set('E_ref', '35.1[GPa]', 'Youngs modulus');",
                "model.param.set('nu_ref', '0.25', 'Poissons ratio');",
            ]
        )
    if _is_joule_heating_plan(plan):
        lines.extend(
            [
                "model.param.set('Vtot', '20[mV]', 'Applied electric potential difference');",
                "model.param.set('T_amb', '293.15[K]', 'Ambient temperature');",
                "model.param.set('htc', '5[W/(m^2*K)]', 'Convective heat transfer coefficient');",
            ]
        )
    for param in _safe_parameters(plan):
        lines.append(f"model.param.set('{param['name']}', '{_matlab_string(param['value'])}', '{_matlab_string(param['description'])}');")
    return lines


def _merged_case_content(matched_cases: list[dict[str, Any]], key: str) -> list[str]:
    values = []
    seen = set()
    for case in matched_cases:
        content = case.get("case_content", {}) if isinstance(case, dict) else {}
        for value in content.get(key, []):
            text = str(value).strip()
            if text and text not in seen:
                seen.add(text)
                values.append(text)
            if len(values) >= 80:
                return values
    return values


def _java_parameters(plan: dict[str, Any], requirement: str = "") -> list[str]:
    defaults = _material_parameter_defaults(requirement, plan)
    lines = [
        "    // Parameters merged from matched case memory and defaults.",
        f"    model.param().set(\"rho_ref\", \"{defaults['density']}\", \"Material density\");",
        f"    model.param().set(\"k_ref\", \"{defaults['thermalconductivity']}\", \"Material thermal conductivity\");",
        f"    model.param().set(\"Cp_ref\", \"{defaults['heatcapacity']}\", \"Material heat capacity\");",
        f"    model.param().set(\"sigma_ref\", \"{defaults['electricconductivity']}\", \"Material electrical conductivity\");",
        "    model.param().set(\"hmax\", \"0.02[m]\", \"Maximum mesh size\");",
    ]
    if {"structural", "geomechanics"}.intersection(plan.get("inferred_domains", [])):
        lines.extend(
            [
                "    model.param().set(\"E_ref\", \"35.1[GPa]\", \"Youngs modulus\");",
                "    model.param().set(\"nu_ref\", \"0.25\", \"Poissons ratio\");",
            ]
        )
    if _is_joule_heating_plan(plan):
        lines.extend(
            [
                "    model.param().set(\"Vtot\", \"20[mV]\", \"Applied electric potential difference\");",
                "    model.param().set(\"T_amb\", \"293.15[K]\", \"Ambient temperature\");",
                "    model.param().set(\"htc\", \"5[W/(m^2*K)]\", \"Convective heat transfer coefficient\");",
            ]
        )
    for param in _safe_parameters(plan):
        lines.append(
            f"    model.param().set(\"{param['name']}\", \"{_java_string(param['value'])}\", \"{_java_string(param['description'])}\");"
        )
    return lines


def _material_parameter_defaults(requirement: str, plan: dict[str, Any]) -> dict[str, str]:
    analysis = analyze_material_properties(
        requirement,
        plan.get("inferred_domains", []),
        plan.get("candidate_parameters", []),
    )
    defaults = {
        "density": "2500[kg/m^3]",
        "thermalconductivity": "1[W/(m*K)]",
        "heatcapacity": "800[J/(kg*K)]",
        "electricconductivity": "1[S/m]",
    }
    recognized = analysis.get("recognized_materials", [])
    if recognized:
        defaults.update(recognized[0].get("properties", {}))
    return defaults


def _material_name(requirement: str, plan: dict[str, Any]) -> str:
    analysis = analyze_material_properties(requirement, plan.get("inferred_domains", []), plan.get("candidate_parameters", []))
    recognized = analysis.get("recognized_materials", [])
    return str(recognized[0]["name"]) if recognized else "material_to_review"


def _matlab_material(plan: dict[str, Any], requirement: str) -> list[str]:
    lines = [
        "model.component('comp1').material.create('mat1', 'Common');",
        f"model.component('comp1').material('mat1').label('{_matlab_string(_material_name(requirement, plan))}');",
        "model.component('comp1').material('mat1').selection.all;",
        "model.component('comp1').material('mat1').propertyGroup('def').set('density', 'rho_ref');",
        "model.component('comp1').material('mat1').propertyGroup('def').set('thermalconductivity', 'k_ref');",
        "model.component('comp1').material('mat1').propertyGroup('def').set('heatcapacity', 'Cp_ref');",
        "model.component('comp1').material('mat1').propertyGroup('def').set('electricconductivity', 'sigma_ref');",
    ]
    if {"structural", "geomechanics"}.intersection(plan.get("inferred_domains", [])):
        lines.extend(
            [
                "model.component('comp1').material('mat1').propertyGroup.create('Enu', 'Enu', 'Youngs modulus and Poissons ratio');",
                "model.component('comp1').material('mat1').propertyGroup('Enu').set('E', 'E_ref');",
                "model.component('comp1').material('mat1').propertyGroup('Enu').set('nu', 'nu_ref');",
            ]
        )
    return lines


def _java_material(plan: dict[str, Any], requirement: str) -> list[str]:
    lines = [
        "    model.component(\"comp1\").material().create(\"mat1\", \"Common\");",
        f"    model.component(\"comp1\").material(\"mat1\").label(\"{_java_string(_material_name(requirement, plan))}\");",
        "    model.component(\"comp1\").material(\"mat1\").selection().all();",
        "    model.component(\"comp1\").material(\"mat1\").propertyGroup(\"def\").set(\"density\", \"rho_ref\");",
        "    model.component(\"comp1\").material(\"mat1\").propertyGroup(\"def\").set(\"thermalconductivity\", \"k_ref\");",
        "    model.component(\"comp1\").material(\"mat1\").propertyGroup(\"def\").set(\"heatcapacity\", \"Cp_ref\");",
        "    model.component(\"comp1\").material(\"mat1\").propertyGroup(\"def\").set(\"electricconductivity\", \"sigma_ref\");",
    ]
    if {"structural", "geomechanics"}.intersection(plan.get("inferred_domains", [])):
        lines.extend(
            [
                "    model.component(\"comp1\").material(\"mat1\").propertyGroup().create(\"Enu\", \"Enu\", \"Youngs modulus and Poissons ratio\");",
                "    model.component(\"comp1\").material(\"mat1\").propertyGroup(\"Enu\").set(\"E\", \"E_ref\");",
                "    model.component(\"comp1\").material(\"mat1\").propertyGroup(\"Enu\").set(\"nu\", \"nu_ref\");",
            ]
        )
    return lines


def _is_joule_heating_plan(plan: dict[str, Any]) -> bool:
    domains = set(plan.get("inferred_domains", []))
    requirement = str(plan.get("requirement", "")).lower()
    return {"electromagnetics", "heat_transfer"}.issubset(domains) and any(
        word in requirement
        for word in (
            "joule",
            "焦耳",
            "电热",
            "electrothermal",
            "通电发热",
            "通电加热",
            "电流发热",
            "电阻发热",
        )
    )


def _has_auto_joule_rectangle_boundaries(plan: dict[str, Any]) -> bool:
    """Allow entity IDs only for the deliberately narrow 2D rectangle benchmark."""
    dimension_requirement = str(plan.get("dimension_requirement") or plan.get("requirement", ""))
    dimensions = _explicit_dimension_parameters(dimension_requirement)
    return _is_joule_heating_plan(plan) and _dimension(plan) == 2 and {"L_ref", "W_ref"}.issubset(dimensions)


def _matlab_geometry(plan: dict[str, Any]) -> list[str]:
    analysis = analyze_geometry_parameters(
        plan.get("requirement", ""),
        plan.get("inferred_domains", []),
        plan.get("candidate_parameters", []),
    )
    if analysis["matches"] and analysis["matches"][0]["id"] == "hydraulic_fracturing_borehole":
        return [
            "% Geometry guidance: " + _comment_text(analysis["summary"]),
            "model.component('comp1').geom('geom1').create('rect1', 'Rectangle');",
            "model.component('comp1').geom('geom1').feature('rect1').set('size', {'L_ref' 'W_ref'});",
            "model.component('comp1').geom('geom1').feature('rect1').set('pos', {'-L_ref/2' '-W_ref/2'});",
            "model.component('comp1').geom('geom1').create('c1', 'Circle');",
            "model.component('comp1').geom('geom1').feature('c1').set('r', 'rb');",
            "model.component('comp1').geom('geom1').create('dif1', 'Difference');",
            "model.component('comp1').geom('geom1').feature('dif1').selection('input').set({'rect1'});",
            "model.component('comp1').geom('geom1').feature('dif1').selection('input2').set({'c1'});",
            "% REVIEW REQUIRED: add the approved fracture/weak-plane or phase-field initialization.",
            "model.component('comp1').geom('geom1').run;",
            "% REVIEW REQUIRED: bind borehole, outer-boundary, and rock-domain named selections.",
        ]
    if _dimension(plan) == 3:
        return [
            "model.component('comp1').geom('geom1').create('blk1', 'Block');",
            "model.component('comp1').geom('geom1').feature('blk1').set('size', {'L_ref' 'W_ref' 'H_ref'});",
            "model.component('comp1').geom('geom1').run;",
        ]
    return [
        "model.component('comp1').geom('geom1').create('r1', 'Rectangle');",
        "model.component('comp1').geom('geom1').feature('r1').set('size', {'L_ref' 'W_ref'});",
        "model.component('comp1').geom('geom1').run;",
    ]


def _java_geometry(plan: dict[str, Any]) -> list[str]:
    analysis = analyze_geometry_parameters(
        plan.get("requirement", ""),
        plan.get("inferred_domains", []),
        plan.get("candidate_parameters", []),
    )
    if analysis["matches"] and analysis["matches"][0]["id"] == "hydraulic_fracturing_borehole":
        return [
            "    // Geometry guidance: " + _comment_text(analysis["summary"]),
            "    model.component(\"comp1\").geom(\"geom1\").create(\"rect1\", \"Rectangle\");",
            "    model.component(\"comp1\").geom(\"geom1\").feature(\"rect1\").set(\"size\", new String[]{\"L_ref\", \"W_ref\"});",
            "    model.component(\"comp1\").geom(\"geom1\").feature(\"rect1\").set(\"pos\", new String[]{\"-L_ref/2\", \"-W_ref/2\"});",
            "    model.component(\"comp1\").geom(\"geom1\").create(\"c1\", \"Circle\");",
            "    model.component(\"comp1\").geom(\"geom1\").feature(\"c1\").set(\"r\", \"rb\");",
            "    model.component(\"comp1\").geom(\"geom1\").create(\"dif1\", \"Difference\");",
            "    model.component(\"comp1\").geom(\"geom1\").feature(\"dif1\").selection(\"input\").set(new String[]{\"rect1\"});",
            "    model.component(\"comp1\").geom(\"geom1\").feature(\"dif1\").selection(\"input2\").set(new String[]{\"c1\"});",
            "    // REVIEW REQUIRED: add the approved fracture/weak-plane or phase-field initialization.",
            "    model.component(\"comp1\").geom(\"geom1\").run();",
            "    // REVIEW REQUIRED: bind borehole, outer-boundary, and rock-domain named selections.",
        ]
    if _dimension(plan) == 3:
        return [
            "    model.component(\"comp1\").geom(\"geom1\").create(\"blk1\", \"Block\");",
            "    model.component(\"comp1\").geom(\"geom1\").feature(\"blk1\").set(\"size\", new String[]{\"L_ref\", \"W_ref\", \"H_ref\"});",
            "    model.component(\"comp1\").geom(\"geom1\").run();",
        ]
    return [
        "    model.component(\"comp1\").geom(\"geom1\").create(\"r1\", \"Rectangle\");",
        "    model.component(\"comp1\").geom(\"geom1\").feature(\"r1\").set(\"size\", new String[]{\"L_ref\", \"W_ref\"});",
        "    model.component(\"comp1\").geom(\"geom1\").run();",
    ]


def _matlab_physics(plan: dict[str, Any]) -> list[str]:
    lines = ["% Physics inferred from requirement, matched cases, and COMSOL knowledge memory."]
    boundary_dimension = max(_dimension(plan) - 1, 0)
    for spec in _physics_specs(plan):
        lines.extend(
            [
                f"model.component('comp1').physics.create('{spec['tag']}', '{spec['interface']}', 'geom1');",
                f"% {spec['note']}",
            ]
        )
    if _is_joule_heating_plan(plan):
        auto_boundaries = _has_auto_joule_rectangle_boundaries(plan)
        lines.extend(
            [
                f"model.component('comp1').multiphysics.create('emh1', 'ElectromagneticHeating', {_dimension(plan)});",
                "model.component('comp1').multiphysics('emh1').set('EMHeat_physics', 'ec');",
                "model.component('comp1').multiphysics('emh1').set('Heat_physics', 'ht');",
                "model.component('comp1').multiphysics('emh1').selection.all;",
                "% Joule Heating coupling transfers electrical loss to the heat-transfer interface.",
                "model.component('comp1').selection.create('sel_terminal', 'Explicit');",
                f"model.component('comp1').selection('sel_terminal').geom('geom1', {boundary_dimension});",
                "model.component('comp1').selection('sel_terminal').label('Terminal boundary - review entity IDs');",
                "model.component('comp1').selection.create('sel_ground', 'Explicit');",
                f"model.component('comp1').selection('sel_ground').geom('geom1', {boundary_dimension});",
                "model.component('comp1').selection('sel_ground').label('Ground boundary - review entity IDs');",
                "model.component('comp1').selection.create('sel_convection', 'Explicit');",
                f"model.component('comp1').selection('sel_convection').geom('geom1', {boundary_dimension});",
                "model.component('comp1').selection('sel_convection').label('Exterior convection boundary - review entity IDs');",
                *(
                    [
                        "% Auto-boundary rule for the verified 2D rectangle benchmark: edges 1/3 are opposite voltage boundaries; all four exterior edges convect.",
                        "model.component('comp1').selection('sel_terminal').set([1]);",
                        "model.component('comp1').selection('sel_ground').set([3]);",
                        "model.component('comp1').selection('sel_convection').set([1 2 3 4]);",
                    ]
                    if auto_boundaries
                    else []
                ),
                f"model.component('comp1').physics('ec').create('pot1', 'ElectricPotential', {boundary_dimension});",
                "model.component('comp1').physics('ec').feature('pot1').selection.named('sel_terminal');",
                "model.component('comp1').physics('ec').feature('pot1').set('V0', 'Vtot');",
                f"model.component('comp1').physics('ec').create('gnd1', 'Ground', {boundary_dimension});",
                "model.component('comp1').physics('ec').feature('gnd1').selection.named('sel_ground');",
                f"model.component('comp1').physics('ht').create('hf1', 'HeatFluxBoundary', {boundary_dimension});",
                "model.component('comp1').physics('ht').feature('hf1').selection.named('sel_convection');",
                "model.component('comp1').physics('ht').feature('hf1').set('HeatFluxType', 'ConvectiveHeatFlux');",
                "model.component('comp1').physics('ht').feature('hf1').set('h', 'htc');",
                "model.component('comp1').physics('ht').feature('hf1').set('Text', 'T_amb');",
                *(
                    ["% This narrow benchmark rule was generated from an explicit rectangle; inspect it before adapting to another geometry."]
                    if auto_boundaries
                    else [
                        "% REVIEW REQUIRED: assign verified boundary IDs to sel_terminal, sel_ground, and sel_convection before solving.",
                        "% model.component('comp1').selection('sel_terminal').set([terminal_boundary_id]);",
                        "% model.component('comp1').selection('sel_ground').set([ground_boundary_id]);",
                        "% model.component('comp1').selection('sel_convection').set([exterior_boundary_ids]);",
                    ]
                ),
            ]
        )
    lines.append("% 边界选择目前是占位内容。请在 COMSOL 中检查生成几何的边界编号。")
    return lines


def _java_physics(plan: dict[str, Any]) -> list[str]:
    lines = ["    // Physics inferred from requirement, matched cases, and COMSOL knowledge memory."]
    boundary_dimension = max(_dimension(plan) - 1, 0)
    for spec in _physics_specs(plan):
        lines.extend(
            [
                f"    model.component(\"comp1\").physics().create(\"{spec['tag']}\", \"{spec['interface']}\", \"geom1\");",
                f"    // {spec['note']}",
            ]
        )
    if _is_joule_heating_plan(plan):
        auto_boundaries = _has_auto_joule_rectangle_boundaries(plan)
        lines.extend(
            [
                f"    model.component(\"comp1\").multiphysics().create(\"emh1\", \"ElectromagneticHeating\", {_dimension(plan)});",
                "    model.component(\"comp1\").multiphysics(\"emh1\").set(\"EMHeat_physics\", \"ec\");",
                "    model.component(\"comp1\").multiphysics(\"emh1\").set(\"Heat_physics\", \"ht\");",
                "    model.component(\"comp1\").multiphysics(\"emh1\").selection().all();",
                "    // Joule Heating coupling transfers electrical loss to the heat-transfer interface.",
                "    model.component(\"comp1\").selection().create(\"sel_terminal\", \"Explicit\");",
                f"    model.component(\"comp1\").selection(\"sel_terminal\").geom(\"geom1\", {boundary_dimension});",
                "    model.component(\"comp1\").selection(\"sel_terminal\").label(\"Terminal boundary - review entity IDs\");",
                "    model.component(\"comp1\").selection().create(\"sel_ground\", \"Explicit\");",
                f"    model.component(\"comp1\").selection(\"sel_ground\").geom(\"geom1\", {boundary_dimension});",
                "    model.component(\"comp1\").selection(\"sel_ground\").label(\"Ground boundary - review entity IDs\");",
                "    model.component(\"comp1\").selection().create(\"sel_convection\", \"Explicit\");",
                f"    model.component(\"comp1\").selection(\"sel_convection\").geom(\"geom1\", {boundary_dimension});",
                "    model.component(\"comp1\").selection(\"sel_convection\").label(\"Exterior convection boundary - review entity IDs\");",
                *(
                    [
                        "    // Auto-boundary rule for the verified 2D rectangle benchmark: edges 1/3 are opposite voltage boundaries; all four exterior edges convect.",
                        "    model.component(\"comp1\").selection(\"sel_terminal\").set(new int[]{1});",
                        "    model.component(\"comp1\").selection(\"sel_ground\").set(new int[]{3});",
                        "    model.component(\"comp1\").selection(\"sel_convection\").set(new int[]{1, 2, 3, 4});",
                    ]
                    if auto_boundaries
                    else []
                ),
                f"    model.component(\"comp1\").physics(\"ec\").create(\"pot1\", \"ElectricPotential\", {boundary_dimension});",
                "    model.component(\"comp1\").physics(\"ec\").feature(\"pot1\").selection().named(\"sel_terminal\");",
                "    model.component(\"comp1\").physics(\"ec\").feature(\"pot1\").set(\"V0\", \"Vtot\");",
                f"    model.component(\"comp1\").physics(\"ec\").create(\"gnd1\", \"Ground\", {boundary_dimension});",
                "    model.component(\"comp1\").physics(\"ec\").feature(\"gnd1\").selection().named(\"sel_ground\");",
                f"    model.component(\"comp1\").physics(\"ht\").create(\"hf1\", \"HeatFluxBoundary\", {boundary_dimension});",
                "    model.component(\"comp1\").physics(\"ht\").feature(\"hf1\").selection().named(\"sel_convection\");",
                "    model.component(\"comp1\").physics(\"ht\").feature(\"hf1\").set(\"HeatFluxType\", \"ConvectiveHeatFlux\");",
                "    model.component(\"comp1\").physics(\"ht\").feature(\"hf1\").set(\"h\", \"htc\");",
                "    model.component(\"comp1\").physics(\"ht\").feature(\"hf1\").set(\"Text\", \"T_amb\");",
                *(
                    ["    // This narrow benchmark rule was generated from an explicit rectangle; inspect it before adapting to another geometry."]
                    if auto_boundaries
                    else [
                        "    // REVIEW REQUIRED: assign verified boundary IDs to sel_terminal, sel_ground, and sel_convection before solving.",
                        "    // model.component(\"comp1\").selection(\"sel_terminal\").set(new int[]{terminalBoundaryId});",
                        "    // model.component(\"comp1\").selection(\"sel_ground\").set(new int[]{groundBoundaryId});",
                        "    // model.component(\"comp1\").selection(\"sel_convection\").set(new int[]{exteriorBoundaryIds});",
                    ]
                ),
            ]
        )
    lines.append("    // 边界选择目前是占位内容。请在 COMSOL 中检查生成几何的边界编号。")
    return lines


def _matlab_result_operators(plan: dict[str, Any]) -> list[str]:
    if not _is_joule_heating_plan(plan):
        return []
    return [
        "% Create field-evaluation operators after the mesh so their source selection is mesh-aware.",
        "model.component('comp1').cpl.create('maxop1', 'Maximum');",
        "model.component('comp1').cpl('maxop1').selection.all;",
        "model.component('comp1').cpl.create('aveop1', 'Average');",
        "model.component('comp1').cpl('aveop1').selection.all;",
    ]


def _java_result_operators(plan: dict[str, Any]) -> list[str]:
    if not _is_joule_heating_plan(plan):
        return []
    return [
        "    // Create field-evaluation operators after the mesh so their source selection is mesh-aware.",
        "    model.component(\"comp1\").cpl().create(\"maxop1\", \"Maximum\");",
        "    model.component(\"comp1\").cpl(\"maxop1\").selection().all();",
        "    model.component(\"comp1\").cpl().create(\"aveop1\", \"Average\");",
        "    model.component(\"comp1\").cpl(\"aveop1\").selection().all();",
    ]


def _matlab_mesh_elements(plan: dict[str, Any]) -> list[str]:
    feature = "FreeTet" if _dimension(plan) == 3 else "FreeTri"
    tag = "ftet1" if feature == "FreeTet" else "ftri1"
    return [f"model.component('comp1').mesh('mesh1').create('{tag}', '{feature}');"]


def _java_mesh_elements(plan: dict[str, Any]) -> list[str]:
    feature = "FreeTet" if _dimension(plan) == 3 else "FreeTri"
    tag = "ftet1" if feature == "FreeTet" else "ftri1"
    return [f'    model.component("comp1").mesh("mesh1").create("{tag}", "{feature}");']


def _matlab_outputs(plan: dict[str, Any]) -> list[str]:
    lines = ["% Derived values suggested by memory-assisted plan."]
    for index, output in enumerate(plan.get("candidate_outputs", [])[:8], start=1):
        tag = f"gev{index}"
        expr = _output_expression(str(output))
        if not expr:
            lines.append(f"% REVIEW REQUIRED: export {_matlab_string(str(output))} with a boundary integration over the verified terminal selection.")
            continue
        kind = _output_kind(str(output))
        numerical_type = _field_numerical_type(kind, _dimension(plan))
        lines.extend(
            [
                f"model.result.numerical.create('{tag}', '{numerical_type}');",
                f"model.result.numerical('{tag}').label('{_matlab_string(str(output))}');",
                f"model.result.numerical('{tag}').set('expr', '{_matlab_string(expr)}');",
            ]
        )
    return lines


def _study_spec(plan: dict[str, Any]) -> tuple[str, str]:
    # The staged workflow supplies expanded case evidence as `requirement`.
    # Study type must follow the user's approved original requirement instead.
    text = str(plan.get("study_requirement") or plan.get("requirement", "")).lower()
    domains = set(plan.get("inferred_domains", []))
    # Keep the narrow DC Joule benchmark stable even when retrieved case
    # evidence contributes unrelated modal or eigenfrequency vocabulary.
    if _is_joule_heating_plan(plan) and not any(
        token in text for token in ("frequency domain", "频域", "扫频", "交流", "ac current", "ac voltage")
    ):
        return "stat", "Stationary"
    if any(token in text for token in ("eigenfrequency", "eigen", "modal", "特征频率", "模态")):
        return "eig", "Eigenfrequency"
    # A DC Joule-heating benchmark is stationary unless the user explicitly
    # asks for AC/frequency-domain analysis. Retrieved case text may contain
    # unrelated words such as "spatial frequency resolution".
    if any(token in text for token in ("frequency domain", "频域", "扫频")) or "acoustics" in domains:
        return "freq", "Frequency"
    if any(token in text for token in ("transient", "time dependent", "瞬态", "时间")):
        return "time", "Transient"
    return "stat", "Stationary"


def _matlab_study(plan: dict[str, Any]) -> list[str]:
    tag, study_type = _study_spec(plan)
    lines = [
        "model.study.create('std1');",
        f"model.study('std1').create('{tag}', '{study_type}');",
    ]
    if _needs_parametric_sweep(plan):
        sweep_expression = _voltage_sweep_expression(plan)
        lines.extend(
            [
                "model.study('std1').feature.create('param', 'Parametric');",
                "model.study('std1').feature('param').set('pname', {'Vtot'});",
                f"model.study('std1').feature('param').set('plistarr', {{'{sweep_expression}'}});",
                "% REVIEW REQUIRED: replace the voltage sweep range with the approved values.",
            ]
        )
    lines.extend(
        [
        "model.study('std1').createAutoSequences('all');",
        "% model.study('std1').run; % Enable after selections, conditions, and solver settings are verified.",
        ]
    )
    return lines


def _java_outputs(plan: dict[str, Any]) -> list[str]:
    lines = ["    // Derived values suggested by memory-assisted plan."]
    for index, output in enumerate(plan.get("candidate_outputs", [])[:8], start=1):
        tag = f"gev{index}"
        expr = _output_expression(str(output))
        if not expr:
            lines.append(f"    // REVIEW REQUIRED: export {_java_string(str(output))} with a boundary integration over the verified terminal selection.")
            continue
        kind = _output_kind(str(output))
        numerical_type = _field_numerical_type(kind, _dimension(plan))
        lines.extend(
            [
                f"    model.result().numerical().create(\"{tag}\", \"{numerical_type}\");",
                f"    model.result().numerical(\"{tag}\").label(\"{_java_string(str(output))}\");",
                f"    model.result().numerical(\"{tag}\").set(\"expr\", \"{_java_string(expr)}\");",
            ]
        )
    return lines


def _java_study(plan: dict[str, Any]) -> list[str]:
    tag, study_type = _study_spec(plan)
    lines = [
        "    model.study().create(\"std1\");",
        f"    model.study(\"std1\").create(\"{tag}\", \"{study_type}\");",
    ]
    if _needs_parametric_sweep(plan):
        sweep_expression = _voltage_sweep_expression(plan)
        lines.extend(
            [
                "    model.study(\"std1\").feature().create(\"param\", \"Parametric\");",
                "    model.study(\"std1\").feature(\"param\").set(\"pname\", new String[]{\"Vtot\"});",
                f"    model.study(\"std1\").feature(\"param\").set(\"plistarr\", new String[]{{\"{sweep_expression}\"}});",
                "    // REVIEW REQUIRED: replace the voltage sweep range with the approved values.",
            ]
        )
    lines.extend(
        [
        "    model.study(\"std1\").createAutoSequences(\"all\");",
        "    // model.study(\"std1\").run(); // Enable after selections, conditions, and solver settings are verified.",
        ]
    )
    return lines


def _needs_parametric_sweep(plan: dict[str, Any]) -> bool:
    text = str(plan.get("requirement", "")).lower()
    return any(token in text for token in ("parametric", "sweep", "参数扫描", "扫描", "比较不同", "不同电压", "compare different", "different voltage"))


def _voltage_sweep_expression(plan: dict[str, Any]) -> str:
    # Copper electrical models are commonly voltage-driven at millivolt scale.
    # This conservative default remains a review item until the user supplies a real operating range.
    return "range(0.1[mV],0.025[mV],1[mV])" if _is_joule_heating_plan(plan) else "range(1[V],1[V],5[V])"


def _physics_specs(plan: dict[str, Any]) -> list[dict[str, str]]:
    domains = set(plan.get("inferred_domains", []))
    # Retrieved cases are evidence and API examples, not permission to add
    # every field they happen to contain. Physics interfaces must come from
    # the current requirement (or an explicit approved correction).
    specs = []
    if "heat_transfer" in domains:
        specs.append({"tag": "ht", "interface": "HeatTransfer", "note": "Add heat flux, temperature, or convection features after selections are verified."})
    if "structural" in domains or "geomechanics" in domains:
        specs.append({"tag": "solid", "interface": "SolidMechanics", "note": "Add fixed constraints, loads, pore/fracture pressure, and stress boundary conditions."})
    if "fluid" in domains:
        specs.append({"tag": "spf", "interface": "LaminarFlow", "note": "Add inlet, outlet, wall, and pressure conditions; switch interface for porous/fracture flow if needed."})
    if "electromagnetics" in domains:
        specs.append({"tag": "ec", "interface": "ConductiveMedia", "note": "Electric Currents interface: add terminal, ground, and insulation boundary conditions."})
    if "acoustics" in domains:
        specs.append({"tag": "acpr", "interface": "PressureAcoustics", "note": "Add sound hard, pressure, source, or radiation boundaries."})
    return specs or [{"tag": "gph", "interface": "GeneralFormPDE", "note": "请替换为已学习案例所需的准确 COMSOL 物理接口。"}]


def _safe_parameters(plan: dict[str, Any]) -> list[dict[str, str]]:
    defaults = [
        {"name": "L_ref", "value": "1[m]", "description": "Reference length"},
        {"name": "W_ref", "value": "1[m]", "description": "Reference width"},
        {"name": "H_ref", "value": "0.1[m]", "description": "Reference height"},
    ]
    explicit_dimensions = _explicit_dimension_parameters(str(plan.get("requirement", "")))
    for item in defaults:
        if item["name"] in explicit_dimensions:
            item["value"] = explicit_dimensions[item["name"]]
            item["description"] = "User-specified geometry dimension"
    seen = {item["name"] for item in defaults}
    safe = list(defaults)
    # Retrieval is evidence, not a parameter import.  The validated Joule
    # benchmark has a deliberately narrow contract; importing values from
    # phase-change, flow, or structural cases silently changes that contract.
    if _is_joule_heating_plan(plan):
        return safe
    for raw in plan.get("candidate_parameters", [])[:25]:
        name = _safe_param_name(str(raw.get("name", "")))
        if not name or name in seen or not _parameter_is_explicitly_requested(name, plan):
            continue
        seen.add(name)
        safe.append(
            {
                "name": name,
                "value": str(raw.get("value") or "1"),
                "description": str(raw.get("description") or raw.get("source_case") or "已学习参数"),
            }
        )
    geometry_analysis = analyze_geometry_parameters(
        plan.get("requirement", ""),
        plan.get("inferred_domains", []),
        plan.get("candidate_parameters", []),
    )
    if geometry_analysis["matches"] and geometry_analysis["matches"][0]["id"] == "hydraulic_fracturing_borehole" and "rb" not in seen:
        safe.append({
            "name": "rb",
            "value": "W_ref/20",
            "description": "Placeholder borehole radius; replace with approved dimension",
        })
        seen.add("rb")
    for raw in geometry_analysis["parameters"][:12]:
        name = _safe_param_name(str(raw.get("name", "")))
        if not name or name in seen or not _parameter_is_explicitly_requested(name, plan):
            continue
        seen.add(name)
        safe.append(
            {
                "name": name,
                "value": str(raw.get("value") or "1"),
                "description": str(raw.get("description") or "几何/参数知识库建议"),
            }
        )
    material_analysis = analyze_material_properties(
        plan.get("requirement", ""),
        plan.get("inferred_domains", []),
        plan.get("candidate_parameters", []),
    )
    for raw in material_analysis["required_properties"] + material_analysis["optional_properties"][:8]:
        name = _safe_param_name(str(raw.get("symbol", "")))
        if not name or name in seen:
            continue
        seen.add(name)
        safe.append(
            {
                "name": name,
                "value": _default_material_value(str(raw.get("comsol_key", ""))),
                "description": str(raw.get("name", "材料物性参数")),
            }
        )
    return safe


def _parameter_is_explicitly_requested(name: str, plan: dict[str, Any]) -> bool:
    """Keep retrieved parameters only when their identifier appears in the request."""
    requirement = str(plan.get("requirement", ""))
    if not requirement:
        return False
    return bool(re.search(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])", requirement, flags=re.IGNORECASE))


def _explicit_dimension_parameters(requirement: str) -> dict[str, str]:
    """Extract explicit rectangular dimensions without changing the geometry template."""
    text = str(requirement or "")
    patterns = {
        "L_ref": r"(?:长度|长|length)\s*[=:：]?\s*(\d+(?:\.\d+)?)\s*(mm|cm|m|um)",
        "W_ref": r"(?:宽度|宽|width)\s*[=:：]?\s*(\d+(?:\.\d+)?)\s*(mm|cm|m|um)",
        "H_ref": r"(?:厚度|厚|thickness|height)\s*[=:：]?\s*(\d+(?:\.\d+)?)\s*(mm|cm|m|um)",
    }
    values: dict[str, str] = {}
    for name, pattern in patterns.items():
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            values[name] = f"{match.group(1)}[{match.group(2)}]"
    return values


def _default_material_value(comsol_key: str) -> str:
    return {
        "density": "2500[kg/m^3]",
        "thermalconductivity": "1[W/(m*K)]",
        "heatcapacity": "800[J/(kg*K)]",
        "youngsmodulus": "35[GPa]",
        "poissonsratio": "0.25",
        "dynamicviscosity": "1e-3[Pa*s]",
        "electricconductivity": "1[S/m]",
        "relpermittivity": "1",
        "soundspeed": "343[m/s]",
    }.get(comsol_key, "1")


def _dimension(plan: dict[str, Any]) -> int:
    dimension_requirement = str(plan.get("dimension_requirement") or plan.get("requirement", ""))
    explicit_dimensions = _explicit_dimension_parameters(dimension_requirement)
    if "H_ref" in explicit_dimensions:
        return 3
    if "L_ref" in explicit_dimensions or "W_ref" in explicit_dimensions:
        return 2
    text = " ".join([dimension_requirement, " ".join(plan.get("inferred_domains", []))]).lower()
    return 3 if any(token in text for token in ("3d", "三维", "solid", "block", "volum", "空间")) else 2


def _output_expression(name: str) -> str:
    lowered = name.lower().replace("_", " ")
    if any(token in lowered for token in ("pressure drop", "压降", "pressure difference", "flow rate", "流量", "体积流量")):
        return ""
    if "temperature" in lowered or "温度" in lowered or lowered in {"tmax", "tavg"}:
        return "T"
    if "stress" in lowered or "von" in lowered:
        return "solid.mises"
    if "displacement" in lowered:
        return "solid.disp"
    if "pressure" in lowered:
        return "p"
    if "velocity" in lowered or "速度" in lowered:
        return "spf.U"
    if "current density" in lowered or "电流密度" in lowered:
        return "ec.normJ"
    if "terminal current" in lowered or "端子电流" in lowered:
        return ""
    return "1"


def _output_kind(name: str) -> str:
    lowered = name.lower().replace("_", " ")
    if any(token in lowered for token in ("tmax", "max temperature", "maximum temperature", "最高温度", "最高温")):
        return "max_volume"
    if any(token in lowered for token in ("tavg", "average temperature", "mean temperature", "平均温度", "平均温")):
        return "average_volume"
    if any(token in lowered for token in ("current density", "电流密度", "max current density", "最大电流密度")):
        return "max_volume"
    if any(token in lowered for token in ("max stress", "maximum stress", "最大应力", "最大应力", "von mises")):
        return "max_volume"
    if any(token in lowered for token in ("max displacement", "maximum displacement", "最大位移")):
        return "max_volume"
    if any(token in lowered for token in ("max velocity", "maximum velocity", "最大速度")):
        return "max_volume"
    return "global"


def _field_numerical_type(kind: str, dimension: int) -> str:
    if kind not in {"max_volume", "average_volume"}:
        return "EvalGlobal"
    measure = "Max" if kind == "max_volume" else "Av"
    suffix = {3: "Volume", 2: "Surface", 1: "Line"}.get(dimension)
    return f"{measure}{suffix}" if suffix else "EvalGlobal"


def _safe_identifier(value: str) -> str:
    normalized = re.sub(r"\W+", "_", value, flags=re.ASCII).strip("_").lower()
    if not normalized or normalized[0].isdigit():
        normalized = f"model_{normalized or 'generated'}"
    return normalized[:80]


def _java_class_name(model_id: str) -> str:
    return "".join(part.capitalize() for part in _safe_identifier(model_id).split("_")) or "GeneratedComsolModel"


def _safe_param_name(value: str) -> str:
    name = re.sub(r"\W+", "_", value, flags=re.ASCII).strip("_")
    if not name:
        return ""
    if name[0].isdigit():
        name = f"p_{name}"
    return name[:40]


def _matlab_string(value: str) -> str:
    return value.replace("'", "''")


def _java_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _comment_text(value: str) -> str:
    return " ".join(value.split())[:500]
