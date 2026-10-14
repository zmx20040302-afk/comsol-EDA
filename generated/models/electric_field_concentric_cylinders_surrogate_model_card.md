# 同心圆柱静电场代理模型 模型卡

## 物理适用范围
同心圆柱一维轴对称静电模型；ri=0.1 m、ro=1 m、外圆柱接地，仅改变内圆柱 V0=50-150 V。

## 训练与独立验证
- 训练数据：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\electric_field_concentric_cylinders_training.csv，5 行
- 独立 COMSOL 留出集：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\electric_field_concentric_cylinders_holdout.csv
- 验证通过：True
- 最大相对误差：{}
- 阈值：%

## 已验证输入范围
- voltage_V: 50.0 到 150.0

## 使用限制
- 可用：仅在模型卡所述物理范围、几何拓扑、边界条件和输入范围内用于快速比较。
- 必须回到 COMSOL：输入越界、输出为零需绝对误差判据、物理范围不完整或最终设计定稿时必须回到 COMSOL。
