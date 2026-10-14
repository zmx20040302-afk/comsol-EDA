# 通信塔桅刚度比代理模型 模型卡

## 物理适用范围
通信塔桅零件的灵敏度分析；固定结构钢材料、安装拓扑、约束、载荷定义和稳态固体力学研究；仅改变板厚 t_p=10-12 mm 与安装厚度 t_m=10-15 mm。

## 训练与独立验证
- 训练数据：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\mast_diagonal_mounting_training.csv，9 行
- 独立 COMSOL 留出集：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\mast_diagonal_mounting_holdout.csv
- 验证通过：True
- 最大相对误差：{}
- 阈值：%

## 已验证输入范围
- t_p_mm: 10.0 到 12.0
- t_m_mm: 10.0 到 15.0

## 使用限制
- 可用：仅在模型卡所述物理范围、几何拓扑、边界条件和输入范围内用于快速比较。
- 必须回到 COMSOL：输入越界、输出为零需绝对误差判据、物理范围不完整或最终设计定稿时必须回到 COMSOL。
