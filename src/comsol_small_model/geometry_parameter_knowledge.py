from __future__ import annotations

import re
from typing import Any


GEOMETRY_PARAMETER_KNOWLEDGE: list[dict[str, Any]] = [
    {
        "id": "hydraulic_fracturing_borehole",
        "label": "水力压裂单孔/裂隙几何",
        "keywords": ["水力压裂", "煤层", "钻孔", "裂缝", "裂纹", "围压", "地应力", "孔隙压力"],
        "domains": ["structural", "fluid", "porous_media"],
        "dimension": "2D 平面应变优先；需要厚度效应或三维钻孔时再升为 3D",
        "geometry": [
            "矩形或正方形煤/岩体代表试验工作面或局部煤层",
            "中心或指定位置圆形钻孔",
            "可选预制裂缝、弱面或自然裂隙线",
            "外边界用于施加地应力、围压或位移约束",
        ],
        "parameters": [
            ("Lx", "300[mm]", "模型宽度/工作面局部代表长度"),
            ("Ly", "300[mm]", "模型高度/煤层局部代表高度"),
            ("rb", "7.5[mm]", "钻孔半径"),
            ("pinj", "20[MPa]", "钻孔注入压力"),
            ("sigH", "15[MPa]", "最大水平主应力"),
            ("sigh", "10[MPa]", "最小水平主应力"),
            ("k_perm", "1e-15[m^2]", "煤/岩体渗透率"),
        ],
        "selection_advice": ["命名钻孔边界", "命名外边界四边", "命名裂缝/弱面边界", "命名煤岩基体域"],
        "sweep_advice": ["pinj", "sigH", "sigh", "k_perm", "rb"],
    },
    {
        "id": "heat_transfer_domain",
        "label": "传热几何与参数",
        "keywords": ["传热", "温度", "导热", "热通量", "热源", "冷却", "heat", "thermal"],
        "domains": ["heat_transfer"],
        "dimension": "先按几何厚度选择 2D 或 3D；薄板可用 2D，实体散热优先 3D",
        "geometry": ["矩形/块体热传导域", "热源区域", "冷却或对流边界", "温度监测点或输出边界"],
        "parameters": [
            ("L", "0.1[m]", "几何长度"),
            ("W", "0.05[m]", "几何宽度"),
            ("Q0", "1e5[W/m^3]", "体热源"),
            ("hconv", "10[W/(m^2*K)]", "对流换热系数"),
            ("Tamb", "293.15[K]", "环境温度"),
        ],
        "selection_advice": ["命名热源域", "命名固定温度边界", "命名对流边界", "命名输出点/面"],
        "sweep_advice": ["Q0", "hconv", "L", "W"],
    },
    {
        "id": "solid_mechanics_part",
        "label": "结构力学几何与参数",
        "keywords": ["应力", "位移", "载荷", "变形", "固定约束", "梁", "支架", "stress", "load"],
        "domains": ["structural"],
        "dimension": "二维截面适合快速判断，真实零件、接触或厚度效应应使用 3D",
        "geometry": ["受力实体或梁/板结构", "固定端", "载荷作用面", "应力集中孔洞或圆角"],
        "parameters": [
            ("L", "1[m]", "结构长度"),
            ("W", "0.1[m]", "结构宽度"),
            ("F0", "100[N]", "外加载荷"),
            ("E_ref", "200[GPa]", "杨氏模量"),
            ("nu_ref", "0.3", "泊松比"),
        ],
        "selection_advice": ["命名固定约束边界", "命名载荷边界", "命名应力输出区域", "命名对称边界"],
        "sweep_advice": ["F0", "E_ref", "L", "W"],
    },
    {
        "id": "microfluidic_channel",
        "label": "流体/传质通道几何与参数",
        "keywords": ["流动", "层流", "微通道", "入口", "出口", "浓度", "扩散", "混合", "flow", "species"],
        "domains": ["fluid"],
        "dimension": "长直微通道可先用 2D；复杂混合器、螺旋结构或真实截面应使用 3D",
        "geometry": ["入口通道", "主流道或混合区", "出口边界", "壁面和可选障碍物/混合结构"],
        "parameters": [
            ("Lch", "10[mm]", "通道长度"),
            ("Wch", "1[mm]", "通道宽度"),
            ("uin", "1e-3[m/s]", "入口平均速度"),
            ("D_s", "1e-9[m^2/s]", "扩散系数"),
            ("c0", "1[mol/m^3]", "入口浓度"),
        ],
        "selection_advice": ["命名入口", "命名出口", "命名壁面", "命名浓度入口"],
        "sweep_advice": ["uin", "D_s", "Wch", "c0"],
    },
]


def analyze_geometry_parameters(
    requirement: str,
    domains: list[str] | None = None,
    candidate_parameters: list[dict[str, Any]] | None = None,
    top_k: int = 2,
) -> dict[str, Any]:
    text = str(requirement or "").lower()
    domain_set = {str(domain).lower() for domain in domains or []}
    scored: list[tuple[int, dict[str, Any]]] = []
    for item in GEOMETRY_PARAMETER_KNOWLEDGE:
        score = sum(1 for word in item["keywords"] if str(word).lower() in text)
        score += sum(2 for domain in item["domains"] if str(domain).lower() in domain_set)
        if score:
            scored.append((score, item))
    scored.sort(key=lambda row: row[0], reverse=True)
    matches = [item for _, item in scored[:top_k]]
    if not matches:
        parameters = _merge_parameters([], candidate_parameters or [])
        if not parameters:
            parameters = [
                {"name": "L_ref", "value": "1[m]", "description": "参考长度"},
                {"name": "W_ref", "value": "1[m]", "description": "参考宽度"},
                {"name": "H_ref", "value": "0.1[m]", "description": "参考厚度"},
            ]
        return {
            "summary": "当前需求还不能唯一确定几何模板，应先按通用参数化几何组织。",
            "dimension": "先从 2D 简化模型开始；若厚度、三维结构或真实装配影响结果，再升级为 3D。",
            "geometry": ["建立参数化基准域", "为材料域、载荷边界和输出区域创建命名选择集", "保留导入 CAD 或案例几何替换接口"],
            "parameters": parameters,
            "selection_advice": ["命名材料域", "命名载荷/入口/热源边界", "命名输出边界或监测点"],
            "sweep_advice": [item["name"] for item in parameters[:5]],
            "matches": [],
            "matlab_snippet": matlab_geometry_parameter_snippet(parameters, "generic"),
        }
    parameters = _merge_parameters(matches, candidate_parameters or [])
    labels = " + ".join(str(item["label"]) for item in matches)
    return {
        "summary": f"几何与参数应优先按“{labels}”组织。",
        "dimension": matches[0]["dimension"],
        "geometry": _unique_text(value for item in matches for value in item["geometry"]),
        "parameters": parameters,
        "selection_advice": _unique_text(value for item in matches for value in item["selection_advice"]),
        "sweep_advice": _unique_text(value for item in matches for value in item["sweep_advice"]),
        "matches": [{"id": item["id"], "label": item["label"]} for item in matches],
        "matlab_snippet": matlab_geometry_parameter_snippet(parameters, matches[0]["id"]),
    }


def geometry_parameter_guidance_text(
    requirement: str,
    domains: list[str] | None = None,
    candidate_parameters: list[dict[str, Any]] | None = None,
) -> str:
    analysis = analyze_geometry_parameters(requirement, domains, candidate_parameters)
    params = "、".join(item["name"] for item in analysis["parameters"][:8])
    geometry = "；".join(analysis["geometry"][:5])
    selections = "；".join(analysis["selection_advice"][:5])
    return (
        f"{analysis['summary']} 维度建议：{analysis['dimension']}。"
        f"几何要点：{geometry}。关键参数：{params}。选择集建议：{selections}。"
    )


def validate_geometry_readiness(
    requirement: str,
    domains: list[str] | None = None,
    candidate_parameters: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Check whether geometry evidence is sufficient for downstream meshing."""
    analysis = analyze_geometry_parameters(requirement, domains, candidate_parameters)
    text = str(requirement or "")
    has_dimension_evidence = bool(re.search(r"\d+(?:\.\d+)?\s*(?:mm|毫米|cm|厘米|m|米|um|微米|°|度)", text, re.IGNORECASE))
    supplied_parameters = bool(candidate_parameters)
    missing: list[str] = []
    if not has_dimension_evidence and not supplied_parameters:
        missing.append("几何尺寸与单位")
    if not analysis.get("matches") and not supplied_parameters:
        missing.append("几何类型或导入文件")
    return {
        "ready_for_meshing": not missing,
        "missing_geometry_evidence": missing,
        "dimension_evidence_found": has_dimension_evidence,
        "matched_patterns": analysis.get("matches", []),
        "selection_advice": analysis.get("selection_advice", []),
    }


def matlab_geometry_parameter_snippet(parameters: list[dict[str, str]], pattern_id: str = "generic") -> str:
    lines = [
        "% Geometry and parameter scaffold generated from learned COMSOL cases.",
        "model.component.create('comp1', true);",
        "model.component('comp1').geom.create('geom1', 2);",
        "model.component('comp1').geom('geom1').lengthUnit('m');",
    ]
    for item in parameters[:12]:
        lines.append(
            f"model.param.set('{_safe_param(item['name'])}', '{_matlab_string(item['value'])}', '{_matlab_string(item['description'])}');"
        )
    if pattern_id == "hydraulic_fracturing_borehole":
        lines.extend(
            [
                "model.component('comp1').geom('geom1').create('rect1', 'Rectangle');",
                "model.component('comp1').geom('geom1').feature('rect1').set('size', {'Lx' 'Ly'});",
                "model.component('comp1').geom('geom1').feature('rect1').set('pos', {'-Lx/2' '-Ly/2'});",
                "model.component('comp1').geom('geom1').create('c1', 'Circle');",
                "model.component('comp1').geom('geom1').feature('c1').set('r', 'rb');",
                "model.component('comp1').geom('geom1').create('dif1', 'Difference');",
                "model.component('comp1').geom('geom1').feature('dif1').selection('input').set({'rect1'});",
                "model.component('comp1').geom('geom1').feature('dif1').selection('input2').set({'c1'});",
                "% TODO: add fracture/weak-plane geometry after confirming orientation and length.",
            ]
        )
    else:
        lines.extend(
            [
                "model.component('comp1').geom('geom1').create('rect1', 'Rectangle');",
                "model.component('comp1').geom('geom1').feature('rect1').set('size', {'L_ref' 'W_ref'});",
            ]
        )
    lines.extend(
        [
            "model.component('comp1').geom('geom1').run;",
            "% TODO: create named selections after checking generated domain and boundary IDs in COMSOL.",
        ]
    )
    return "\n".join(lines)


def _merge_parameters(matches: list[dict[str, Any]], candidate_parameters: list[dict[str, Any]]) -> list[dict[str, str]]:
    merged: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in candidate_parameters:
        name = _safe_param(str(raw.get("name", "")))
        if not name or name in seen:
            continue
        seen.add(name)
        merged.append(
            {
                "name": name,
                "value": str(raw.get("value") or "1"),
                "description": str(raw.get("description") or raw.get("source_case") or "案例学习参数"),
            }
        )
    for item in matches:
        for name, value, description in item["parameters"]:
            safe_name = _safe_param(name)
            if safe_name in seen:
                continue
            seen.add(safe_name)
            merged.append({"name": safe_name, "value": value, "description": description})
    return merged


def _unique_text(values: Any) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        text = str(value)
        if text and text not in seen:
            seen.add(text)
            unique.append(text)
    return unique


def _safe_param(value: str) -> str:
    name = re.sub(r"\W+", "_", value, flags=re.ASCII).strip("_")
    if not name or name[0].isdigit():
        name = f"p_{name or 'ref'}"
    return name[:60]


def _matlab_string(value: str) -> str:
    return str(value).replace("'", "''")
