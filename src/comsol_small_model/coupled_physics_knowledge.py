from __future__ import annotations

from typing import Any


COUPLED_PHYSICS_KNOWLEDGE: list[dict[str, Any]] = [
    {
        "id": "joule_heating",
        "label": "电-热耦合 / 焦耳热",
        "keywords": ["电流", "电压", "电势", "焦耳热", "通电", "发热", "母线板", "current", "voltage", "joule"],
        "domains": ["electromagnetics", "heat_transfer"],
        "primary": "Electric Currents",
        "coupled": ["Heat Transfer in Solids"],
        "multiphysics": ["Joule Heating / Electromagnetic Heating"],
        "coupling_variables": ["电流密度", "电损耗/焦耳热源", "温度场", "温度相关电导率"],
        "reason": "电流守恒先给出电势和电流密度，电损耗作为热源进入能量方程；若电导率随温度变化，热场会反过来影响电场。",
        "checks": ["确认是否稳态或瞬态", "确认电导率是否随温度变化", "确认端子、接地、绝缘和散热边界"],
    },
    {
        "id": "thermal_stress",
        "label": "热-结构耦合 / 热应力",
        "keywords": ["热应力", "热膨胀", "温度", "变形", "应力", "位移", "thermal stress", "thermal expansion"],
        "domains": ["heat_transfer", "structural"],
        "primary": "Heat Transfer",
        "coupled": ["Solid Mechanics"],
        "multiphysics": ["Thermal Expansion"],
        "coupling_variables": ["温度场", "热膨胀应变", "应力/位移", "热膨胀系数"],
        "reason": "温度梯度产生热膨胀应变，结构约束会把热应变转化为应力和位移。",
        "checks": ["确认热膨胀系数", "确认结构约束是否过强", "确认温度场是否来自稳态或瞬态传热"],
    },
    {
        "id": "nonisothermal_flow",
        "label": "非等温流动",
        "keywords": ["非等温", "流动", "温度", "对流换热", "自然对流", "浮力", "冷却", "nonisothermal", "buoyancy"],
        "domains": ["fluid", "heat_transfer"],
        "primary": "Laminar Flow",
        "coupled": ["Heat Transfer in Fluids"],
        "multiphysics": ["Nonisothermal Flow"],
        "coupling_variables": ["速度场", "压力场", "温度场", "对流项", "温度相关密度/黏度"],
        "reason": "流场携带热量形成对流换热，温度又可能通过密度、黏度或浮力影响流动。",
        "checks": ["确认雷诺数", "确认是否需要浮力/Boussinesq近似", "确认入口温度和壁面对流/热通量"],
    },
    {
        "id": "flow_species",
        "label": "流动-传质耦合",
        "keywords": ["浓度", "扩散", "混合", "传质", "反应", "吸附", "溶质", "species", "diffusion", "mixing"],
        "domains": ["fluid"],
        "primary": "Laminar Flow",
        "coupled": ["Transport of Diluted Species"],
        "multiphysics": ["Reacting Flow or manual velocity-coupled species transport"],
        "coupling_variables": ["速度场", "压力场", "浓度场", "扩散系数", "反应/吸附速率"],
        "reason": "速度场决定溶质对流输运，浓度方程还需要扩散和反应项；若浓度影响密度/黏度则形成双向耦合。",
        "checks": ["确认是否稀溶液", "确认扩散系数和反应速率", "确认入口浓度、出口流出和壁面无通量/反应"],
    },
    {
        "id": "poroelastic_fracture",
        "label": "孔压-应力-裂缝耦合",
        "keywords": ["水力压裂", "裂缝", "裂纹", "孔隙压力", "渗流", "煤层", "地应力", "fracture", "poroelastic"],
        "domains": ["structural", "fluid", "porous_media"],
        "primary": "Solid Mechanics",
        "coupled": ["Darcy's Law / Porous Media Flow", "Fracture Flow", "Phase Field or Cohesive Zone"],
        "multiphysics": ["Poroelasticity", "Fracture flow-stress coupling"],
        "coupling_variables": ["岩体位移/应力", "孔隙压力", "渗流速度", "裂缝开度/损伤变量", "注入压力"],
        "reason": "地应力和煤岩本构决定变形，孔隙压力和注入压力改变有效应力，裂缝扩展又改变渗流通道。",
        "checks": ["确认只做孔压-应力还是真实裂缝扩展", "确认渗透率/孔隙率", "确认断裂能、抗拉强度或损伤准则"],
    },
    {
        "id": "fsi",
        "label": "流固耦合",
        "keywords": ["流固", "流体结构", "变形壁面", "压力载荷", "fsi", "fluid structure"],
        "domains": ["fluid", "structural"],
        "primary": "Laminar Flow",
        "coupled": ["Solid Mechanics", "Moving Mesh"],
        "multiphysics": ["Fluid-Structure Interaction"],
        "coupling_variables": ["流体压力/剪切力", "结构位移", "移动网格", "壁面速度"],
        "reason": "流体压力和剪切力加载结构，结构变形改变流体域和边界速度。",
        "checks": ["确认是否小变形", "确认是否需要移动网格", "确认流体和结构交界面的选择集"],
    },
    {
        "id": "acoustic_structure",
        "label": "声-结构耦合",
        "keywords": ["声结构", "声压", "振动", "共振", "音叉", "声学", "acoustic structure"],
        "domains": ["acoustics", "structural"],
        "primary": "Pressure Acoustics",
        "coupled": ["Solid Mechanics"],
        "multiphysics": ["Acoustic-Structure Boundary"],
        "coupling_variables": ["声压", "结构法向加速度/位移", "频率响应", "声阻抗"],
        "reason": "声压作用在结构边界上，结构振动又向声场辐射声波。",
        "checks": ["确认频域/特征频率", "确认声-结构交界面", "确认材料密度、声速和结构弹性参数"],
    },
]


def analyze_coupled_physics(requirement: str, domains: list[str] | None = None, top_k: int = 4) -> dict[str, Any]:
    text = str(requirement or "").lower()
    domain_set = {str(domain).lower() for domain in domains or []}
    scored: list[tuple[int, dict[str, Any]]] = []
    for item in COUPLED_PHYSICS_KNOWLEDGE:
        score = sum(1 for word in item["keywords"] if str(word).lower() in text)
        score += sum(2 for domain in item["domains"] if str(domain).lower() in domain_set)
        if score:
            scored.append((score, item))
    scored.sort(key=lambda row: row[0], reverse=True)
    matches = [item for _, item in scored[:top_k]]
    if not matches:
        return {
            "is_coupled": False,
            "summary": "当前证据不足，暂按单物理场判断；若需求同时包含两类守恒量或变量相互影响，应升级为复合场。",
            "primary_physics": "",
            "coupled_physics": [],
            "multiphysics_nodes": [],
            "coupling_variables": [],
            "reasoning": [],
            "checks": ["确认是否存在热-电、热-结构、流-热、流-传质、孔压-应力、声-结构等变量耦合。"],
            "matches": [],
        }
    primary = matches[0]["primary"]
    coupled = _unique(value for item in matches for value in item["coupled"])
    nodes = _unique(value for item in matches for value in item["multiphysics"])
    variables = _unique(value for item in matches for value in item["coupling_variables"])
    reasoning = _unique(str(item["reason"]) for item in matches)
    checks = _unique(value for item in matches for value in item["checks"])
    labels = " + ".join(str(item["label"]) for item in matches)
    return {
        "is_coupled": True,
        "summary": f"该需求应按复合场判断，优先考虑：{labels}。",
        "primary_physics": primary,
        "coupled_physics": coupled,
        "multiphysics_nodes": nodes,
        "coupling_variables": variables,
        "reasoning": reasoning,
        "checks": checks,
        "matches": [{"id": item["id"], "label": item["label"]} for item in matches],
    }


def coupled_physics_text(requirement: str, domains: list[str] | None = None) -> str:
    analysis = analyze_coupled_physics(requirement, domains)
    if not analysis["is_coupled"]:
        return analysis["summary"]
    return (
        f"{analysis['summary']} 主物理场：{analysis['primary_physics']}；"
        f"耦合物理场：{'、'.join(analysis['coupled_physics'][:6])}；"
        f"COMSOL 多物理场节点：{'、'.join(analysis['multiphysics_nodes'][:6])}；"
        f"耦合变量：{'、'.join(analysis['coupling_variables'][:8])}。"
    )


def _unique(values: Any) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = str(value)
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result
