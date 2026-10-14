from __future__ import annotations

from typing import Any


MATERIAL_PROPERTY_KNOWLEDGE: list[dict[str, Any]] = [
    {
        "id": "heat_transfer_material",
        "label": "传热材料",
        "keywords": ["传热", "温度", "导热", "热源", "冷却", "辐射", "heat", "thermal"],
        "domains": ["heat_transfer"],
        "required": [
            ("density", "rho", "密度", "kg/m^3", "参与瞬态热惯性；稳态也常作为材料完整性检查项"),
            ("thermalconductivity", "k", "导热系数", "W/(m*K)", "决定热传导能力，可为各向异性张量"),
            ("heatcapacity", "Cp", "比热容", "J/(kg*K)", "瞬态传热必须给出"),
        ],
        "optional": [
            ("emissivity", "epsilon", "表面发射率", "1", "存在辐射换热时需要"),
            ("thermalexpansioncoefficient", "alpha_T", "热膨胀系数", "1/K", "热-结构耦合时需要"),
        ],
        "dependencies": ["导热系数、比热和密度可随温度变化；复合材料导热系数可能随方向变化。"],
    },
    {
        "id": "structural_material",
        "label": "结构力学材料",
        "keywords": ["应力", "应变", "位移", "载荷", "变形", "固体力学", "结构", "流固", "弹性模量", "泊松比", "stress", "solid"],
        "domains": ["structural", "geomechanics"],
        "required": [
            ("density", "rho", "密度", "kg/m^3", "重力、惯性、特征频率和瞬态结构分析需要"),
            ("youngsmodulus", "E", "弹性模量", "Pa", "决定线弹性刚度"),
            ("poissonsratio", "nu", "泊松比", "1", "决定横向变形和体积响应"),
        ],
        "optional": [
            ("tensilestrength", "ft", "抗拉强度", "Pa", "损伤、断裂、水力压裂需要"),
            ("compressivestrength", "fc", "抗压强度", "Pa", "岩土/煤岩破坏需要"),
            ("fractureenergy", "Gc", "断裂能", "J/m^2", "裂缝扩展、相场或黏聚区模型需要"),
        ],
        "dependencies": ["弹性模量和强度可为空间随机场；复合材料或层状材料需要方向相关弹性矩阵。"],
    },
    {
        "id": "fluid_material",
        "label": "流体材料",
        "keywords": ["流体", "流动", "速度", "压力", "层流", "黏度", "雷诺数", "flow", "fluid", "viscosity"],
        "domains": ["fluid"],
        "required": [
            ("density", "rho_f", "密度", "kg/m^3", "动量方程、惯性和重力项需要"),
            ("dynamicviscosity", "mu", "动力黏度", "Pa*s", "决定黏性阻力和雷诺数"),
        ],
        "optional": [
            ("heatcapacity", "Cp_f", "比热容", "J/(kg*K)", "非等温流动需要"),
            ("thermalconductivity", "k_f", "导热系数", "W/(m*K)", "流体传热需要"),
            ("diffusioncoefficient", "D", "扩散系数", "m^2/s", "稀物质传递需要"),
        ],
        "dependencies": ["黏度和密度可能随温度、浓度或压力变化；气体可压缩时需要状态方程。"],
    },
    {
        "id": "electric_material",
        "label": "电学材料",
        "keywords": ["电流", "电压", "电势", "电导率", "焦耳热", "电极", "electric", "current"],
        "domains": ["electromagnetics"],
        "required": [
            ("electricconductivity", "sigma", "电导率", "S/m", "电流守恒和焦耳热计算需要"),
        ],
        "optional": [
            ("relpermittivity", "epsr", "相对介电常数", "1", "静电、电容或频域电场需要"),
            ("thermalconductivity", "k", "导热系数", "W/(m*K)", "电-热耦合需要"),
            ("heatcapacity", "Cp", "比热容", "J/(kg*K)", "瞬态焦耳热需要"),
            ("density", "rho", "密度", "kg/m^3", "瞬态焦耳热需要"),
        ],
        "dependencies": ["电导率常随温度变化；频域问题中介电常数和损耗因子可能随频率变化。"],
    },
    {
        "id": "species_transport_material",
        "label": "传质与电化学材料",
        "keywords": ["传质", "扩散", "浓度", "溶液", "电化学", "diffusion", "concentration"],
        "domains": ["chemical", "electrochemistry"],
        "required": [
            ("diffusioncoefficient", "D", "扩散系数", "m^2/s", "稀物质传递和浓度场计算需要"),
        ],
        "optional": [
            ("electricconductivity", "sigma", "电导率", "S/m", "电化学电流和电解质导电需要"),
            ("density", "rho", "密度", "kg/m^3", "流动、对流传质和重力项需要"),
            ("dynamicviscosity", "mu", "动力黏度", "Pa*s", "流动传质需要"),
        ],
        "dependencies": ["扩散系数可能随温度、浓度和方向变化；电化学问题还需核对电导率与反应动力学参数。"],
    },
    {
        "id": "acoustic_material",
        "label": "声学材料",
        "keywords": ["声学", "声腔", "声压", "频率", "共振", "声速", "acoustic", "sound"],
        "domains": ["acoustics"],
        "required": [
            ("density", "rho0", "密度", "kg/m^3", "声波方程需要"),
            ("soundspeed", "c", "声速", "m/s", "决定波长和共振频率"),
        ],
        "optional": [
            ("bulkviscosity", "muB", "体黏度", "Pa*s", "热黏性声学或损耗模型需要"),
            ("dynamicviscosity", "mu", "动力黏度", "Pa*s", "热黏性边界层需要"),
        ],
        "dependencies": ["声速和密度可随温度变化；吸声/阻抗边界常随频率变化。"],
    },
]


MATERIAL_PROFILES: list[dict[str, Any]] = [
    {"name": "Copper", "keywords": ["copper", "铜", "母线"], "properties": {"density": "8960[kg/m^3]", "thermalconductivity": "400[W/(m*K)]", "heatcapacity": "385[J/(kg*K)]", "electricconductivity": "5.998e7[S/m]", "youngsmodulus": "110e9[Pa]", "poissonsratio": "0.34[1]"}, "note": "Check temperature-dependent electrical conductivity for Joule heating."},
    {"name": "Aluminum", "keywords": ["aluminum", "aluminium", "铝"], "properties": {"density": "2700[kg/m^3]", "thermalconductivity": "238[W/(m*K)]", "heatcapacity": "900[J/(kg*K)]", "electricconductivity": "3.5e7[S/m]", "youngsmodulus": "69e9[Pa]", "poissonsratio": "0.33[1]"}, "note": "Confirm the alloy grade before final solve."},
    {"name": "Structural steel", "keywords": ["steel", "结构钢", "钢"], "properties": {"density": "7850[kg/m^3]", "thermalconductivity": "44.5[W/(m*K)]", "heatcapacity": "475[J/(kg*K)]", "electricconductivity": "4.03e6[S/m]", "youngsmodulus": "200e9[Pa]", "poissonsratio": "0.30[1]"}, "note": "Confirm the steel grade and yield strength before a strength release decision."},
    {"name": "Titanium alloy", "keywords": ["titanium", "钛合金", "钛"], "properties": {"density": "4430[kg/m^3]", "thermalconductivity": "6.7[W/(m*K)]", "heatcapacity": "526[J/(kg*K)]", "electricconductivity": "5.8e5[S/m]", "youngsmodulus": "114e9[Pa]", "poissonsratio": "0.34[1]"}, "note": "Confirm the titanium alloy designation before final solve."},
    {"name": "Nichrome", "keywords": ["nichrome", "镍铬"], "properties": {"density": "8400[kg/m^3]", "thermalconductivity": "11.3[W/(m*K)]", "heatcapacity": "450[J/(kg*K)]", "electricconductivity": "9.1e5[S/m]", "youngsmodulus": "200e9[Pa]", "poissonsratio": "0.30[1]"}, "note": "Use temperature-dependent resistivity for wide heater temperature ranges."},
    {"name": "Silicon", "keywords": ["silicon", "硅", "芯片"], "properties": {"density": "2329[kg/m^3]", "thermalconductivity": "130[W/(m*K)]", "heatcapacity": "700[J/(kg*K)]", "youngsmodulus": "130e9[Pa]", "poissonsratio": "0.28[1]"}, "note": "Confirm crystal orientation and temperature dependence for precision semiconductor models."},
    {"name": "Water", "keywords": ["water", "水", "冷却液"], "properties": {"density": "998[kg/m^3]", "dynamicviscosity": "1e-3[Pa*s]", "thermalconductivity": "0.6[W/(m*K)]", "heatcapacity": "4182[J/(kg*K)]"}, "note": "Use temperature-dependent fluid properties for a wide temperature range."},
    {"name": "Air", "keywords": ["air", "空气"], "properties": {"density": "1.2[kg/m^3]", "dynamicviscosity": "1.8e-5[Pa*s]", "thermalconductivity": "0.026[W/(m*K)]", "heatcapacity": "1005[J/(kg*K)]", "soundspeed": "343[m/s]"}, "note": "Validate buoyancy for natural convection and temperature dependence for acoustics."},
    {"name": "Generic oil", "keywords": ["oil", "油", "导热油"], "properties": {"density": "850[kg/m^3]", "dynamicviscosity": "0.02[Pa*s]", "thermalconductivity": "0.13[W/(m*K)]", "heatcapacity": "2000[J/(kg*K)]"}, "note": "Replace the generic oil properties with the approved grade and temperature-dependent data before final solve."},
]


def analyze_material_properties(
    requirement: str,
    domains: list[str] | None = None,
    candidate_parameters: list[dict[str, Any]] | None = None,
    top_k: int = 3,
) -> dict[str, Any]:
    text = str(requirement or "").lower()
    domain_set = {str(domain).lower() for domain in domains or []}
    scored: list[tuple[int, dict[str, Any]]] = []
    for item in MATERIAL_PROPERTY_KNOWLEDGE:
        if domain_set and "general_multiphysics" not in domain_set:
            item_domains = {str(domain).lower() for domain in item["domains"]}
            if not item_domains.intersection(domain_set):
                continue
        score = sum(1 for word in item["keywords"] if str(word).lower() in text)
        score += sum(2 for domain in item["domains"] if str(domain).lower() in domain_set)
        if score:
            scored.append((score, item))
    scored.sort(key=lambda row: row[0], reverse=True)
    matches = [item for _, item in scored[:top_k]]
    if not matches:
        matches = [MATERIAL_PROPERTY_KNOWLEDGE[1], MATERIAL_PROPERTY_KNOWLEDGE[0]]
    required = _merge_property_rows(item["required"] for item in matches)
    optional = _merge_property_rows(item["optional"] for item in matches)
    recognized_materials = _recognized_materials(text)
    candidate_names = {str(item.get("name", "")).lower() for item in candidate_parameters or []}
    profile_property_keys = {
        str(key).lower()
        for profile in recognized_materials
        for key in profile.get("properties", {})
    }
    covered = [
        row
        for row in required + optional
        if (
            row["symbol"].lower() in candidate_names
            or row["name"].lower() in candidate_names
            or row["comsol_key"].lower() in profile_property_keys
        )
    ]
    missing = [row for row in required if row not in covered]
    dependencies = _unique(str(dep) for item in matches for dep in item["dependencies"])
    labels = " + ".join(str(item["label"]) for item in matches)
    material_text = (
        " Recognized material: " + ", ".join(item["name"] for item in recognized_materials) + "."
        if recognized_materials
        else ""
    )
    return {
        "summary": f"材料与物性参数应优先按“{labels}”配置。{material_text}",
        "required_properties": required,
        "optional_properties": optional,
        "covered_by_case_parameters": covered,
        "missing_required_properties": missing,
        "dependencies": dependencies,
        "matches": [{"id": item["id"], "label": item["label"]} for item in matches],
        "recognized_materials": recognized_materials,
        "matlab_snippet": matlab_material_property_snippet(required + optional[:4]),
    }


def _recognized_materials(text: str) -> list[dict[str, Any]]:
    matches = []
    for profile in MATERIAL_PROFILES:
        if any(keyword.lower() in text for keyword in profile["keywords"]):
            matches.append({"name": profile["name"], "properties": profile["properties"], "note": profile["note"]})
    return matches


def validate_material_readiness(
    requirement: str,
    domains: list[str] | None = None,
    candidate_parameters: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Check whether material data is sufficient for the selected physics."""
    analysis = analyze_material_properties(requirement, domains, candidate_parameters)
    missing = analysis["missing_required_properties"]
    domain_set = {str(domain).lower() for domain in domains or []}
    risks: list[str] = []
    if missing:
        names = "、".join(row["name"] for row in missing)
        risks.append(f"缺少必需物性：{names}，当前不宜直接生成最终求解模型")
    if {"electromagnetics", "heat_transfer"}.issubset(domain_set):
        keys = {row["comsol_key"] for row in analysis["required_properties"]}
        if "electricconductivity" not in keys:
            risks.append("电-热耦合尚未确认电导率，焦耳热源无法可靠计算")
        if not {"thermalconductivity", "heatcapacity"}.issubset(keys):
            risks.append("电-热耦合尚未确认导热系数和比热，温升结果可能不完整")
    if {"fluid", "chemical"}.issubset(domain_set) or "electrochemistry" in domain_set:
        risks.append("传质/电化学场还需确认扩散系数是否随温度、浓度或方向变化")
    return {
        "ready_for_model_generation": not missing,
        "missing_required_properties": missing,
        "risks": _unique(risks),
        "required_properties": analysis["required_properties"],
        "recognized_materials": analysis["recognized_materials"],
        "assumptions": [str(item.get("note", "")) for item in analysis["recognized_materials"] if item.get("note")],
    }


def matlab_material_property_snippet(properties: list[dict[str, str]]) -> str:
    lines = [
        "% Material property scaffold generated from COMSOL training knowledge.",
        "model.component('comp1').material.create('mat1', 'Common');",
        "model.component('comp1').material('mat1').label('material_to_review');",
    ]
    for row in properties[:12]:
        lines.append(f"model.param.set('{row['symbol']}', '{_default_value(row)}', '{row['name']} ({row['unit']})');")
    for row in properties[:12]:
        lines.append(
            f"model.component('comp1').material('mat1').propertyGroup('def').set('{row['comsol_key']}', '{row['symbol']}');"
        )
    lines.append("% If a property depends on temperature/frequency/direction, replace the scalar parameter with an interpolation, analytic function, or tensor expression.")
    return "\n".join(lines)


def material_guidance_text(requirement: str, domains: list[str] | None = None, candidate_parameters: list[dict[str, Any]] | None = None) -> str:
    analysis = analyze_material_properties(requirement, domains, candidate_parameters)
    required = "；".join(f"{row['name']}({row['symbol']}, {row['unit']})" for row in analysis["required_properties"][:8])
    deps = "；".join(analysis["dependencies"][:4])
    missing = "、".join(row["name"] for row in analysis["missing_required_properties"][:8])
    return f"{analysis['summary']} 必填物性：{required}。变化关系：{deps}。待补充：{missing or '当前候选参数已覆盖主要必填项'}。"


def _merge_property_rows(groups: Any) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for group in groups:
        for comsol_key, symbol, name, unit, reason in group:
            if comsol_key in seen:
                continue
            seen.add(comsol_key)
            rows.append(
                {
                    "comsol_key": comsol_key,
                    "symbol": symbol,
                    "name": name,
                    "unit": unit,
                    "reason": reason,
                }
            )
    return rows


def _default_value(row: dict[str, str]) -> str:
    defaults = {
        "density": "2500[kg/m^3]",
        "thermalconductivity": "1[W/(m*K)]",
        "heatcapacity": "800[J/(kg*K)]",
        "youngsmodulus": "35[GPa]",
        "poissonsratio": "0.25",
        "dynamicviscosity": "1e-3[Pa*s]",
        "electricconductivity": "1[S/m]",
        "relpermittivity": "1",
        "soundspeed": "343[m/s]",
    }
    return defaults.get(row["comsol_key"], "1")


def _unique(values: Any) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            unique.append(value)
    return unique
