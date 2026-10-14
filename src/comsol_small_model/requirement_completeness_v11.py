from __future__ import annotations

import re
from typing import Any, Iterable


SCHEMA = "comsol-requirement-completeness"
VERSION = "1.1.0"

_MISSING_MARKERS = (
    "尚未", "未提供", "未给出", "没有提供", "未说明", "未指定", "未定义",
    "尚不明确", "不明确", "待确定", "未知", "缺少", "无法确定", "不清楚",
    "not provided", "not specified", "not defined", "not yet", "unknown",
    "to be determined", "missing", "tbd",
)

_FIELD_PATTERNS: dict[str, tuple[str, ...]] = {
    "objective": (
        r"目标", r"输出", r"观察", r"计算量", r"结果", r"objective", r"output", r"observable",
    ),
    "thermal_boundary": (
        r"环境", r"散热", r"热边界", r"边界温度", r"固定温度", r"对流", r"热流", r"绝热",
        r"ambient", r"thermal boundary", r"temperature boundary", r"convection", r"heat flux", r"insulat",
    ),
    "electrical_boundary": (
        r"端子", r"接地", r"电压", r"电流", r"电势", r"电边界",
        r"terminal", r"ground", r"voltage", r"current", r"electric boundary",
    ),
    "structural_boundary": (
        r"固定", r"约束", r"支撑", r"载荷", r"力", r"压力", r"位移边界",
        r"fixed", r"constraint", r"support", r"load", r"force", r"structural boundary",
    ),
    "flow_boundary": (
        r"入口", r"出口", r"壁面", r"流量", r"流速", r"压强", r"压力边界", r"流动边界",
        r"inlet", r"outlet", r"wall", r"mass flow", r"velocity", r"pressure boundary", r"flow boundary",
    ),
    "acoustic_boundary": (
        r"声源", r"声压边界", r"辐射边界", r"硬声场", r"声学边界", r"入射波",
        r"acoustic source", r"sound pressure boundary", r"radiation boundary", r"sound hard", r"incident wave",
    ),
    "species_boundary": (
        r"入口浓度", r"初始浓度", r"浓度边界", r"通量", r"反应边界", r"传质边界",
        r"inlet concentration", r"initial concentration", r"concentration boundary", r"species flux", r"reaction boundary",
    ),
    "study": (
        r"稳态", r"瞬态", r"频域", r"特征频率", r"研究类型", r"stationary", r"transient", r"frequency", r"eigenfrequency", r"study type",
    ),
}

_POSITIVE_PATTERNS: dict[str, tuple[str, ...]] = {
    "thermal_boundary": (
        r"(?:环境|周围|外界)[^，,。.;；]{0,18}\d+(?:\.\d+)?\s*[kK]",
        r"(?:侧|面|端|壁)[^，,。.;；]{0,10}(?:保持|固定为|设为)?\s*\d+(?:\.\d+)?\s*[kK]",
        r"(?:入口|inlet)[^，,。.;；]{0,18}(?:温度|temperature)",
        r"(?:对流|热流|绝热|固定温度|温度边界|convection|heat flux|insulat|fixed temperature)",
    ),
    "electrical_boundary": (
        r"\d+(?:\.\d+)?\s*(?:mA|A|mV|V)\b", r"(?:端子|terminal)", r"(?:接地|ground)",
    ),
    "structural_boundary": (
        r"(?:固定|约束|支撑|fixed|constraint|support)",
        r"(?:载荷|施加[^，,。.;；]{0,12}(?:力|压力|位移)|load|force|pressure)",
    ),
    "flow_boundary": (
        r"(?:入口|inlet)[^，,。.;；]{0,24}(?:速度|流量|温度|压力|velocity|flow|temperature|pressure)",
        r"(?:出口|outlet)[^，,。.;；]{0,20}(?:压力|压强|流量|pressure|flow)",
        r"(?:壁面|wall)[^，,。.;；]{0,16}(?:无滑移|温度|热流|绝热|no.?slip|temperature|heat flux|insulat)",
    ),
    "acoustic_boundary": (
        r"(?:声源|入射波|声压边界|辐射边界|硬声场|acoustic source|incident wave|sound pressure boundary|radiation boundary|sound hard)",
    ),
    "species_boundary": (
        r"(?:入口浓度|初始浓度|浓度边界|物质通量|反应边界|inlet concentration|initial concentration|concentration boundary|species flux|reaction boundary)",
    ),
}

_REASON_CODES = {
    "objective": "OBJECTIVE_MISSING_OR_UNRESOLVED",
    "thermal_boundary": "MISSING_THERMAL_BOUNDARY",
    "electrical_boundary": "MISSING_ELECTRICAL_BOUNDARY",
    "structural_boundary": "MISSING_STRUCTURAL_CONSTRAINT_OR_LOAD",
    "flow_boundary": "MISSING_FLOW_BOUNDARY",
    "acoustic_boundary": "MISSING_ACOUSTIC_BOUNDARY",
    "species_boundary": "MISSING_SPECIES_BOUNDARY",
    "study": "STUDY_TYPE_UNRESOLVED",
}

_QUESTIONS = {
    "objective": "请明确需要计算、比较或验证的目标物理量。",
    "thermal_boundary": "请补充有效的温度、热流、对流或绝热边界。",
    "electrical_boundary": "请补充端子电压、电流及参考地等电边界。",
    "structural_boundary": "请补充结构约束以及机械载荷或明确的热驱动。",
    "flow_boundary": "请补充入口、出口和壁面条件。",
    "acoustic_boundary": "请补充声源以及声学边界条件。",
    "species_boundary": "请补充浓度、通量或反应边界。",
    "study": "请明确稳态、瞬态、频域或特征频率研究类型。",
}


def _clauses(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"[。；;!?！？\n]|(?<=[，,])", text) if part.strip()]


def _is_missing_clause(clause: str) -> bool:
    lower = clause.lower()
    return any(marker.lower() in lower for marker in _MISSING_MARKERS)


def _matches_any(text: str, patterns: Iterable[str]) -> bool:
    return any(re.search(pattern, text, re.I) for pattern in patterns)


def sanitize_missing_clauses(requirement: str) -> tuple[str, list[str]]:
    """Remove only clauses that explicitly state unavailable or unresolved facts."""
    clauses = _clauses(requirement)
    removed = [clause for clause in clauses if _is_missing_clause(clause)]
    kept = [clause for clause in clauses if not _is_missing_clause(clause)]
    return "。".join(kept).strip("。 "), removed


def _required_fields(interface_ids: set[str], goal_ids: set[str]) -> list[str]:
    required = ["objective"]
    if {"heat_transfer_solids", "heat_transfer_fluids"} & interface_ids or "temperature" in goal_ids:
        required.append("thermal_boundary")
    if "electric_currents" in interface_ids or "electrical_response" in goal_ids:
        required.append("electrical_boundary")
    if "solid_mechanics" in interface_ids or "structural_response" in goal_ids:
        required.append("structural_boundary")
    if "laminar_flow" in interface_ids or "flow_response" in goal_ids:
        required.append("flow_boundary")
    if "pressure_acoustics" in interface_ids or "acoustic_response" in goal_ids:
        required.append("acoustic_boundary")
    if "transport_diluted_species" in interface_ids or "species_response" in goal_ids:
        required.append("species_boundary")
    return required


def analyze_requirement_completeness(
    requirement: str,
    *,
    interface_ids: Iterable[str],
    goal_ids: Iterable[str],
    coupling_ids: Iterable[str] = (),
) -> dict[str, Any]:
    """Return explicit positive, missing and inferred evidence for execution-critical fields."""
    text = " ".join(str(requirement or "").split())
    interfaces = set(interface_ids)
    goals = set(goal_ids)
    couplings = set(coupling_ids)
    sanitized, missing_clauses = sanitize_missing_clauses(text)
    missing_fields: set[str] = set()
    field_evidence: dict[str, dict[str, Any]] = {}

    for field, patterns in _FIELD_PATTERNS.items():
        negative = [clause for clause in missing_clauses if _matches_any(clause, patterns)]
        positive_patterns = _POSITIVE_PATTERNS.get(field, patterns)
        positive = [clause for clause in _clauses(sanitized) if _matches_any(clause, positive_patterns)]
        field_evidence[field] = {"positive": positive, "missing": negative}
        if negative:
            missing_fields.add(field)

    required = _required_fields(interfaces, goals)
    if not goals:
        missing_fields.add("objective")

    # Explicit positive boundary evidence is required for fields that make a
    # model executable. A thermal expansion task may use the thermal field as
    # its load, but it still needs a structural constraint.
    for field in required:
        if field == "objective":
            continue
        if not field_evidence[field]["positive"]:
            missing_fields.add(field)

    # Structural models need a constraint. A separate mechanical load is not
    # required when thermal expansion supplies the declared drive.
    if "structural_boundary" in required:
        positive_text = " ".join(field_evidence["structural_boundary"]["positive"])
        has_constraint = bool(re.search(r"固定|约束|支撑|fixed|constraint|support", positive_text, re.I))
        has_load = bool(re.search(r"载荷|力|压力|load|force|pressure", positive_text, re.I))
        thermally_driven = "thermal_expansion" in couplings
        modal_study = bool(re.search(r"特征频率|固有频率|模态|eigenfrequency|eigenmode", text, re.I))
        if not has_constraint or (not has_load and not thermally_driven and not modal_study):
            missing_fields.add("structural_boundary")

    reason_codes = [_REASON_CODES[field] for field in required + ["study"] if field in missing_fields]
    questions = [_QUESTIONS[field] for field in required + ["study"] if field in missing_fields]
    return {
        "schema": SCHEMA,
        "schemaVersion": VERSION,
        "sanitized_requirement": sanitized,
        "removed_missing_clauses": missing_clauses,
        "required_fields": required,
        "missing_fields": [field for field in required + ["study"] if field in missing_fields],
        "field_evidence": field_evidence,
        "complete": not any(field in missing_fields for field in required + ["study"]),
        "reason_codes": reason_codes,
        "clarification_questions": questions,
    }
