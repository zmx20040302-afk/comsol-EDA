# Batch PDF Physics Judgement Learning Report 3

??????? COMSOL ????????????? PDF/????????????????????????????

| ?? | ?? | ?? | PDF | MATLAB | Java | MPH | ????? | ???? |
|---|---:|---:|---:|---:|---:|---:|---|---|
| 恒温器特性建模6.2 | modeling_logic_learning_ready | 3 | 0 | 1 | 1 | 1 | Heat Transfer | Transient |
| 化学蚀刻 | modeling_logic_learning_ready | 8 | 2 | 1 | 1 | 2 | Laminar Flow | Stationary |
| 积分-偏微分方程 | modeling_logic_learning_ready | 5 | 2 | 1 | 0 | 2 | Heat Transfer | Time Dependent |
| 基于扫描数据生成可供仿真的网格 | modeling_logic_learning_ready | 5 | 0 | 1 | 1 | 2 | Coefficient Form PDE | unknown |
| 激波管 | modeling_logic_learning_ready | 5 | 0 | 1 | 1 | 1 | Heat Transfer | Transient |
| 集群设置验证 | modeling_logic_learning_ready | 7 | 2 | 1 | 1 | 3 | Pressure Acoustics | Stationary |
| 借助变形几何接口修改导入的 CAD 几何 | modeling_logic_learning_ready | 3 | 0 | 1 | 1 | 1 | Heat Transfer | Stationary |
| 科赫雪花建模 | modeling_logic_learning_ready | 3 | 0 | 1 | 1 | 1 | needs_more_evidence | unknown |
| 馈线夹的变形 | modeling_logic_learning_ready | 6 | 2 | 1 | 1 | 2 | Solid Mechanics | Stationary |
| 两种载荷工况下的锥形悬臂梁 | modeling_logic_learning_ready | 6 | 2 | 1 | 1 | 2 | Solid Mechanics | Stationary |
| 轮辋几何虚拟操作 | modeling_logic_learning_ready | 6 | 2 | 1 | 1 | 2 | Solid Mechanics | unknown |
| 螺旋静态混合器 | modeling_logic_learning_ready | 8 | 2 | 1 | 1 | 3 | Laminar Flow | Stationary |
| 洛伦兹吸引子 | modeling_logic_learning_ready | 7 | 3 | 1 | 1 | 2 | Heat Transfer | Time Dependent |
| 曼德勃罗集和柏林噪声 | modeling_logic_learning_ready | 6 | 0 | 2 | 2 | 2 | needs_more_evidence | Stationary |
| 母线板焦耳热 | modeling_logic_learning_ready | 15 | 3 | 3 | 3 | 6 | Heat Transfer | Stationary |

## ???????

### 恒温器特性建模6.2
恒温器特性建模6.2 主要研究模型中的主要物理现象和输出量，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Heat Transfer，并采用 Transient 研究。

- ????: 若 PDF 的核心量和方程关键词指向 Heat Transfer，并且脚本/文本中出现同类接口，就把它作为主物理场；研究类型可由 Transient 确认。
- ??: 脚本/文本识别到的物理场: ht / HeatTransfer
- ??: 识别到的研究类型: std1 / time / Transient, std1

### 化学蚀刻
化学蚀刻 主要研究流动速度、压力或输运过程，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Laminar Flow，并采用 Stationary 研究。

- ????: 若 PDF 的核心量和方程关键词指向 Laminar Flow，并且脚本/文本中出现同类接口，就把它作为主物理场；研究类型可由 Stationary 确认。
- ??: PDF: 在 COMSOL Multiphysics 6.4 版本中创建
- ??: PDF: • 液体蚀刻剂与要蚀刻的材料发生反应。通常会发生还原 -氧化（氧化还原）反应，在
- ??: PDF: 反应中，材料先氧化后溶解。

### 积分-偏微分方程
积分-偏微分方程 主要研究温度场和热传递过程，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Heat Transfer，并采用 Time Dependent 研究。

- ????: 若 PDF 的核心量和方程关键词指向 Heat Transfer，并且脚本/文本中出现同类接口，就把它作为主物理场；研究类型可由 Time Dependent 确认。
- ??: PDF: 在 COMSOL Multiphysics 6.4 版本中创建
- ??: PDF: 积分 ‐ 偏微分方程 1
- ??: PDF: 2 | 积分 -偏微分方程

### 基于扫描数据生成可供仿真的网格
基于扫描数据生成可供仿真的网格 主要研究模型中的主要物理现象和输出量，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Coefficient Form PDE。

- ????: 若 PDF 强调自定义方程、薛定谔方程、能级、波函数或特征值，优先判断为系数形式 PDE；再用脚本中的 CoefficientFormPDE 校验。
- ??: 脚本/文本识别到的物理场: c / CoefficientFormPDE

### 激波管
激波管 主要研究流动速度、压力或输运过程，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Heat Transfer，并采用 Transient 研究。

- ????: 若 PDF 的核心量和方程关键词指向 Heat Transfer，并且脚本/文本中出现同类接口，就把它作为主物理场；研究类型可由 Transient 确认。
- ??: 脚本/文本识别到的物理场: wahw / WaveFormPDE
- ??: 识别到的研究类型: std1 / time / Transient, std1
- ??: 理论关键词: 流体, 传热

### 集群设置验证
集群设置验证 主要研究流动速度、压力或输运过程，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Pressure Acoustics，并采用 Stationary 研究。

- ????: 若 PDF 的核心量和方程关键词指向 Pressure Acoustics，并且脚本/文本中出现同类接口，就把它作为主物理场；研究类型可由 Stationary 确认。
- ??: PDF: Application created in COMSOL Multiphysics 6.4
- ??: PDF: of COMSOL Multiphysics
- ??: PDF: Update Geometry, Create

### 借助变形几何接口修改导入的 CAD 几何
借助变形几何接口修改导入的 CAD 几何 主要研究温度场和热传递过程，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Heat Transfer，并采用 Stationary 研究。

- ????: 若 PDF 的核心量和方程关键词指向 Heat Transfer，并且脚本/文本中出现同类接口，就把它作为主物理场；研究类型可由 Stationary 确认。
- ??: 脚本/文本识别到的物理场: solid / SolidMechanics
- ??: 识别到的研究类型: std1, Stationary
- ??: 理论关键词: 传热, 电磁, 多孔介质/裂隙

### 科赫雪花建模
科赫雪花建模 的 PDF 可用于理解案例目的、假设和操作步骤；当前证据还不足以唯一确定物理场，后续应结合 MATLAB/Java 中的 physics.create 或 COMSOL 模型树再确认。

- ????: 先根据 PDF 的核心物理量提出候选物理场，再用 MATLAB/Java/MPH 摘要中的 physics.create 做最终确认。

### 馈线夹的变形
馈线夹的变形 主要研究模型中的主要物理现象和输出量，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Solid Mechanics，并采用 Stationary 研究。

- ????: 若 PDF 的核心量和方程关键词指向 Solid Mechanics，并且脚本/文本中出现同类接口，就把它作为主物理场；研究类型可由 Stationary 确认。
- ??: PDF: 在 COMSOL Multiphysics 6.4 版本中创建
- ??: PDF: 由于载荷及几何均呈对称性，所以仅使用一半几何就可以执行完整的模型分析。但是，
- ??: PDF: 为了便于演示，本例还是模拟了整个几何。

### 两种载荷工况下的锥形悬臂梁
两种载荷工况下的锥形悬臂梁 主要研究流动速度、压力或输运过程，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Solid Mechanics，并采用 Stationary 研究。

- ????: 若 PDF 的核心量和方程关键词指向 Solid Mechanics，并且脚本/文本中出现同类接口，就把它作为主物理场；研究类型可由 Stationary 确认。
- ??: PDF: 在 COMSOL Multiphysics 6.4 版本中创建
- ??: PDF: 本示例取自 NAFEMS 基准集合 （参考资料 1） ，演示了如何对悬臂梁施加不同的边界
- ??: PDF: 在第一种情况中，沿 y 负方向施加重力载荷 mg，其重力加速度为 9.81 m/s2。左端边界

### 轮辋几何虚拟操作
轮辋几何虚拟操作 主要研究结构受力、变形或强度响应，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Solid Mechanics。

- ????: 若 PDF 的核心量和方程关键词指向 Solid Mechanics，并且脚本/文本中出现同类接口，就把它作为主物理场；研究类型需要继续从研究步骤确认。
- ??: PDF: 在 COMSOL Multiphysics 6.4 版本中创建
- ??: PDF: 轮辋几何清理
- ??: PDF: 2 | 轮辋几何清理

### 螺旋静态混合器
螺旋静态混合器 主要研究流动速度、压力或输运过程，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Laminar Flow，并采用 Stationary 研究。

- ????: 若 PDF 的核心量和方程关键词指向 Laminar Flow，并且脚本/文本中出现同类接口，就把它作为主物理场；研究类型可由 Stationary 确认。
- ??: PDF: 在 COMSOL Multiphysics 6.3 版本中创建
- ??: PDF: “螺旋静态混合器” App 的目的是演示零件与参数化几何的用法，此外，还可用于估计
- ??: PDF: 输入参数如下：

### 洛伦兹吸引子
洛伦兹吸引子 主要研究温度场和热传递过程，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Heat Transfer，并采用 Time Dependent 研究。

- ????: 若 PDF 的核心量和方程关键词指向 Heat Transfer，并且脚本/文本中出现同类接口，就把它作为主物理场；研究类型可由 Time Dependent 确认。
- ??: PDF: 在 COMSOL Multiphysics 6.4 版本中创建
- ??: PDF: 洛伦兹系统是由 Edward N. Lorenz 最先研究的一个常微分方程组（洛伦兹方程）。对于
- ??: PDF: 特定的参数值和初始条件，该常微分方程组具有混沌解，这些解就是所谓的奇异吸引

### 曼德勃罗集和柏林噪声
曼德勃罗集和柏林噪声 的 PDF 可用于理解案例目的、假设和操作步骤；当前证据还不足以唯一确定物理场，后续应结合 MATLAB/Java 中的 physics.create 或 COMSOL 模型树再确认。

- ????: 先根据 PDF 的核心物理量提出候选物理场，再用 MATLAB/Java/MPH 摘要中的 physics.create 做最终确认。
- ??: 识别到的研究类型: std1 / stat / Stationary, std1, Stationary

### 母线板焦耳热
母线板焦耳热 主要研究温度场和热传递过程，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Heat Transfer，并采用 Stationary 研究。

- ????: 若 PDF 的核心量和方程关键词指向 Heat Transfer，并且脚本/文本中出现同类接口，就把它作为主物理场；研究类型可由 Stationary 确认。
- ??: PDF: 在 COMSOL Multiphysics 6.3 版本中创建
- ??: PDF: 参数化母线板几何
- ??: PDF: 2 | 参数化母线板几何
