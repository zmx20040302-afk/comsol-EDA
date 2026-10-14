# 二维铜矩形焦耳热温度代理模型 模型卡

## 物理适用范围
2D copper rectangle Joule-heating model, 100 mm by 50 mm, fixed material and convection assumptions, Vtot 0.1-1 mV only.

## 训练与独立验证
- 训练数据：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\joule_first_batch_37.csv，37 行
- 独立 COMSOL 留出集：D:\桌面\codex\comsol1\comsol_training_small_model\generated\staged_workflows\final_code\joule_rectangle_holdout.csv
- 验证通过：True
- 最大相对误差：{}
- 阈值：%

## 已验证输入范围
- Vtot_V: 0.0001 到 0.001

## 使用限制
- 可用：仅在模型卡所述物理范围、几何拓扑、边界条件和输入范围内用于快速比较。
- 必须回到 COMSOL：输入越界、输出为零需绝对误差判据、物理范围不完整或最终设计定稿时必须回到 COMSOL。
