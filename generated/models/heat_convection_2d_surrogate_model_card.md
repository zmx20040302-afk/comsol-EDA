# 二维传导-对流温度代理模型 模型卡

## 物理适用范围
二维稳态传导传热；固定矩形几何、导热系数 52 W/(m*K)、左边界 100 degC、环境温度 0 degC、网格与稳态研究；仅改变另外两边的对流换热系数 h=500-1000 W/(m^2*K)。

## 训练与独立验证
- 训练数据：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\heat_convection_2d_training.csv，5 行
- 独立 COMSOL 留出集：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\heat_convection_2d_holdout.csv
- 验证通过：True
- 最大相对误差：{}
- 阈值：%

## 已验证输入范围
- convection_coefficient_W_m2_K: 500.0 到 1000.0

## 使用限制
- 可用：仅在模型卡所述物理范围、几何拓扑、边界条件和输入范围内用于快速比较。
- 必须回到 COMSOL：输入越界、输出为零需绝对误差判据、物理范围不完整或最终设计定稿时必须回到 COMSOL。
