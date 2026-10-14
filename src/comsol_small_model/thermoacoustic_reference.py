from __future__ import annotations

from math import pi, sqrt
from typing import Any


def uniform_temperature_tube_reference(
    *,
    length_m: float,
    temperature_k: float,
    gamma: float = 1.4,
    gas_constant_j_kg_k: float = 287.05,
    dynamic_viscosity_pa_s: float = 1.846e-5,
    density_kg_m3: float = 1.177,
) -> dict[str, Any]:
    """Reference results for an open-open air tube with a uniform background temperature.

    This is a small-signal acoustic check, not a full thermoacoustic instability model.
    """
    values = {
        "length_m": length_m,
        "temperature_k": temperature_k,
        "gamma": gamma,
        "gas_constant_j_kg_k": gas_constant_j_kg_k,
        "dynamic_viscosity_pa_s": dynamic_viscosity_pa_s,
        "density_kg_m3": density_kg_m3,
    }
    if any(float(value) <= 0 for value in values.values()):
        raise ValueError("thermoacoustic reference inputs must all be greater than zero")

    sound_speed = sqrt(gamma * gas_constant_j_kg_k * temperature_k)
    fundamental_frequency = sound_speed / (2.0 * length_m)
    angular_frequency = 2.0 * pi * fundamental_frequency
    viscous_boundary_layer = sqrt(2.0 * dynamic_viscosity_pa_s / (density_kg_m3 * angular_frequency))
    return {
        "kind": "uniform_temperature_open_tube_thermoacoustic_reference",
        "inputs_si": values,
        "sound_speed_m_s": sound_speed,
        "fundamental_frequency_hz": fundamental_frequency,
        "frequency_temperature_sensitivity_per_k": fundamental_frequency / (2.0 * temperature_k),
        "viscous_boundary_layer_m": viscous_boundary_layer,
        "assumptions": [
            "ideal gas with uniform background temperature",
            "small-signal linear acoustics",
            "open-open tube without end correction",
            "no mean flow and no acoustic heat-source feedback",
        ],
        "validity": {
            "temperature_range_note": "Use temperature-dependent gas properties and end corrections for quantitative engineering prediction.",
            "coupling_scope": "A COMSOL first pass can sequence Heat Transfer in Fluids and Pressure Acoustics using the temperature field to define sound speed. Thermoviscous Acoustics or a full thermoacoustic formulation is required when boundary-layer loss or heat-acoustic feedback is material.",
        },
    }
