from __future__ import annotations

from math import exp
from typing import Any


def constant_wall_temperature_channel_reference(
    *,
    mass_flow_rate_kg_s: float,
    heat_capacity_j_kg_k: float,
    inlet_temperature_k: float,
    wall_temperature_k: float,
    heat_transfer_coefficient_w_m2_k: float,
    wetted_perimeter_m: float,
    length_m: float,
) -> dict[str, Any]:
    """Plug-flow reference for a channel subject to a uniform wall temperature in SI units."""
    values = {
        "mass_flow_rate_kg_s": mass_flow_rate_kg_s,
        "heat_capacity_j_kg_k": heat_capacity_j_kg_k,
        "heat_transfer_coefficient_w_m2_k": heat_transfer_coefficient_w_m2_k,
        "wetted_perimeter_m": wetted_perimeter_m,
        "length_m": length_m,
    }
    if any(float(value) <= 0 for value in values.values()):
        raise ValueError("flow-heat reference transport inputs must all be greater than zero")
    ntu = heat_transfer_coefficient_w_m2_k * wetted_perimeter_m * length_m / (mass_flow_rate_kg_s * heat_capacity_j_kg_k)
    outlet_temperature = wall_temperature_k - (wall_temperature_k - inlet_temperature_k) * exp(-ntu)
    absorbed_heat = mass_flow_rate_kg_s * heat_capacity_j_kg_k * (outlet_temperature - inlet_temperature_k)
    return {
        "kind": "constant_wall_temperature_channel_reference",
        "inputs_si": {**values, "inlet_temperature_k": inlet_temperature_k, "wall_temperature_k": wall_temperature_k},
        "number_of_transfer_units": ntu,
        "outlet_temperature_k": outlet_temperature,
        "heat_to_fluid_w": absorbed_heat,
        "assumptions": [
            "steady single-phase flow", "constant properties", "uniform wall temperature",
            "plug-flow energy balance with prescribed effective heat-transfer coefficient",
        ],
        "validity": {
            "outlet_bounded_by_inlet_and_wall": min(inlet_temperature_k, wall_temperature_k) <= outlet_temperature <= max(inlet_temperature_k, wall_temperature_k),
            "guidance": "In COMSOL, compare the area-averaged outlet temperature and integrated wall heat flow. Determine the heat-transfer coefficient from a resolved flow/thermal solution rather than using this reference as a substitute for it.",
        },
    }
