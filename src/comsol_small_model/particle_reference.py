from __future__ import annotations

from typing import Any


GRAVITY_M_S2 = 9.80665


def stokes_settling_reference(
    *,
    particle_diameter_m: float,
    particle_density_kg_m3: float,
    fluid_density_kg_m3: float,
    dynamic_viscosity_pa_s: float,
    gravity_m_s2: float = GRAVITY_M_S2,
) -> dict[str, Any]:
    """Signed Stokes terminal velocity, positive in the gravity direction, in SI units."""
    values = {
        "particle_diameter_m": particle_diameter_m,
        "particle_density_kg_m3": particle_density_kg_m3,
        "fluid_density_kg_m3": fluid_density_kg_m3,
        "dynamic_viscosity_pa_s": dynamic_viscosity_pa_s,
        "gravity_m_s2": gravity_m_s2,
    }
    if any(float(value) <= 0 for value in values.values()):
        raise ValueError("particle settling reference inputs must all be greater than zero")
    velocity = (particle_density_kg_m3 - fluid_density_kg_m3) * gravity_m_s2 * particle_diameter_m**2 / (18.0 * dynamic_viscosity_pa_s)
    particle_reynolds = fluid_density_kg_m3 * abs(velocity) * particle_diameter_m / dynamic_viscosity_pa_s
    return {
        "kind": "stokes_particle_settling_reference",
        "inputs_si": values,
        "terminal_velocity_m_s": velocity,
        "particle_reynolds_number": particle_reynolds,
        "direction": "with gravity" if velocity > 0 else "against gravity (buoyant rise)",
        "assumptions": [
            "isolated rigid spherical particle", "quiescent Newtonian fluid", "no wall, particle-particle, or turbulent-flow effects", "Stokes drag regime",
        ],
        "validity": {
            "stokes_regime": particle_reynolds < 0.1,
            "guidance": "In COMSOL Particle Tracing, compare the long-time particle velocity in a quiescent fluid. Use a nonlinear drag correlation when particle Reynolds number is not much smaller than one, and model wall effects near boundaries.",
        },
    }
