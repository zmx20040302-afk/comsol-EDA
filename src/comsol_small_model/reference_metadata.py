from __future__ import annotations

from typing import Any


REFERENCE_QUANTITY_METADATA: dict[str, dict[str, dict[str, str]]] = {
    "laminar_pipe_poiseuille": {"pressure_drop_pa": {"unit": "Pa", "label": "Pressure drop"}, "mean_velocity_m_s": {"unit": "m/s", "label": "Mean velocity"}},
    "thermoacoustic_open_tube": {"fundamental_frequency_hz": {"unit": "Hz", "label": "Fundamental frequency"}, "sound_speed_m_s": {"unit": "m/s", "label": "Sound speed"}},
    "flow_heat_channel": {"outlet_temperature_k": {"unit": "K", "label": "Outlet temperature"}, "heat_to_fluid_w": {"unit": "W", "label": "Heat to fluid"}},
    "acoustic_structure_cantilever": {"first_bending_frequency_hz": {"unit": "Hz", "label": "First bending frequency"}},
    "electrochemical_nernst": {"equilibrium_potential_v": {"unit": "V", "label": "Equilibrium potential"}},
    "particle_stokes_settling": {"terminal_velocity_m_s": {"unit": "m/s", "label": "Terminal velocity"}},
    "rf_half_wave_resonator": {"fundamental_frequency_hz": {"unit": "Hz", "label": "Fundamental frequency"}},
    "acoustic_rectangular_cavity": {"eigenfrequency_hz": {"unit": "Hz", "label": "Eigenfrequency"}},
}


def reference_quantity_metadata(case_type: str, reference_key: str) -> dict[str, Any]:
    """Return canonical SI display metadata for a supported reference quantity."""
    return dict(REFERENCE_QUANTITY_METADATA.get(case_type, {}).get(reference_key, {"unit": "", "label": reference_key}))
