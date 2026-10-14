from __future__ import annotations

from typing import Any

from .acoustic_cavity_reference import rectangular_rigid_cavity_mode_reference
from .cantilever_reference import cantilever_first_bending_mode_reference
from .electrochemistry_reference import nernst_equilibrium_potential_reference
from .flow_heat_reference import constant_wall_temperature_channel_reference
from .fluid_reference import poiseuille_pipe_reference
from .particle_reference import stokes_settling_reference
from .rf_reference import half_wave_resonator_reference
from .thermoacoustic_reference import uniform_temperature_tube_reference


REFERENCE_CHECKS = {
    "acoustic_rectangular_cavity": rectangular_rigid_cavity_mode_reference,
    "acoustic_structure_cantilever": cantilever_first_bending_mode_reference,
    "electrochemical_nernst": nernst_equilibrium_potential_reference,
    "laminar_pipe_poiseuille": poiseuille_pipe_reference,
    "thermoacoustic_open_tube": uniform_temperature_tube_reference,
    "flow_heat_channel": constant_wall_temperature_channel_reference,
    "particle_stokes_settling": stokes_settling_reference,
    "rf_half_wave_resonator": half_wave_resonator_reference,
}


def evaluate_reference_case(case_type: str, parameters_si: dict[str, Any]) -> dict[str, Any]:
    """Evaluate a declared analytical or conservation reference without claiming a COMSOL solve."""
    evaluator = REFERENCE_CHECKS.get(case_type)
    if evaluator is None:
        supported = ", ".join(sorted(REFERENCE_CHECKS))
        raise ValueError(f"unsupported reference case '{case_type}'; supported cases: {supported}")
    result = evaluator(**parameters_si)
    return {
        "kind": "physics_reference_evaluation",
        "case_type": case_type,
        "execution_status": "reference_only_not_a_comsol_result",
        "passed": True,
        "reference": result,
        "next_comsol_check": _next_comsol_check(case_type),
    }


def _next_comsol_check(case_type: str) -> str:
    checks = {
        "acoustic_rectangular_cavity": "Compare the selected 2D acoustic eigenmode shape and frequency with the rigid-cavity (m,n) reference, rather than relying only on its order in the eigenvalue list.",
        "acoustic_structure_cantilever": "Compare the structural-only first eigenfrequency before adding Pressure Acoustics and an Acoustic-Structure Boundary; then quantify the coupled frequency shift and damping.",
        "electrochemical_nernst": "Sweep the stated activity ratio at zero net Faradaic current and compare equilibrium potential with the Nernst equation before enabling kinetics or transport.",
        "laminar_pipe_poiseuille": "Compare pressure drop and the radial axial-velocity profile with the 2D-axisymmetric Laminar Flow result.",
        "thermoacoustic_open_tube": "Sweep uniform background temperature and compare eigenfrequency with c(T)/(2L); review loss-model selection against the boundary-layer scale.",
        "flow_heat_channel": "Compare area-averaged outlet temperature and integrated wall heat flow with the Nonisothermal Flow result.",
        "particle_stokes_settling": "Compare the late-time particle velocity in a quiescent fluid with Stokes terminal velocity, after confirming the particle Reynolds number remains in range.",
        "rf_half_wave_resonator": "Compare the first RF eigenfrequency with the half-wave reference, then document any shift caused by the actual boundary, geometry, and material-loss choices.",
    }
    return checks[case_type]
