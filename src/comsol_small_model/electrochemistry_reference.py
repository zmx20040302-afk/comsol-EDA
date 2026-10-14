from __future__ import annotations

from math import log
from typing import Any


GAS_CONSTANT_J_MOL_K = 8.31446261815324
FARADAY_CONSTANT_C_MOL = 96485.33212


def nernst_equilibrium_potential_reference(
    *,
    standard_potential_v: float,
    temperature_k: float,
    electron_count: int,
    oxidized_activity: float,
    reduced_activity: float,
) -> dict[str, Any]:
    """Nernst equilibrium potential for Ox + n e- <-> Red with dimensionless activities."""
    if temperature_k <= 0 or electron_count <= 0 or oxidized_activity <= 0 or reduced_activity <= 0:
        raise ValueError("temperature, electron_count, and activities must all be greater than zero")
    reaction_quotient = oxidized_activity / reduced_activity
    thermal_voltage_per_electron = GAS_CONSTANT_J_MOL_K * temperature_k / (electron_count * FARADAY_CONSTANT_C_MOL)
    correction = thermal_voltage_per_electron * log(reaction_quotient)
    equilibrium_potential = standard_potential_v + correction
    return {
        "kind": "nernst_equilibrium_potential_reference",
        "inputs": {
            "standard_potential_v": standard_potential_v,
            "temperature_k": temperature_k,
            "electron_count": electron_count,
            "oxidized_activity": oxidized_activity,
            "reduced_activity": reduced_activity,
        },
        "reaction_quotient": reaction_quotient,
        "thermal_voltage_per_electron_v": thermal_voltage_per_electron,
        "nernst_correction_v": correction,
        "equilibrium_potential_v": equilibrium_potential,
        "assumptions": [
            "Ox + n e- <-> Red reaction written in the stated reduction direction",
            "dimensionless activities or a stated activity model",
            "electrochemical equilibrium with zero net Faradaic current",
            "uniform prescribed temperature",
        ],
        "validity": {
            "guidance": "In COMSOL, verify reaction stoichiometry, electron count, reference electrode convention, and activity definition. Add Butler-Volmer kinetics and transport only after the equilibrium sign and potential scale are confirmed.",
        },
    }
