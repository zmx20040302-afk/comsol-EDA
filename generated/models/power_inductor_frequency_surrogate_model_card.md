# 功率电感器频率响应代理模型 模型卡

## 物理适用范围
功率电感器频率响应模型；几何、材料、端口、网格与研究设置固定，仅改变频率，输出 real(1/mef.Y11/mef.iomega) 电感和 real(mef.Y11) 等效电导。仅适用于 COMSOL 已验证的 500-20000 Hz 范围。

## 训练与独立验证
- 训练数据：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\power_inductor_frequency_training_combined.csv，6 行
- 独立 COMSOL 留出集：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\power_inductor_frequency_holdout_combined.csv
- 验证通过：True
- 最大相对误差：{}
- 阈值：5.0%

## 已验证输入范围
- frequency_Hz: 500.0 到 20000.0

## 使用限制
- 可用：仅在模型卡所述物理范围、几何拓扑、边界条件和输入范围内用于快速比较。
- 必须回到 COMSOL：输入越界、输出为零需绝对误差判据、物理范围不完整或最终设计定稿时必须回到 COMSOL。
