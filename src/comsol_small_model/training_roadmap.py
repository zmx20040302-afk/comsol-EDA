from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from .case_memory import load_memory


def build_training_roadmap(memory_path: str | Path = "generated/case_memory/case_memory.json") -> dict[str, Any]:
    """Turn the current memory audit into an actionable, ordered training backlog."""
    memory = load_memory(memory_path)
    cases = [item for item in memory.get("cases", []) if isinstance(item, dict)]
    audit = memory.get("knowledge_system", {}).get("quality_audit", {})
    domains = memory.get("knowledge_system", {}).get("domains", [])
    domain_names = [str(item.get("domain", "")) for item in domains if isinstance(item, dict)]
    gap_counts = {str(item.get("issue", "")): int(item.get("count", 0)) for item in audit.get("issue_counts", [])}
    total = len(cases)
    csv_cases = sum(1 for item in cases if (item.get("file_summary", {}) or {}).get("csv_files", 0))
    validated = len(memory.get("template_validations", []))
    return {
        "kind": "comsol_training_roadmap",
        "memory_path": str(memory_path),
        "current_state": {
            "case_count": total,
            "domain_count": len(domain_names),
            "domains": domain_names,
            "average_quality_score": audit.get("average_quality_score", 0),
            "csv_case_count": csv_cases,
            "validated_template_count": validated,
        },
        "principle": "先训练可解释的建模判断，再训练可执行代码，最后训练数值代理模型。",
        "phases": [
            {
                "id": "P1",
                "name": "案例质量门控",
                "status": "active",
                "goal": "把已有案例区分为可用于物理判断、可用于代码参考、仅可用于背景阅读三类。",
                "actions": [
                    "优先补齐物理场、几何、边界条件、材料和求解证据。",
                    "所有推断字段标记 evidence_level=inferred，禁止当作已验证事实。",
                    "对低质量案例降低检索权重，不删除原始案例。",
                ],
                "evidence_needed": ["PDF/MATLAB/Java/MPH 对照", "命名选择集", "求解日志或结果导出"],
            },
            {
                "id": "P2",
                "name": "物理场判断基准集",
                "status": "next",
                "goal": "用人工确认的需求-物理场-理论依据样本训练和评估判断能力。",
                "actions": [
                    "每个主要领域至少整理 10 条正例和 5 条易混淆反例。",
                    "记录主要未知量、控制方程、边界条件和适用假设。",
                    "用户纠正必须进入 corrections，并参与回归测试。",
                ],
                "target": "至少 80 条带标准答案的物理场判断样本",
            },
            {
                "id": "P3",
                "name": "边界、材料和几何推理",
                "status": "pending",
                "goal": "让模型从物理场继续推导可执行的域、边界、材料和参数结构。",
                "actions": [
                    "为每个训练样本增加单位、温度/频率/方向依赖和选择集名称。",
                    "把边界条件写成‘几何边界-物理意义-接口节点-数值表达式’四元组。",
                    "增加维度、坐标系、对称性和网格局部加密的反例。",
                ],
            },
            {
                "id": "P4",
                "name": "可执行 COMSOL 模板",
                "status": "pending",
                "goal": "把 review_required 骨架逐步替换为经过 mphserver 验证的模板。",
                "actions": [
                    "先完成焦耳热，再扩展热应力、流固耦合和水力压裂。",
                    "每个模板必须通过打开、求解、网格检查、结果导出四项检查。",
                    "记录 COMSOL 版本、许可证接口、选择集和求解器日志。",
                ],
            },
            {
                "id": "P5",
                "name": "参数扫描与代理模型",
                "status": "blocked_by_data" if csv_cases == 0 else "ready_to_expand",
                "goal": "在真实 COMSOL 扫描数据上训练数值代理模型，而不是用案例文本代替数值训练。",
                "actions": [
                    "为每个模板导出输入参数、单位、输出量和求解状态。",
                    "保留范围内测试、范围外测试和新 COMSOL holdout。",
                    "比较线性/Ridge、随机森林和 MLP，并保存模型卡与适用范围。",
                ],
                "target": "每个标杆至少 50 条有效扫描记录和 5 条独立验证记录",
            },
            {
                "id": "P6",
                "name": "持续评估与反馈学习",
                "status": "pending",
                "goal": "用统一指标判断模型是否真的变好。",
                "actions": [
                    "记录用户纠正前后的物理场、边界和代码差异。",
                    "每次知识库刷新后运行固定回归问题集。",
                    "只有通过人工审核或 COMSOL 实机验证的知识才提升可信度。",
                ],
                "metrics": ["物理场准确率", "边界完整率", "代码可打开率", "求解成功率", "结果误差", "纠错复用率"],
            },
        ],
        "priority_gaps": sorted(gap_counts.items(), key=lambda pair: pair[1], reverse=True)[:8],
        "recommended_next_task": "先从 10 个焦耳热/热传导案例建立带标准答案的物理场与边界条件基准集，再接入回归测试。",
    }


def write_training_roadmap(
    output_dir: str | Path = "generated/training_roadmap",
    memory_path: str | Path = "generated/case_memory/case_memory.json",
) -> dict[str, str]:
    roadmap = build_training_roadmap(memory_path)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    json_path = destination / "training_roadmap.json"
    md_path = destination / "training_roadmap.md"
    json_path.write_text(json.dumps(roadmap, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# COMSOL 小模型训练路线", "", roadmap["principle"], ""]
    state = roadmap["current_state"]
    lines.append(f"当前案例：{state['case_count']}；领域：{state['domain_count']}；平均质量分：{state['average_quality_score']}；已验证模板：{state['validated_template_count']}；含 CSV 案例：{state['csv_case_count']}。")
    lines.append("")
    for phase in roadmap["phases"]:
        lines.extend([f"## {phase['id']} {phase['name']}（{phase['status']}）", phase["goal"]])
        for action in phase.get("actions", []):
            lines.append(f"- {action}")
        if phase.get("target"):
            lines.append(f"目标：{phase['target']}")
        lines.append("")
    lines.append("## 当前优先缺口")
    for gap, count in roadmap["priority_gaps"]:
        lines.append(f"- {gap}：{count}")
    lines.extend(["", f"## 下一项工作\n{roadmap['recommended_next_task']}"])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}
