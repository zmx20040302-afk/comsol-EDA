# 微执行器焦耳热最高温度代理模型 模型卡

## 物理适用范围
微执行器焦耳热分布参数案例；DV=2-5 V，htc_s=15000-25000 W/(m^2*K)，htc_us=300-500 W/(m^2*K)。模型只用于该已验证工作区内的最高温度预测，不外推至高温失控区。

## 训练与独立验证
- 训练数据：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\thermal_actuator_voltage_extended_training.csv，48 行
- 独立 COMSOL 留出集：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\thermal_actuator_voltage_extension_holdout.csv
- 验证通过：False
- 最大相对误差：{}
- 阈值：%

## 已验证输入范围
- DV_V: 2.0 到 6.6
- htc_s_W_m2K: 15000.0 到 25000.0
- htc_us_W_m2K: 300.0 到 500.0

## 使用限制
- 可用：仅在模型卡所述物理范围、几何拓扑、边界条件和输入范围内用于快速比较。
- 必须回到 COMSOL：输入越界、输出为零需绝对误差判据、物理范围不完整或最终设计定稿时必须回到 COMSOL。
