from __future__ import annotations

import re
from typing import Any


def detect_requirement_conflicts(requirement: str) -> list[dict[str, Any]]:
    """Detect explicit contradictions that must block automatic execution.

    The checks are deliberately narrow. They only reject contradictions that are
    stated in the request itself; ambiguous engineering choices remain questions
    in the modeling contract.
    """
    text = " ".join(str(requirement).split())
    lower = text.lower()
    findings: list[dict[str, Any]] = []

    if re.search(r"(?:长度|宽度|高度|厚度|直径|半径)\s*(?:同时设为)?[^，。;；]*-\s*\d", text):
        findings.append(_finding("NONPOSITIVE_GEOMETRY", "几何尺寸包含负值，无法进入自动建模。"))
    if "同时要求稳态和瞬态" in text or ("steady and transient" in lower):
        findings.append(_finding("STUDY_TYPE_CONFLICT", "同一研究步骤同时要求稳态和瞬态。"))
    if ("同一端子" in text and "接地" in text and ("电压" in text or re.search(r"\d+(?:\.\d+)?\s*v", lower))):
        findings.append(_finding("ELECTRICAL_BOUNDARY_CONFLICT", "同一端子同时设置电势和接地。"))
    if "禁止传热" in text and any(token in text for token in ("焦耳热", "最高温度", "温升")):
        findings.append(_finding("PHYSICS_SCOPE_CONFLICT", "需求禁止传热，同时又要求电热温度结果。"))
    if "同时完全固定和施加自由位移" in text:
        findings.append(_finding("STRUCTURAL_BOUNDARY_CONFLICT", "同一结构边界同时完全固定和自由位移。"))
    if "同一入口" in text and "封闭无滑移壁" in text and any(token in text for token in ("入口速度", "速度")):
        findings.append(_finding("FLOW_BOUNDARY_CONFLICT", "同一入口同时设置入口速度和封闭壁。"))
    if "同一端" in text and "刚性壁" in text and "压力释放" in text:
        findings.append(_finding("ACOUSTIC_BOUNDARY_CONFLICT", "同一声学边界同时设置刚性壁和压力释放。"))
    return findings


def _finding(code: str, message: str) -> dict[str, Any]:
    return {
        "code": code,
        "severity": "critical",
        "message": message,
        "blocks_automatic_execution": True,
    }
