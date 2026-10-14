# COMSOL Modeling Logic Knowledge Base

This file is generated from the local COMSOL PDF documentation catalog and the small model ontology.

## Catalog Summary

- Modules: 51
- PDF files: 107
- Total size bytes: 526279684

## Domain Coverage

- acoustics_and_vibration: 1 module(s)
- automation_and_scripting: 1 module(s)
- cad_livelink_integration: 6 module(s)
- chemical_reaction_and_transport: 1 module(s)
- composite_materials: 1 module(s)
- core_platform: 1 module(s)
- data_livelink_integration: 1 module(s)
- electrochemistry_and_energy: 3 module(s)
- electrochemistry_and_material_degradation: 1 module(s)
- electrochemistry_and_material_processing: 1 module(s)
- electromagnetic_waves: 1 module(s)
- electromagnetics: 1 module(s)
- electronics_geometry_import: 1 module(s)
- fatigue_and_lifetime: 1 module(s)
- fluid_flow: 1 module(s)
- geomechanics: 1 module(s)
- geometry_and_import: 1 module(s)
- geometry_design_and_parametric_modeling: 1 module(s)
- granular_flow: 1 module(s)
- heat_transfer: 1 module(s)
- materials: 1 module(s)
- materials_and_fluid_properties: 1 module(s)
- mems_multiphysics: 1 module(s)
- metal_processing: 1 module(s)
- microfluidics: 1 module(s)
- mixer_design_and_fluid_mixing: 1 module(s)
- multibody_dynamics: 1 module(s)
- nonlinear_structural_materials: 1 module(s)
- optimization_and_inverse_design: 1 module(s)
- particle_and_ray_methods: 1 module(s)
- plasma_and_discharge: 2 module(s)
- polymer_flow: 1 module(s)
- porous_media_transport: 1 module(s)
- rarefied_and_molecular_flow: 1 module(s)
- ray_optics: 1 module(s)
- reduced_fluid_networks: 1 module(s)
- rotordynamics: 1 module(s)
- semiconductor_devices: 1 module(s)
- structural_mechanics: 1 module(s)
- subsurface_flow: 1 module(s)
- system_simulation_integration: 1 module(s)
- uncertainty_quantification: 1 module(s)
- wave_optics: 1 module(s)

## Core Modeling Logic

### problem_definition

- Purpose: Convert an engineering question into a finite element problem.
- Learned objects: domain, physics, assumptions, design_variables, targets
- COMSOL artifacts: model label, component, parameters, global definitions

### geometry

- Purpose: Represent the computational domain and named selections.
- Learned objects: dimension, length_scale, symmetry, parts, selections
- COMSOL artifacts: geom, features, work planes, selections

### materials

- Purpose: Attach constitutive laws and properties to domains.
- Learned objects: material_property, unit, temperature_dependence, anisotropy
- COMSOL artifacts: material, propertyGroup, functions

### physics

- Purpose: Choose governing equations and dependent variables.
- Learned objects: physics_interface, dependent_variable, domain_equation, coupling
- COMSOL artifacts: physics.create, features, multiphysics couplings

### boundary_initial_conditions

- Purpose: Close the mathematical model and encode loads, sources, and constraints.
- Learned objects: boundary_condition, initial_condition, source_term, constraint
- COMSOL artifacts: feature.selection, feature.set, initial values

### mesh

- Purpose: Discretize geometry with enough resolution for gradients and waves.
- Learned objects: element_size, boundary_layer, mesh_quality, convergence
- COMSOL artifacts: mesh, size, FreeTri, FreeTet, swept mesh

### study_solver

- Purpose: Define the mathematical task and numerical solution strategy.
- Learned objects: stationary, time_dependent, frequency_domain, eigenvalue, parametric_sweep
- COMSOL artifacts: study, solver sequence, parametric sweep, time range

### results_validation

- Purpose: Extract quantities of interest and compare against expectations.
- Learned objects: derived_value, plot, probe, error_metric, validation_target
- COMSOL artifacts: result, numerical, plot group, export

### surrogate_learning

- Purpose: Turn repeated COMSOL solves into a trainable dataset.
- Learned objects: input_columns, output_columns, units, constraints, train_test_split
- COMSOL artifacts: parameter table, CSV export, model summary, surrogate model

## Module Documents

### Microfluidics_Module

- Domain: microfluidics
- PDFs: 2
  - IntroductionToMicrofluidicsModule.pdf (introduction_and_examples, 3517089 bytes)
  - MicrofluidicsModuleUsersGuide.pdf (module_users_guide, 3730781 bytes)

### Mixer_Module

- Domain: mixer_design_and_fluid_mixing
- PDFs: 1
  - MixerModuleUsersGuide.pdf (module_users_guide, 3275261 bytes)

### Molecular_Flow_Module

- Domain: rarefied_and_molecular_flow
- PDFs: 2
  - IntroductionToMolecularFlowModule.pdf (introduction_and_examples, 3025126 bytes)
  - MolecularFlowModuleUsersGuide.pdf (module_users_guide, 1469072 bytes)

### Multibody_Dynamics_Module

- Domain: multibody_dynamics
- PDFs: 1
  - MultibodyDynamicsModuleUsersGuide.pdf (module_users_guide, 7202336 bytes)

### Nonlinear_Structural_Materials_Module

- Domain: nonlinear_structural_materials
- PDFs: 1
  - NonlinearStructuralMaterialsModuleUsersGuide.pdf (module_users_guide, 283273 bytes)

### Optimization_Module

- Domain: optimization_and_inverse_design
- PDFs: 3
  - gcmma.pdf (documentation, 272654 bytes)
  - IntroductionToOptimizationModule.pdf (introduction_and_examples, 2896522 bytes)
  - OptimizationModuleUsersGuide.pdf (module_users_guide, 1691697 bytes)

### Particle_Tracing_Module

- Domain: particle_and_ray_methods
- PDFs: 2
  - IntroductionToParticleTracingModule.pdf (introduction_and_examples, 7911326 bytes)
  - ParticleTracingModuleUsersGuide.pdf (module_users_guide, 4809371 bytes)

### Pipe_Flow_Module

- Domain: reduced_fluid_networks
- PDFs: 2
  - IntroductionToPipeFlowModule.pdf (introduction_and_examples, 3994791 bytes)
  - PipeFlowModuleUsersGuide.pdf (module_users_guide, 885069 bytes)

### Plasma_Module

- Domain: plasma_and_discharge
- PDFs: 2
  - IntroductionToPlasmaModule.pdf (introduction_and_examples, 3198238 bytes)
  - PlasmaModuleUsersGuide.pdf (module_users_guide, 3944845 bytes)

### Polymer_Flow_Module

- Domain: polymer_flow
- PDFs: 2
  - IntroductionToPolymerFlowModule.pdf (introduction_and_examples, 2782945 bytes)
  - PolymerFlowModuleUsersGuide.pdf (module_users_guide, 3866984 bytes)

### Porous_Media_Flow_Module

- Domain: porous_media_transport
- PDFs: 2
  - IntroductionToPorousMediaFlowModule.pdf (introduction_and_examples, 2928627 bytes)
  - PorousMediaFlowModuleUsersGuide.pdf (module_users_guide, 3073214 bytes)

### Ray_Optics_Module

- Domain: ray_optics
- PDFs: 2
  - IntroductionToRayOpticsModule.pdf (introduction_and_examples, 7553128 bytes)
  - RayOpticsModuleUsersGuide.pdf (module_users_guide, 5276722 bytes)

### RF_Module

- Domain: electromagnetic_waves
- PDFs: 2
  - IntroductionToRFModule.pdf (introduction_and_examples, 3141821 bytes)
  - RFModuleUsersGuide.pdf (module_users_guide, 3746884 bytes)

### Rotordynamics_Module

- Domain: rotordynamics
- PDFs: 1
  - RotordynamicsModuleUsersGuide.pdf (module_users_guide, 6236956 bytes)

### Semiconductor_Module

- Domain: semiconductor_devices
- PDFs: 2
  - IntroductionToSemiconductorModule.pdf (introduction_and_examples, 3639387 bytes)
  - SemiconductorModuleUsersGuide.pdf (module_users_guide, 4891924 bytes)

### Structural_Mechanics_Module

- Domain: structural_mechanics
- PDFs: 3
  - IntroductionToStructuralMechanicsModule.pdf (introduction_and_examples, 5287668 bytes)
  - StructuralMechanicsModuleUsersGuide.pdf (module_users_guide, 21641446 bytes)
  - StructuralMechanicsVerificationExamples.pdf (documentation, 13083370 bytes)

### Subsurface_Flow_Module

- Domain: subsurface_flow
- PDFs: 2
  - IntroductionToSubsurfaceFlowModule.pdf (introduction_and_examples, 3119800 bytes)
  - SubsurfaceFlowModuleUsersGuide.pdf (module_users_guide, 3396269 bytes)

### Uncertainty_Quantification_Module

- Domain: uncertainty_quantification
- PDFs: 1
  - UncertaintyQuantificationModuleUsersGuide.pdf (module_users_guide, 596973 bytes)

### Wave_Optics_Module

- Domain: wave_optics
- PDFs: 2
  - IntroductionToWaveOpticsModule.pdf (introduction_and_examples, 6974957 bytes)
  - WaveOpticsModuleUsersGuide.pdf (module_users_guide, 2573702 bytes)

### ACDC_Module

- Domain: electromagnetics
- PDFs: 2
  - ACDCModuleUsersGuide.pdf (module_users_guide, 3586980 bytes)
  - IntroductionToACDCModule.pdf (introduction_and_examples, 5720352 bytes)

### Acoustics_Module

- Domain: acoustics_and_vibration
- PDFs: 2
  - AcousticsModuleUsersGuide.pdf (module_users_guide, 7964979 bytes)
  - IntroductionToAcousticsModule.pdf (introduction_and_examples, 4463008 bytes)

### Battery_Design_Module

- Domain: electrochemistry_and_energy
- PDFs: 2
  - BatteryDesignModuleUsersGuide.pdf (module_users_guide, 7578868 bytes)
  - IntroductionToBatteryDesignModule.pdf (introduction_and_examples, 1797964 bytes)

### CAD_Import_Module

- Domain: geometry_and_import
- PDFs: 2
  - CADImportModuleUsersGuide.pdf (module_users_guide, 1097311 bytes)
  - IntroductionToCADImportModule.pdf (introduction_and_examples, 8810414 bytes)

### CFD_Module

- Domain: fluid_flow
- PDFs: 2
  - CFDModuleUsersGuide.pdf (module_users_guide, 8474430 bytes)
  - IntroductionToCFDModule.pdf (introduction_and_examples, 2971111 bytes)

### Chemical_Reaction_Engineering_Module

- Domain: chemical_reaction_and_transport
- PDFs: 3
  - ChemicalReactionEngineeringModuleUsersGuide.pdf (module_users_guide, 4536946 bytes)
  - IntroductionToChemicalReactionEngineeringModule.pdf (introduction_and_examples, 3169364 bytes)
  - IntroductionToThermodynamicProperties.pdf (introduction_and_examples, 4036471 bytes)

### Composite_Materials_Module

- Domain: composite_materials
- PDFs: 1
  - CompositeMaterialsModuleUsersGuide.pdf (module_users_guide, 5092971 bytes)

### COMSOL_Multiphysics

- Domain: core_platform
- PDFs: 14
  - ApplicationProgrammingGuide.pdf (programming_api, 12264014 bytes)
  - COMSOL_ApplicationBuilderManual.pdf (documentation, 2715171 bytes)
  - COMSOL_MultiphysicsInstallationGuide.pdf (installation, 4396953 bytes)
  - COMSOL_PhysicsBuilderManual.pdf (documentation, 2608041 bytes)
  - COMSOL_PostprocessingAndVisualization.pdf (documentation, 4586005 bytes)
  - COMSOL_ProgrammingReferenceManual.pdf (reference_manual, 6576942 bytes)
  - COMSOL_ReferenceManual.pdf (reference_manual, 71843447 bytes)
  - COMSOL_ReleaseNotes.pdf (release_notes, 1012458 bytes)
  - COMSOL_SoftwareLicenseAgreement.pdf (documentation, 642327 bytes)
  - COMSOL_SpecializedTechniquesForPostprocessingAndVisualization.pdf (documentation, 17869943 bytes)
  - IntroductionToApplicationBuilder.pdf (introduction_and_examples, 12871206 bytes)
  - IntroductionToCOMSOLMultiphysics.pdf (introduction_and_examples, 11288812 bytes)
  - ModelManagerReferenceManual.pdf (reference_manual, 7366246 bytes)
  - ModelManagerServerManual.pdf (documentation, 1772558 bytes)

### Corrosion_Module

- Domain: electrochemistry_and_material_degradation
- PDFs: 2
  - CorrosionModuleUsersGuide.pdf (module_users_guide, 4400093 bytes)
  - IntroductionToCorrosionModule.pdf (introduction_and_examples, 2932575 bytes)

### Design_Module

- Domain: geometry_design_and_parametric_modeling
- PDFs: 2
  - DesignModuleUsersGuide.pdf (module_users_guide, 2649334 bytes)
  - IntroductionToDesignModule.pdf (introduction_and_examples, 6446710 bytes)

### ECAD_Import_Module

- Domain: electronics_geometry_import
- PDFs: 2
  - ECADImportModuleUsersGuide.pdf (module_users_guide, 683714 bytes)
  - IntroductionToECADImportModule.pdf (introduction_and_examples, 2634534 bytes)

### Electric_Discharge_Module

- Domain: plasma_and_discharge
- PDFs: 2
  - ElectricDischargeModuleUsersGuide.pdf (module_users_guide, 3217747 bytes)
  - IntroductionToElectricDischargeModule.pdf (introduction_and_examples, 442666 bytes)

### Electrochemistry_Module

- Domain: electrochemistry_and_energy
- PDFs: 2
  - ElectrochemistryModuleUsersGuide.pdf (module_users_guide, 3962126 bytes)
  - IntroductionToElectrochemistryModule.pdf (introduction_and_examples, 3074586 bytes)

### Electrodeposition_Module

- Domain: electrochemistry_and_material_processing
- PDFs: 2
  - ElectrodepositionModuleUsersGuide.pdf (module_users_guide, 4247676 bytes)
  - IntroductionToElectrodepositionModule.pdf (introduction_and_examples, 3565926 bytes)

### Fatigue_Module

- Domain: fatigue_and_lifetime
- PDFs: 1
  - FatigueModuleUsersGuide.pdf (module_users_guide, 1443541 bytes)

### Fuel_Cell_and_Electrolyzer_Module

- Domain: electrochemistry_and_energy
- PDFs: 2
  - FuelCellAndElectrolyzerModuleUsersGuide.pdf (module_users_guide, 6858177 bytes)
  - IntroductionToFuelCellAndElectrolyzerModule.pdf (introduction_and_examples, 4076247 bytes)

### Geomechanics_Module

- Domain: geomechanics
- PDFs: 1
  - GeomechanicsModuleUsersGuide.pdf (module_users_guide, 282302 bytes)

### Granular_Flow_Module

- Domain: granular_flow
- PDFs: 2
  - GranularFlowModuleUsersGuide.pdf (module_users_guide, 1433888 bytes)
  - IntroductionToGranularFlowModule.pdf (introduction_and_examples, 421287 bytes)

### Heat_Transfer_Module

- Domain: heat_transfer
- PDFs: 2
  - HeatTransferModuleUsersGuide.pdf (module_users_guide, 9604857 bytes)
  - IntroductionToHeatTransferModule.pdf (introduction_and_examples, 5009177 bytes)

### Liquid_and_Gas_Properties_Module

- Domain: materials_and_fluid_properties
- PDFs: 2
  - IntroductionToLiquidAndGasPropertiesModule.pdf (introduction_and_examples, 2786704 bytes)
  - LiquidAndGasPropertiesModuleUsersGuide.pdf (module_users_guide, 1476839 bytes)

### LiveLink_for_AutoCAD

- Domain: cad_livelink_integration
- PDFs: 2
  - IntroductionToLiveLinkForAutoCAD.pdf (introduction_and_examples, 6426719 bytes)
  - LiveLinkForAutoCADUsersGuide.pdf (module_users_guide, 1223281 bytes)

### LiveLink_for_Excel

- Domain: data_livelink_integration
- PDFs: 2
  - IntroductionToLiveLinkForExcel.pdf (introduction_and_examples, 3145175 bytes)
  - LiveLinkForExcelUsersGuide.pdf (module_users_guide, 1497295 bytes)

### LiveLink_for_Inventor

- Domain: cad_livelink_integration
- PDFs: 2
  - IntroductionToLiveLinkForInventor.pdf (introduction_and_examples, 6511984 bytes)
  - LiveLinkForInventorUsersGuide.pdf (module_users_guide, 1245873 bytes)

### LiveLink_for_MATLAB

- Domain: automation_and_scripting
- PDFs: 2
  - IntroductionToLiveLinkForMATLAB.pdf (introduction_and_examples, 3093789 bytes)
  - LiveLinkForMATLABUsersGuide.pdf (module_users_guide, 7275761 bytes)

### LiveLink_for_PTC_Creo_Parametric

- Domain: cad_livelink_integration
- PDFs: 2
  - IntroductionToLiveLinkForPTCCreoParametric.pdf (introduction_and_examples, 6450124 bytes)
  - LiveLinkForPTCCreoParametricUsersGuide.pdf (module_users_guide, 1248686 bytes)

### LiveLink_for_Revit

- Domain: cad_livelink_integration
- PDFs: 2
  - IntroductionToLiveLinkForRevit.pdf (introduction_and_examples, 6802725 bytes)
  - LiveLinkForRevitUsersGuide.pdf (module_users_guide, 1246166 bytes)

### LiveLink_for_Simulink

- Domain: system_simulation_integration
- PDFs: 2
  - IntroductionToLiveLinkForSimulink.pdf (introduction_and_examples, 1006002 bytes)
  - LiveLinkForSimulinkUsersGuide.pdf (module_users_guide, 1005024 bytes)

### LiveLink_for_Solid_Edge

- Domain: cad_livelink_integration
- PDFs: 2
  - IntroductionToLiveLinkForSolidEdge.pdf (introduction_and_examples, 6463265 bytes)
  - LiveLinkForSolidEdgeUsersGuide.pdf (module_users_guide, 1238732 bytes)

### LiveLink_for_SOLIDWORKS

- Domain: cad_livelink_integration
- PDFs: 2
  - IntroductionToLiveLinkForSOLIDWORKS.pdf (introduction_and_examples, 6449981 bytes)
  - LiveLinkForSOLIDWORKSUsersGuide.pdf (module_users_guide, 1233508 bytes)

### Material_Library

- Domain: materials
- PDFs: 1
  - MaterialLibraryUsersGuide.pdf (module_users_guide, 1589332 bytes)

### MEMS_Module

- Domain: mems_multiphysics
- PDFs: 2
  - IntroductionToMEMSModule.pdf (introduction_and_examples, 2998681 bytes)
  - MEMSModuleUsersGuide.pdf (module_users_guide, 2464976 bytes)

### Metal_Processing_Module

- Domain: metal_processing
- PDFs: 1
  - MetalProcessingModuleUsersGuide.pdf (module_users_guide, 976379 bytes)

## Small Model Learning Schema

### Knowledge Inputs
- pdf: Theory, assumptions, governing equations, validation examples, module-specific feature descriptions.
- matlab: Executable LiveLink model construction sequence and parameter names.
- java: COMSOL exported model tree, feature tags, physics interfaces, studies, and result nodes.
- mph_summary: Authoritative model metadata exported through COMSOL API.
- csv: Numerical sweep data for surrogate training.
- json: Constraints, model summaries, module catalogs, or generated knowledge records.

### Reasoning Order
- identify domain and physics interface
- retrieve module documentation and similar case evidence
- extract parameters and units
- map geometry and selections
- map materials and constitutive properties
- map boundary and initial conditions
- map mesh and solver/study
- map outputs and validation targets
- cross-check API and feature settings against official documentation
- build constraints JSON
- generate or modify LiveLink script
- train surrogate from exported sweep data

### Theory Learning Outputs
- module domain map
- governing equation and physics-interface notes
- required inputs and material properties
- boundary condition vocabulary
- mesh and solver recommendations
- validation and postprocessing quantities
- automation/API references for script generation
