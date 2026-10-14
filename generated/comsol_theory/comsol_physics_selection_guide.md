# COMSOL 物理场类型与选择指南

这份总结来自小模型已学习的 COMSOL 案例库和每个案例的 `physics_judgement` 字段。核心原则是：先判断主变量和控制方程，再选择物理场接口，最后用 MATLAB/Java 或模型树证据校验。

## 总体选择流程

1. 先用一句话写清楚要观察或预测的主变量，例如温度、应力、速度、浓度、电势、声压或自定义变量。
2. 根据主变量选择主物理场：温度选传热，应力/位移选固体力学，速度/压力选流体，浓度选物质传递，电势/电流选电学，声压选声学。
3. 如果需求出现两个以上主变量，先确定驱动关系，再选择多物理场耦合，例如电流产生焦耳热，再导致温升或热变形。
4. 如果 PDF 或需求给出的是自定义方程，而不是标准物理接口，优先考虑 PDE 接口，并把方程系数、变量和边界条件列出来。
5. 再选择研究类型：稳态看最终平衡，瞬态看随时间变化，特征频率/特征值看模态或能级，频域看谐波响应，参数扫描看变量影响。
6. 最后用 MATLAB/Java 中的 physics.create 或 COMSOL 模型树证据校验物理场名称，避免只凭案例标题猜测。

## 常见物理场类型

### 传热 (Heat Transfer)
- 什么时候选：需求关注温度、热通量、导热、对流、辐射、冷却、热源、热失控或瞬态加热。
- 判断关键词：温度, 热通量, 导热, 对流换热, 辐射传热, 热源, 冷却, 热失控
- 常见研究类型：Stationary, Time Dependent, Parametric Sweep
- 已学习案例示例：使用网格划分序列, 借助变形几何接口修改导入的 CAD 几何, 受载弹簧 - 使用全局方程满足约束条件, 含载荷突变的瞬时加热6.2, 在轨航天器, 多孔材料的有效扩散系数, 如何生成随机非均匀材料数据6.2, 安装验证

### 固体力学 (Solid Mechanics)
- 什么时候选：需求关注应力、应变、位移、载荷、固定约束、刚度、模态或结构安全。
- 判断关键词：应力, 应变, 位移, 载荷, 固定约束, 模态, 刚度, 变形
- 常见研究类型：Stationary, Time Dependent, Eigenfrequency, Eigenvalue
- 已学习案例示例：App 中用户定义的许可协议, 两种载荷工况下的锥形悬臂梁, 传输线参数计算器, 变形曲面的泽尼克多项式拟合, 心脏电信号, 扳手的应力和应变, 承受动载荷的梁, 支架几何的扫掠网格

### 层流 (Laminar Flow)
- 什么时候选：需求关注低雷诺数流动、入口速度、出口压力、压力降、通道流、绕流或速度场。
- 判断关键词：速度, 压力, 入口, 出口, 层流, 不可压缩流, Navier-Stokes, 绕流
- 常见研究类型：Stationary, Time Dependent
- 已学习案例示例：Blasius 边界层, 传递和吸附, 使用 PID 控制器的过程控制, 化学蚀刻, 圆柱绕流, 如何在求解后自动导出图像仅6.3, 岩石裂隙流, 带非等温冷却夹套的管式反应器

### 电流 / 静电 (Electric Currents / Electrostatics)
- 什么时候选：需求关注电势、电流、电极、接地、端子、电场分布、电阻、电传感或焦耳热来源。
- 判断关键词：电压, 电流, 电势, 电极, 接地, 端子, 电阻, 电场
- 常见研究类型：Stationary, Frequency Domain, Parametric Sweep
- 已学习案例示例：四极透镜, 电传感器, 电传感器批处理扫描

### 稀物质传递 (Transport of Diluted Species)
- 什么时候选：需求关注浓度、扩散、吸附、反应、通量、化学蚀刻或与流场耦合的物质输运。
- 判断关键词：浓度, 扩散, 吸附, 反应速率, 通量, 物质传递, 化学蚀刻
- 常见研究类型：Stationary, Time Dependent
- 已学习案例示例：当前案例库证据较少，需要结合脚本校验

### 压力声学 (Pressure Acoustics)
- 什么时候选：需求关注声压、声场、共振、房间模态、消声器、频域声学响应或瞬态声压级。
- 判断关键词：声压, 声场, 声学, 共振, 特征模态, 频域, 消声器
- 常见研究类型：Frequency Domain, Eigenfrequency, Time Dependent
- 已学习案例示例：房间的特征模态, 瞬态声压级6.3, 集群设置验证

### 系数形式 PDE / 通用 PDE (Coefficient Form PDE / General Form PDE)
- 什么时候选：需求核心是自定义控制方程，或 COMSOL 没有直接对应的专用接口，例如量子能级、Black-Scholes、KdV、浅水方程、延迟方程或积分方程。
- 判断关键词：自定义方程, 偏微分方程, 系数形式, 弱形式, 特征值, 波函数, 能级, Black-Scholes, KdV
- 常见研究类型：Stationary, Time Dependent, Eigenvalue
- 已学习案例示例：Black-Scholes 方程, KdV 方程和孤子, 同频鼓, 基于扫描数据生成可供仿真的网格, 真空干燥, 衍射图样, 钢罐中的壳扩散, 锥形量子点

### 优化 (Optimization)
- 什么时候选：需求关注目标函数、约束、灵敏度、参数最优解、几何优化、材料优化或工况优化。
- 判断关键词：目标函数, 约束, 优化, 灵敏度, 参数扫描, 最优
- 常见研究类型：Optimization, Parametric Sweep, Stationary
- 已学习案例示例：STL导入教程

## 容易误判的地方

- 不要只看到“方程”就选 PDE；如果方程描述的是普通流体、传热或结构问题，优先用专用物理场接口。
- 不要只看到“热”就只选传热；焦耳热案例通常需要 Electric Currents 与 Heat Transfer 耦合。
- 几何教程、网格教程和导入教程可能没有真正的主物理场，应标记为 geometry/mesh workflow，而不是硬套物理场。
- 边界编号会随几何改变而变化，自动生成代码前必须复核选择集和边界 ID。
- 没有 CSV 的案例只能学习建模逻辑，不能说明数值代理模型已经训练完成。

## 已学习物理场频率

- Heat Transfer: 37
- Solid Mechanics: 19
- Laminar Flow: 19
- Coefficient Form PDE: 8
- Pressure Acoustics: 3
- Electric Currents: 2
- GlobalEquations: 2
- Optimization: 1
- LaplaceEquation: 1
- Electrostatics: 1
- ConductiveMedia: 1