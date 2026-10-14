# Approved COMSOL Modeling Package

- Workflow: `Build_a_COMSOL_hydraulic_fracturing_mode_20260803111808`
- Requirement: Build a COMSOL hydraulic fracturing model for a single borehole under different confining stress conditions. 中文需求关键词：水力压裂 单孔 围压 主应力 天然裂缝 煤层 岩石裂隙流 多孔介质 裂缝拓展 损伤演化。 Use article parameters: square_side=300[mm] borehole_diameter=15[mm] stress_ratio_range=1.5~2.0 initial_pressure=0.1[MPa] mean_elastic_modulus=35.1[GPa] mean_compressive_strength=152[MPa] principal_stress_direction_135=135[deg] principal_stress_direction_180=180[deg] principal_stress_direction_90=90[deg]. Include features: 2D square domain central borehole natural fracture or weak-plane features coal/rock medium heterogeneous elastic modulus heterogeneous tensile/compressive strength Weibull random field distribution solid mechanics damage evolution pore/fluid pressure loading hydraulic fracture propagation outer boundary in-situ stress loading symmetric roller/fixed displacement support borehole injection pressure free triangular mesh local refinement near borehole and natural fractures time-dependent pressure/damage evolution parametric sweep over stress ratio and stress direction damage length vs time pressure field fracture path initiation pressure stress distribution fracture deflection and branching under natural fractures.

## Modeling Sequence

- Define parameters and units.
- Build/import geometry and selections.
- Assign materials.
- Create approved physics interfaces and boundary conditions.
- Create mesh and refinement settings.
- Create study and solver sequence.
- Export approved results and CSV training columns.
- Save model and report verification checklist.

## MATLAB Requirements

- Use LiveLink MATLAB API in the approved sequence.
- Keep boundary IDs and named selections as explicit review comments.
- Add table export for approved outputs.
- Requirement: Build a COMSOL hydraulic fracturing model for a single borehole under different confining stress conditions. 中文需求关键词：水力压裂 单孔 围压 主应力 天然裂缝 煤层 岩石裂隙流 多孔介质 裂缝拓展 损伤演化。 Use article parameters: square_side=300[mm] borehole_diameter=15[mm] stress_ratio_range=1.5~2.0 initial_pressure=0.1[MPa] mean_elastic_modulus=35.1[GPa] mean_compressive_strength=152[MPa] principal_stress_direction_135=135[deg] principal_stress_direction_180=180[deg] principal_stress_direction_90=90[deg]. Include features: 2D square domain central borehole natural fracture or weak-plane features coal/rock medium heterogeneous elastic modulus heterogeneous tensile/compressive strength Weibull random field distribution solid mechanics damage evolution pore/fluid pressure loading hydraulic fracture propagation outer boundary in-situ stress loading symmetric roller/fixed displacement support borehole injection pressure free triangular mesh local refinement near borehole and natural fractures time-dependent pressure/damage evolution parametric sweep over stress ratio and stress direction damage length vs time pressure field fracture path initiation pressure stress distribution fracture deflection and branching under natural fractures.

## Java Requirements

- Use COMSOL Java API equivalents for parameters, geometry, physics, mesh, study, and results.
- Keep comments where COMSOL entity IDs must be verified.
- Save the final model as MPH after baseline solve settings are reviewed.

## Verification Checklist

- Confirm material units and property sources.
- Confirm boundary selections after geometry generation.
- Run one baseline solve before parameter sweeps.
- Run mesh refinement checks for key outputs.
- Export CSV only after derived values are verified.

## Generated Files

- matlab: `generated\demo_hydraulic_fracture_package\final_code\build_a_comsol_hydraulic_fracturing_mode_20260803111808.m`
- java: `generated\demo_hydraulic_fracture_package\final_code\BuildAComsolHydraulicFracturingMode20260803111808.java`
- guidance: `generated\demo_hydraulic_fracture_package\final_code\build_a_comsol_hydraulic_fracturing_mode_20260803111808_guidance.md`
- verification: `generated\demo_hydraulic_fracture_package\final_code\build_a_comsol_hydraulic_fracturing_mode_20260803111808_verification.json`

## Generation Readiness

- status: `review_required`
- ready_to_open: `True`
- ready_to_solve: `False`
- unresolved: 确认生成几何中的材料域和边界选择集。
- unresolved: 在 COMSOL 中核对物理接口名称是否与已安装模块一致。
- unresolved: 把已批准边界条件绑定到经过核对的命名选择集。
- unresolved: 确认裂缝表示方法、断裂参数和裂纹起始区域。

## Execution Handoff

- next_action: `review_named_selections_and_boundaries`
- approved_steps: `physics, materials, data_structure, mesh, study_solver, results_export`
- review_before_execution: 确认生成几何中的材料域和边界选择集。
- review_before_execution: 在 COMSOL 中核对物理接口名称是否与已安装模块一致。
- review_before_execution: 把已批准边界条件绑定到经过核对的命名选择集。
- review_before_execution: 确认裂缝表示方法、断裂参数和裂纹起始区域。
