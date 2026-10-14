from __future__ import annotations

from typing import Any


def infer_result_exports(requirement: str, domains: list[str] | None = None, candidate_outputs: list[str] | None = None) -> dict[str, Any]:
    text = str(requirement or "").lower()
    outputs = [str(item) for item in candidate_outputs or [] if str(item).strip()]
    if any(token in text for token in ("温度", "传热", "焦耳热", "heat", "thermal")):
        outputs.extend(["T_max", "heat_flux", "temperature_profile"])
    if any(token in text for token in ("应力", "应变", "位移", "stress", "strain", "displacement")):
        outputs.extend(["u_max", "mises_max", "displacement_field"])
    if any(token in text for token in ("压力", "流量", "速度", "流动", "flow", "pressure")):
        outputs.extend(["p_max", "velocity_max", "flow_rate"])
    if any(token in text for token in ("电流", "电势", "电场", "焦耳", "electric", "current")):
        outputs.extend(["V_max", "current_density_max", "Q_joule_max"])
    if any(token in text for token in ("特征频率", "模态", "共振", "eigenfrequency")):
        outputs.extend(["eigenfrequency", "mode_shape"])
    outputs = list(dict.fromkeys(outputs or ["primary_quantity_of_interest"]))
    return {
        "outputs": outputs,
        "export_format": ["CSV", "model report"],
        "validation": [
            "先确认输出量、单位和积分/最大值定义",
            "对关键输出进行网格加密和基准工况对比",
            "导出 CSV 前检查结果是否有限、无 NaN 且与边界条件一致",
        ],
        "requires_reference_comparison": any(token in text for token in ("试验", "实验", "现场", "对比", "validation")),
    }
