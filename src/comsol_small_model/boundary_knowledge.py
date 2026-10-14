from __future__ import annotations

from typing import Any


BOUNDARY_CONDITION_KNOWLEDGE: list[dict[str, Any]] = [
    {
        "id": "hydraulic_fracturing",
        "label": "水力压裂/孔压-应力耦合",
        "keywords": ["水力压裂", "煤层", "地应力", "围压", "钻孔", "裂缝", "裂纹", "孔隙压力", "渗流", "超高压"],
        "domains": ["structural", "fluid", "porous_media"],
        "theory": "水力压裂边界条件要同时约束岩体力学平衡和压裂液渗流；外部地应力决定初始受力，钻孔内压决定裂缝起裂和扩展驱动力。",
        "boundary_types": [
            "外边界原位地应力、围压或位移约束",
            "钻孔内壁注入压力或流量",
            "煤层/岩体渗透率、孔隙率和初始孔隙压力",
            "裂缝面压力、泄漏或损伤/相场边界",
        ],
        "initial_conditions": ["初始孔隙压力", "初始地应力", "初始位移为零或原位平衡状态", "初始裂缝/损伤变量"],
        "checks": [
            "确认只求孔压-应力响应，还是要求真实裂缝路径",
            "确认最大/最小主应力方向、煤层非均质性和抗拉强度",
            "若生成代码，钻孔、外边界和裂缝面必须使用命名选择集复核",
        ],
    },
    {
        "id": "heat_transfer",
        "label": "传热",
        "keywords": ["温度", "传热", "导热", "热通量", "热源", "冷却", "对流", "辐射", "heat", "thermal"],
        "domains": ["heat_transfer"],
        "theory": "传热边界条件由能量守恒决定；温度、热通量、绝热、对流和辐射分别代表不同的热交换方式。",
        "boundary_types": ["固定温度/给定温度", "热通量或热源", "绝热/对称", "对流换热", "表面对表面或环境辐射"],
        "initial_conditions": ["初始温度", "初始热源状态", "环境温度"],
        "checks": ["确认稳态或瞬态", "确认材料热导率、热容和密度", "确认热源是否来自电流、化学反应或激光输入"],
    },
    {
        "id": "solid_mechanics",
        "label": "固体力学",
        "keywords": ["应力", "应变", "位移", "载荷", "压力", "固定约束", "变形", "stress", "strain", "load"],
        "domains": ["structural"],
        "theory": "固体力学边界条件来自力平衡；必须明确哪些边界限制位移，哪些边界施加载荷、压力、接触或初始应力。",
        "boundary_types": ["固定约束", "位移约束", "边界载荷/压力", "接触边界", "初始应力或体载荷"],
        "initial_conditions": ["初始位移", "初始速度", "初始应力/预应力", "初始接触状态"],
        "checks": ["确认约束不会导致刚体运动", "确认载荷方向和单位", "确认是否需要非线性、大变形、接触或损伤模型"],
    },
    {
        "id": "laminar_flow",
        "label": "流体流动",
        "keywords": ["流动", "流速", "压力", "入口", "出口", "层流", "微通道", "flow", "velocity", "pressure"],
        "domains": ["fluid"],
        "theory": "流体边界条件由质量守恒和动量守恒决定；通常需要入口速度/流量、出口压力和壁面无滑移。",
        "boundary_types": ["入口速度或体积流量", "出口压力", "壁面无滑移", "对称/周期边界", "初始压力或速度"],
        "initial_conditions": ["初始压力", "初始速度", "初始流量或静止状态"],
        "checks": ["确认雷诺数和层流/湍流选择", "确认是否可压缩", "确认入口和出口位置是否与几何方向一致"],
    },
    {
        "id": "species_transport",
        "label": "稀物质传递",
        "keywords": ["浓度", "扩散", "传质", "溶质", "反应", "吸附", "混合", "species", "diffusion"],
        "domains": ["chemical", "fluid"],
        "theory": "传质边界条件由对流-扩散方程决定；入口浓度、壁面通量、反应和出口流出条件决定浓度场。",
        "boundary_types": ["入口浓度", "无通量壁面", "指定通量", "表面反应/吸附", "出口流出条件"],
        "initial_conditions": ["初始浓度", "初始吸附量", "初始反应物分布"],
        "checks": ["确认扩散系数和反应速率", "确认是否由流场携带", "确认浓度是否影响材料或流体性质"],
    },
    {
        "id": "electric",
        "label": "电流/静电",
        "keywords": ["电压", "电流", "电势", "电场", "电极", "接地", "通电", "terminal", "ground", "electric"],
        "domains": ["electromagnetics"],
        "theory": "电学边界条件由电荷守恒和电势方程决定；导电问题需要端子、接地和绝缘边界，静电问题需要电势、电荷或零电荷边界。",
        "boundary_types": ["端子电压或电流", "接地", "电绝缘", "表面电荷", "浮动电势"],
        "initial_conditions": ["初始电势", "初始电荷分布", "初始电流状态"],
        "checks": ["确认介质是否导电", "确认是否频域或瞬态", "若有发热，需把电损耗作为热源耦合到传热"],
    },
    {
        "id": "acoustics",
        "label": "声学",
        "keywords": ["声压", "声学", "噪声", "频率", "共振", "acoustic", "sound"],
        "domains": ["acoustics"],
        "theory": "声学边界条件由声波方程决定；边界可表示刚性反射、吸收、辐射、阻抗或声源激励。",
        "boundary_types": ["声硬边界", "阻抗/吸收边界", "辐射边界", "压力或速度声源", "声-结构耦合边界"],
        "initial_conditions": ["初始声压", "初始质点速度", "初始结构位移/速度（声-结构耦合）"],
        "checks": ["确认频域、瞬态或特征频率研究", "确认介质密度和声速", "确认是否与结构振动耦合"],
    },
]


def infer_boundary_conditions(requirement: str, domains: list[str] | None = None, top_k: int = 3) -> dict[str, Any]:
    text = str(requirement or "").lower()
    domain_set = {str(domain).lower() for domain in domains or []}
    scored: list[tuple[int, dict[str, Any]]] = []
    for item in BOUNDARY_CONDITION_KNOWLEDGE:
        score = sum(1 for word in item["keywords"] if str(word).lower() in text)
        score += sum(2 for domain in item["domains"] if str(domain).lower() in domain_set)
        if score:
            scored.append((score, item))
    scored.sort(key=lambda row: row[0], reverse=True)
    matches = [item for _, item in scored[:top_k]]
    if not matches:
        return {
            "summary": "暂不能可靠判断边界条件类型，需要先确认主物理量、控制方程、几何边界含义和研究类型。",
            "boundary_types": ["入口/出口", "载荷/约束", "温度/热通量", "电压/接地", "浓度/通量", "声源/辐射边界"],
            "initial_conditions": ["初始温度", "初始速度", "初始压力", "初始位移", "初始电势", "初始浓度"],
            "theory": "边界条件必须由控制方程的未知量决定；未知量不明确时，不能直接给出唯一边界设置。",
            "checks": ["补充主要未知量", "补充几何边界名称", "补充材料区域", "补充稳态/瞬态/频域研究类型"],
            "matches": [],
            "matlab_snippet": matlab_boundary_initial_snippet(
                ["入口/出口", "载荷/约束", "温度/热通量"],
                ["初始温度", "初始速度", "初始压力"],
            ),
        }
    boundary_types: list[str] = []
    initial_conditions: list[str] = []
    checks: list[str] = []
    for item in matches:
        boundary_types.extend(str(value) for value in item["boundary_types"])
        initial_conditions.extend(str(value) for value in item.get("initial_conditions", []))
        checks.extend(str(value) for value in item["checks"])
    if "对称" in text:
        boundary_types.append("对称边界")
    if "不穿透" in text or "不可穿透" in text:
        boundary_types.append("不穿透")
    if "固定温度" in text:
        boundary_types.append("固定温度")
    if "给定温度" in text:
        boundary_types.append("给定温度")
    labels = " + ".join(str(item["label"]) for item in matches)
    theory = "；".join(str(item["theory"]) for item in matches)
    return {
        "summary": f"按当前需求，边界条件应优先按“{labels}”来判断。",
        "boundary_types": _unique(boundary_types),
        "initial_conditions": _unique(initial_conditions),
        "theory": theory,
        "checks": _unique(checks),
        "matches": [{"id": item["id"], "label": item["label"]} for item in matches],
        "matlab_snippet": matlab_boundary_initial_snippet(_unique(boundary_types), _unique(initial_conditions)),
    }


def boundary_judgment_text(requirement: str, domains: list[str] | None = None) -> str:
    judgment = infer_boundary_conditions(requirement, domains)
    boundary_types = "、".join(judgment["boundary_types"][:8])
    initial_conditions = "、".join(judgment["initial_conditions"][:6])
    checks = "；".join(judgment["checks"][:5])
    return (
        f"{judgment['summary']} 理论依据：{judgment['theory']} "
        f"建议边界类型：{boundary_types}。 初始条件：{initial_conditions}。 必须确认：{checks}。"
    )


def matlab_boundary_initial_snippet(boundary_types: list[str], initial_conditions: list[str]) -> str:
    lines = [
        "% Boundary and initial condition scaffold generated from COMSOL training knowledge.",
        "% Replace placeholder selections after checking geometry boundary/domain IDs.",
    ]
    joined = " ".join(boundary_types + initial_conditions)
    if any(token in joined for token in ("固定", "位移约束")):
        lines.extend(
            [
                "model.component('comp1').physics('solid').create('fix1', 'Fixed', 1);",
                "% model.component('comp1').physics('solid').feature('fix1').selection.set([boundary_ids]);",
            ]
        )
    if any(token in joined for token in ("载荷", "压力", "围压", "注入")):
        lines.extend(
            [
                "model.component('comp1').physics('solid').create('bndl1', 'BoundaryLoad', 1);",
                "model.component('comp1').physics('solid').feature('bndl1').set('FperArea', {'0' '-p_load' '0'});",
            ]
        )
    if any(token in joined for token in ("入口", "速度", "流量")):
        lines.extend(
            [
                "model.component('comp1').physics('spf').create('inl1', 'InletBoundary', 1);",
                "model.component('comp1').physics('spf').feature('inl1').set('U0in', 'u_in');",
            ]
        )
    if "出口" in joined:
        lines.extend(
            [
                "model.component('comp1').physics('spf').create('out1', 'OutletBoundary', 1);",
                "model.component('comp1').physics('spf').feature('out1').set('p0', 'p_out');",
            ]
        )
    if any(token in joined for token in ("热通量", "热源")):
        lines.extend(
            [
                "model.component('comp1').physics('ht').create('hf1', 'HeatFluxBoundary', 1);",
                "model.component('comp1').physics('ht').feature('hf1').set('q0', 'q0');",
            ]
        )
    if "对流" in joined:
        lines.extend(
            [
                "model.component('comp1').physics('ht').create('hfconv1', 'HeatFluxBoundary', 1);",
                "model.component('comp1').physics('ht').feature('hfconv1').set('HeatFluxType', 'ConvectiveHeatFlux');",
                "model.component('comp1').physics('ht').feature('hfconv1').set('h', 'hconv');",
            ]
        )
    if any(token in joined for token in ("电压", "端子", "电流")):
        lines.extend(
            [
                "model.component('comp1').physics('ec').create('term1', 'Terminal', 1);",
                "model.component('comp1').physics('ec').feature('term1').set('V0', 'V0');",
            ]
        )
    if any(token in joined for token in ("接地", "绝缘")):
        lines.extend(
            [
                "model.component('comp1').physics('ec').create('gnd1', 'Ground', 1);",
                "model.component('comp1').physics('ec').create('ncd1', 'ElectricInsulation', 1);",
            ]
        )
    if "初始温度" in joined:
        lines.append("model.component('comp1').physics('ht').feature('init1').set('Tinit', 'T0');")
    if any(token in joined for token in ("初始速度", "初始压力")):
        lines.extend(
            [
                "model.component('comp1').physics('spf').feature('init1').set('u', {'u0' '0' '0'});",
                "model.component('comp1').physics('spf').feature('init1').set('p', 'p0');",
            ]
        )
    if "初始位移" in joined:
        lines.append("model.component('comp1').physics('solid').feature('init1').set('u', {'0' '0' '0'});")
    if "初始电势" in joined:
        lines.append("model.component('comp1').physics('ec').feature('init1').set('V', 'Vinit');")
    if len(lines) == 2:
        lines.append("% Add physics-specific boundary and initial features after physics tags and selections are confirmed.")
    return "\n".join(lines)


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            unique.append(value)
    return unique
