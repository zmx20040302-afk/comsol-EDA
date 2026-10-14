from __future__ import annotations

import csv
from math import isfinite
from pathlib import Path
from typing import Any

from .reference_checks import evaluate_reference_case
from .reference_metadata import reference_quantity_metadata


def compare_comsol_observation_to_reference(
    case_type: str,
    parameters_si: dict[str, Any],
    *,
    reference_key: str,
    observed_value: float,
    observed_unit: str = "",
    relative_error_threshold_percent: float = 5.0,
) -> dict[str, Any]:
    """Compare one user-supplied COMSOL value with a declared analytical reference."""
    if relative_error_threshold_percent < 0:
        raise ValueError("relative_error_threshold_percent must be nonnegative")
    baseline = evaluate_reference_case(case_type, parameters_si)
    reference = baseline["reference"]
    if reference_key not in reference or not isinstance(reference[reference_key], (int, float)):
        raise ValueError(f"reference_key must name a numeric result in this reference case: {reference_key}")
    expected = float(reference[reference_key])
    observed = float(observed_value)
    if not isfinite(observed):
        raise ValueError("observed_value must be finite")
    absolute_error = abs(observed - expected)
    relative_error = None if abs(expected) < 1e-12 else absolute_error / abs(expected) * 100.0
    passed = absolute_error <= 1e-12 if relative_error is None else relative_error <= relative_error_threshold_percent
    metadata = reference_quantity_metadata(case_type, reference_key)
    expected_unit = str(metadata.get("unit", ""))
    normalized_observed_unit = observed_unit.strip()
    unit_match = None if not normalized_observed_unit else normalized_observed_unit == expected_unit
    return {
        "kind": "comsol_observation_reference_comparison",
        "case_type": case_type,
        "reference_key": reference_key,
        "expected_reference_value": expected,
        "observed_comsol_value": observed,
        "expected_unit": expected_unit,
        "observed_unit": normalized_observed_unit,
        "unit_match": unit_match,
        "absolute_error": absolute_error,
        "relative_error_percent": relative_error,
        "threshold_percent": relative_error_threshold_percent,
        "passed": passed,
        "reference_execution_status": baseline["execution_status"],
        "guidance": "This compares a user-supplied COMSOL result against the selected reference quantity only. A mismatch can arise from model assumptions, boundary conditions, mesh, material data, study type, or result extraction; it does not by itself select a physics interface.",
    }


def compare_comsol_results_csv_to_reference(
    csv_path: str | Path,
    *,
    observed_result_name: str,
    case_type: str,
    parameters_si: dict[str, Any],
    reference_key: str,
    relative_error_threshold_percent: float = 5.0,
    observed_unit: str = "",
) -> dict[str, Any]:
    """Compare a named scalar exported in a COMSOL ``name,value`` results CSV."""
    source = Path(csv_path)
    with source.open("r", encoding="utf-8", newline="") as handle:
        values = {
            str(row.get("name", "")).strip(): str(row.get("value", "")).strip()
            for row in csv.DictReader(handle)
            if str(row.get("name", "")).strip()
        }
    if observed_result_name not in values:
        raise ValueError(f"results CSV does not contain named value: {observed_result_name}")
    report = compare_comsol_observation_to_reference(
        case_type,
        parameters_si,
        reference_key=reference_key,
        observed_value=float(values[observed_result_name]),
        observed_unit=observed_unit,
        relative_error_threshold_percent=relative_error_threshold_percent,
    )
    report["observed_result_name"] = observed_result_name
    report["results_csv"] = str(source)
    return report
