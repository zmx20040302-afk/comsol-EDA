# 热电发电机开路电压代理模型 模型卡

## 物理适用范围
三维热电发电机稳态耦合模型；冷端 0 degC、热端温度 T0=100-200 degC，铜和 Bi-Sb-Te 材料、温度相关 Seebeck 系数/电导率/导热率、几何、网格、接地和浮动端子固定，输出浮动端开路电压。

## 训练与独立验证
- 训练数据：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\thermoelectric_generator_training.csv，6 行
- 独立 COMSOL 留出集：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\thermoelectric_generator_holdout.csv
- 验证通过：True
- 最大相对误差：{}
- 阈值：%

## 已验证输入范围
- hot_temperature_degC: 100.0 到 200.0

## 使用限制
- 可用：仅在模型卡所述物理范围、几何拓扑、边界条件和输入范围内用于快速比较。
- 必须回到 COMSOL：输入越界、输出为零需绝对误差判据、物理范围不完整或最终设计定稿时必须回到 COMSOL。
