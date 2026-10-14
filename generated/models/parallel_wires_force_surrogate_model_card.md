# 平行载流导线电磁力代理模型 模型卡

## 物理适用范围
二维平行圆导线静磁场模型；导线半径 r_wire=0.2 m、间距、方向、外域、网格和力计算区域固定，两个导线由同一同向电流 I0=0.25-3 A 驱动，输出第二导线 x 向电磁力。

## 训练与独立验证
- 训练数据：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\parallel_wires_force_training.csv，9 行
- 独立 COMSOL 留出集：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\parallel_wires_force_holdout.csv
- 验证通过：True
- 最大相对误差：{}
- 阈值：%

## 已验证输入范围
- current_A: 0.25 到 3.0

## 使用限制
- 可用：仅在模型卡所述物理范围、几何拓扑、边界条件和输入范围内用于快速比较。
- 必须回到 COMSOL：输入越界、输出为零需绝对误差判据、物理范围不完整或最终设计定稿时必须回到 COMSOL。
