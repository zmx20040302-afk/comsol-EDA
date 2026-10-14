from __future__ import annotations

import re
from typing import Any

from .boundary_knowledge import boundary_judgment_text, infer_boundary_conditions
from .coupled_physics_knowledge import analyze_coupled_physics
from .geometry_parameter_knowledge import analyze_geometry_parameters
from .material_property_knowledge import analyze_material_properties, validate_material_readiness


ANSWER_POLICY = {
    "kind": "targeted_theory_first_answer_policy",
    "general_rule": "只回答当前问题的结论和理论理由，不主动扩展无关功能、历史过程或实现细节。",
    "theory_rule": "所有判断先说明理论依据，再给出结论；缺少证据时明确指出需要补充的文件或参数。",
    "physics_rule": "涉及物理场选择时必须详细说明控制方程/主要变量/边界条件/适用假设/COMSOL 接口建议。",
}


def respond_to_instruction(
    instruction: str,
    file_summary: dict[str, Any] | None = None,
    model_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    text = instruction.strip()
    lowered = text.lower()
    intents: list[str] = []
    feedback: list[str] = []
    next_actions: list[str] = []
    correction = parse_physics_correction(text)

    if not text:
        return {
            "intent": ["empty"],
            "feedback": ["请先输入建模、文件阅读、训练或约束相关需求。"],
            "next_actions": [],
            "assistant_message": "请先输入一个和 COMSOL 案例学习、建模、约束、仿真或代理模型训练有关的问题。",
            "explanation_sections": [],
            "suggested_tool": "chat",
            "response_policy": ANSWER_POLICY,
        }

    if correction:
        intents.append("physics_correction")
        feedback.append(f"已识别用户纠错：正确物理场应记为 {correction['corrected_physics']}。")
        next_actions.append("把该纠错写入物理场选择记忆，下次相似需求优先采用。")

    if _is_physics_selection_question(text):
        intents.append("physics_selection")
        feedback.append("物理场选择应先看理论对象：守恒量、控制方程、未知变量、边界条件和是否存在多物理耦合。")
        next_actions.append("先确认主要物理量和控制方程，再映射到 COMSOL 物理场接口。")

    if _is_boundary_condition_question(text):
        intents.append("boundary_condition_judgment")
        feedback.append("边界条件与初始条件判断应从控制方程未知量出发，再映射为固定约束、载荷、入口出口、热通量、电压电流、接触、绝缘、对称边界和初始场。")
        next_actions.append("确认每个几何边界/域的物理含义，并用命名选择集避免边界编号变化。")

    if _is_geometry_parameter_question(text):
        intents.append("geometry_parameter_guidance")
        feedback.append("几何与参数分析应在物理场确认后进行：先定维度和几何来源，再定关键尺寸、材料/载荷参数、选择集和扫描变量。")
        next_actions.append("把几何尺寸、边界名称和参数范围整理为可生成 MATLAB/Java 的约束。")

    if _is_material_property_question(text):
        intents.append("material_property_guidance")
        feedback.append("材料与物性参数应根据物理场决定：传热看导热/密度/比热，结构看弹性模量/泊松比，流体看密度/黏度，电学看电导率。")
        next_actions.append("确认物性来源、单位，以及是否随温度、频率或方向变化。")

    if _contains_any(lowered, ["读取", "阅读", "解析", "文件", "read", "inspect", "file"]):
        intents.append("read_file")
        feedback.append("我可以先读取文件摘要；MATLAB .m 文件通常能暴露参数、物理场、研究和结果设置。")
        next_actions.append("先使用文件阅读功能，再检查提取出的摘要。")

    if _contains_any(lowered, ["学习", "总结", "归纳", "案例", "summary", "summarize", "learn", "pdf", "java"]):
        intents.append("learning_summary")
        feedback.append("我可以把相关 COMSOL PDF、MATLAB 建模脚本、Java 导出、MPH 文件、JSON 元数据和 CSV 数据汇总成一个学习包。")
        next_actions.append("把相关文件一起读取，然后生成学习总结。")

    if _contains_any(lowered, ["建模", "生成", "自动", "模型", "comsol", "livelink", "build", "generate", "model"]):
        intents.append("generate_comsol_model")
        feedback.append("我可以根据已校验的约束 JSON 或案例记忆生成 COMSOL LiveLink MATLAB/Java 建模脚本。")
        next_actions.append("先校验约束或检索案例记忆，再生成建模脚本。")

    if _contains_any(lowered, ["约束", "限制", "范围", "边界", "条件", "constraint", "limit"]):
        intents.append("validate_constraints")
        feedback.append("约束应包含几何、材料、边界条件、网格、研究类型和输出量。")
        next_actions.append("检查所有数值是否处在允许范围内。")

    if _contains_any(lowered, ["训练", "代理", "预测", "csv", "train", "surrogate", "predict"]):
        intents.append("train_surrogate")
        feedback.append("代理模型训练需要 COMSOL 参数扫描 CSV，并明确输入列和输出列。")
        next_actions.append("确认依赖已安装，然后用选定的 CSV 列训练。")

    if _contains_any(lowered, [".mph", "mph"]):
        intents.append("read_mph")
        feedback.append(".mph 文件应通过 COMSOL with MATLAB 导出摘要；仅靠 Python 不能可靠恢复完整模型树。")
        next_actions.append("在 COMSOL with MATLAB 中运行 matlab/export_mph_summary.m。")

    if file_summary:
        feedback.append(_feedback_for_file_kind(str(file_summary.get("kind", "unknown")), file_summary))

    if not intents:
        intents.append("general")
        feedback.append("我可以帮助你在文件阅读、脚本生成、约束校验和代理模型训练之间选择下一步。")
        next_actions.append("添加一个或多个文件，或说明要读取、生成、校验还是训练。")

    clarification = _build_clarification(text, intents, file_summary, model_plan)

    return {
        "intent": intents,
        "feedback": feedback,
        "next_actions": next_actions,
        "assistant_message": _assistant_message(text, intents, feedback, next_actions, file_summary, model_plan),
        "explanation_sections": _explanation_sections(intents, file_summary, model_plan),
        "suggested_tool": _suggested_tool(intents),
        "response_policy": ANSWER_POLICY,
        "physics_correction": correction,
        "clarifying_questions": clarification["questions"],
        "assumptions": clarification["assumptions"],
        "risk_flags": clarification["risk_flags"],
    }


def _build_clarification(
    instruction: str,
    intents: list[str],
    file_summary: dict[str, Any] | None,
    model_plan: dict[str, Any] | None,
) -> dict[str, list[str]]:
    """Expose missing evidence before the agent proposes executable COMSOL code."""
    questions: list[str] = []
    assumptions: list[str] = []
    risk_flags: list[str] = []
    plan = model_plan if isinstance(model_plan, dict) else {}
    lowered = instruction.lower()
    has_files = bool(file_summary)
    has_matches = bool(plan.get("matched_cases"))

    if "physics_selection" in intents:
        if not any(token in lowered for token in ("温度", "热", "应力", "位移", "流速", "压力", "浓度", "电流", "电势", "声压")):
            questions.append("主要未知量是什么，例如温度、位移/应力、压力/速度、浓度、电势/电流或声压？")
        if not any(token in lowered for token in ("稳态", "瞬态", "时变", "频域", "特征频率", "特征值", "stationary", "transient", "frequency")):
            questions.append("研究类型是稳态、瞬态、频域、特征值，还是参数扫描？")
        if not any(token in lowered for token in ("耦合", "同时", "联合", "多物理", "热-结构", "流固", "焦耳热")):
            assumptions.append("暂按单一主物理场判断，尚未确认是否需要多物理场耦合。")
    if "generate_comsol_model" in intents:
        if not has_files and not has_matches:
            questions.append("请提供几何来源或尺寸、材料参数、边界/初始条件和目标输出；目前没有足够证据生成可执行模型。")
        if not any(token in lowered for token in ("二维", "三维", "2d", "3d", "轴对称", "一维", "1d")):
            questions.append("模型维度是什么：1D、2D、轴对称还是 3D？")
        risk_flags.append("自动生成的 MATLAB/Java 只能在选择集、单位、物理接口和网格经过检查后执行。")
    if "train_surrogate" in intents:
        if not file_summary or (file_summary.get("details", {}) or {}).get("csv_files", 0) == 0:
            questions.append("请提供 COMSOL 参数扫描 CSV，并说明输入列、输出列和单位；没有 CSV 只能学习建模逻辑，不能训练数值代理模型。")
        risk_flags.append("代理模型只能在已验证的几何、材料、边界和参数范围内使用。")
    if "read_mph" in intents:
        risk_flags.append("MPH 完整模型树需要 COMSOL with MATLAB 或 mphserver 导出摘要，不能仅凭文件名推断。")
    if not has_files and not has_matches and len(questions) == 0 and "general" in intents:
        questions.append("你希望当前先做文件阅读、物理场判断、分步建模、代码生成，还是 CSV 代理模型训练？")
    if questions:
        risk_flags.append("当前信息不足，建议先回答澄清问题，再进入下一步建模或代码生成。")
    return {"questions": questions[:5], "assumptions": assumptions[:5], "risk_flags": risk_flags[:5]}


def _contains_any(text: str, needles: list[str]) -> bool:
    return any(needle.lower() in text for needle in needles)


def _is_physics_selection_question(text: str) -> bool:
    lowered = text.lower()
    return _contains_any(
        lowered,
        [
            "物理场",
            "选择物理",
            "控制方程",
            "温度",
            "应力",
            "流动",
            "电流",
            "电势",
            "电场",
            "电容",
            "电荷",
            "浓度",
            "声压",
            "physics",
            "governing equation",
            "field interface",
        ],
    )


def _explicitly_asks_for_physics_selection(text: str) -> bool:
    lowered = text.lower()
    if "物理场选择后" in lowered or "完成物理场选择后" in lowered:
        return False
    return _contains_any(
        lowered,
        ["选择物理场", "物理场选择", "判断物理场", "选什么物理场", "选哪种物理场", "which physics", "select physics"],
    )


def _is_boundary_condition_question(text: str) -> bool:
    lowered = text.lower()
    return _contains_any(
        lowered,
        [
            "边界条件",
            "边界",
            "入口",
            "出口",
            "载荷",
            "固定约束",
            "热通量",
            "对流换热",
            "端子",
            "接地",
            "无通量",
            "声源",
            "初始条件",
            "初始温度",
            "初始速度",
            "初始位移",
            "初始压力",
            "接触",
            "绝缘",
            "对称边界",
            "boundary condition",
            "initial condition",
            "inlet",
            "outlet",
            "load",
            "terminal",
            "ground",
        ],
    )


def _is_geometry_parameter_question(text: str) -> bool:
    lowered = text.lower()
    return _contains_any(
        lowered,
        [
            "几何",
            "尺寸",
            "结构",
            "选择集",
            "扫描变量",
            "建模指导",
            "matlab代码",
            "matlab 代码",
            "geometry",
            "parameter",
            "dimension",
            "selection",
        ],
    )


def _is_material_property_question(text: str) -> bool:
    lowered = text.lower()
    return _contains_any(
        lowered,
        [
            "材料",
            "物性",
            "密度",
            "导热系数",
            "弹性模量",
            "泊松比",
            "黏度",
            "粘度",
            "电导率",
            "比热",
            "热容",
            "频率",
            "各向异性",
            "随温度",
            "material",
            "density",
            "thermal conductivity",
            "young",
            "poisson",
            "viscosity",
            "conductivity",
            "heat capacity",
        ],
    )


def parse_physics_correction(text: str) -> dict[str, str] | None:
    clean = " ".join(str(text or "").split())
    if not clean:
        return None
    patterns = [
        r"(?:正确|应当|应该|改为|修正为|答案是|物理场是|正确选择为)\s*(?:的)?\s*(?:物理场)?\s*(?:是|为|:|：)?\s*(?P<physics>[A-Za-z][A-Za-z0-9 +/_-]{2,80})",
        r"(?:正确|应当|应该|改为|修正为|答案是|物理场是|正确选择为)\s*(?:的)?\s*(?:物理场)?\s*(?:是|为|:|：)?\s*(?P<physics>[\u4e00-\u9fffA-Za-z0-9 +/_-]{2,80})",
    ]
    for pattern in patterns:
        match = re.search(pattern, clean, flags=re.IGNORECASE)
        if match:
            physics = match.group("physics").strip(" 。；;，,")
            if physics:
                return {
                    "kind": "physics_selection_correction",
                    "corrected_physics": physics,
                    "requirement": clean,
                    "rationale": "用户在对话中给出的正确答案。",
                }
    return None


def _feedback_for_file_kind(kind: str, file_summary: dict[str, Any]) -> str:
    name = file_summary.get("name", "file")
    details = file_summary.get("details", {})
    if kind == "matlab_livelink":
        return (
            f"已识别 {name} 为 COMSOL MATLAB LiveLink 脚本，包含 "
            f"{details.get('parameters', 0)} 个参数，可作为自动建模模板来源。"
        )
    if kind == "csv_table":
        columns = details.get("columns", [])
        return f"已识别 {name} 为可用于代理模型训练的 CSV 表格，列包括：{', '.join(columns[:12])}。"
    if kind == "json":
        return f"已识别 {name} 为 JSON，可能是约束配置或导出的模型摘要。"
    if kind == "comsol_mph":
        return f"已识别 {name} 为 .mph 文件，需要先通过 COMSOL LiveLink 导出摘要。"
    if kind == "file_collection":
        return (
            f"Read {details.get('count', 0)} files: "
            f"{details.get('matlab_files', 0)} MATLAB, "
            f"{details.get('java_files', 0)} Java, "
            f"{details.get('pdf_files', 0)} PDF, "
            f"{details.get('csv_files', 0)} CSV, "
            f"{details.get('json_files', 0)} JSON, "
            f"{details.get('mph_files', 0)} MPH. "
            "我可以把这些文件合并判断建模模板、约束条件和训练数据。"
        )
    return f"已读取 {name}，可根据预览判断它是否支持建模或训练。"


def _assistant_message(
    instruction: str,
    intents: list[str],
    feedback: list[str],
    next_actions: list[str],
    file_summary: dict[str, Any] | None,
    model_plan: dict[str, Any] | None,
) -> str:
    lines = [
        "回答原则：只针对当前问题回答；先给理论依据，再给结论；除物理场选择外保持简洁。",
        "",
        f"我会把这个问题当作 COMSOL 训练任务来处理：{instruction}",
        "",
        "我的理解：你希望把案例、文件或约束转化为可复用的建模知识，而不是只做一次性的文件读取。",
    ]
    # A mention of physics is common background context for later modeling
    # steps. Give priority to the topic explicitly requested in this turn.
    if "physics_selection" in intents and _explicitly_asks_for_physics_selection(instruction):
        lines.extend(_physics_selection_answer(instruction, file_summary, model_plan))
        return "\n".join(lines)
    if "geometry_parameter_guidance" in intents:
        lines.extend(_geometry_parameter_answer(instruction, file_summary, model_plan))
        return "\n".join(lines)
    if "material_property_guidance" in intents:
        lines.extend(_material_property_answer(instruction, file_summary, model_plan))
        return "\n".join(lines)
    if "boundary_condition_judgment" in intents:
        lines.extend(_boundary_condition_answer(instruction, file_summary, model_plan))
        return "\n".join(lines)
    if "physics_selection" in intents:
        lines.extend(_physics_selection_answer(instruction, file_summary, model_plan))
        return "\n".join(lines)

    if "read_file" in intents:
        lines.append("第一步要先读文件证据：MATLAB/Java 用来恢复模型树，PDF 用来理解理论和建模目的，MPH 用来回到 COMSOL 侧验证真实设置。")
    if "learning_summary" in intents:
        lines.append("学习后的总结会沉淀为案例卡，记录建模逻辑、参数、可复用脚本、训练就绪状态和后续缺口。")
    if "generate_comsol_model" in intents:
        lines.append("建模时我会按 COMSOL 底层顺序组织：参数、几何、选择集、材料、物理场、网格、研究、结果导出。")
    if "validate_constraints" in intents:
        lines.append("约束部分会重点检查参数范围、边界条件、单位、输出量和是否能转成 LiveLink MATLAB 脚本。")
    if "train_surrogate" in intents:
        lines.append("训练小模型需要参数扫描 CSV；案例脚本本身先用于学习建模逻辑，数值代理模型要等 sweep 数据存在后再训练。")
    if file_summary:
        lines.append("")
        lines.append("当前文件上下文：" + _compact_file_context(file_summary))
    if model_plan:
        matches = model_plan.get("matched_cases", [])
        lines.append("")
        if matches:
            names = ", ".join(str(item.get("title", "case")) for item in matches[:3])
            lines.append(f"我在本地案例记忆中找到相似案例：{names}。可以优先复用这些案例的参数命名、几何顺序和 API 调用模式。")
        else:
            lines.append("本地案例记忆暂时没有强匹配案例，因此会先按通用 COMSOL 建模流程给方案。")
    if feedback:
        lines.append("")
        lines.append("判断依据：" + " ".join(feedback[:3]))
    if next_actions:
        lines.append("")
        lines.append("下一步我建议：" + " -> ".join(next_actions[:4]))
    return "\n".join(lines)


def _physics_selection_answer(
    instruction: str,
    file_summary: dict[str, Any] | None,
    model_plan: dict[str, Any] | None,
) -> list[str]:
    plan = model_plan or {}
    domains = plan.get("inferred_domains", []) if isinstance(plan, dict) else []
    matches = plan.get("matched_cases", []) if isinstance(plan, dict) else []
    corrections = plan.get("physics_corrections", []) if isinstance(plan, dict) else []
    correction = _best_physics_correction(corrections)
    selection = _selection_from_correction(correction) if correction else _select_physics_from_requirement(instruction, domains)
    boundary_knowledge = infer_boundary_conditions(instruction, domains)
    coupling = analyze_coupled_physics(instruction, domains)
    context = _compact_file_context(file_summary) if file_summary else "当前未提供文件上下文。"
    matched_names = ", ".join(str(item.get("title", "case")) for item in matches[:3]) if matches else "暂无匹配案例"
    correction_note = (
        f"；已优先采用用户纠错记忆：{correction.get('corrected_physics')}"
        if correction
        else ""
    )
    study = _study_type_from_requirement(instruction)
    return [
        "物理场选择判断：",
        f"1. 选择结果：{selection['result']}",
        f"2. 理论依据：{selection['theory']}",
        f"3. COMSOL 接口建议：{selection['interfaces']}",
        f"4. 边界条件判断：{selection['boundaries']}",
        f"5. 边界知识库依据：{boundary_knowledge['summary']} 需要重点确认：{'；'.join(boundary_knowledge['checks'][:4])}。",
        f"6. 复合场检查：{_coupling_line(coupling)}",
        f"7. 研究类型建议：{study}",
        f"8. 当前证据：{context}",
        f"9. 案例记忆依据：匹配案例为 {matched_names}；推断领域为 {', '.join(domains) if domains else '尚未形成明确领域'}{correction_note}。",
        f"10. 需要确认：{selection['checks']}；复合场复核项：{'；'.join(coupling['checks'][:4])}",
    ]


def _study_type_from_requirement(instruction: str) -> str:
    text = instruction.lower()
    if any(token in text for token in ("瞬态", "时变", "随时间", "初始温度", "transient", "time dependent")):
        return "瞬态/Time Dependent"
    if any(token in text for token in ("频域", "频率响应", "frequency", "频响")):
        return "频域/Frequency Domain"
    if any(token in text for token in ("特征值", "特征频率", "模态", "eigenfrequency", "eigenvalue")):
        return "特征值或特征频率/Eigenfrequency"
    if any(token in text for token in ("参数扫描", "扫参", "parametric sweep")):
        return "参数化扫描/Parametric Sweep"
    if any(token in text for token in ("稳态", "stationary")):
        return "稳态/Stationary"
    return "需要确认：稳态、瞬态、频域、特征值或参数扫描"


def _coupling_line(coupling: dict[str, Any]) -> str:
    if not coupling.get("is_coupled"):
        return str(coupling.get("summary", "暂未识别复合场。"))
    return (
        f"{coupling['summary']} 主物理场={coupling['primary_physics']}；"
        f"耦合物理场={'、'.join(coupling['coupled_physics'][:6])}；"
        f"多物理场节点={'、'.join(coupling['multiphysics_nodes'][:6])}；"
        f"耦合变量={'、'.join(coupling['coupling_variables'][:8])}。"
    )


def _boundary_condition_answer(
    instruction: str,
    file_summary: dict[str, Any] | None,
    model_plan: dict[str, Any] | None,
) -> list[str]:
    plan = model_plan or {}
    domains = plan.get("inferred_domains", []) if isinstance(plan, dict) else []
    judgment = infer_boundary_conditions(instruction, domains)
    context = _compact_file_context(file_summary) if file_summary else "当前未提供文件上下文。"
    return [
        "边界条件与初始条件判断：",
        f"1. 判断结论：{judgment['summary']}",
        f"2. 理论依据：{judgment['theory']}",
        f"3. 建议边界类型：{'、'.join(judgment['boundary_types'][:8])}",
        f"4. 初始条件：{'、'.join(judgment['initial_conditions'][:8])}",
        f"5. 必须确认：{'；'.join(judgment['checks'][:5])}",
        f"6. 当前证据：{context}",
        "7. MATLAB 边界/初始条件代码片段：\n```matlab\n" + judgment["matlab_snippet"] + "\n```",
    ]


def _geometry_parameter_answer(
    instruction: str,
    file_summary: dict[str, Any] | None,
    model_plan: dict[str, Any] | None,
) -> list[str]:
    plan = model_plan or {}
    domains = plan.get("inferred_domains", []) if isinstance(plan, dict) else []
    candidate_parameters = plan.get("candidate_parameters", []) if isinstance(plan, dict) else []
    analysis = analyze_geometry_parameters(instruction, domains, candidate_parameters)
    context = _compact_file_context(file_summary) if file_summary else "当前未提供文件上下文。"
    parameter_rows = [
        f"{item['name']}={item['value']}（{item['description']}）"
        for item in analysis["parameters"][:8]
    ]
    return [
        "几何模型与参数分析：",
        f"1. 分析结论：{analysis['summary']}",
        f"2. 维度建议：{analysis['dimension']}",
        f"3. 几何要点：{'；'.join(analysis['geometry'][:6])}",
        f"4. 关键参数：{'；'.join(parameter_rows)}",
        f"5. 选择集建议：{'；'.join(analysis['selection_advice'][:6])}",
        f"6. 后续扫描变量：{'、'.join(analysis['sweep_advice'][:6])}",
        f"7. 当前证据：{context}",
        "8. MATLAB 建模代码片段：\n```matlab\n" + analysis["matlab_snippet"] + "\n```",
    ]


def _material_property_answer(
    instruction: str,
    file_summary: dict[str, Any] | None,
    model_plan: dict[str, Any] | None,
) -> list[str]:
    plan = model_plan or {}
    domains = plan.get("inferred_domains", []) if isinstance(plan, dict) else []
    candidate_parameters = plan.get("candidate_parameters", []) if isinstance(plan, dict) else []
    analysis = analyze_material_properties(instruction, domains, candidate_parameters)
    readiness = validate_material_readiness(instruction, domains, candidate_parameters)
    required = [
        f"{row['name']}={row['symbol']}（{row['unit']}，{row['reason']}）"
        for row in analysis["required_properties"][:10]
    ]
    optional = [
        f"{row['name']}={row['symbol']}（{row['unit']}，{row['reason']}）"
        for row in analysis["optional_properties"][:8]
    ]
    context = _compact_file_context(file_summary) if file_summary else "当前未提供文件上下文。"
    return [
        "材料与物性参数分析：",
        f"1. 分析结论：{analysis['summary']}",
        f"2. 必填物性：{'；'.join(required)}",
        f"3. 可选/耦合物性：{'；'.join(optional) if optional else '暂无'}",
        f"4. 温度/频率/方向依赖：{'；'.join(analysis['dependencies'])}",
        f"5. 待补充物性：{'、'.join(row['name'] for row in analysis['missing_required_properties'][:10]) or '当前候选参数已覆盖主要必填项'}",
        f"6. 建模就绪检查：{'可以进入材料配置' if readiness['ready_for_model_generation'] else '暂不能进入最终求解模型'}",
        f"7. 联动风险：{'；'.join(readiness['risks']) or '未发现明显物性联动风险'}",
        f"8. 默认物性假设：{'；'.join(readiness['assumptions']) or '未使用材料档案默认值'}",
        f"9. 当前证据：{context}",
        "10. MATLAB 材料代码片段：\n```matlab\n" + analysis["matlab_snippet"] + "\n```",
    ]


def _best_physics_correction(corrections: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not corrections:
        return None
    first = corrections[0]
    correction = first.get("correction", first) if isinstance(first, dict) else {}
    if isinstance(correction, dict) and correction.get("corrected_physics"):
        return correction
    return None


def _selection_from_correction(correction: dict[str, Any]) -> dict[str, str]:
    corrected = str(correction.get("corrected_physics", "")).strip()
    rationale = str(correction.get("rationale", "")).strip() or "该选择来自用户纠错记忆，优先级高于关键词推断。"
    return {
        "result": corrected,
        "interfaces": corrected,
        "theory": f"{rationale} 后续相似需求中，模型应先采用这个被人工确认过的物理场，再检查控制方程、主要变量和边界条件是否一致。",
        "boundaries": "边界条件仍需按该物理场的理论要求重新确认。",
        "checks": "确认当前需求与该纠错记忆是否同类；若几何、材料或主变量不同，需要再次修正。",
    }


def _select_physics_from_requirement(instruction: str, domains: list[str]) -> dict[str, str]:
    text = instruction.lower()
    rules = [
        {
            "label": "固体力学 + 达西定律/多孔介质流，必要时加入裂缝扩展模型",
            "interfaces": "Solid Mechanics + Darcy's Law 或 Porous Media Flow；若要模拟裂纹起裂和扩展，需要结合 Fracture Flow、Phase Field 或 Cohesive Zone 等裂缝描述方法",
            "keywords": ["水力压裂", "煤层", "地应力", "围压", "钻孔", "裂纹", "裂缝", "起裂", "扩展", "渗流", "孔隙压力", "超高压", "hydraulic fracturing", "fracture", "poro"],
            "domain_bonus": ["structural", "fluid"],
            "theory": "主要物理量/未知量包括岩体位移和应力、孔隙压力以及裂缝扩展状态。地应力和煤层力学条件由固体力学平衡方程控制，压裂液压力和渗流由达西定律或多孔介质流控制，裂纹扩展需要断裂准则或相场/黏聚区模型描述。",
            "boundaries": "需要设置原位地应力或围压、钻孔内压/注入压力、外边界位移或应力约束、煤层渗透率/孔隙率，以及裂缝面压力或流体泄漏条件。",
            "checks": "确认是只模拟孔压-应力响应，还是要模拟真实裂纹扩展；若要裂纹路径，需要补充断裂能、抗拉强度、损伤准则或相场参数。",
        },
        {
            "label": "电流 + 固体传热（焦耳热耦合）",
            "interfaces": "Electric Currents + Heat Transfer in Solids，可用 Joule Heating 多物理场耦合",
            "keywords": ["电流", "电压", "通电", "电势", "焦耳热", "发热", "母线板", "current", "voltage", "joule"],
            "domain_bonus": [],
            "theory": "需求同时包含电荷守恒/电势分布和温度升高，电流损耗会作为热源进入热传导方程，因此需要电-热耦合。",
            "boundaries": "需要端子电压或电流、接地端、绝缘边界，以及热边界中的温度、热通量或对流换热。",
            "checks": "确认导电材料电导率、热导率、是否稳态、是否需要温度依赖电阻率。",
        },
        {
            "label": "传热",
            "interfaces": "Heat Transfer in Solids；若有流体参与，改用 Heat Transfer in Fluids 或 Nonisothermal Flow",
            "keywords": ["温度", "传热", "导热", "热通量", "热源", "冷却", "对流换热", "辐射", "temperature", "heat", "thermal"],
            "domain_bonus": ["heat_transfer"],
            "theory": "主要物理量/未知量是温度，控制方程是能量守恒；热源、导热、对流或辐射决定温度场。",
            "boundaries": "需要给定温度、热通量、绝热、对流换热系数或辐射边界。",
            "checks": "确认固体/流体区域、材料热参数、稳态或瞬态、是否存在热源耦合。",
        },
        {
            "label": "固体力学",
            "interfaces": "Solid Mechanics",
            "keywords": ["应力", "应变", "位移", "变形", "载荷", "固定约束", "强度", "stress", "strain", "displacement", "load"],
            "domain_bonus": ["structural"],
            "theory": "主要物理量/未知量是位移、应力和应变，控制方程是力平衡方程；应力和应变由材料本构关系得到。",
            "boundaries": "需要固定约束、载荷、压力、位移约束或接触条件。",
            "checks": "确认线弹性/非线性、大变形、材料弹性参数和约束位置。",
        },
        {
            "label": "层流 + 稀物质传递",
            "interfaces": "Laminar Flow + Transport of Diluted Species",
            "keywords": ["浓度", "扩散", "溶质", "混合", "传质", "反应", "吸附", "species", "concentration", "diffusion"],
            "domain_bonus": ["fluid"],
            "theory": "主要物理量/未知量是速度、压力和浓度；若浓度随流场输运，速度压力由流体方程给出，浓度由对流-扩散方程给出，因此需要流动和稀物质传递耦合。",
            "boundaries": "需要入口浓度、入口速度/流量、出口压力或流出条件、壁面无通量/反应/吸附条件。",
            "checks": "确认扩散系数、反应速率、是否稀溶液假设、流场是否影响浓度分布。",
        },
        {
            "label": "层流",
            "interfaces": "Laminar Flow；若雷诺数高再考虑 Turbulent Flow",
            "keywords": ["流动", "流速", "压力", "入口", "出口", "微通道", "层流", "不可压缩", "flow", "velocity", "pressure", "laminar"],
            "domain_bonus": ["fluid"],
            "theory": "主要物理量/未知量是速度和压力，控制方程是质量守恒和 Navier-Stokes 方程；微尺度或低雷诺数通常选层流。",
            "boundaries": "需要入口速度/流量、出口压力、壁面无滑移和初始压力或速度。",
            "checks": "确认雷诺数、是否可压缩、是否稳态、是否需要自由液面或湍流模型。",
        },
        {
            "label": "电流或静电",
            "interfaces": "Electric Currents；若无导电电流、只研究电场分布，选 Electrostatics",
            "keywords": ["电势", "电场", "电流", "电压", "电极", "电导率", "electric", "electrode"],
            "domain_bonus": ["electromagnetics"],
            "theory": "主要物理量/未知量是电势和电流密度；导电介质中由电荷守恒和欧姆定律得到电流分布，绝缘介质静电问题由泊松方程描述。",
            "boundaries": "需要端子、电压、电流、接地、绝缘或电荷边界。",
            "checks": "确认材料是否导电、是否需要频域、电容效应或与热场耦合。",
        },
        {
            "label": "压力声学",
            "interfaces": "Pressure Acoustics；结构振动耦合时增加 Solid Mechanics 或 Acoustic-Structure Boundary",
            "keywords": ["声压", "声学", "噪声", "频率", "共振", "特征频率", "acoustic", "sound"],
            "domain_bonus": ["acoustics"],
            "theory": "主要物理量/未知量是声压，控制方程是频域或时域声波方程；共振问题通常关注频率响应或特征频率。",
            "boundaries": "需要声硬边界、辐射边界、阻抗、声源或背景压力场。",
            "checks": "确认频域/瞬态/特征频率研究、介质声速密度和是否与结构耦合。",
        },
    ]
    scored = []
    for rule in rules:
        score = sum(1 for word in rule["keywords"] if word.lower() in text)
        score += sum(2 for domain in rule["domain_bonus"] if domain in domains)
        if score:
            scored.append((score, rule))
    if not scored:
        return {
            "result": "暂不能唯一确定物理场，建议先给出主要物理量、材料和边界条件。",
            "interfaces": "候选接口需要根据主要物理量确认。",
            "theory": "当前需求缺少足够的控制方程或主要未知量线索，无法可靠映射到单一 COMSOL 物理场。",
            "boundaries": "需要补充入口/出口、载荷、温度、电压、浓度或声源等边界条件。",
            "checks": "补充研究对象、主要输出量、材料类型和是否多物理耦合。",
        }
    scored.sort(key=lambda item: item[0], reverse=True)
    primary = scored[0][1]
    coupled = [item[1]["label"] for item in scored[1:3] if item[0] >= max(2, scored[0][0] - 1)]
    result = primary["label"]
    if coupled:
        result += "；可能还需要耦合：" + "、".join(coupled)
    return {
        "result": result,
        "interfaces": primary["interfaces"],
        "theory": primary["theory"],
        "boundaries": primary["boundaries"],
        "checks": primary["checks"],
    }


def _explanation_sections(
    intents: list[str],
    file_summary: dict[str, Any] | None,
    model_plan: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = [
        {
            "title": "回答约束",
            "items": [
                ANSWER_POLICY["general_rule"],
                ANSWER_POLICY["theory_rule"],
                ANSWER_POLICY["physics_rule"],
            ],
        },
        {
            "title": "COMSOL 训练对话逻辑",
            "items": [
                "先理解需求属于文件阅读、案例学习、约束校验、建模生成还是代理模型训练。",
                "再把可执行证据和理论证据分开：脚本负责模型树，PDF 负责理论，CSV 负责训练。",
                "最后给出可操作的下一步，而不是只返回分类结果。",
            ],
        }
    ]
    if file_summary:
        sections.append({"title": "已读文件如何使用", "items": [_compact_file_context(file_summary)]})
    if model_plan:
        sections.append(
            {
                "title": "记忆库辅助",
                "items": [
                    f"当前记忆库案例数：{model_plan.get('case_count', 0)}",
                    "匹配案例可作为参数、几何顺序和训练路径的参考。",
                ],
            }
        )
    if "train_surrogate" in intents:
        sections.append(
            {
                "title": "训练判断",
                "items": [
                    "没有 CSV 时不能直接训练数值代理模型。",
                    "有 MATLAB/Java/MPH/PDF 时，可以先学习建模逻辑，再用 COMSOL 参数扫描生成训练数据。",
                ],
            }
        )
    return sections


def _suggested_tool(intents: list[str]) -> str:
    if "read_file" in intents:
        return "read_files"
    if "learning_summary" in intents:
        return "learning_summary"
    if "validate_constraints" in intents:
        return "validate_constraints"
    if "generate_comsol_model" in intents:
        return "plan_or_generate_model"
    if "train_surrogate" in intents:
        return "train_surrogate"
    return "chat"


def _compact_file_context(file_summary: dict[str, Any]) -> str:
    kind = str(file_summary.get("kind", "unknown"))
    details = file_summary.get("details", {})
    if kind == "file_collection":
        return (
            f"已读 {details.get('count', 0)} 个文件，其中 MATLAB={details.get('matlab_files', 0)}, "
            f"Java={details.get('java_files', 0)}, PDF={details.get('pdf_files', 0)}, "
            f"MPH={details.get('mph_files', 0)}, CSV={details.get('csv_files', 0)}。"
        )
    return f"已读 {file_summary.get('name', 'file')}，类型为 {kind}。"
