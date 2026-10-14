from __future__ import annotations

from math import sqrt
from typing import Any


SPEED_OF_LIGHT_M_S = 299792458.0


def half_wave_resonator_reference(*, length_m: float, relative_permittivity: float = 1.0, relative_permeability: float = 1.0) -> dict[str, Any]:
    """Lossless uniform half-wave resonator reference in SI units."""
    values = {
        "length_m": length_m,
        "relative_permittivity": relative_permittivity,
        "relative_permeability": relative_permeability,
    }
    if any(float(value) <= 0 for value in values.values()):
        raise ValueError("RF resonator reference inputs must all be greater than zero")
    phase_velocity = SPEED_OF_LIGHT_M_S / sqrt(relative_permittivity * relative_permeability)
    frequency = phase_velocity / (2.0 * length_m)
    return {
        "kind": "lossless_half_wave_resonator_reference",
        "inputs": values,
        "phase_velocity_m_s": phase_velocity,
        "fundamental_frequency_hz": frequency,
        "vacuum_wavelength_m": SPEED_OF_LIGHT_M_S / frequency,
        "assumptions": [
            "uniform lossless medium", "ideal half-wave resonance", "one-dimensional field variation", "no conductor loss, dispersion, or fringing-field correction",
        ],
        "validity": {
            "guidance": "In COMSOL RF, compare the first eigenfrequency with c/(2L*sqrt(epsilon_r*mu_r)). For a practical cavity, document port/end conditions, conductor loss, mesh resolution, and deviations due to fringing or geometry.",
        },
    }
