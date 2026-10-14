from __future__ import annotations

from math import pi
from typing import Any


def poiseuille_pipe_reference(*, length_m: float, diameter_m: float, flow_rate_m3_s: float, viscosity_pa_s: float, density_kg_m3: float) -> dict[str, Any]:
    """Return the fully developed circular-pipe laminar-flow reference quantities in SI units."""
    values = {
        "length_m": length_m,
        "diameter_m": diameter_m,
        "flow_rate_m3_s": flow_rate_m3_s,
        "viscosity_pa_s": viscosity_pa_s,
        "density_kg_m3": density_kg_m3,
    }
    if any(float(value) <= 0 for value in values.values()):
        raise ValueError("pipe reference inputs must all be greater than zero")
    area = pi * diameter_m**2 / 4.0
    mean_velocity = flow_rate_m3_s / area
    reynolds = density_kg_m3 * mean_velocity * diameter_m / viscosity_pa_s
    pressure_drop = 128.0 * viscosity_pa_s * length_m * flow_rate_m3_s / (pi * diameter_m**4)
    return {
        "kind": "hagen_poiseuille_circular_pipe_reference",
        "inputs_si": values,
        "mean_velocity_m_s": mean_velocity,
        "centerline_velocity_m_s": 2.0 * mean_velocity,
        "pressure_drop_pa": pressure_drop,
        "reynolds_number": reynolds,
        "fully_developed_length_ratio": length_m / diameter_m,
        "assumptions": ["Newtonian incompressible fluid", "straight circular pipe", "steady fully developed laminar flow", "no-slip wall"],
        "validity": {
            "reynolds_laminar": reynolds < 2300.0,
            "development_length_recommended": length_m / diameter_m >= 20.0,
            "guidance": "Use a 2D axisymmetric Laminar Flow COMSOL model with an inlet flow rate or mean velocity, pressure outlet, and no-slip wall. Compare pressure drop and the parabolic axial velocity profile.",
        },
    }


def poiseuille_velocity_at_radius(*, radius_m: float, pipe_diameter_m: float, mean_velocity_m_s: float) -> float:
    """Parabolic axial velocity for a fully developed circular pipe; radius must lie inside the pipe."""
    radius = pipe_diameter_m / 2.0
    if pipe_diameter_m <= 0 or abs(radius_m) > radius:
        raise ValueError("radius_m must lie within a pipe of positive diameter")
    return 2.0 * mean_velocity_m_s * (1.0 - (radius_m / radius) ** 2)
