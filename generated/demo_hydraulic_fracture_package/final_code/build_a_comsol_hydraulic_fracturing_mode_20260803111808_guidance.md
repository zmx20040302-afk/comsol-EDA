# COMSOL 建模代码与理论指导

- 需求: Build a COMSOL hydraulic fracturing model for a single borehole under different confining stress conditions. 中文需求关键词：水力压裂 单孔 围压 主应力 天然裂缝 煤层 岩石裂隙流 多孔介质 裂缝拓展 损伤演化。 Use article parameters: square_side=300[mm] borehole_diameter=15[mm] stress_ratio_range=1.5~2.0 initial_pressure=0.1[MPa] mean_elastic_modulus=35.1[GPa] mean_compressive_strength=152[MPa] principal_stress_direction_135=135[deg] principal_stress_direction_180=180[deg] principal_stress_direction_90=90[deg]. Include features: 2D square domain central borehole natural fracture or weak-plane features coal/rock medium heterogeneous elastic modulus heterogeneous tensile/compressive strength Weibull random field distribution solid mechanics damage evolution pore/fluid pressure loading hydraulic fracture propagation outer boundary in-situ stress loading symmetric roller/fixed displacement support borehole injection pressure free triangular mesh local refinement near borehole and natural fractures time-dependent pressure/damage evolution parametric sweep over stress ratio and stress direction damage length vs time pressure field fracture path initiation pressure stress distribution fracture deflection and branching under natural fractures.

已批准建模决策：
[选择物理场]
选择结果：固体力学 + 达西定律/多孔介质流，必要时加入裂缝扩展模型
COMSOL 接口建议：Solid Mechanics + Darcy's Law 或 Porous Media Flow；若要模拟裂纹起裂和扩展，需要结合 Fracture Flow、Phase Field 或 Cohesive Zone 等裂缝描述方法
理论依据：主要物理量/未知量包括岩体位移和应力、孔隙压力以及裂缝扩展状态。地应力和煤层力学条件由固体力学平衡方程控制，压裂液压力和渗流由达西定律或多孔介质流控制，裂纹扩展需要断裂准则或相场/黏聚区模型描述。
复合场检查：该需求应按复合场判断，优先考虑：孔压-应力-裂缝耦合 + 流固耦合 + 热-结构耦合 / 热应力 + 非等温流动。 主物理场=Solid Mechanics；耦合物理场=Darcy's Law / Porous Media Flow、Fracture Flow、Phase Field or Cohesive Zone、Solid Mechanics、Moving Mesh、Heat Transfer in Fluids；多物理场节点=Poroelasticity、Fracture flow-stress coupling、Fluid-Structure Interaction、Thermal Expansion、Nonisothermal Flow；耦合变量=岩体位移/应力、孔隙压力、渗流速度、裂缝开度/损伤变量、注入压力、流体压力/剪切力、结构位移、移动网格。
边界条件判断：需要设置原位地应力或围压、钻孔内压/注入压力、外边界位移或应力约束、煤层渗透率/孔隙率，以及裂缝面压力或流体泄漏条件。
边界条件知识库：按当前需求，边界条件应优先按“水力压裂/孔压-应力耦合 + 固体力学 + 流体流动”来判断。 建议边界类型：外边界原位地应力、围压或位移约束、钻孔内壁注入压力或流量、煤层/岩体渗透率、孔隙率和初始孔隙压力、裂缝面压力、泄漏或损伤/相场边界、固定约束、位移约束。
初始条件建议：初始孔隙压力、初始地应力、初始位移为零或原位平衡状态、初始裂缝/损伤变量、初始位移、初始速度。
需要确认：确认是只模拟孔压-应力响应，还是要模拟真实裂纹扩展；若要裂纹路径，需要补充断裂能、抗拉强度、损伤准则或相场参数。
相似案例参考：COMSOL不同围压条件下单孔水力压裂裂纹的拓展规律研究, 岩石裂隙流, 带轮应力, 扳手的应力和应变, 已验证：二维热应力矩形模板。
用户确认：论文对象为固体-渗流-裂缝耦合；裂缝准则作为后续校准项。
[确定材料]
材料与物性结论：材料与物性参数应优先按“结构力学材料 + 流体材料”配置。 Recognized material: Water.
已识别材料配置：Water: density=998[kg/m^3], dynamicviscosity=1e-3[Pa*s], thermalconductivity=0.6[W/(m*K)], heatcapacity=4182[J/(kg*K)]
必填物性参数：密度(rho, kg/m^3)；弹性模量(E, Pa)；泊松比(nu, 1)；动力黏度(mu, Pa*s)
可选/耦合物性：抗拉强度(ft)；抗压强度(fc)；断裂能(Gc)；比热容(Cp_f)；导热系数(k_f)；扩散系数(D)
温度/频率/方向依赖：弹性模量和强度可为空间随机场；复合材料或层状材料需要方向相关弹性矩阵。；黏度和密度可能随温度、浓度或压力变化；气体可压缩时需要状态方程。
待补充物性：泊松比
MATLAB 材料设置应使用 material.propertyGroup('def').set(...)，并先用 model.param.set(...) 定义带单位参数。
用户确认：采用文章给出的煤岩非均质参数与水的密度、黏度；断裂参数待试验标定。
[建模数据与结构]
几何与参数结论：几何与参数应优先按“水力压裂单孔/裂隙几何 + 结构力学几何与参数”组织。
维度建议：2D 平面应变优先；需要厚度效应或三维钻孔时再升为 3D
几何要点：矩形或正方形煤/岩体代表试验工作面或局部煤层；中心或指定位置圆形钻孔；可选预制裂缝、弱面或自然裂隙线；外边界用于施加地应力、围压或位移约束；受力实体或梁/板结构；固定端
关键参数：square_side=300[mm], borehole_diameter=15[mm], stress_ratio_range=1.5~2.0, initial_pressure=0.1[MPa], mean_elastic_modulus=35.1[GPa], mean_compressive_strength=152[MPa], principal_stress_direction_135=135[deg], principal_stress_direction_180=180[deg]
选择集建议：命名钻孔边界；命名外边界四边；命名裂缝/弱面边界；命名煤岩基体域；命名固定约束边界；命名载荷边界
后续扫描变量：pinj、sigH、sigh、k_perm、rb、F0
用户确认：采用二维平面应变、300 mm 正方形与15 mm中心孔。
[网格策略]
Start with a controlled mesh size parameter, then add local refinement where gradients are expected.
Plan at least one mesh refinement comparison before parameter sweeps.
用户确认：在钻孔、预期裂缝尖端和天然裂缝附近局部加密。
[求解分步]
Run a baseline solve before adding parameter sweeps or surrogate-training exports.
Use the study path suggested by memory: Baseline solve, Mesh refinement check, Parameter sweep, Result validation, Stress/displacement safety check, Pressure drop and flow uniformity analysis.
用户确认：先基准稳态地应力，再进行注入压力时变/参数扫描。
[结果与导出]
Export derived values as CSV columns for validation and surrogate training.
Candidate outputs: max_displacement, max_von_mises_stress, reaction_force, pressure_drop, max_velocity, flow_rate.
用户确认：导出孔压、损伤变量、裂缝长度、起裂压力和应力场 CSV。
- MATLAB 输出: `generated\demo_hydraulic_fracture_package\final_code\build_a_comsol_hydraulic_fracturing_mode_20260803111808.m`
- Java 输出: `generated\demo_hydraulic_fracture_package\final_code\BuildAComsolHydraulicFracturingMode20260803111808.java`

## 理论与建模指导

- 建模顺序应保持为：参数 -> 几何 -> 选择集 -> 材料 -> 物理场 -> 边界/初始条件 -> 网格 -> 研究/求解 -> 结果导出。
- 生成代码中的边界编号和选择集必须在 COMSOL 中复核；学习库只能提供案例模式和 API 结构，不能替代几何实体编号确认。
- 几何模型与参数指导：几何与参数应优先按“水力压裂单孔/裂隙几何 + 结构力学几何与参数”组织。 2D 平面应变优先；需要厚度效应或三维钻孔时再升为 3D
- 几何要点：矩形或正方形煤/岩体代表试验工作面或局部煤层；中心或指定位置圆形钻孔；可选预制裂缝、弱面或自然裂隙线；外边界用于施加地应力、围压或位移约束；受力实体或梁/板结构；固定端。
- 关键参数建议：square_side=300[mm]（COMSOL不同围压条件下单孔水力压裂裂纹的拓展规律研究）；borehole_diameter=15[mm]（COMSOL不同围压条件下单孔水力压裂裂纹的拓展规律研究）；stress_ratio_range=1.5~2.0（COMSOL不同围压条件下单孔水力压裂裂纹的拓展规律研究）；initial_pressure=0.1[MPa]（COMSOL不同围压条件下单孔水力压裂裂纹的拓展规律研究）；mean_elastic_modulus=35.1[GPa]（COMSOL不同围压条件下单孔水力压裂裂纹的拓展规律研究）；mean_compressive_strength=152[MPa]（COMSOL不同围压条件下单孔水力压裂裂纹的拓展规律研究）；principal_stress_direction_135=135[deg]（COMSOL不同围压条件下单孔水力压裂裂纹的拓展规律研究）；principal_stress_direction_180=180[deg]（COMSOL不同围压条件下单孔水力压裂裂纹的拓展规律研究）。
- 选择集与扫描建议：选择集=命名钻孔边界；命名外边界四边；命名裂缝/弱面边界；命名煤岩基体域；命名固定约束边界；命名载荷边界；扫描变量=pinj、sigH、sigh、k_perm、rb、F0。
- 材料与物性参数指导：材料与物性参数应优先按“结构力学材料 + 流体材料 + 传热材料”配置。 Recognized material: Water.
- 必填物性：密度(rho, kg/m^3)；弹性模量(E, Pa)；泊松比(nu, 1)；动力黏度(mu, Pa*s)；导热系数(k, W/(m*K))；比热容(Cp, J/(kg*K))。
- 物性变化关系：弹性模量和强度可为空间随机场；复合材料或层状材料需要方向相关弹性矩阵。；黏度和密度可能随温度、浓度或压力变化；气体可压缩时需要状态方程。；导热系数、比热和密度可随温度变化；复合材料导热系数可能随方向变化。。
- 边界条件与初始条件指导：按当前需求，边界条件应优先按“水力压裂/孔压-应力耦合 + 固体力学 + 流体流动”来判断。
- 建议边界：外边界原位地应力、围压或位移约束；钻孔内壁注入压力或流量；煤层/岩体渗透率、孔隙率和初始孔隙压力；裂缝面压力、泄漏或损伤/相场边界；固定约束；位移约束；边界载荷/压力；接触边界。
- 建议初始条件：初始孔隙压力；初始地应力；初始位移为零或原位平衡状态；初始裂缝/损伤变量；初始位移；初始速度。
- 物理场复合场检查：该需求应按复合场判断，优先考虑：孔压-应力-裂缝耦合 + 热-结构耦合 / 热应力 + 非等温流动 + 流固耦合。 主物理场=Solid Mechanics；耦合物理场=Darcy's Law / Porous Media Flow、Fracture Flow、Phase Field or Cohesive Zone、Solid Mechanics、Heat Transfer in Fluids、Moving Mesh；多物理场节点=Poroelasticity、Fracture flow-stress coupling、Thermal Expansion、Nonisothermal Flow、Fluid-Structure Interaction。
- 传热模型需要确认热源、温度边界、热通量或对流换热条件，并检查材料的导热系数、密度和热容。
- 流体模型需要确认入口、出口、壁面和压力条件；微流动案例通常还要同时检查稀物质传递或扩散系数。
- 结构力学模型需要确认固定约束、载荷、接触/对称条件和材料弹性参数；特征频率问题应使用 Eigenfrequency 研究。
- 已学习案例中的理论关键词包括：文章围绕煤层超高，压水力压裂数值模，研究不同地应力条，主应力方向，煤层非均匀性和天，然裂缝对单孔裂纹，起裂压力，扩展方向，损伤演化和裂缝长，度的影响，热传导，热膨胀。
- 本次生成优先参考以下已学习案例：COMSOL不同围压条件下单孔水力压裂裂纹的拓展规律研究，已验证：二维热应力矩形模板，扳手的应力和应变，已验证：二维固体力学矩形受载模板，岩石裂隙流。

## 已学习案例证据

- `COMSOL不同围压条件下单孔水力压裂裂纹的拓展规律研究`: 内容证据 0 条；物理场=solid mechanics damage evolution, pore/fluid pressure loading, hydraulic fracture propagation
- `已验证：二维热应力矩形模板`: 内容证据 0 条；物理场=HeatTransfer, SolidMechanics, ThermalExpansion
- `扳手的应力和应变`: 内容证据 8 条；物理场=solid / SolidMechanics
- `已验证：二维固体力学矩形受载模板`: 内容证据 0 条；物理场=SolidMechanics
- `岩石裂隙流`: 内容证据 16 条；物理场=cdeq / ConvectionDiffusionEquation

## 现有内容检查

- 未提供现有内容，本次按新建模型模板处理。

## 调整和完善建议

- 未提供现有脚本或模型摘要；本次输出为基于学习库的新建模型模板，可作为后续修正基线。
- 补充参数定义，并把关键尺寸、材料参数和载荷写成可扫描参数。
- 补充或替换几何构建段，优先复用相似案例中的几何序列。
- 补充物理场接口，并与需求和已学习案例中的物理场保持一致。
- 补充材料节点，至少包含密度、弹性参数、导热或电学参数等必要属性。
- 补充网格设置，并在孔、裂纹、边界层或高梯度区域局部加密。
- 补充研究/求解器设置，按稳态、瞬态、频域、特征频率或参数扫描选择。
- 补充结果导出，保存关键全局量、场图和用于训练的 CSV。
- 补充选择集或边界编号复核步骤，避免边界条件施加到错误实体。
- 根据需求和学习库，应补充或复核 `HeatTransfer` 物理接口。
- 根据需求和学习库，应补充或复核 `SolidMechanics` 物理接口。
- 根据需求和学习库，应补充或复核 `LaminarFlow` 物理接口。
- 可参考 `COMSOL不同围压条件下单孔水力压裂裂纹的拓展规律研究` 中的物理场设置：solid mechanics damage evolution, pore/fluid pressure loading, hydraulic fracture propagation。
- 可参考 `COMSOL不同围压条件下单孔水力压裂裂纹的拓展规律研究` 中的研究设置：time-dependent pressure/damage evolution, parametric sweep over stress ratio and stress direction。

## 后续验证路径

- 在 COMSOL 中打开生成脚本，先不批量扫描，只运行一个基准模型。
- 核对所有选择集、边界编号和材料参数。
- 求解通过后，再添加参数扫描并导出 CSV。
- 把修正后的 MATLAB/Java 脚本重新放回案例库，继续学习和完善记忆库。
