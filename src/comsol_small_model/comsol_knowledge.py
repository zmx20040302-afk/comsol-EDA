from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


DEFAULT_DOC_ROOT = Path("D:/COMSOL64/Multiphysics/doc/pdf")


MODULE_DOMAINS = {
    "ACDC_Module": "electromagnetics",
    "Acoustics_Module": "acoustics_and_vibration",
    "Battery_Design_Module": "electrochemistry_and_energy",
    "CAD_Import_Module": "geometry_and_import",
    "CFD_Module": "fluid_flow",
    "Chemical_Reaction_Engineering_Module": "chemical_reaction_and_transport",
    "Composite_Materials_Module": "composite_materials",
    "Corrosion_Module": "electrochemistry_and_material_degradation",
    "Design_Module": "geometry_design_and_parametric_modeling",
    "ECAD_Import_Module": "electronics_geometry_import",
    "Electric_Discharge_Module": "plasma_and_discharge",
    "Electrochemistry_Module": "electrochemistry_and_energy",
    "Electrodeposition_Module": "electrochemistry_and_material_processing",
    "Fatigue_Module": "fatigue_and_lifetime",
    "Fuel_Cell_and_Electrolyzer_Module": "electrochemistry_and_energy",
    "Geomechanics_Module": "geomechanics",
    "Granular_Flow_Module": "granular_flow",
    "Heat_Transfer_Module": "heat_transfer",
    "Liquid_and_Gas_Properties_Module": "materials_and_fluid_properties",
    "LiveLink_for_AutoCAD": "cad_livelink_integration",
    "LiveLink_for_Excel": "data_livelink_integration",
    "LiveLink_for_Inventor": "cad_livelink_integration",
    "LiveLink_for_MATLAB": "automation_and_scripting",
    "LiveLink_for_PTC_Creo_Parametric": "cad_livelink_integration",
    "LiveLink_for_Revit": "cad_livelink_integration",
    "LiveLink_for_Simulink": "system_simulation_integration",
    "LiveLink_for_Solid_Edge": "cad_livelink_integration",
    "LiveLink_for_SOLIDWORKS": "cad_livelink_integration",
    "Material_Library": "materials",
    "MEMS_Module": "mems_multiphysics",
    "Metal_Processing_Module": "metal_processing",
    "Microfluidics_Module": "microfluidics",
    "Mixer_Module": "mixer_design_and_fluid_mixing",
    "Molecular_Flow_Module": "rarefied_and_molecular_flow",
    "Multibody_Dynamics_Module": "multibody_dynamics",
    "Nonlinear_Structural_Materials_Module": "nonlinear_structural_materials",
    "Optimization_Module": "optimization_and_inverse_design",
    "Particle_Tracing_Module": "particle_and_ray_methods",
    "Pipe_Flow_Module": "reduced_fluid_networks",
    "Plasma_Module": "plasma_and_discharge",
    "Polymer_Flow_Module": "polymer_flow",
    "Porous_Media_Flow_Module": "porous_media_transport",
    "Ray_Optics_Module": "ray_optics",
    "RF_Module": "electromagnetic_waves",
    "Rotordynamics_Module": "rotordynamics",
    "Semiconductor_Module": "semiconductor_devices",
    "Structural_Mechanics_Module": "structural_mechanics",
    "Subsurface_Flow_Module": "subsurface_flow",
    "Uncertainty_Quantification_Module": "uncertainty_quantification",
    "Wave_Optics_Module": "wave_optics",
    "COMSOL_Multiphysics": "core_platform",
}


CORE_MODELING_LOGIC = [
    {
        "stage": "problem_definition",
        "purpose": "Convert an engineering question into a finite element problem.",
        "learned_objects": ["domain", "physics", "assumptions", "design_variables", "targets"],
        "comsol_artifacts": ["model label", "component", "parameters", "global definitions"],
    },
    {
        "stage": "geometry",
        "purpose": "Represent the computational domain and named selections.",
        "learned_objects": ["dimension", "length_scale", "symmetry", "parts", "selections"],
        "comsol_artifacts": ["geom", "features", "work planes", "selections"],
    },
    {
        "stage": "materials",
        "purpose": "Attach constitutive laws and properties to domains.",
        "learned_objects": ["material_property", "unit", "temperature_dependence", "anisotropy"],
        "comsol_artifacts": ["material", "propertyGroup", "functions"],
    },
    {
        "stage": "physics",
        "purpose": "Choose governing equations and dependent variables.",
        "learned_objects": ["physics_interface", "dependent_variable", "domain_equation", "coupling"],
        "comsol_artifacts": ["physics.create", "features", "multiphysics couplings"],
    },
    {
        "stage": "boundary_initial_conditions",
        "purpose": "Close the mathematical model and encode loads, sources, and constraints.",
        "learned_objects": ["boundary_condition", "initial_condition", "source_term", "constraint"],
        "comsol_artifacts": ["feature.selection", "feature.set", "initial values"],
    },
    {
        "stage": "mesh",
        "purpose": "Discretize geometry with enough resolution for gradients and waves.",
        "learned_objects": ["element_size", "boundary_layer", "mesh_quality", "convergence"],
        "comsol_artifacts": ["mesh", "size", "FreeTri", "FreeTet", "swept mesh"],
    },
    {
        "stage": "study_solver",
        "purpose": "Define the mathematical task and numerical solution strategy.",
        "learned_objects": ["stationary", "time_dependent", "frequency_domain", "eigenvalue", "parametric_sweep"],
        "comsol_artifacts": ["study", "solver sequence", "parametric sweep", "time range"],
    },
    {
        "stage": "results_validation",
        "purpose": "Extract quantities of interest and compare against expectations.",
        "learned_objects": ["derived_value", "plot", "probe", "error_metric", "validation_target"],
        "comsol_artifacts": ["result", "numerical", "plot group", "export"],
    },
    {
        "stage": "surrogate_learning",
        "purpose": "Turn repeated COMSOL solves into a trainable dataset.",
        "learned_objects": ["input_columns", "output_columns", "units", "constraints", "train_test_split"],
        "comsol_artifacts": ["parameter table", "CSV export", "model summary", "surrogate model"],
    },
]


@dataclass(frozen=True)
class PdfDocument:
    name: str
    path: str
    size_bytes: int
    role: str


@dataclass(frozen=True)
class ModuleCatalog:
    module: str
    path: str
    domain: str
    pdf_count: int
    total_size_bytes: int
    documents: list[PdfDocument]


def scan_pdf_module(module_dir: str | Path) -> ModuleCatalog:
    module_path = Path(module_dir)
    documents = []
    for pdf in sorted(module_path.glob("*.pdf")):
        documents.append(
            PdfDocument(
                name=pdf.name,
                path=str(pdf),
                size_bytes=pdf.stat().st_size,
                role=_infer_pdf_role(pdf.name),
            )
        )
    return ModuleCatalog(
        module=module_path.name,
        path=str(module_path),
        domain=MODULE_DOMAINS.get(module_path.name, _infer_domain(module_path.name)),
        pdf_count=len(documents),
        total_size_bytes=sum(doc.size_bytes for doc in documents),
        documents=documents,
    )


def scan_pdf_modules(paths: list[str | Path]) -> dict[str, Any]:
    modules = [scan_pdf_module(path) for path in paths if Path(path).exists()]
    return build_catalog_summary(modules)


def scan_pdf_root(root: str | Path = DEFAULT_DOC_ROOT) -> dict[str, Any]:
    root_path = Path(root)
    modules = [scan_pdf_module(path) for path in sorted(root_path.iterdir()) if path.is_dir()]
    return build_catalog_summary(modules)


def build_catalog_summary(modules: list[ModuleCatalog]) -> dict[str, Any]:
    domain_counts: dict[str, int] = {}
    for module in modules:
        domain_counts[module.domain] = domain_counts.get(module.domain, 0) + 1
    return {
        "kind": "comsol_pdf_catalog",
        "module_count": len(modules),
        "pdf_count": sum(module.pdf_count for module in modules),
        "total_size_bytes": sum(module.total_size_bytes for module in modules),
        "domain_counts": domain_counts,
        "modules": [asdict(module) for module in modules],
        "modeling_logic": CORE_MODELING_LOGIC,
        "small_model_learning_schema": build_small_model_schema(),
    }


def build_small_model_schema() -> dict[str, Any]:
    return {
        "knowledge_inputs": {
            "pdf": "Theory, assumptions, governing equations, validation examples, module-specific feature descriptions.",
            "matlab": "Executable LiveLink model construction sequence and parameter names.",
            "java": "COMSOL exported model tree, feature tags, physics interfaces, studies, and result nodes.",
            "mph_summary": "Authoritative model metadata exported through COMSOL API.",
            "csv": "Numerical sweep data for surrogate training.",
            "json": "Constraints, model summaries, module catalogs, or generated knowledge records.",
        },
        "canonical_model_record": {
            "physics_domain": [],
            "parameters": [],
            "geometry": [],
            "materials": [],
            "boundary_conditions": [],
            "mesh": [],
            "study_solver": [],
            "outputs": [],
            "constraints": [],
            "training_dataset": [],
            "validation": [],
            "source_documents": [],
        },
        "reasoning_order": [
            "identify domain and physics interface",
            "retrieve module documentation and similar case evidence",
            "extract parameters and units",
            "map geometry and selections",
            "map materials and constitutive properties",
            "map boundary and initial conditions",
            "map mesh and solver/study",
            "map outputs and validation targets",
            "cross-check API and feature settings against official documentation",
            "build constraints JSON",
            "generate or modify LiveLink script",
            "train surrogate from exported sweep data",
        ],
        "theory_learning_outputs": [
            "module domain map",
            "governing equation and physics-interface notes",
            "required inputs and material properties",
            "boundary condition vocabulary",
            "mesh and solver recommendations",
            "validation and postprocessing quantities",
            "automation/API references for script generation",
        ],
    }


def build_modeling_logic_markdown(catalog: dict[str, Any]) -> str:
    lines = [
        "# COMSOL Modeling Logic Knowledge Base",
        "",
        "This file is generated from the local COMSOL PDF documentation catalog and the small model ontology.",
        "",
        "## Catalog Summary",
        "",
        f"- Modules: {catalog['module_count']}",
        f"- PDF files: {catalog['pdf_count']}",
        f"- Total size bytes: {catalog['total_size_bytes']}",
        "",
        "## Domain Coverage",
        "",
    ]
    for domain, count in sorted(catalog["domain_counts"].items()):
        lines.append(f"- {domain}: {count} module(s)")

    lines.extend(["", "## Core Modeling Logic", ""])
    for item in catalog["modeling_logic"]:
        lines.extend(
            [
                f"### {item['stage']}",
                "",
                f"- Purpose: {item['purpose']}",
                f"- Learned objects: {', '.join(item['learned_objects'])}",
                f"- COMSOL artifacts: {', '.join(item['comsol_artifacts'])}",
                "",
            ]
        )

    lines.extend(["## Module Documents", ""])
    for module in catalog["modules"]:
        lines.append(f"### {module['module']}")
        lines.append("")
        lines.append(f"- Domain: {module['domain']}")
        lines.append(f"- PDFs: {module['pdf_count']}")
        for doc in module["documents"]:
            lines.append(f"  - {doc['name']} ({doc['role']}, {doc['size_bytes']} bytes)")
        lines.append("")

    schema = catalog["small_model_learning_schema"]
    lines.extend(["## Small Model Learning Schema", ""])
    lines.append("### Knowledge Inputs")
    for name, description in schema["knowledge_inputs"].items():
        lines.append(f"- {name}: {description}")
    lines.extend(["", "### Reasoning Order"])
    for step in schema["reasoning_order"]:
        lines.append(f"- {step}")
    lines.extend(["", "### Theory Learning Outputs"])
    for output in schema["theory_learning_outputs"]:
        lines.append(f"- {output}")
    lines.append("")
    return "\n".join(lines)


def write_catalog_outputs(catalog: dict[str, Any], output_dir: str | Path) -> dict[str, str]:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    json_path = destination / "comsol_pdf_catalog.json"
    md_path = destination / "comsol_modeling_logic.md"
    json_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(build_modeling_logic_markdown(catalog), encoding="utf-8")
    return {"json": str(json_path), "markdown": str(md_path)}


def _infer_pdf_role(name: str) -> str:
    lowered = name.lower()
    if "introduction" in lowered:
        return "introduction_and_examples"
    if "usersguide" in lowered or "userguide" in lowered or "users_guide" in lowered:
        return "module_users_guide"
    if "reference" in lowered:
        return "reference_manual"
    if "programming" in lowered or "applicationprogramming" in lowered:
        return "programming_api"
    if "release" in lowered:
        return "release_notes"
    if "installation" in lowered:
        return "installation"
    return "documentation"


def _infer_domain(module_name: str) -> str:
    name = module_name.lower()
    if "livelink" in name:
        return "automation_and_integration"
    if "import" in name or "cad" in name:
        return "geometry_and_import"
    if "material" in name:
        return "materials"
    if "flow" in name or "fluid" in name:
        return "fluid_flow"
    if "mechanics" in name or "structural" in name or "fatigue" in name:
        return "structural_mechanics"
    if "optics" in name or "rf" in name:
        return "waves_and_electromagnetics"
    if "electro" in name or "battery" in name or "fuel" in name:
        return "electrochemistry_and_energy"
    return "module"
