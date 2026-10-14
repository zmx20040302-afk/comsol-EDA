# 一维稳态辐射传热代理模型 模型卡

## 物理适用范围
一维稳态传热模型；左端固定 1000 K、右端向 300 K 环境表面对环境辐射，仅改变右端发射率 epsilon=0.2-0.98。

## 训练与独立验证
- 训练数据：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\heat_radiation_1d_emissivity_training.csv，5 行
- 独立 COMSOL 留出集：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\heat_radiation_1d_emissivity_holdout.csv
- 验证通过：True
- 最大相对误差：{}
- 阈值：%

## 已验证输入范围
- emissivity: 0.2 到 0.98

## 使用限制
- 可用：仅在模型卡所述物理范围、几何拓扑、边界条件和输入范围内用于快速比较。
- 必须回到 COMSOL：输入越界、输出为零需绝对误差判据、物理范围不完整或最终设计定稿时必须回到 COMSOL。
