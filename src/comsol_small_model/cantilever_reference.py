from __future__ import annotations

from math import pi, sqrt
from typing import Any


def cantilever_first_bending_mode_reference(
    *,
    length_m: float,
    width_m: float,
    thickness_m: float,
    youngs_modulus_pa: float,
    density_kg_m3: float,
) -> dict[str, Any]:
    """Euler-Bernoulli first bending-mode reference for a uniform rectangular cantilever."""
    values = {
        "length_m": length_m,
        "width_m": width_m,
        "thickness_m": thickness_m,
        "youngs_modulus_pa": youngs_modulus_pa,
        "density_kg_m3": density_kg_m3,
    }
    if any(float(value) <= 0 for value in values.values()):
        raise ValueError("cantilever reference inputs must all be greater than zero")
    area = width_m * thickness_m
    second_moment = width_m * thickness_m**3 / 12.0
    beta_l = 1.875104068711961
    frequency = beta_l**2 / (2.0 * pi * length_m**2) * sqrt(youngs_modulus_pa * second_moment / (density_kg_m3 * area))
    return {
        "kind": "euler_bernoulli_cantilever_first_bending_mode_reference",
        "inputs_si": values,
        "cross_section_area_m2": area,
        "second_moment_area_m4": second_moment,
        "first_bending_frequency_hz": frequency,
        "assumptions": [
            "uniform straight rectangular beam", "linear elastic material", "perfect clamp", "Euler-Bernoulli slender-beam behavior", "vacuum or negligible fluid loading",
        ],
        "validity": {
            "slenderness_ratio": length_m / thickness_m,
            "guidance": "First verify Solid Mechanics eigenfrequency against this value. Then add Pressure Acoustics and an Acoustic-Structure Boundary; fluid added mass and radiation damping will shift the coupled response.",
        },
    }
