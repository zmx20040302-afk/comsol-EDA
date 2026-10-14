# 锥形悬臂梁边界力位移代理模型 模型卡

## 物理适用范围
二维锥形悬臂梁小变形线弹性静力学；固定几何、E=210 GPa、nu=0.3、重力工况、约束和网格，仅改变边界力工况 5e6-1.5e7 N/m。

## 训练与独立验证
- 训练数据：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\tapered_cantilever_force_training.csv，5 行
- 独立 COMSOL 留出集：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\tapered_cantilever_force_holdout.csv
- 验证通过：True
- 最大相对误差：{}
- 阈值：%

## 已验证输入范围
- boundary_force_N_m: 5000000.0 到 15000000.0

## 使用限制
- 可用：仅在模型卡所述物理范围、几何拓扑、边界条件和输入范围内用于快速比较。
- 必须回到 COMSOL：输入越界、输出为零需绝对误差判据、物理范围不完整或最终设计定稿时必须回到 COMSOL。
