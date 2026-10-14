# 壁虎足载荷与角度响应代理模型 模型卡

## 物理适用范围
壁虎足三维固体力学静态模型；几何、材料、网格、约束和边界载荷定义固定，仅在 Fc_uN、Ff_uN、theta_deg 的已采样范围内预测 max_v_Mises_Pa、max_disp_m 和 max_ep1。该代理模型用于快速筛选，最终设计仍须回到 COMSOL。

## 训练与独立验证
- 训练数据：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\gecko_foot_combined_training.csv，135 行
- 独立 COMSOL 留出集：D:\桌面\codex\comsol1\comsol_training_small_model\generated\training_runs\gecko_foot_load_holdout.csv
- 验证通过：True
- 最大相对误差：{'max_v_Mises_Pa': 2.0148437485186568, 'max_disp_m': 1.848904533007533, 'max_ep1': 1.9352352674391056}
- 阈值：5.0%

## 已验证输入范围
- Fc_uN: 0.2 到 0.6
- Ff_uN: 0.1 到 0.3
- theta_deg: 30.0 到 90.0

## 使用限制
- 可用：仅在模型卡所述物理范围、几何拓扑、边界条件和输入范围内用于快速比较。
- 必须回到 COMSOL：输入越界、输出为零需绝对误差判据、物理范围不完整或最终设计定稿时必须回到 COMSOL。
