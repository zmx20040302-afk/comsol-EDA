# 亥姆霍兹线圈中心磁场代理模型 模型卡

## 物理适用范围
三维亥姆霍兹双圆线圈磁场模型；两个线圈同向等电流、几何、材料、网格、无限元域与中心测点固定，仅改变线圈电流 I0=0.05-0.6 mA，输出中心带符号 By。

## 训练与独立验证
- 训练数据：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\helmholtz_coil_training.csv，9 行
- 独立 COMSOL 留出集：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\helmholtz_coil_holdout.csv
- 验证通过：True
- 最大相对误差：{}
- 阈值：%

## 已验证输入范围
- coil_current_mA: 0.05 到 0.6

## 使用限制
- 可用：仅在模型卡所述物理范围、几何拓扑、边界条件和输入范围内用于快速比较。
- 必须回到 COMSOL：输入越界、输出为零需绝对误差判据、物理范围不完整或最终设计定稿时必须回到 COMSOL。
