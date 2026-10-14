# 电阻 FEM 场路耦合多输出代理 模型卡

## 物理适用范围
电阻 FEM 场路耦合模型；固定圆柱几何、端子、电路拓扑、R1/R2 和稳态研究；仅改变材料电导率 sigma=800-1200 S/m。

## 训练与独立验证
- 训练数据：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\circuit_fem_resistor_training.csv，5 行
- 独立 COMSOL 留出集：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\circuit_fem_resistor_holdout.csv
- 验证通过：True
- 最大相对误差：{}
- 阈值：%

## 已验证输入范围
- sigma_S_m: 800.0 到 1200.0

## 使用限制
- 可用：仅在模型卡所述物理范围、几何拓扑、边界条件和输入范围内用于快速比较。
- 必须回到 COMSOL：输入越界、输出为零需绝对误差判据、物理范围不完整或最终设计定稿时必须回到 COMSOL。
