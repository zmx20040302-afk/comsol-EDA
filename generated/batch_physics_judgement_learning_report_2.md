# Batch PDF Physics Judgement Learning Report 2

??????? COMSOL ????????????? PDF/????????????????????????????

| ?? | ?? | ?? | PDF | MATLAB | Java | MPH | ????? | ???? |
|---|---:|---:|---:|---:|---:|---:|---|---|
| 点源实现 | modeling_logic_learning_ready | 6 | 2 | 1 | 1 | 2 | LaplaceEquation | Stationary |
| 电传感器 | modeling_logic_learning_ready | 6 | 2 | 1 | 1 | 2 | Electric Currents | Stationary |
| 电传感器批处理扫描 | modeling_logic_learning_ready | 3 | 0 | 1 | 1 | 1 | Electrostatics | Stationary |
| 电化学抛光 | modeling_logic_learning_ready | 6 | 2 | 1 | 1 | 2 | Solid Mechanics | Time Dependent |
| 电芯热失控 | modeling_logic_learning_ready | 3 | 0 | 1 | 1 | 1 | Heat Transfer | unknown |
| 调整非结构网格生成器的单元大小 | modeling_logic_learning_ready | 5 | 2 | 1 | 1 | 1 | Solid Mechanics | unknown |
| 顶盖驱动方腔流 | modeling_logic_learning_ready | 9 | 0 | 1 | 1 | 1 | Laminar Flow | Stationary |
| 多孔材料的有效扩散系数 | modeling_logic_learning_ready | 10 | 2 | 2 | 2 | 4 | Heat Transfer | Time Dependent |
| 房间的特征模态 | modeling_logic_learning_ready | 6 | 2 | 1 | 1 | 2 | Pressure Acoustics | Eigenvalue |
| 飞秒激光加热引起的超快传热 | modeling_logic_learning_ready | 3 | 0 | 1 | 1 | 1 | Heat Transfer | Transient |
| 钢罐中的壳扩散 | modeling_logic_learning_ready | 10 | 2 | 2 | 2 | 4 | Coefficient Form PDE | Stationary |
| 高尔夫球的轨迹 | modeling_logic_learning_ready | 3 | 0 | 1 | 1 | 1 | needs_more_evidence | unknown |
| 管式反应器代理模型 App | modeling_logic_learning_ready | 8 | 4 | 1 | 1 | 2 | Laminar Flow | Stationary |
| 硅晶片激光加热 | modeling_logic_learning_ready | 6 | 2 | 1 | 1 | 2 | Heat Transfer | Time Dependent |
| 含载荷突变的瞬时加热6.2 | modeling_logic_learning_ready | 3 | 0 | 1 | 1 | 1 | Heat Transfer | Transient |

## ???????

### 点源实现
点源实现 主要研究模型中的主要物理现象和输出量，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 LaplaceEquation，并采用 Stationary 研究。

- ????: 若 PDF 的核心量和方程关键词指向 LaplaceEquation，并且脚本/文本中出现同类接口，就把它作为主物理场；研究类型可由 Stationary 确认。
- ??: PDF: 在 COMSOL Multiphysics 6.4 版本中创建
- ??: PDF: 考虑点源在原点的单位圆上的泊松方程，正式的表达式为：
- ??: PDF: 其中，  是位于原点的 D irac  分布。 该边界值问题的精确解为 12logr，在原点处

### 电传感器
电传感器 主要研究流动速度、压力或输运过程，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Electric Currents，并采用 Stationary 研究。

- ????: 若 PDF 的核心量和方程关键词指向 Electric Currents，并且脚本/文本中出现同类接口，就把它作为主物理场；研究类型可由 Stationary 确认。
- ??: PDF: 在 COMSOL Multiphysics 6.4 版本中创建
- ??: PDF: 本模型显示如何根据盒内小物体的不同材料属性从盒外判断其形状及其在盒内的位置。
- ??: PDF: 在盒子边界施加一个势差，会产生一个表面电荷密度，其大小根据盒内介电常数分布

### 电传感器批处理扫描
电传感器批处理扫描 主要研究模型中的主要物理现象和输出量，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Electrostatics，并采用 Stationary 研究。

- ????: 若 PDF 的核心量和方程关键词指向 Electrostatics，并且脚本/文本中出现同类接口，就把它作为主物理场；研究类型可由 Stationary 确认。
- ??: 脚本/文本识别到的物理场: es / Electrostatics, Electrostatics
- ??: 识别到的研究类型: std1 / stat / Stationary, std1, Stationary
- ??: 理论关键词: 电磁

### 电化学抛光
电化学抛光 主要研究流动速度、压力或输运过程，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Solid Mechanics，并采用 Time Dependent 研究。

- ????: 若 PDF 的核心量和方程关键词指向 Solid Mechanics，并且脚本/文本中出现同类接口，就把它作为主物理场；研究类型可由 Time Dependent 确认。
- ??: PDF: 在 COMSOL Multiphysics 6.4 版本中创建
- ??: PDF: 本例阐述电化学抛光原理。简化的二维模型几何由两个电极及其中间的电解质域构成，
- ??: PDF: 起部分及周围电极材料的消耗情况。

### 电芯热失控
电芯热失控 主要研究温度场和热传递过程，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Heat Transfer。

- ????: 若 PDF 的核心量和方程关键词指向 Heat Transfer，并且脚本/文本中出现同类接口，就把它作为主物理场；研究类型需要继续从研究步骤确认。
- ??: 理论关键词: 传热, 电磁

### 调整非结构网格生成器的单元大小
调整非结构网格生成器的单元大小 主要研究结构受力、变形或强度响应，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Solid Mechanics。

- ????: 若 PDF 的核心量和方程关键词指向 Solid Mechanics，并且脚本/文本中出现同类接口，就把它作为主物理场；研究类型需要继续从研究步骤确认。
- ??: PDF: Model created in COMSOL Multiphysics 6.4
- ??: PDF: Unstructured Mesh Generator
- ??: PDF: 2 | ADJUSTING THE ELEMENT SIZE FOR THE UNSTRUCTURED MESH GENERATOR

### 顶盖驱动方腔流
顶盖驱动方腔流 主要研究流动速度、压力或输运过程，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Laminar Flow，并采用 Stationary 研究。

- ????: 若 PDF 的核心量和方程关键词指向 Laminar Flow，并且脚本/文本中出现同类接口，就把它作为主物理场；研究类型可由 Stationary 确认。
- ??: 脚本/文本识别到的物理场: spf / LaminarFlow
- ??: 识别到的研究类型: std1 / stat / Stationary, std1, Stationary
- ??: 理论关键词: 结构力学, 流体

### 多孔材料的有效扩散系数
多孔材料的有效扩散系数 主要研究流动速度、压力或输运过程，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Heat Transfer，并采用 Time Dependent 研究。

- ????: 若 PDF 的核心量和方程关键词指向 Heat Transfer，并且脚本/文本中出现同类接口，就把它作为主物理场；研究类型可由 Time Dependent 确认。
- ??: PDF: 在 COMSOL Multiphysics 6.4 版本中创建
- ??: PDF: 多孔材料的有效扩散系数
- ??: PDF: 2 | 多孔材料的有效扩散系数

### 房间的特征模态
房间的特征模态 主要研究量子能级或波函数分布，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Pressure Acoustics，并采用 Eigenvalue 研究。

- ????: 若 PDF 的核心量和方程关键词指向 Pressure Acoustics，并且脚本/文本中出现同类接口，就把它作为主物理场；研究类型可由 Eigenvalue 确认。
- ??: PDF: 在 COMSOL Multiphysics 6.4 版本中创建
- ??: PDF: 域方程
- ??: PDF: 自由空气中的声音传播通过波动方程来描述：

### 飞秒激光加热引起的超快传热
飞秒激光加热引起的超快传热 主要研究温度场和热传递过程，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Heat Transfer，并采用 Transient 研究。

- ????: 若 PDF 的核心量和方程关键词指向 Heat Transfer，并且脚本/文本中出现同类接口，就把它作为主物理场；研究类型可由 Transient 确认。
- ??: 脚本/文本识别到的物理场: ht / HeatTransfer, dode / DomainODE
- ??: 识别到的研究类型: std1 / time / Transient, std1
- ??: 理论关键词: 传热

### 钢罐中的壳扩散
钢罐中的壳扩散 主要研究温度场和热传递过程，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Coefficient Form PDE，并采用 Stationary 研究。

- ????: 若 PDF 强调自定义方程、薛定谔方程、能级、波函数或特征值，优先判断为系数形式 PDE；再用脚本中的 CoefficientFormPDE 校验。
- ??: PDF: 在 COMSOL Multiphysics 6.4 版本中创建
- ??: PDF: 因为长宽比非常大时，网格剖分及几何分析会出现问题。这一模型演示如何使用
- ??: PDF: COMSOL Multiphysics 中的切向导数变量 求解弯曲三维壳及二维边界上的偏微分方

### 高尔夫球的轨迹
高尔夫球的轨迹 的 PDF 可用于理解案例目的、假设和操作步骤；当前证据还不足以唯一确定物理场，后续应结合 MATLAB/Java 中的 physics.create 或 COMSOL 模型树再确认。

- ????: 先根据 PDF 的核心物理量提出候选物理场，再用 MATLAB/Java/MPH 摘要中的 physics.create 做最终确认。
- ??: 理论关键词: 流体

### 管式反应器代理模型 App
管式反应器代理模型 App 主要研究流动速度、压力或输运过程，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Laminar Flow，并采用 Stationary 研究。

- ????: 若 PDF 的核心量和方程关键词指向 Laminar Flow，并且脚本/文本中出现同类接口，就把它作为主物理场；研究类型可由 Stationary 确认。
- ??: PDF: 在 COMSOL Multiphysics 6.3 版本中创建
- ??: PDF: 代理模型训练过程基于对嵌入式管式反应器模型进行的大量参数化扫描的输出数据。
- ??: PDF: 为了优化参数化扫描的效率，我们采用了实验设计法。

### 硅晶片激光加热
硅晶片激光加热 主要研究温度场和热传递过程，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Heat Transfer，并采用 Time Dependent 研究。

- ????: 若 PDF 的核心量和方程关键词指向 Heat Transfer，并且脚本/文本中出现同类接口，就把它作为主物理场；研究类型可由 Time Dependent 确认。
- ??: PDF: 在 COMSOL Multiphysics 6.3 版本中创建
- ??: PDF: 在为晶片温度分布生成可视化结果时，可以在空间坐标系或材料坐标系中生成可视化
- ??: PDF: 案例库路径：COMSOL_Multiphysics/Heat_Transfer/laser_heating_wafer

### 含载荷突变的瞬时加热6.2
含载荷突变的瞬时加热6.2 主要研究温度场和热传递过程，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Heat Transfer，并采用 Transient 研究。

- ????: 若 PDF 的核心量和方程关键词指向 Heat Transfer，并且脚本/文本中出现同类接口，就把它作为主物理场；研究类型可由 Transient 确认。
- ??: 脚本/文本识别到的物理场: ht / HeatTransfer
- ??: 识别到的研究类型: std1 / time / Transient, std1
- ??: 理论关键词: 传热, 电磁, 多孔介质/裂隙
