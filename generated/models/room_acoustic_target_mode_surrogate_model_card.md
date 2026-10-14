# 房间声学目标模态频率代理模型 模型卡

## 物理适用范围
固定房间几何、空气密度、网格和压力声学特征频率研究；仅改变声速 300-380 m/s，追踪基准声速 343 m/s 时靠近 90 Hz 的同一目标模态。

## 训练与独立验证
- 训练数据：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\eigenmodes_of_room_target_mode_training.csv，5 行
- 独立 COMSOL 留出集：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\eigenmodes_of_room_target_mode_holdout.csv
- 验证通过：True
- 最大相对误差：{}
- 阈值：%

## 已验证输入范围
- sound_speed_m_s: 300.0 到 380.0

## 使用限制
- 可用：仅在模型卡所述物理范围、几何拓扑、边界条件和输入范围内用于快速比较。
- 必须回到 COMSOL：输入越界、输出为零需绝对误差判据、物理范围不完整或最终设计定稿时必须回到 COMSOL。
