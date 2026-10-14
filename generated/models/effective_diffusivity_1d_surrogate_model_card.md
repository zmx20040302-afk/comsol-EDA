# 一维等效多孔扩散浓度代理模型 模型卡

## 物理适用范围
一维等效多孔扩散瞬态模型；固定孔隙率 epsilon=0.383、传质系数、初始浓度、几何、网格和 100 ms 观测时刻，仅改变等效扩散系数 D1=1e-6-4e-6 m^2/s，输出 x=0.2 mm 的浓度。

## 训练与独立验证
- 训练数据：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\effective_diffusivity_1d_training.csv，5 行
- 独立 COMSOL 留出集：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\effective_diffusivity_1d_holdout.csv
- 验证通过：True
- 最大相对误差：{}
- 阈值：%

## 已验证输入范围
- D1_m2_s: 1e-06 到 4e-06

## 使用限制
- 可用：仅在模型卡所述物理范围、几何拓扑、边界条件和输入范围内用于快速比较。
- 必须回到 COMSOL：输入越界、输出为零需绝对误差判据、物理范围不完整或最终设计定稿时必须回到 COMSOL。
