from __future__ import annotations

import copy
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .constraints import validate_constraints


PARAMETER_ALIASES = {
    "T_hot": ["热端温度", "hot temperature", "t_hot"],
    "T_cold": ["冷端温度", "cold temperature", "t_cold"],
    "V_left": ["电压", "voltage", "v_left"],
    "p_load": ["载荷", "压力载荷", "load", "pressure load", "p_load"],
    "L": ["长度", "length"],
    "W": ["宽度", "width"],
    "k": ["导热系数", "thermal conductivity"],
    "E": ["弹性模量", "杨氏模量", "elastic modulus", "young's modulus", "young modulus", "e_mod"],
    "E_mod": ["弹性模量", "杨氏模量", "elastic modulus", "young's modulus", "young modulus", "e_mod"],
    "nu": ["泊松比", "poisson ratio"],
    "nu_mat": ["泊松比", "poisson ratio"],
    "rho": ["密度", "density"],
    "rho_mat": ["密度", "density"],
    "Cp": ["比热", "比热容", "heat capacity", "specific heat"],
    "sigma": ["电导率", "electric conductivity", "conductivity"],
    "D": ["扩散系数", "diffusion coefficient", "diffusivity"],
    "c_left": ["左端浓度", "入口浓度", "left concentration"],
    "c_right": ["右端浓度", "出口浓度", "right concentration"],
    "F": ["力", "集中力", "point load", "force"],
    "hmax": ["最大网格尺寸", "网格尺寸", "mesh size", "hmax"],
}


def extract_text_overrides(requirement: str, template_path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(template_path).read_text(encoding="utf-8"))
    specs = _parameter_specs(data)
    text = str(requirement or "").lower()
    overrides, unmatched = {}, []
    for name, aliases in _aliases_for_specs(specs).items():
        if name not in specs:
            continue
        for alias in aliases:
            match = re.search(
                rf"{re.escape(alias.lower())}\s*(?:为|是|=|:|：)?\s*"
                r"([+-]?[0-9]+(?:\.[0-9]+)?(?:e[+-]?\d+)?)\s*([^\s,，。；;]*)",
                text,
            )
            if not match:
                continue
            value = float(match.group(1))
            unit = _clean_unit(match.group(2)) or str(specs[name]["unit"])
            overrides[name] = {"value": value, "unit": unit, "source_alias": alias}
            break
    for name, aliases in _aliases_for_specs(specs).items():
        if name in specs and any(word.lower() in text for word in aliases) and name not in overrides:
            unmatched.append(aliases[0])
    return {
        "overrides": overrides,
        "unmatched": unmatched,
        "template": data["model_name"],
        "matched_parameter_count": len(overrides),
    }


def derive_constraints(template_path: str | Path, overrides: dict[str, Any], output_dir: str | Path) -> dict[str, Any]:
    source = Path(template_path)
    data = json.loads(source.read_text(encoding="utf-8"))
    values = _parameter_specs(data)
    applied, missing, provenance = [], [], []
    for name, value in overrides.items():
        if name not in values:
            missing.append(name)
            continue
        spec = values[name]
        numeric = float(value["value"] if isinstance(value, dict) else value)
        supplied_unit = value.get("unit") if isinstance(value, dict) else None
        if supplied_unit:
            numeric = _convert_unit(numeric, str(supplied_unit), str(spec["unit"]))
        if numeric < float(spec["min"]) or numeric > float(spec["max"]):
            raise ValueError(f"{name}={numeric} outside [{spec['min']}, {spec['max']}]")
        spec["value"] = numeric
        applied.append(name)
        provenance.append({
            "parameter": name,
            "source_value": value.get("value") if isinstance(value, dict) else value,
            "source_unit": supplied_unit or spec["unit"],
            "normalized_value": numeric,
            "normalized_unit": spec["unit"],
            "source_alias": value.get("source_alias", "") if isinstance(value, dict) else "",
        })
    validate_constraints(data)
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    path = destination / f"{data['model_name']}_derived_{stamp}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "path": str(path),
        "model_name": data["model_name"],
        "applied": applied,
        "unknown": missing,
        "provenance": provenance,
        "constraints": data,
    }


def _parameter_specs(data: dict[str, Any]) -> dict[str, dict[str, Any]]:
    groups = [data["geometry"].get("parameters", {}), data["materials"], data["boundary_conditions"], data["mesh"]]
    result = {}
    for group in groups:
        result.update(group)
    return result


def _convert_unit(value: float, supplied: str, expected: str) -> float:
    supplied, expected = _clean_unit(supplied).lower(), _clean_unit(expected).lower()
    if supplied == expected:
        return value
    factors = {
        ("gpa", "pa"): 1e9,
        ("mpa", "pa"): 1e6,
        ("kpa", "pa"): 1e3,
        ("cm", "m"): 1e-2,
        ("mm", "m"): 1e-3,
        ("um", "m"): 1e-6,
        ("µm", "m"): 1e-6,
        ("mm2", "m2"): 1e-6,
        ("cm2", "m2"): 1e-4,
        ("g/cm3", "kg/m3"): 1e3,
    }
    if (supplied, expected) in factors:
        return value * factors[(supplied, expected)]
    if supplied in {"c", "degc", "°c"} and expected == "k":
        return value + 273.15
    raise ValueError(f"unit {supplied} must be {expected}")


def _aliases_for_specs(specs: dict[str, dict[str, Any]]) -> dict[str, list[str]]:
    """Add each parameter identifier as a dependable fallback alias."""
    return {
        name: list(dict.fromkeys(PARAMETER_ALIASES.get(name, []) + [name, name.replace("_", " ")]))
        for name in specs
    }


def _clean_unit(value: str) -> str:
    return str(value or "").strip().replace("^", "").replace("²", "2").replace("³", "3")
