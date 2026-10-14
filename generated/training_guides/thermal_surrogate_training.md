# 二维传热代理模型训练任务

使用 `thermal_surrogate_training.json` 的 7 个输入列和 `Tmax_K`、`Tavg_K` 两个输出列。

先运行 COMSOL 参数扫描并导出 CSV；随后进行网格收敛与能量平衡检查，最后按 80/20 划分训练与留出集，报告 RMSE、MAE 和 R2。
