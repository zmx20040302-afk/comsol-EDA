# COMSOL 建模代码与理论指导

- 需求: 根据母线板焦耳热案例生成电流和传热耦合模型，并指导如何修正现有脚本
- MATLAB 输出: `D:\桌面\codex\comsol1\comsol_training_small_model\generated\code\busbar_joule_heat_refined_builder.m`
- Java 输出: `D:\桌面\codex\comsol1\comsol_training_small_model\generated\code\BusbarJouleHeatRefinedBuilder.java`

## 理论与建模指导

- 建模顺序应保持为：参数 -> 几何 -> 选择集 -> 材料 -> 物理场 -> 边界/初始条件 -> 网格 -> 研究/求解 -> 结果导出。
- 生成代码中的边界编号和选择集必须在 COMSOL 中复核；学习库只能提供案例模式和 API 结构，不能替代几何实体编号确认。
- 传热模型需要确认热源、温度边界、热通量或对流换热条件，并检查材料的导热系数、密度和热容。
- 电流/电磁模型需要确认端子、电势、接地和绝缘边界；若与传热耦合，应把焦耳热或损耗项传递到热场。
- 结构力学模型需要确认固定约束、载荷、接触/对称条件和材料弹性参数；特征频率问题应使用 Eigenfrequency 研究。
- 已学习案例中的理论关键词包括：传热，电磁，多孔介质/裂隙。
- 本次生成优先参考以下已学习案例：母线板焦耳热，母线板装配的焦耳热，微执行器焦耳热 - 分布式参数版本，如何生成随机非均匀材料数据6.2，母线板装配几何系列教程。

## 已学习案例证据

- `母线板焦耳热`: 内容证据 24 条；物理场=ec / ConductiveMedia, ht / HeatTransfer
- `母线板装配的焦耳热`: 内容证据 68 条；物理场=ec / ConductiveMedia, ht / HeatTransfer
- `微执行器焦耳热 - 分布式参数版本`: 内容证据 17 条；物理场=ec / ConductiveMedia, ht / HeatTransfer
- `如何生成随机非均匀材料数据6.2`: 内容证据 37 条；物理场=ht / HeatTransfer, solid / SolidMechanics
- `母线板装配几何系列教程`: 内容证据 54 条；物理场=未抽取

## 现有内容检查

- has_parameters: 缺失或未识别
- has_geometry: 已包含
- has_physics: 缺失或未识别
- has_material: 缺失或未识别
- has_mesh: 缺失或未识别
- has_study: 已包含
- has_results: 缺失或未识别
- has_boundary_selection: 缺失或未识别

## 调整和完善建议

- 补充参数定义，并把关键尺寸、材料参数和载荷写成可扫描参数。
- 补充物理场接口，并与需求和已学习案例中的物理场保持一致。
- 补充材料节点，至少包含密度、弹性参数、导热或电学参数等必要属性。
- 补充网格设置，并在孔、裂纹、边界层或高梯度区域局部加密。
- 补充结果导出，保存关键全局量、场图和用于训练的 CSV。
- 补充选择集或边界编号复核步骤，避免边界条件施加到错误实体。
- 根据需求和学习库，应补充或复核 `HeatTransferInSolids` 物理接口。
- 根据需求和学习库，应补充或复核 `SolidMechanics` 物理接口。
- 根据需求和学习库，应补充或复核 `ElectricCurrents` 物理接口。
- 可参考 `母线板焦耳热` 中的物理场设置：ec / ConductiveMedia, ht / HeatTransfer。
- 可参考 `母线板焦耳热` 中的研究设置：std1 / stat / Stationary, std1。

## 后续验证路径

- 在 COMSOL 中打开生成脚本，先不批量扫描，只运行一个基准模型。
- 核对所有选择集、边界编号和材料参数。
- 求解通过后，再添加参数扫描并导出 CSV。
- 把修正后的 MATLAB/Java 脚本重新放回案例库，继续学习和完善记忆库。
