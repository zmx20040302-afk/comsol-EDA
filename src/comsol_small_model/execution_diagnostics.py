from __future__ import annotations

from typing import Any


def diagnose_execution_failure(error: str, *, stage: str = "execution") -> dict[str, Any]:
    """Turn common MATLAB/COMSOL failures into concise, actionable Chinese feedback."""
    text = str(error or "").lower()
    category, title, summary, actions, retry = (
        "unknown",
        "未分类执行错误",
        "执行节点返回了未分类错误，请查看完整 MATLAB/COMSOL 日志。",
        ["查看任务日志中最先出现的 COMSOL 错误。", "检查最近修改的物理场、材料、边界条件和单位。"],
        False,
    )
    if stage == "timeout" or "timed out" in text:
        category, title, summary, actions, retry = "timeout", "求解超时", "任务在配置的时限内未完成，可能是网格过密、非线性过强或求解器收敛困难。", ["先减小几何尺寸或网格密度进行基线求解。", "检查边界条件和材料参数的数量级。", "确认后可重试。"], True
    elif "mphserver" in text or "无法启动 mphserver" in text or "connection" in text or "连接" in text:
        category, title, summary, actions, retry = "connection", "COMSOL 服务连接失败", "MATLAB LiveLink 无法连接到 COMSOL mphserver。", ["检查 127.0.0.1:2036 是否监听。", "确认 COMSOL 许可证和 mphserver 正在运行。", "服务恢复后可直接重试。"], True
    elif "license" in text or "许可证" in text:
        category, title, summary, actions, retry = "license", "COMSOL 许可证错误", "COMSOL 或相关模块许可证不可用。", ["检查许可证服务器、模块授权和当前并发占用。", "许可证恢复后再重试。"], True
    elif "livelink" in text or "mphstart" in text:
        category, title, summary, actions, retry = "livelink", "MATLAB LiveLink 配置错误", "MATLAB 未能加载或连接 LiveLink for COMSOL。", ["检查 execution_node.json 中的 livelink_matlab_path。", "在 MATLAB 中确认 mphstart 可用。"], True
    elif "未知物理场接口" in str(error) or "unknown physics interface" in text:
        category, title, summary, actions, retry = "physics_interface", "COMSOL 物理场接口不可用", "当前许可证或安装组件不提供脚本请求的物理场接口。", ["改用当前许可证已包含的等价基础接口，例如 Solid Mechanics。", "仅在确认相应模块许可可用后再使用专用接口。", "修正模型接口后重新生成任务。"], False
    elif "未进行网格划分" in str(error) or "mesh" in text or "网格" in str(error):
        category, title, summary, actions, retry = "mesh", "网格构建或网格结果错误", "模型域没有有效网格，或网格质量/尺寸阻止求解。", ["确认几何已构建并创建了对应维度的网格操作。", "先使用较粗网格验证边界和物理场。", "修正后再重试。"], False
    elif "未定义变量" in str(error) or "未知参数" in str(error) or "undefined variable" in text:
        category, title, summary, actions, retry = "variable", "变量或材料参数未定义", "物理场引用了不存在、同名冲突或未赋值的参数。", ["检查材料属性、全局参数和物理场变量名称。", "避免使用 E、T 等可能与 COMSOL 内部变量冲突的参数名。", "修正脚本后重新生成任务。"], False
    elif "参数值无效" in str(error) or "invalid parameter" in text:
        category, title, summary, actions, retry = "api_property", "COMSOL API 属性值不兼容", "当前 COMSOL 版本不接受脚本中的特征属性或枚举值。", ["读取本机原生示例的相同物理场节点属性。", "按允许值修正建模器，再重新生成任务。"], False
    elif "求解器" in str(error) or "solver" in text or "无法计算表达式" in str(error):
        category, title, summary, actions, retry = "solver", "求解器或方程设置错误", "方程、约束、材料或边界条件导致求解器无法完成计算。", ["检查是否存在刚体运动、缺失材料或矛盾边界。", "先简化为线性稳态基线模型。", "确认模型结构后再重试。"], False
    elif "results csv" in text or "physical result validation" in text or "物理结果检查" in str(error):
        category, title, summary, actions, retry = "result_validation", "结果导出或物理校验未通过", "模型可能已生成，但结果文件缺失或数值不符合模板理论约束。", ["检查 CSV 输出表达式和单位。", "核对边界条件、载荷方向和材料数量级。", "修正模型后重新运行。"], False
    elif "mph artifact" in text:
        category, title, summary, actions, retry = "artifact", "MPH 模型文件未生成", "COMSOL 执行结束但没有得到可打开的 MPH 工件。", ["检查输出目录权限和 mphsave 调用。", "查看 MATLAB 执行日志后重试。"], True
    return {"kind": "execution_diagnosis", "stage": stage, "category": category, "title": title, "summary": summary, "actions": actions, "retry_recommended": retry}
