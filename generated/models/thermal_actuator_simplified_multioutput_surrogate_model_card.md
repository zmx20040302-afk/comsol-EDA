# 热微执行器简化模型多输出代理 模型卡

## 物理适用范围
热微执行器简化模型；固定几何、材料、电流-传热-结构耦合和边界条件；DV=4.5-5.5 V，htc_s=15000-25000 W/(m^2*K)，htc_us=400 W/(m^2*K)。

## 训练与独立验证
- 训练数据：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\thermal_actuator_simplified_training.csv，9 行
- 独立 COMSOL 留出集：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\thermal_actuator_simplified_holdout.csv
- 验证通过：True
- 最大相对误差：{}
- 阈值：%

## 已验证输入范围
- DV_V: 4.5 到 5.5
- htc_s_W_m2K: 15000.0 到 25000.0
- htc_us_W_m2K: 400.0 到 400.0

## 使用限制
- 可用：仅在模型卡所述物理范围、几何拓扑、边界条件和输入范围内用于快速比较。
- 必须回到 COMSOL：输入越界、输出为零需绝对误差判据、物理范围不完整或最终设计定稿时必须回到 COMSOL。
