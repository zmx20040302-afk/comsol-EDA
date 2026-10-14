from __future__ import annotations

from typing import Any


def infer_study_solver(requirement: str, domains: list[str] | None = None) -> dict[str, Any]:
    text = str(requirement or "").lower()
    studies: list[str] = []
    reasons: list[str] = []
    if any(token in text for token in ("特征频率", "特征值", "模态", "共振", "eigenfrequency", "eigenvalue")):
        studies.append("Eigenfrequency")
        reasons.append("需求关注固有频率、模态或特征值")
    elif any(token in text for token in ("瞬态", "随时间", "动态", "动作电位", "transient", "time dependent")):
        studies.append("Time Dependent")
        reasons.append("需求包含时间演化或动态响应")
    else:
        studies.append("Stationary")
        reasons.append("需求未明确时间变化，先采用稳态基准求解")
    if any(token in text for token in ("参数扫描", "不同", "范围", "扫掠", "sweep", "parametric")):
        studies.append("Parametric Sweep")
        reasons.append("需求包含参数变化或工况对比")
    if "optimization" in {str(item).lower() for item in domains or []} or any(token in text for token in ("优化", "灵敏度", "optimization", "sensitivity")):
        studies.append("Optimization/Sensitivity")
        reasons.append("需求包含优化或灵敏度分析")
    return {
        "studies": studies,
        "primary_study": studies[0],
        "reasons": reasons,
        "solver_checks": [
            "先完成一次基准求解并记录收敛状态",
            "检查残差、相对误差和关键输出是否稳定",
            "参数扫描或代理模型训练必须在基准求解通过后进行",
        ],
        "requires_time_range": "Time Dependent" in studies,
        "requires_eigenvalue_count": "Eigenfrequency" in studies,
    }
