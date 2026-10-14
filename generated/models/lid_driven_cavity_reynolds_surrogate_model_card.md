# 顶盖驱动方腔流 Reynolds 数速度代理模型 模型卡

## 物理适用范围
二维单位方腔稳态层流；顶盖单位滑移速度、密度 1、黏度 1/Re、固定网格和压力点约束，仅改变 Reynolds 数 Re=50-800，输出 (0.5,0.75) 的速度模。

## 训练与独立验证
- 训练数据：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\lid_driven_cavity_re_training_dense.csv，10 行
- 独立 COMSOL 留出集：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\lid_driven_cavity_re_holdout_v2.csv
- 验证通过：True
- 最大相对误差：{}
- 阈值：%

## 已验证输入范围
- Re: 50.0 到 800.0

## 使用限制
- 可用：仅在模型卡所述物理范围、几何拓扑、边界条件和输入范围内用于快速比较。
- 必须回到 COMSOL：输入越界、输出为零需绝对误差判据、物理范围不完整或最终设计定稿时必须回到 COMSOL。
