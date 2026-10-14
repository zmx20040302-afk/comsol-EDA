# COMSOL不同围压条件下单孔水力压裂裂纹的拓展规律研究

- Source: `D:\桌面\COMSOL不同围压条件下单孔水力压裂裂纹的拓展规律研究.docx`
- Paragraphs: 23

## Article Summary

文章围绕煤层超高压水力压裂数值模拟，研究不同地应力条件、主应力方向、煤层非均匀性和天然裂缝对单孔裂纹起裂压力、扩展方向、损伤演化和裂缝长度的影响。

## Modeling Requirement

Build a COMSOL hydraulic fracturing model for a single borehole under different confining stress conditions. 中文需求关键词：水力压裂 单孔 围压 主应力 天然裂缝 煤层 岩石裂隙流 多孔介质 裂缝拓展 损伤演化。 Use article parameters: square_side=300[mm] borehole_diameter=15[mm] stress_ratio_range=1.5~2.0 initial_pressure=0.1[MPa] mean_elastic_modulus=35.1[GPa] mean_compressive_strength=152[MPa] principal_stress_direction_135=135[deg] principal_stress_direction_180=180[deg] principal_stress_direction_90=90[deg]. Include features: 2D square domain central borehole natural fracture or weak-plane features coal/rock medium heterogeneous elastic modulus heterogeneous tensile/compressive strength Weibull random field distribution solid mechanics damage evolution pore/fluid pressure loading hydraulic fracture propagation outer boundary in-situ stress loading symmetric roller/fixed displacement support borehole injection pressure free triangular mesh local refinement near borehole and natural fractures time-dependent pressure/damage evolution parametric sweep over stress ratio and stress direction damage length vs time pressure field fracture path initiation pressure stress distribution fracture deflection and branching under natural fractures.

## Extracted Parameters

- `square_side` = `300[mm]` (geometry length)
- `borehole_diameter` = `15[mm]` (borehole diameter)
- `stress_ratio_range` = `1.5~2.0` (principal stress ratio range)
- `initial_pressure` = `0.1[MPa]` (initial pressure)
- `mean_elastic_modulus` = `35.1[GPa]` (Weibull mean elastic modulus)
- `mean_compressive_strength` = `152[MPa]` (Weibull mean compressive strength)
- `principal_stress_direction_135` = `135[deg]` (stress direction case)
- `principal_stress_direction_180` = `180[deg]` (stress direction case)
- `principal_stress_direction_90` = `90[deg]` (stress direction case)

## Model Features

- geometry: 2D square domain, central borehole, natural fracture or weak-plane features
- materials: coal/rock medium, heterogeneous elastic modulus, heterogeneous tensile/compressive strength, Weibull random field distribution
- physics: solid mechanics damage evolution, pore/fluid pressure loading, hydraulic fracture propagation
- boundary_conditions: outer boundary in-situ stress loading, symmetric roller/fixed displacement support, borehole injection pressure
- mesh: free triangular mesh, local refinement near borehole and natural fractures
- studies: time-dependent pressure/damage evolution, parametric sweep over stress ratio and stress direction
- outputs: damage length vs time, pressure field, fracture path, initiation pressure, stress distribution, fracture deflection and branching under natural fractures

## Correction Strategy

- 优先使用文章参数作为基准约束，而不是套用通用热学或结构默认值。
- Correct geometry to a 300 mm square domain with a 15 mm borehole and optional natural-fracture weak planes.
- Correct loads by sweeping principal stress ratio from 1.5 to 2.0 and stress directions such as 90, 135, and 180 degrees.
- Correct material definition by adding Weibull-distributed elastic modulus and strength rather than a single homogeneous material.
- Correct mesh by refining near the borehole, expected crack tips, and natural fractures.
- Correct validation outputs to compare damage length over time, pressure field, crack morphology, and initiation pressure against article/field observations.
- Add a measurement-correction loop: compare simulated fracture/stress response with measured data and update fracture orientation, density, and weak-plane parameters.

## Memory-Assisted COMSOL Construction Plan

### Retrieved Cases
- `COMSOL不同围压条件下单孔水力压裂裂纹的拓展规律研究` score=67.81339611063653
- `岩石裂隙流` score=26.01324490029408
- `带轮应力` score=7.636994336101661
- `扳手的应力和应变` score=6.437432590799961
- `已验证：二维热应力矩形模板` score=6.349389079621698
- `如何生成随机非均匀材料数据6.2` score=5.4692651680936
- `受载弹簧 - 使用全局方程满足约束条件` score=5.0055731996703
- `COMSOL 物理场类型与选择指南` score=4.912889112810202

### Construction Steps
- Clarify model objective, dimensionality, input parameters, outputs, and validation targets.
- 查看检索到的相似案例，并复用其参数命名、几何序列和 LiveLink API 调用模式。
- Choose geometry strategy: reuse similar case script, import CAD, or generate parametric geometry.
- Define materials, units, selections, and reusable parameter groups.
- Add physics interfaces and boundary/initial conditions.
- Create mesh and study sequence, then solve a baseline model.
- Export derived values and plots for validation.

### Article-Specific Modifications
- 优先使用文章参数作为基准约束，而不是套用通用热学或结构默认值。
- Correct geometry to a 300 mm square domain with a 15 mm borehole and optional natural-fracture weak planes.
- Correct loads by sweeping principal stress ratio from 1.5 to 2.0 and stress directions such as 90, 135, and 180 degrees.
- Correct material definition by adding Weibull-distributed elastic modulus and strength rather than a single homogeneous material.
- Correct mesh by refining near the borehole, expected crack tips, and natural fractures.
- Correct validation outputs to compare damage length over time, pressure field, crack morphology, and initiation pressure against article/field observations.
- Add a measurement-correction loop: compare simulated fracture/stress response with measured data and update fracture orientation, density, and weak-plane parameters.

### Validation Outputs
- damage length vs time
- pressure field
- fracture path
- initiation pressure
- stress distribution
- fracture deflection and branching under natural fractures
