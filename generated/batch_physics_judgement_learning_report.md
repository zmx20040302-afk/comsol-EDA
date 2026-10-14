# Batch PDF Physics Judgement Learning Report

??????? COMSOL ?????????????? PDF/????????????????????????????

| ?? | ?? | ?? | PDF | MATLAB | Java | MPH | ????? | ???? |
|---|---:|---:|---:|---:|---:|---:|---|---|
| “图像到曲线”插件示例6.2 | needs_comsol_sweep_csv | 2 | 0 | 0 | 0 | 2 | needs_more_evidence | unknown |
| App 中用户定义的许可协议 | modeling_logic_learning_ready | 2 | 0 | 0 | 1 | 1 | Solid Mechanics | Eigenfrequency |
| Black-Scholes 方程 | needs_comsol_sweep_csv | 4 | 2 | 0 | 0 | 2 | Coefficient Form PDE | Time Dependent |
| Blasius 边界层 | needs_comsol_sweep_csv | 4 | 2 | 0 | 0 | 2 | Laminar Flow | Stationary |
| KdV 方程和孤子 | needs_comsol_sweep_csv | 4 | 2 | 0 | 0 | 2 | Coefficient Form PDE | Time Dependent |
| STL导入教程 | needs_comsol_sweep_csv | 11 | 2 | 0 | 0 | 5 | Optimization | Parametric Sweep |
| 安装验证 | needs_comsol_sweep_csv | 4 | 2 | 0 | 0 | 2 | Heat Transfer | Optimization |
| 扳手的应力和应变 | modeling_logic_learning_ready | 5 | 2 | 1 | 0 | 2 | Solid Mechanics | Stationary |
| 薄膜电阻 | needs_comsol_sweep_csv | 4 | 2 | 0 | 0 | 2 | Heat Transfer | Stationary |
| 边界网格划分教程 | needs_comsol_sweep_csv | 11 | 4 | 0 | 0 | 7 | Laminar Flow | unknown |
| 变形曲面的泽尼克多项式拟合 | modeling_logic_learning_ready | 3 | 0 | 1 | 1 | 1 | Solid Mechanics | Stationary |
| 沉降 App（考虑颗粒大小分布） | modeling_logic_learning_ready | 4 | 1 | 1 | 1 | 1 | Heat Transfer | Parametric Sweep |
| 承受动载荷的梁 | modeling_logic_learning_ready | 8 | 2 | 1 | 1 | 2 | Solid Mechanics | Eigenfrequency |
| 传递和吸附 | modeling_logic_learning_ready | 8 | 2 | 1 | 1 | 2 | Laminar Flow | Stationary |
| 传输线参数计算器 | modeling_logic_learning_ready | 9 | 2 | 2 | 2 | 3 | Solid Mechanics | Frequency Domain |
| 创建随机几何 | modeling_logic_learning_ready | 3 | 0 | 1 | 1 | 1 | needs_more_evidence | unknown |
| 磁滞作用下的相变建模 | modeling_logic_learning_ready | 6 | 0 | 2 | 2 | 2 | Heat Transfer | Stationary |
| 带非等温冷却夹套的管式反应器 | modeling_logic_learning_ready | 13 | 4 | 1 | 1 | 3 | Laminar Flow | Stationary |
| 带轮应力 | modeling_logic_learning_ready | 10 | 2 | 1 | 1 | 2 | Heat Transfer | Stationary |
| 灯泡几何 | modeling_logic_learning_ready | 5 | 1 | 1 | 1 | 2 | Heat Transfer | unknown |
| 递归和递归定义的几何对象 | modeling_logic_learning_ready | 6 | 0 | 2 | 2 | 2 | needs_more_evidence | unknown |

## ???????

### “图像到曲线”插件示例6.2
“图像到曲线”插件示例6.2 的 PDF 可用于理解案例目的、假设和操作步骤；当前证据还不足以唯一确定物理场，后续应结合 MATLAB/Java 中的 physics.create 或 COMSOL 模型树再确认。

- ????: 先根据 PDF 的核心物理量提出候选物理场，再用 MATLAB/Java/MPH 摘要中的 physics.create 做最终确认。

### App 中用户定义的许可协议
App 中用户定义的许可协议 主要研究声压、模态或频域声学响应，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Solid Mechanics，并采用 Eigenfrequency 研究。

- ????: 若 PDF 的核心量和方程关键词指向 Solid Mechanics，并且脚本/文本中出现同类接口，就把它作为主物理场；研究类型可由 Eigenfrequency 确认。
- ??: 脚本/文本识别到的物理场: solid / SolidMechanics
- ??: 识别到的研究类型: std1 / eig / Eigenfrequency, std1, Eigenfrequency
- ??: 理论关键词: 声学

### Black-Scholes 方程
Black-Scholes 方程 主要研究温度场和热传递过程，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Coefficient Form PDE，并采用 Time Dependent 研究。

- ????: 若 PDF 强调自定义方程、薛定谔方程、能级、波函数或特征值，优先判断为系数形式 PDE；再用脚本中的 CoefficientFormPDE 校验。
- ??: PDF: 在 COMSOL Multiphysics 6.4 版本中创建
- ??: PDF: Black ‐Scholes 方程
- ??: PDF: 2 | BLACK-SCHOLES 方程

### Blasius 边界层
Blasius 边界层 主要研究流动速度、压力或输运过程，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Laminar Flow，并采用 Stationary 研究。

- ????: 若 PDF 的核心量和方程关键词指向 Laminar Flow，并且脚本/文本中出现同类接口，就把它作为主物理场；研究类型可由 Stationary 确认。
- ??: PDF: 在 COMSOL Multiphysics 6.4 版本中创建
- ??: PDF: Blasius 边界层
- ??: PDF: 2 | BLASIUS 边界层

### KdV 方程和孤子
KdV 方程和孤子 主要研究流动速度、压力或输运过程，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Coefficient Form PDE，并采用 Time Dependent 研究。

- ????: 若 PDF 强调自定义方程、薛定谔方程、能级、波函数或特征值，优先判断为系数形式 PDE；再用脚本中的 CoefficientFormPDE 校验。
- ??: PDF: 在 COMSOL Multiphysics 6.4 版本中创建
- ??: PDF: KdV 方程和孤子
- ??: PDF: 2 | KDV 方程和孤子

### STL导入教程
STL导入教程 主要研究模型中的主要物理现象和输出量，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Optimization，并采用 Parametric Sweep 研究。

- ????: 若 PDF 的核心量和方程关键词指向 Optimization，并且脚本/文本中出现同类接口，就把它作为主物理场；研究类型可由 Parametric Sweep 确认。
- ??: PDF: Created in COMSOL Multiphysics 6.3
- ??: PDF: 1. The STL geometry is provided courtesy of Mark Yeoman, Continuum Blue, UK.
- ??: PDF: When working with imported STL meshes, there is often a need to repair and edit the

### 安装验证
安装验证 主要研究流动速度、压力或输运过程，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Heat Transfer，并采用 Optimization 研究。

- ????: 若 PDF 的核心量和方程关键词指向 Heat Transfer，并且脚本/文本中出现同类接口，就把它作为主物理场；研究类型可由 Optimization 确认。
- ??: PDF: 在 COMSOL Multiphysics 6.3 版本中创建
- ??: PDF: “安装验证”App 可用于帮助验证您的 COMSOL Multiphysics® 或 COMSOL Server™ 安
- ??: PDF: 要运行“安装验证” App，首先启动 COMSOL Multiphysics，然后，从文件菜单中选择

### 扳手的应力和应变
扳手的应力和应变 主要研究结构受力、变形或强度响应，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Solid Mechanics，并采用 Stationary 研究。

- ????: 若 PDF 的核心量和方程关键词指向 Solid Mechanics，并且脚本/文本中出现同类接口，就把它作为主物理场；研究类型可由 Stationary 确认。
- ??: PDF: Created in COMSOL Multiphysics 6.3
- ??: PDF: analysis in COMSOL Multiphysics.
- ??: PDF: The model geometry is shown below.

### 薄膜电阻
薄膜电阻 主要研究温度场和热传递过程，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Heat Transfer，并采用 Stationary 研究。

- ????: 若 PDF 的核心量和方程关键词指向 Heat Transfer，并且脚本/文本中出现同类接口，就把它作为主物理场；研究类型可由 Stationary 确认。
- ??: PDF: 在 COMSOL Multiphysics 6.4 版本中创建
- ??: PDF: 在模拟薄层中的传导或物质扩散时，常常存在着不同域的几何尺寸之间差异很大的情
- ??: PDF: 图 1：实际模型的几何 （左图）和使用薄层近似的几何 （右图） 。电流由底部边界流

### 边界网格划分教程
边界网格划分教程 主要研究流动速度、压力或输运过程，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Laminar Flow。

- ????: 若 PDF 的核心量和方程关键词指向 Laminar Flow，并且脚本/文本中出现同类接口，就把它作为主物理场；研究类型需要继续从研究步骤确认。
- ??: PDF: 在 COMSOL Multiphysics 6.3 版本中创建
- ??: PDF: 边界层网格划分 - 探索设置
- ??: PDF: 边界层网格是一种结构化的各向异性网格，其中网格单元具有高纵横比。例如，在接

### 变形曲面的泽尼克多项式拟合
变形曲面的泽尼克多项式拟合 主要研究模型中的主要物理现象和输出量，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Solid Mechanics，并采用 Stationary 研究。

- ????: 若 PDF 的核心量和方程关键词指向 Solid Mechanics，并且脚本/文本中出现同类接口，就把它作为主物理场；研究类型可由 Stationary 确认。
- ??: 脚本/文本识别到的物理场: solid / SolidMechanics
- ??: 识别到的研究类型: std1 / stat / Stationary, std1, Stationary

### 沉降 App（考虑颗粒大小分布）
沉降 App（考虑颗粒大小分布） 主要研究温度场和热传递过程，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Heat Transfer，并采用 Parametric Sweep 研究。

- ????: 若 PDF 的核心量和方程关键词指向 Heat Transfer，并且脚本/文本中出现同类接口，就把它作为主物理场；研究类型可由 Parametric Sweep 确认。
- ??: PDF: COMSOL Multiphysics® is a physics simulation software product developed by COMSOL AB. There is no
- ??: PDF: 5. Geometrical parametric sweep
- ??: PDF: Save As : Click this button if you want to generate a COMSOL Multiphysics file (You will need a license to

### 承受动载荷的梁
承受动载荷的梁 主要研究流动速度、压力或输运过程，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Solid Mechanics，并采用 Eigenfrequency 研究。

- ????: 若 PDF 的核心量和方程关键词指向 Solid Mechanics，并且脚本/文本中出现同类接口，就把它作为主物理场；研究类型可由 Eigenfrequency 确认。
- ??: PDF: 在 COMSOL Multiphysics 6.4 版本中创建
- ??: PDF: 模型已参数化，因此很容易改变载荷脉冲的速度或脉冲间距等参数。模型用于表明，
- ??: PDF: 使用 COMSOL Multiphysics，可以在载荷及边界条件的输入字段中输入解析表达式并使

### 传递和吸附
传递和吸附 主要研究流动速度、压力或输运过程，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Laminar Flow，并采用 Stationary 研究。

- ????: 若 PDF 的核心量和方程关键词指向 Laminar Flow，并且脚本/文本中出现同类接口，就把它作为主物理场；研究类型可由 Stationary 确认。
- ??: PDF: 在 COMSOL Multiphysics 6.4 版本中创建
- ??: PDF: 本例演示如何在 COMSOL Multiphysics 中以全耦合的方式对不同维度 （本例中是二维
- ??: PDF: 可采用的第一个近似处理是将三维几何简化为二维，当沿域深度方向的浓度变化非常

### 传输线参数计算器
传输线参数计算器 主要研究电流、电势或电磁场分布，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Solid Mechanics，并采用 Frequency Domain 研究。

- ????: 若 PDF 的核心量和方程关键词指向 Solid Mechanics，并且脚本/文本中出现同类接口，就把它作为主物理场；研究类型可由 Frequency Domain 确认。
- ??: PDF: 在 COMSOL Multiphysics 6.3 版本中创建
- ??: PDF: 电磁场沿传输线传播，近似为横电磁 (TEM) 波。传输线上电势的一维频域波动方程可
- ??: PDF: 电流，也可以推导出类似的波动方程。下面是由负载阻抗端接的传输线的等效电路模

### 创建随机几何
创建随机几何 的 PDF 可用于理解案例目的、假设和操作步骤；当前证据还不足以唯一确定物理场，后续应结合 MATLAB/Java 中的 physics.create 或 COMSOL 模型树再确认。

- ????: 先根据 PDF 的核心物理量提出候选物理场，再用 MATLAB/Java/MPH 摘要中的 physics.create 做最终确认。

### 磁滞作用下的相变建模
磁滞作用下的相变建模 主要研究温度场和热传递过程，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Heat Transfer，并采用 Stationary 研究。

- ????: 若 PDF 的核心量和方程关键词指向 Heat Transfer，并且脚本/文本中出现同类接口，就把它作为主物理场；研究类型可由 Stationary 确认。
- ??: 脚本/文本识别到的物理场: ht / HeatTransfer
- ??: 识别到的研究类型: std1 / stat / Stationary, std1, Stationary
- ??: 理论关键词: 传热, 电磁, 多孔介质/裂隙

### 带非等温冷却夹套的管式反应器
带非等温冷却夹套的管式反应器 主要研究流动速度、压力或输运过程，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Laminar Flow，并采用 Stationary 研究。

- ????: 若 PDF 的核心量和方程关键词指向 Laminar Flow，并且脚本/文本中出现同类接口，就把它作为主物理场；研究类型可由 Stationary 确认。
- ??: PDF: 在 COMSOL Multiphysics 6.3 版本中创建
- ??: PDF: 几何
- ??: PDF: 图 1 显示模型几何。我们假定绕中心轴角方向的变化忽略不计，因此模型可以视为轴

### 带轮应力
带轮应力 主要研究结构受力、变形或强度响应，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Heat Transfer，并采用 Stationary 研究。

- ????: 若 PDF 的核心量和方程关键词指向 Heat Transfer，并且脚本/文本中出现同类接口，就把它作为主物理场；研究类型可由 Stationary 确认。
- ??: PDF: 在 COMSOL Multiphysics 6.4 版本中创建
- ??: PDF: 盘方程 （在德语文献中称为 Eytelwein 公式）表示：
- ??: PDF: 其中，  是摩擦系数，  是传动带和带轮之间的接触角。为使此方程有效，须满足传

### 灯泡几何
灯泡几何 主要研究温度场和热传递过程，PDF 用来说明问题目标、基本假设和求解对象；从核心内容看，建模时应优先选择 Heat Transfer。

- ????: 若 PDF 的核心量和方程关键词指向 Heat Transfer，并且脚本/文本中出现同类接口，就把它作为主物理场；研究类型需要继续从研究步骤确认。
- ??: PDF: Model created in COMSOL Multiphysics 6.4
- ??: PDF: Light Bulb Geometry
- ??: PDF: 2 | LIGHT BULB GEOMETRY

### 递归和递归定义的几何对象
递归和递归定义的几何对象 的 PDF 可用于理解案例目的、假设和操作步骤；当前证据还不足以唯一确定物理场，后续应结合 MATLAB/Java 中的 physics.create 或 COMSOL 模型树再确认。

- ????: 先根据 PDF 的核心物理量提出候选物理场，再用 MATLAB/Java/MPH 摘要中的 physics.create 做最终确认。
