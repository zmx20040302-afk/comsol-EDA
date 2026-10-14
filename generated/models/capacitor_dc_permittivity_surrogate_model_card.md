# 三维电容介电常数代理模型 模型卡

## 物理适用范围
三维电容器静电模型；固定几何、金属端子、接地和网格，仅改变石英域相对介电常数 epsilon_r=2-8。

## 训练与独立验证
- 训练数据：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\capacitor_dc_permittivity_training.csv，5 行
- 独立 COMSOL 留出集：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\capacitor_dc_permittivity_holdout.csv
- 验证通过：True
- 最大相对误差：{}
- 阈值：%

## 已验证输入范围
- relative_permittivity: 2.0 到 8.0

## 使用限制
- 可用：仅在模型卡所述物理范围、几何拓扑、边界条件和输入范围内用于快速比较。
- 必须回到 COMSOL：输入越界、输出为零需绝对误差判据、物理范围不完整或最终设计定稿时必须回到 COMSOL。
