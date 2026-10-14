from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_TOP_LEVEL = {
    "model_name",
    "physics",
    "geometry",
    "materials",
    "boundary_conditions",
    "mesh",
    "study",
    "outputs",
}

ONE_DIMENSIONAL_PHYSICS = {
    "heat_transfer_1d",
    "diffusion_1d",
    "axial_bar_1d",
    "electrothermal_1d",
    "thermal_expansion_bar_1d",
    "acoustic_pressure_1d",
    "electric_current_1d",
}


class ConstraintError(ValueError):
    pass


def load_constraints(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    validate_constraints(data)
    return data


def validate_constraints(data: dict[str, Any]) -> None:
    missing = REQUIRED_TOP_LEVEL - set(data)
    if missing:
        raise ConstraintError(f"Missing required sections: {', '.join(sorted(missing))}")

    geometry_type = data["geometry"].get("type")
    physics = data["physics"]
    is_legacy_2d = geometry_type == "rectangle_2d" and physics in {"heat_transfer_solid", "solid_mechanics_2d", "thermal_stress_2d", "flow_heat_2d"}
    is_one_dimensional = geometry_type == "interval_1d" and physics in ONE_DIMENSIONAL_PHYSICS
    if not (is_legacy_2d or is_one_dimensional):
        raise ConstraintError(
            "Supported templates are rectangle_2d + heat_transfer_solid, or "
            "interval_1d with a supported one-dimensional physics type"
        )

    for section_name in ("geometry", "materials", "boundary_conditions", "mesh"):
        section = data[section_name]
        parameters = section.get("parameters", section) if section_name == "geometry" else section
        if not isinstance(parameters, dict):
            raise ConstraintError(f"{section_name} must contain parameter dictionaries")
        for name, spec in parameters.items():
            _validate_numeric_spec(section_name, name, spec)

    allowed_studies = {"stationary"} if is_legacy_2d else {"stationary", "transient"}
    if physics == "acoustic_pressure_1d":
        allowed_studies.add("eigenfrequency")
    if data["study"].get("type") not in allowed_studies:
        raise ConstraintError(f"study.type must be one of {sorted(allowed_studies)}")

    if is_one_dimensional and "L" not in data["geometry"].get("parameters", {}):
        raise ConstraintError("interval_1d requires geometry.parameters.L")

    if not data["outputs"]:
        raise ConstraintError("At least one output expression is required")


def _validate_numeric_spec(section_name: str, name: str, spec: dict[str, Any]) -> None:
    for key in ("value", "unit", "min", "max"):
        if key not in spec:
            raise ConstraintError(f"{section_name}.{name} is missing '{key}'")
    if float(spec["min"]) > float(spec["value"]) or float(spec["value"]) > float(spec["max"]):
        raise ConstraintError(
            f"{section_name}.{name} value={spec['value']} is outside [{spec['min']}, {spec['max']}]"
        )


def format_value(spec: dict[str, Any]) -> str:
    return f"{spec['value']}[{spec['unit']}]"
