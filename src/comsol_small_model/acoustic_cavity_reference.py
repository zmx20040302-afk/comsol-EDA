from __future__ import annotations

from math import sqrt
from typing import Any


def rectangular_rigid_cavity_mode_reference(
    *,
    length_x_m: float,
    length_y_m: float,
    sound_speed_m_s: float,
    mode_m: int = 1,
    mode_n: int = 0,
) -> dict[str, Any]:
    """Eigenfrequency reference for a 2D rectangular cavity with rigid walls."""
    if length_x_m <= 0 or length_y_m <= 0 or sound_speed_m_s <= 0:
        raise ValueError("cavity dimensions and sound speed must be greater than zero")
    if mode_m < 0 or mode_n < 0 or (mode_m == 0 and mode_n == 0):
        raise ValueError("at least one nonnegative cavity mode index must be positive")
    frequency = sound_speed_m_s / 2.0 * sqrt((mode_m / length_x_m) ** 2 + (mode_n / length_y_m) ** 2)
    return {
        "kind": "rectangular_rigid_acoustic_cavity_mode_reference",
        "inputs_si": {"length_x_m": length_x_m, "length_y_m": length_y_m, "sound_speed_m_s": sound_speed_m_s, "mode_m": mode_m, "mode_n": mode_n},
        "mode_label": f"({mode_m},{mode_n})",
        "eigenfrequency_hz": frequency,
        "assumptions": ["two-dimensional rectangular cavity", "rigid sound-hard walls", "uniform inviscid lossless medium", "linear acoustics"],
        "validity": {"guidance": "In COMSOL Pressure Acoustics, use a 2D rectangle with Sound Hard Boundary walls and compare the selected eigenmode with this frequency. Review mode ordering and degeneracy before comparing by ordinal mode number."},
    }
