# 三维导线电阻电导率代理模型 模型卡

## 物理适用范围
三维铜导线 Conductive Media 模型；固定几何、1 A 端子、接地和网格，仅改变各向同性电导率 sigma=3e7-7e7 S/m。

## 训练与独立验证
- 训练数据：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\simple_resistor_conductivity_training.csv，5 行
- 独立 COMSOL 留出集：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\simple_resistor_conductivity_holdout.csv
- 验证通过：True
- 最大相对误差：{}
- 阈值：%

## 已验证输入范围
- conductivity_S_m: 30000000.0 到 70000000.0

## 使用限制
- 可用：仅在模型卡所述物理范围、几何拓扑、边界条件和输入范围内用于快速比较。
- 必须回到 COMSOL：输入越界、输出为零需绝对误差判据、物理范围不完整或最终设计定稿时必须回到 COMSOL。
