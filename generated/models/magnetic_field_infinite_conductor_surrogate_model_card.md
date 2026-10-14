# 无限导体磁场电流代理模型 模型卡

## 物理适用范围
无限长圆导体二维轴对称静磁场；导体半径 ri=1 cm、外计算域半径 ro=10 cm、测点距中心 5 cm，固定几何、网格和磁场边界，仅改变电流 I0=0.25-5 A。

## 训练与独立验证
- 训练数据：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\magnetic_field_infinite_conductor_training.csv，9 行
- 独立 COMSOL 留出集：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\magnetic_field_infinite_conductor_holdout.csv
- 验证通过：True
- 最大相对误差：{}
- 阈值：%

## 已验证输入范围
- current_A: 0.25 到 5.0

## 使用限制
- 可用：仅在模型卡所述物理范围、几何拓扑、边界条件和输入范围内用于快速比较。
- 必须回到 COMSOL：输入越界、输出为零需绝对误差判据、物理范围不完整或最终设计定稿时必须回到 COMSOL。
