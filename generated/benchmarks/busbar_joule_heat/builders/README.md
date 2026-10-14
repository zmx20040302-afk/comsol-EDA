# 母线板焦耳热基准建模文件

- `busbar_joule_heat_baseline.m`：由已学习的 COMSOL 案例适配而来；保留原始几何、材料、电-热耦合、边界、网格和稳态研究。
- `BusbarJouleHeatBaseline.java`：同一模型的可迁移 Java 导出版本。
- `run_busbar_joule_heat_baseline.m`：在 MATLAB LiveLink for COMSOL 环境中运行，并在本目录保存 `busbar_joule_heat_baseline.mph`。

基准模型保持案例参数：`Vtot=20[mV]`、`htc=5[W/(m^2*K)]`、`L=9[cm]`、`wbb=5[cm]`、`tbb=5[mm]`、螺栓半径 `6[mm]`。热-结构耦合仅作为后续扩展，当前不启用。

运行前需要确认 MATLAB 已安装并配置 LiveLink for COMSOL，且许可证可用。首次求解后应复核边界实体编号、环境温度默认值和 `Tmax` 表格结果。
