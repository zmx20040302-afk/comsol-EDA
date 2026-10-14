"""Rank learned COMSOL cases for safe CSV sweep and surrogate-training preparation.

This script only proposes candidates. It never launches COMSOL or changes a case card.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCALAR_RESULT_HINTS = ("tmax", "max", "avg", "temperature", "stress", "displacement", "voltage", "current")
OUTPUT_PATTERNS = (
    r"mph(?:global|max|min|int\d?)\s*\(\s*model\s*,\s*['\"]([^'\"]+)",
    r"result\.numerical\s*\(\s*['\"][^'\"]+['\"]\s*\)\.set\s*\(\s*['\"]expr['\"]\s*,\s*['\"]([^'\"]+)",
)
NUMERICAL_EXPR_PATTERN = re.compile(
    r"result\s*\.\s*numerical\s*\([^)]*\)\s*(?:\.\s*)?set\s*\(\s*['\"]expr['\"]\s*,\s*(?:new\s+String\s*\[\s*\]\s*)?\{(?P<items>.*?)\}\s*\)",
    flags=re.IGNORECASE | re.DOTALL,
)
QUOTED_VALUE_PATTERN = re.compile(r"['\"]([^'\"]+)['\"]")
SAFE_STATIONARY_PHYSICS = (
    "ConductiveMedia",
    "HeatTransfer",
    "SolidMechanics",
    "LaminarFlow",
    "DilutedSpecies",
)
UNSUPPORTED_PHYSICS_HINTS = (
    "magnetic",
    "electrostatics",
    "particle",
    "acoustic",
    "wave",
    "semiconductor",
    "plasma",
    "piezo",
    "electrochem",
    "diluted species",
    "dilutedspecies",
    "general form pde",
    "global ode",
    "optimization",
    "rotating machinery",
)
SUPPORTED_SINGLE_PHYSICS = {
    "ConductiveMedia",
    "HeatTransfer",
    "SolidMechanics",
    "LaminarFlow",
}


def _as_list(value: Any) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _physics_tags(physics: list[str]) -> set[str]:
    text = " ".join(physics).lower()
    tags: set[str] = set()
    for tag, tokens in {
        "ConductiveMedia": ("conductivemedia", "electric currents"),
        "HeatTransfer": ("heattransfer", "heat transfer"),
        "SolidMechanics": ("solidmechanics", "solid mechanics"),
        "LaminarFlow": ("laminarflow", "laminar flow"),
    }.items():
        if any(token in text for token in tokens):
            tags.add(tag)
    if any(token in text for token in UNSUPPORTED_PHYSICS_HINTS):
        tags.add("__unsupported__")
    return tags


def _safe_automatic_physics(physics: list[str]) -> bool:
    """Allow only combinations whose default scalar outputs are unambiguous."""
    tags = _physics_tags(physics)
    if "__unsupported__" in tags:
        return False
    if not tags or not tags.issubset(SUPPORTED_SINGLE_PHYSICS):
        return False
    return len(tags) == 1 or tags == {"ConductiveMedia", "HeatTransfer"}


def _script_output_expressions(case_dir: Path, sources: list[Any]) -> list[str]:
    expressions: list[str] = []
    seen: set[str] = set()
    for source in sources:
        if not isinstance(source, dict):
            continue
        name = str(source.get("name", ""))
        if Path(name).suffix.lower() not in {".m", ".java"}:
            continue
        path = Path(str(source.get("path", ""))) if source.get("path") else case_dir / name
        if not path.is_file():
            matches = list(case_dir.rglob(name)) if name else []
            path = matches[0] if len(matches) == 1 else path
        if not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in OUTPUT_PATTERNS:
            for expression in re.findall(pattern, text, flags=re.IGNORECASE):
                normalized = str(expression).strip()
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    expressions.append(normalized)
        for match in NUMERICAL_EXPR_PATTERN.finditer(text):
            for expression in QUOTED_VALUE_PATTERN.findall(match.group("items")):
                normalized = expression.strip()
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    expressions.append(normalized)
    return expressions


def rank_card(card_path: Path) -> dict[str, Any]:
    card = json.loads(card_path.read_text(encoding="utf-8"))
    summary = card.get("file_summary", {})
    content = card.get("case_content", {})
    case_dir = Path(str(card.get("case_dir", "")))
    source_files = card.get("source_files", [])
    physics = _as_list(content.get("physics"))
    studies = _as_list(content.get("studies"))
    parameters = _as_list(content.get("parameters"))
    results = _as_list(content.get("results"))
    output_expressions = _script_output_expressions(case_dir, source_files if isinstance(source_files, list) else [])
    text = " ".join([*physics, *studies])

    reasons: list[str] = []
    cautions: list[str] = []
    score = 0
    mph_files = int(summary.get("mph_files", 0))
    matlab_files = int(summary.get("matlab_files", 0))
    java_files = int(summary.get("java_files", 0))
    csv_files = int(summary.get("csv_files", 0))
    if mph_files:
        score += 4
        reasons.append("含 MPH 权威模型文件")
    if matlab_files:
        score += 4
        reasons.append("含 MATLAB LiveLink 脚本")
    elif java_files:
        score += 2
        reasons.append("含 Java API 脚本")
    if studies:
        score += 2
        reasons.append("已识别研究类型")
    if parameters:
        score += min(4, len(parameters))
        reasons.append(f"已识别 {len(parameters)} 个可扫描参数")
    else:
        cautions.append("未识别可扫描参数")
    if results:
        score += 3
        reasons.append(f"已识别 {len(results)} 个结果量")
    else:
        cautions.append("未识别可导出结果量")

    has_scalar_result = bool(output_expressions) or any(hint in item.lower() for item in results for hint in SCALAR_RESULT_HINTS)
    if output_expressions:
        score += 4
        reasons.append(f"脚本中识别到 {len(output_expressions)} 个数值输出表达式")
    if results and not has_scalar_result:
        cautions.append("当前仅识别到绘图或节点标签，尚未确认标量训练输出")
    is_stationary = "Stationary" in text
    safe_physics = any(token in text for token in SAFE_STATIONARY_PHYSICS)
    safe_automatic_physics = _safe_automatic_physics(physics)
    if is_stationary:
        score += 4
        reasons.append("稳态研究适合先做小型参数扫描")
    else:
        cautions.append("非稳态研究需要控制时间步与计算成本")
    if safe_physics:
        score += 2
    else:
        cautions.append("物理场不在首批低风险自动扫描范围")
    if not safe_automatic_physics:
        cautions.append("多物理场组合或接口未纳入自动扫描默认输出映射")
    if "Eigen" in text or "PDE" in text:
        score -= 4
        cautions.append("特征值或通用 PDE 模型应单独设计训练目标")
    if card.get("training_stage") == "surrogate_validated":
        score -= 12
        cautions.append("已有验证代理模型，不重复纳入首批")
    if csv_files:
        score -= 12
        cautions.append("已关联 CSV 训练证据，应优先复用或检查现有验证状态")

    tier = "C"
    action = "先人工确认参数、输出量和求解成本，再生成扫描脚本。"
    if score >= 17 and is_stationary and safe_automatic_physics and matlab_files and parameters and has_scalar_result and not csv_files:
        tier = "A"
        action = "可先生成 12-24 点小型 COMSOL 扫描计划，并保留独立留出集。"
    elif score >= 11 and mph_files and (matlab_files or java_files):
        tier = "B"
        action = "可读取脚本和模型树后生成扫描计划，但执行前需人工核对参数与结果表达式。"

    return {
        "title": str(card.get("title", card_path.stem)),
        "card_path": str(card_path.resolve()),
        "case_dir": str(case_dir),
        "tier": tier,
        "score": score,
        "training_stage": str(card.get("training_stage", "")),
        "physics": physics,
        "studies": studies,
        "parameters": parameters,
        "results": results,
        "detected_output_expressions": output_expressions,
        "evidence": {"mph_files": mph_files, "matlab_files": matlab_files, "java_files": java_files, "csv_files": csv_files},
        "reasons": reasons,
        "cautions": cautions,
        "recommended_action": action,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cards-dir", type=Path, default=Path("generated/case_knowledge"))
    parser.add_argument("--output", type=Path, default=Path("generated/training_candidates/surrogate_candidates.json"))
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()

    candidates = [rank_card(path) for path in args.cards_dir.glob("*.case.json")]
    candidates.sort(key=lambda item: (item["tier"], -int(item["score"]), item["title"]))
    report = {
        "kind": "comsol-surrogate-candidate-ranking",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "case_count": len(candidates),
        "tier_counts": {tier: sum(item["tier"] == tier for item in candidates) for tier in ("A", "B", "C")},
        "candidates": candidates[: max(1, args.limit)],
        "policy": "候选评分只用于准备训练；真实 COMSOL CSV、独立留出集和物理范围验证后才能登记代理模型。",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output.resolve()), "tier_counts": report["tier_counts"], "shown": len(report["candidates"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

