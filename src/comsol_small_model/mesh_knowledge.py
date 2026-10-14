from __future__ import annotations

from typing import Any


def infer_mesh_strategy(requirement: str, domains: list[str] | None = None) -> dict[str, Any]:
    """Recommend a conservative mesh plan from the requested physics and geometry."""
    text = str(requirement or "").lower()
    domain_set = {str(item).lower() for item in domains or []}
    strategy = ["先使用可控的全局网格尺寸，再对结果梯度大的区域局部加密"]
    refinements: list[str] = []
    checks = ["至少进行一次网格加密对比，确认关键输出基本收敛"]

    if "fluid" in domain_set or any(token in text for token in ("流动", "流体", "入口", "出口", "flow", "fluid")):
        strategy.append("流体入口、出口和壁面附近优先采用边界层或局部加密")
        refinements.append("入口/出口/壁面边界层")
        checks.append("检查边界层数量、增长率以及壁面附近速度梯度")
    if any(token in text for token in ("裂纹", "裂缝", "水力压裂", "断裂", "fracture", "crack")):
        strategy.append("裂纹尖端、弱面和孔洞周围采用局部细化，避免全域盲目加密")
        refinements.append("裂纹尖端/孔洞/弱面")
        checks.append("比较裂纹路径、应力集中或压力梯度对网格的敏感性")
    if "heat_transfer" in domain_set or any(token in text for token in ("传热", "温度", "焦耳热", "heat", "thermal")):
        strategy.append("热源、材料界面和温度梯度大的区域局部加密")
        refinements.append("热源/材料界面")
        checks.append("检查最高温度和热流密度在网格加密后的变化")
    if "electromagnetics" in domain_set or any(token in text for token in ("电流", "电势", "电场", "电导", "electric")):
        strategy.append("电极、端子和电流密度集中区域局部加密")
        refinements.append("电极/端子/电流集中区")
        checks.append("检查电流密度峰值是否受单个尖角单元控制")

    return {
        "strategy": strategy,
        "local_refinements": list(dict.fromkeys(refinements)),
        "checks": list(dict.fromkeys(checks)),
        "mesh_parameter": "hmax",
        "requires_user_confirmation": not bool(refinements),
    }
