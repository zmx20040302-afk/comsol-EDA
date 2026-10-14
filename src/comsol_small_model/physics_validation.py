from __future__ import annotations

import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def validate_physics_results(
    physics_ids: list[str] | tuple[str, ...],
    values: dict[str, Any],
    *,
    thresholds: dict[str, float] | None = None,
    evidence_paths: list[str | Path] | None = None,
) -> dict[str, Any]:
    """Apply common conservation, range, direction, and resolution checks."""
    physics = {str(item) for item in physics_ids}
    limits = {
        "balance_relative": 0.05,
        "mesh_change_relative": 0.05,
        "reference_relative": 0.05,
        "wavelength_elements_min": 6.0,
        **(thresholds or {}),
    }
    checks: list[dict[str, Any]] = []

    def check(rule: str, actual: Any, threshold: Any, passed: bool, severity: str, message: str) -> None:
        checks.append({
            "rule": rule, "inputs": actual, "calculated_value": actual, "threshold": threshold,
            "passed": bool(passed), "severity": severity, "message": message,
            "evidence_paths": [str(path) for path in (evidence_paths or [])],
        })

    if {"heat_transfer_solids", "heat_transfer_fluids"}.intersection(physics):
        _balance_check(checks, values, "heat_power_in", "heat_power_out", "HEAT_ENERGY_BALANCE", limits["balance_relative"])
        if _has(values, "temperature_min", "temperature_max"):
            low, high = _float(values["temperature_min"]), _float(values["temperature_max"])
            finite = math.isfinite(low) and math.isfinite(high) and low <= high and low > 0
            check("HEAT_TEMPERATURE_RANGE", {"min": low, "max": high}, "0 < min <= max", finite, "error", "温度应为有限正值且最小值不高于最大值。")
        _mesh_check(check, values, limits)

    if "electric_currents" in physics:
        _balance_check(checks, values, "current_in", "current_out", "CURRENT_CONTINUITY", limits["balance_relative"])
        if "electric_power" in values:
            power = _float(values["electric_power"])
            check("ELECTRIC_POWER_SIGN", power, ">= 0", math.isfinite(power) and power >= 0, "error", "耗散电功率应为非负有限值。")
        if "has_terminal" in values or "has_ground" in values:
            complete = bool(values.get("has_terminal")) and bool(values.get("has_ground"))
            check("ELECTRIC_BOUNDARY_COMPLETENESS", {"terminal": bool(values.get("has_terminal")), "ground": bool(values.get("has_ground"))}, "both true", complete, "error", "电流模型需要端子和接地。")

    if "solid_mechanics" in physics:
        _balance_check(checks, values, "applied_force", "reaction_force", "SOLID_REACTION_BALANCE", limits["balance_relative"], signed=True)
        for key, rule in (("displacement_max", "SOLID_DISPLACEMENT_FINITE"), ("von_mises_max", "SOLID_STRESS_FINITE")):
            if key in values:
                actual = _float(values[key])
                check(rule, actual, ">= 0 and finite", math.isfinite(actual) and actual >= 0, "error", "结构结果应为有限非负值。")
        if "rigid_body_constrained" in values:
            check("SOLID_RIGID_BODY_CONSTRAINT", bool(values["rigid_body_constrained"]), True, bool(values["rigid_body_constrained"]), "error", "静力结构必须消除刚体运动。")

    if "laminar_flow" in physics:
        _balance_check(checks, values, "mass_flow_in", "mass_flow_out", "FLOW_MASS_BALANCE", limits["balance_relative"])
        if _has(values, "pressure_in", "pressure_out"):
            delta = _float(values["pressure_in"]) - _float(values["pressure_out"])
            check("FLOW_PRESSURE_DROP", delta, ">= 0", math.isfinite(delta) and delta >= 0, "error", "被动流道的入口压力应不低于出口压力。")
        if "reynolds_number" in values:
            reynolds = _float(values["reynolds_number"])
            check("FLOW_LAMINAR_REGIME", reynolds, "< 2300", math.isfinite(reynolds) and 0 <= reynolds < 2300, "warning", "层流模板应位于声明的雷诺数范围。")

    if "pressure_acoustics" in physics:
        if _has(values, "frequency", "reference_frequency"):
            actual, expected = _float(values["frequency"]), _float(values["reference_frequency"])
            relative = _relative_error(actual, expected)
            check("ACOUSTIC_REFERENCE_FREQUENCY", relative, f"<= {limits['reference_relative']}", relative <= limits["reference_relative"], "error", "声学频率应与解析或高等级参考值一致。")
        if "wavelength_elements" in values:
            count = _float(values["wavelength_elements"])
            check("ACOUSTIC_WAVELENGTH_RESOLUTION", count, f">= {limits['wavelength_elements_min']}", count >= limits["wavelength_elements_min"], "error", "每个波长需要足够网格单元。")

    if "electromagnetic_heating" in physics or {"electric_currents", "heat_transfer_solids"}.issubset(physics):
        if _has(values, "electric_power", "joule_heat"):
            relative = _relative_error(_float(values["electric_power"]), _float(values["joule_heat"]))
            check("COUPLING_JOULE_POWER_TRANSFER", relative, f"<= {limits['balance_relative']}", relative <= limits["balance_relative"], "error", "电耗散功率与传入热场的焦耳热应一致。")

    errors = [row for row in checks if not row["passed"] and row["severity"] == "error"]
    warnings = [row for row in checks if not row["passed"] and row["severity"] == "warning"]
    return {
        "schema": "comsol-physics-validation-report",
        "schemaVersion": "1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "physics_ids": sorted(physics),
        "passed": bool(checks) and not errors,
        "summary": {"checks": len(checks), "passed": sum(int(row["passed"]) for row in checks), "errors": len(errors), "warnings": len(warnings)},
        "checks": checks,
        "missing_evidence": _missing_evidence(physics, values),
    }


def _balance_check(checks: list[dict[str, Any]], values: dict[str, Any], in_key: str, out_key: str, rule: str, threshold: float, signed: bool = False) -> None:
    if not _has(values, in_key, out_key):
        return
    left, right = _float(values[in_key]), _float(values[out_key])
    if signed:
        relative = abs(left + right) / max(abs(left), abs(right), 1e-12)
    else:
        relative = abs(abs(left) - abs(right)) / max(abs(left), abs(right), 1e-12)
    checks.append({"rule": rule, "inputs": {in_key: left, out_key: right}, "calculated_value": relative, "threshold": f"<= {threshold}", "passed": relative <= threshold, "severity": "error", "message": "守恒相对残差必须低于阈值。", "evidence_paths": []})


def _mesh_check(check: Any, values: dict[str, Any], limits: dict[str, float]) -> None:
    if "mesh_change_relative" in values:
        change = abs(_float(values["mesh_change_relative"]))
        check("MESH_CONVERGENCE", change, f"<= {limits['mesh_change_relative']}", change <= limits["mesh_change_relative"], "error", "网格加密后的关键结果变化应低于阈值。")


def _missing_evidence(physics: set[str], values: dict[str, Any]) -> list[str]:
    expected: set[str] = set()
    if {"heat_transfer_solids", "heat_transfer_fluids"}.intersection(physics):
        expected.update(("temperature_min", "temperature_max"))
    if "electric_currents" in physics:
        expected.add("electric_power")
    if "solid_mechanics" in physics:
        expected.update(("displacement_max", "von_mises_max"))
    if "laminar_flow" in physics:
        expected.update(("mass_flow_in", "mass_flow_out"))
    if "pressure_acoustics" in physics:
        expected.add("frequency")
    return sorted(expected - set(values))


def _relative_error(actual: float, expected: float) -> float:
    return abs(actual - expected) / max(abs(expected), 1e-12)


def _float(value: Any) -> float:
    return float(value)


def _has(values: dict[str, Any], *keys: str) -> bool:
    return all(key in values and values[key] is not None for key in keys)
