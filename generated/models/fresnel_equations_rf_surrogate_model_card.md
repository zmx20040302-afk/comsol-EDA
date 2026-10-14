# 菲涅尔方程 TE/TM 反射率代理模型 模型卡

## 物理适用范围
菲涅尔方程 RF 模型；空气 n=1 与无损介质 n=1.5 的平面界面，频率固定为 f0，入射角 0-75 deg，分别输出 COMSOL 频域计算的 TE 与 TM 功率反射率。

## 训练与独立验证
- 训练数据：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\fresnel_equations_rf_training.csv，13 行
- 独立 COMSOL 留出集：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\fresnel_equations_rf_holdout.csv
- 验证通过：True
- 最大相对误差：{}
- 阈值：%

## 已验证输入范围
- incident_angle_deg: 0.0 到 75.0

## 使用限制
- 可用：仅在模型卡所述物理范围、几何拓扑、边界条件和输入范围内用于快速比较。
- 必须回到 COMSOL：输入越界、输出为零需绝对误差判据、物理范围不完整或最终设计定稿时必须回到 COMSOL。
