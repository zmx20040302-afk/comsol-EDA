from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .boundary_knowledge import infer_boundary_conditions
from .coupled_physics_knowledge import analyze_coupled_physics
from .geometry_parameter_knowledge import analyze_geometry_parameters, validate_geometry_readiness
from .instruction_agent import _select_physics_from_requirement
from .material_property_knowledge import analyze_material_properties, validate_material_readiness
from .mesh_knowledge import infer_mesh_strategy
from .modeling_contract import add_missing_information, create_empty_contract, now_iso, update_field_evidence
from .physics_dependency_graph import compile_physics_dependency_plan
from .physics_selection import COUPLING_CATALOG, PHYSICS_CATALOG
from .result_knowledge import infer_result_exports
from .solver_knowledge import infer_study_solver
from .validated_templates import select_validated_template


PROJECT_ROOT = Path(__file__).resolve().parents[2]

DOMAIN_INTERFACES: dict[str, tuple[str, str, list[str]]] = {
    "heat_transfer": ("Heat Transfer", "ht", ["T"]),
    "electromagnetics": ("Electric Currents", "ec", ["V", "J"]),
    "structural": ("Solid Mechanics", "solid", ["u", "stress"]),
    "fluid": ("Laminar Flow", "spf", ["u", "p"]),
    "chemical": ("Transport of Diluted Species", "tds", ["c"]),
    "electrochemistry": ("Electrochemistry", "ecm", ["phi", "c"]),
    "acoustics": ("Pressure Acoustics", "acpr", ["p"]),
    "porous_media": ("Darcy's Law", "dl", ["p", "u"]),
}

DIMENSION_PATTERNS = (
    ("2D_axisymmetric", ("轴对称", "axisymmetric")),
    ("3D", ("三维", "3d", "3-d")),
    ("2D", ("二维", "2d", "2-d")),
    ("1D", ("一维", "1d", "1-d")),
)

BOUNDARY_EVIDENCE_TOKENS = (
    "固定温度", "给定温度", "热通量", "热源", "对流", "辐射", "绝热",
    "端子", "接地", "施加电压", "施加电流", "绝缘", "固定约束", "位移约束", "载荷",
    "入口", "出口", "流量", "壁面", "声硬", "刚性壁", "阻抗", "声源", "压力释放",
    "fixed temperature", "heat flux", "terminal", "ground", "inlet", "outlet", "fixed constraint",
)

OUTPUT_TOKENS = (
    "温度", "温升", "热流", "换热量", "焦耳热", "耗散功率", "位移", "应力", "应变", "压力", "速度", "流量", "电势", "电流",
    "电流密度", "声压", "频率", "模态", "temperature", "stress", "pressure", "velocity",
    "current", "voltage", "frequency", "displacement",
)

OUTPUT_REQUEST_TOKENS = ("输出", "导出", "观察", "监测", "计算结果", "求取", "evaluate", "export", "report")

STUDY_TOKENS = (
    "稳态", "瞬态", "时域", "频域", "特征频率", "特征值", "参数扫描",
    "stationary", "transient", "time dependent", "frequency domain", "eigenfrequency", "sweep",
)


def parse_modeling_requirement(requirement: str, plan: dict[str, Any] | None = None) -> dict[str, Any]:
    requirement = " ".join(str(requirement or "").split())
    if not requirement:
        raise ValueError("requirement is empty")
    plan = dict(plan or {})
    domains = _domains(requirement, plan)
    contract = create_empty_contract(requirement)

    selection = _select_physics_from_requirement(requirement, domains)
    coupling = analyze_coupled_physics(requirement, domains)
    dependency_plan = compile_physics_dependency_plan(requirement, domains)
    geometry_analysis = analyze_geometry_parameters(requirement, domains, plan.get("candidate_parameters", []))
    geometry_readiness = validate_geometry_readiness(requirement, domains, plan.get("candidate_parameters", []))
    material_analysis = analyze_material_properties(requirement, domains, plan.get("candidate_parameters", []))
    material_readiness = validate_material_readiness(requirement, domains, plan.get("candidate_parameters", []))
    boundary = infer_boundary_conditions(requirement, domains)
    mesh = infer_mesh_strategy(requirement, domains)
    study = infer_study_solver(requirement, domains)
    result_plan = infer_result_exports(requirement, domains, plan.get("candidate_outputs", []))

    contract["task"]["name"] = _task_name(requirement)
    contract["task"]["completion_criteria"] = [
        "COMSOL 模型成功构建、网格划分和求解",
        "生成可打开的 MPH、结果数据和预览",
        "关键结果通过合同中定义的物理验证规则",
    ]

    contract["geometry"] = {
        "dimension": _geometry_dimension(requirement, geometry_analysis.get("dimension", "")),
        "source": "natural_language_requirement" if not _has_import_source(requirement) else "user_supplied_geometry",
        "objects": [{"description": item, "evidence_level": "proposed", "source": "geometry_knowledge"} for item in geometry_analysis.get("geometry", [])[:8]],
        "parameters": _geometry_parameters(requirement, plan.get("candidate_parameters", [])),
        "named_selections": [
            {"name": _selection_name(item, index), "purpose": item, "evidence_level": "proposed", "source": "geometry_knowledge"}
            for index, item in enumerate(geometry_analysis.get("selection_advice", [])[:8], start=1)
        ],
    }

    interfaces = []
    dependent_variables: list[str] = []
    physics_catalog = {row["id"]: row for row in PHYSICS_CATALOG}
    variable_map = {
        "heat_transfer_solids": ["T"],
        "heat_transfer_fluids": ["T"],
        "electric_currents": ["V", "J"],
        "solid_mechanics": ["u", "stress"],
        "laminar_flow": ["u", "p"],
        "pressure_acoustics": ["p"],
        "transport_diluted_species": ["c"],
    }
    dependency_sources = {item["id"]: item.get("source", "physics_dependency_graph") for item in dependency_plan["interfaces"]}
    for interface_id in dependency_plan["interface_ids"]:
        spec = physics_catalog[interface_id]
        interfaces.append({
            "id": interface_id,
            "name": spec["display_name"],
            "tag": spec["interface_tag"],
            "evidence_level": "proposed",
            "source": dependency_sources.get(interface_id, "physics_dependency_graph"),
        })
        dependent_variables.extend(variable_map.get(interface_id, []))
    coupling_catalog = {row["id"]: row for row in COUPLING_CATALOG}
    couplings = [
        {
            "id": coupling_id,
            "name": coupling_catalog[coupling_id]["display_name"],
            "tag": f"multiphysics_{index}_{coupling_id}",
            "evidence_level": "proposed",
            "source": "physics_dependency_graph",
        }
        for index, coupling_id in enumerate(dependency_plan["coupling_ids"], start=1)
    ]
    contract["physics"] = {
        "interfaces": interfaces,
        "couplings": couplings,
        "dependent_variables": list(dict.fromkeys(dependent_variables)),
        "selection_summary": selection,
    }

    contract["materials"] = _materials(material_analysis)
    explicit_boundary = _contains_any(requirement, BOUNDARY_EVIDENCE_TOKENS)
    contract["boundary_conditions"] = _conditions(
        boundary.get("boundary_types", []),
        "bc",
        "user_requirement" if explicit_boundary else "boundary_knowledge_proposal",
        "source_supported" if explicit_boundary else "proposed",
    )
    contract["initial_conditions"] = _conditions(
        boundary.get("initial_conditions", []),
        "init",
        "boundary_knowledge_proposal",
        "proposed",
    )
    contract["mesh"] = {
        "strategy": list(mesh.get("strategy", [])),
        "local_refinements": list(mesh.get("local_refinements", [])),
        "parameter": str(mesh.get("mesh_parameter", "")),
        "independence_check": list(mesh.get("checks", [])),
        "evidence_level": "proposed",
    }
    contract["study"] = {
        "types": list(study.get("studies", [])),
        "steps": [{"type": item, "order": index} for index, item in enumerate(study.get("studies", []), start=1)],
        "evidence_level": "source_supported" if _contains_any(requirement, STUDY_TOKENS) else "proposed",
    }
    contract["solver"] = {
        "strategy": ["baseline_solve_before_sweep"],
        "checks": list(study.get("solver_checks", [])),
        "evidence_level": "proposed",
    }
    contract["outputs"] = [
        {
            "name": str(name),
            "expression": "unresolved_expression",
            "unit": "",
            "aggregation": "field_or_derived_value_to_confirm",
            "evidence_level": "source_supported" if _contains_any(requirement, OUTPUT_TOKENS) else "proposed",
            "source": "result_knowledge",
        }
        for name in result_plan.get("outputs", [])
    ]
    contract["validation"] = [
        {
            "name": f"validation_{index}",
            "rule": str(rule),
            "severity": "critical" if index == 1 else "warning",
            "evidence_level": "proposed",
            "source": "result_knowledge",
        }
        for index, rule in enumerate(result_plan.get("validation", []), start=1)
    ]
    contract["decision_support"] = {
        "physics_selection": selection,
        "physics_dependency_graph": dependency_plan,
        "coupling": coupling,
        "geometry_readiness": geometry_readiness,
        "material_readiness": material_readiness,
        "boundary": boundary,
    }

    _add_missing_items(
        contract,
        requirement,
        domains,
        geometry_readiness,
        material_readiness,
        explicit_boundary,
    )
    template = _validated_template(requirement)
    template["compatible_with_contract"] = _template_compatible(template, contract)
    if template.get("compatible_with_contract"):
        for material in contract.get("materials", []):
            if material.get("selection") == "unresolved_domain_selection":
                material["selection"] = "template_defined_domain"
        for condition in contract.get("boundary_conditions", []):
            if condition.get("target") == "unresolved_selection":
                condition["target"] = "template_defined_selection"
    contract["validated_template"] = template
    _set_execution_policy(contract, template)
    _record_evidence(contract, domains, template)
    contract["clarifying_questions"] = clarification_questions(contract)
    contract["updated_at"] = now_iso()
    return contract


def clarification_questions(contract: dict[str, Any], limit: int = 8) -> list[str]:
    rows = sorted(
        (item for item in contract.get("missing_information", []) if isinstance(item, dict)),
        key=lambda item: (item.get("severity") != "critical", str(item.get("category", ""))),
    )
    seen: set[str] = set()
    questions: list[str] = []
    for row in rows:
        question = " ".join(str(row.get("question", "")).split())
        if question and question not in seen:
            seen.add(question)
            questions.append(question)
    return questions[:limit]


def missing_categories(contract: dict[str, Any], critical_only: bool = False) -> set[str]:
    return {
        str(item.get("category"))
        for item in contract.get("missing_information", [])
        if isinstance(item, dict) and (not critical_only or item.get("severity") == "critical")
    }


def _domains(requirement: str, plan: dict[str, Any]) -> list[str]:
    domains = [str(item) for item in plan.get("inferred_domains", []) if str(item) in DOMAIN_INTERFACES]
    if domains:
        return list(dict.fromkeys(domains))
    text = requirement.lower()
    rules = (
        ("heat_transfer", ("温度", "传热", "导热", "热源", "热流", "冷却", "heat", "thermal", "joule")),
        ("electromagnetics", ("电流", "电压", "电势", "电场", "焦耳", "current", "voltage", "electric", "joule")),
        ("structural", ("应力", "应变", "位移", "载荷", "变形", "固体力学", "stress", "strain", "displacement")),
        ("fluid", ("流体", "流动", "流速", "入口", "出口", "层流", "flow", "velocity", "laminar")),
        ("chemical", ("浓度", "扩散", "传质", "溶质", "concentration", "diffusion", "species")),
        ("acoustics", ("声学", "声腔", "声压", "噪声", "共振", "acoustic", "sound")),
        ("porous_media", ("多孔", "渗流", "孔隙", "darcy", "porous")),
    )
    return [domain for domain, keywords in rules if any(keyword in text for keyword in keywords)]


def _add_missing_items(
    contract: dict[str, Any],
    requirement: str,
    domains: list[str],
    geometry_readiness: dict[str, Any],
    material_readiness: dict[str, Any],
    explicit_boundary: bool,
) -> None:
    if not domains:
        add_missing_information(
            contract, "physics", "physics.interfaces",
            "请说明主要未知量和激励，例如温度与热源、位移与载荷、电势与电流、流速与压差或声压与频率。",
            "physics_study",
        )
    geometry = contract.get("geometry", {})
    geometry_gaps: list[tuple[str, str]] = []
    if geometry.get("dimension") == "unknown" and not _has_import_source(requirement):
        geometry_gaps.append(("geometry.dimension_or_source", "dimension"))
    if not geometry.get("parameters") and not _has_import_source(requirement):
        geometry_gaps.append(("geometry.parameters", "parameters"))
    for field, _ in geometry_gaps:
        add_missing_information(
            contract, "geometry", field,
            "请提供模型维度、几何类型或 CAD 文件，并给出关键尺寸和单位。",
            "geometry",
        )
    missing_properties = material_readiness.get("missing_required_properties", [])
    if missing_properties:
        names = "、".join(str(item.get("name", "未命名物性")) for item in missing_properties)
        add_missing_information(
            contract, "materials", "materials.properties",
            f"请提供材料名称或以下物性及单位：{names}，并说明数据来源或允许采用的材料库。",
            "materials",
        )
    if not explicit_boundary:
        add_missing_information(
            contract, "boundary_conditions", "boundary_conditions.targets_and_values",
            "请说明激励、约束和散逸边界作用在哪些几何面，并提供相应数值和单位。",
            "boundary_initial",
        )
    if not _has_specific_output_request(requirement):
        add_missing_information(
            contract, "outputs", "outputs.quantities",
            "请说明需要观察或导出的结果量，以及最大值、平均值、积分值、曲线或场分布等统计方式。",
            "results_validation",
        )
    if not _contains_any(requirement, STUDY_TOKENS):
        add_missing_information(
            contract, "study", "study.types",
            "请确认研究类型是稳态、瞬态、频域、特征频率还是参数扫描；当前仅能提出稳态基线建议。",
            "physics_study",
            severity="warning",
        )
    if _has_number_without_unit(requirement):
        add_missing_information(
            contract, "units", "geometry_or_boundary.numeric_units",
            "需求中存在未带单位的数值，请为尺寸、载荷、温度、电压、电流或频率补充单位。",
            "geometry",
        )


def _set_execution_policy(contract: dict[str, Any], template: dict[str, Any]) -> None:
    critical = [item for item in contract.get("missing_information", []) if item.get("severity") == "critical"]
    if template.get("matched") and template.get("compatible_with_contract") and not critical:
        risk = "A"
    elif contract.get("physics", {}).get("interfaces") and len(critical) <= 2:
        risk = "B"
    else:
        risk = "C"
    contract["execution_policy"] = {
        "risk_level": risk,
        "allow_automatic_generation": risk == "A" and not critical,
        "allow_automatic_solve": risk == "A" and not critical,
        "max_retries": 1 if risk == "A" else 0,
        "allowed_automatic_changes": ["api_label_reference", "result_dataset_reference", "equivalent_named_selection"],
    }
    contract["status"] = "missing_information" if critical else "ready_for_review"


def _record_evidence(contract: dict[str, Any], domains: list[str], template: dict[str, Any]) -> None:
    update_field_evidence(contract, "raw_requirement", "user_confirmed", "user_requirement")
    if domains:
        update_field_evidence(contract, "physics.interfaces", "source_supported", "local_physics_rules")
    if template.get("matched"):
        update_field_evidence(contract, "validated_template", "template_verified", str(template.get("template_path", "template_catalog")))


def _validated_template(requirement: str) -> dict[str, Any]:
    try:
        return select_validated_template(requirement, root=PROJECT_ROOT)
    except (OSError, ValueError, KeyError):
        return {"matched": False, "reason": "validated template catalog unavailable"}


def _template_compatible(template: dict[str, Any], contract: dict[str, Any]) -> bool:
    if not template.get("matched"):
        return False
    template_id = str(template.get("template_id", "")).lower()
    dimension = str(contract.get("geometry", {}).get("dimension", "unknown"))
    if "_1d" in template_id and dimension != "1D":
        return False
    if "_2d" in template_id and dimension not in {"2D", "2D_axisymmetric"}:
        return False
    if dimension == "unknown":
        return False
    return True


def _materials(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, material in enumerate(analysis.get("recognized_materials", []), start=1):
        properties = []
        for key, raw_value in material.get("properties", {}).items():
            value, unit = _split_comsol_value(str(raw_value))
            properties.append({
                "name": str(key),
                "value": value,
                "unit": unit,
                "description": str(key),
                "evidence_level": "source_supported",
                "source": "local_material_profile",
            })
        rows.append({
            "name": str(material.get("name", f"material_{index}")),
            "tag": f"mat{index}",
            "selection": "unresolved_domain_selection",
            "properties": properties,
            "evidence_level": "source_supported",
            "source": "local_material_profile",
        })
    return rows


def _conditions(values: list[str], prefix: str, source: str, level: str) -> list[dict[str, Any]]:
    return [
        {
            "name": str(value),
            "tag": f"{prefix}{index}",
            "type": str(value),
            "target": "unresolved_selection",
            "values": [],
            "evidence_level": level,
            "source": source,
        }
        for index, value in enumerate(values[:8], start=1)
    ]


def _geometry_parameters(requirement: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in candidates:
        name = _safe_name(str(item.get("name", "parameter")))
        if not name or name in seen:
            continue
        value, unit = _split_comsol_value(str(item.get("value", "")))
        result.append({
            "name": name,
            "value": value,
            "unit": unit,
            "description": str(item.get("description", name)),
            "evidence_level": "source_supported",
            "source": "case_memory",
        })
        seen.add(name)
    pattern = re.compile(r"(?P<label>长度|宽度|厚度|半径|直径|高度|length|width|thickness|radius|diameter|height)?\s*[:=为]?\s*(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>mm|cm|m|um|µm|毫米|厘米|米|微米)\b(?!\s*/)", re.IGNORECASE)
    aliases = {"长度": "length", "宽度": "width", "厚度": "thickness", "半径": "radius", "直径": "diameter", "高度": "height", "毫米": "mm", "厘米": "cm", "米": "m", "微米": "um", "µm": "um"}
    unnamed = 0
    for match in pattern.finditer(requirement):
        raw_label = str(match.group("label") or "")
        if raw_label:
            name = aliases.get(raw_label.lower(), aliases.get(raw_label, raw_label.lower()))
        else:
            unnamed += 1
            name = f"dimension_{unnamed}"
        if name in seen:
            name = f"{name}_{len(seen) + 1}"
        unit = aliases.get(match.group("unit"), match.group("unit").lower())
        result.append({
            "name": name,
            "value": float(match.group("value")),
            "unit": unit,
            "description": raw_label or "geometry dimension",
            "evidence_level": "user_confirmed",
            "source": "user_requirement",
        })
        seen.add(name)
    return result


def _geometry_dimension(requirement: str, suggestion: str) -> str:
    lowered = requirement.lower()
    for dimension, tokens in DIMENSION_PATTERNS:
        if any(token in lowered for token in tokens):
            return dimension
    suggestion_lower = str(suggestion).lower()
    if "3d" in suggestion_lower or "三维" in suggestion_lower:
        return "3D"
    if "axis" in suggestion_lower or "轴对称" in suggestion_lower:
        return "2D_axisymmetric"
    if "2d" in suggestion_lower or "二维" in suggestion_lower:
        return "2D"
    if "1d" in suggestion_lower or "一维" in suggestion_lower:
        return "1D"
    return "unknown"


def _has_import_source(requirement: str) -> bool:
    text = requirement.lower()
    return any(token in text for token in ("cad", "step", "stp", "iges", "igs", "导入几何", ".mph"))


def _has_number_without_unit(requirement: str) -> bool:
    number = r"\d+(?:\.\d+)?(?:e[-+]?\d+)?"
    unit = r"(?:w/\(m2\*k\)|kg/s|n\*m|w/m2|m/s|s/m|mm|cm|um|µm|kpa|mpa|gpa|pa|mv|ma|khz|mhz|hz|kg|°c|d|m|k|c|v|a|w|s|n|%)(?![a-z])"
    for match in re.finditer(rf"(?<![0-9.a-z]){number}(?![0-9.])", requirement, re.IGNORECASE):
        suffix = requirement[match.end(): match.end() + 12].lstrip().lower()
        if re.match(unit, suffix):
            continue
        if re.match(rf"(?:到|至|~|-)\s*{number}\s*{unit}", suffix, re.IGNORECASE):
            continue
        if re.match(r"\s*\[?1\]?\b", suffix):
            continue
        if not re.match(unit, suffix):
            return True
    return False


def _split_comsol_value(raw: str) -> tuple[Any, str]:
    match = re.fullmatch(r"\s*([-+]?\d+(?:\.\d+)?(?:e[-+]?\d+)?)\s*\[([^\]]+)\]\s*", raw, re.IGNORECASE)
    if match:
        return float(match.group(1)), match.group(2)
    return raw, ""


def _task_name(requirement: str) -> str:
    text = re.sub(r"\s+", " ", requirement).strip()
    return text[:64] + ("…" if len(text) > 64 else "")


def _selection_name(text: str, index: int) -> str:
    prefix = "sel_" + _safe_name(text)[:24]
    return prefix if prefix != "sel_" else f"sel_{index}"


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_").lower()


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(token.lower() in lowered for token in tokens)


def _has_specific_output_request(requirement: str) -> bool:
    lowered = requirement.lower()
    if not _contains_any(lowered, OUTPUT_REQUEST_TOKENS):
        return False
    if re.search(r"(?:输出|导出|观察|监测|求取|report|export).{0,24}(?:温度|温升|热流|换热量|焦耳热|耗散功率|位移|应力|应变|压力|速度|流量|电势|电压|电流|声压|频率|模态|temperature|stress|pressure|velocity|current|voltage|frequency|displacement)", lowered):
        return True
    return False
