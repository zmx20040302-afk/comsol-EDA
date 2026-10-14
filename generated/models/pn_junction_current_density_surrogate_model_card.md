# 一维 P-N 结截面电流密度代理模型 模型卡

## 物理适用范围
一维硅 P-N 结稳态半导体模型；Tl=300 K、Na=Nd=1e15 1/cm^3、几何、材料、网格和金属接触固定；仅改变正向偏压 0.05-0.5 V，输出 x=2.5 um 截面的 x 向总电流密度 semi.JX。

## 训练与独立验证
- 训练数据：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\pn_junction_current_density_training.csv，6 行
- 独立 COMSOL 留出集：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\pn_junction_current_density_holdout.csv
- 验证通过：True
- 最大相对误差：3.039838475712522
- 阈值：5.0%

## 已验证输入范围
- bias_V: 0.05 到 0.5

## 使用限制
- 可用：仅在模型卡所述物理范围、几何拓扑、边界条件和输入范围内用于快速比较。
- 必须回到 COMSOL：输入越界、输出为零需绝对误差判据、物理范围不完整或最终设计定稿时必须回到 COMSOL。
