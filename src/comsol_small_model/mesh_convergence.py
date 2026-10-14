from __future__ import annotations

from typing import Any


def assess_mesh_convergence(records: list[dict[str, Any]], *, output_name: str, relative_change_threshold_percent: float = 1.0) -> dict[str, Any]:
    """Assess a declared mesh-refinement sequence without claiming solution accuracy."""
    if len(records) < 3:
        raise ValueError("at least three mesh records are required")
    if relative_change_threshold_percent < 0:
        raise ValueError("relative_change_threshold_percent must be nonnegative")
    normalized: list[dict[str, float]] = []
    for index, item in enumerate(records):
        try:
            hmax = float(item["hmax_m"])
            dofs = float(item["dofs"])
            output = float(item["output"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"mesh record {index} requires numeric hmax_m, dofs, and output") from exc
        if hmax <= 0 or dofs <= 0:
            raise ValueError(f"mesh record {index} has nonpositive hmax_m or dofs")
        normalized.append({"hmax_m": hmax, "dofs": dofs, "output": output})
    refinements = [
        normalized[index + 1]["hmax_m"] < normalized[index]["hmax_m"] and normalized[index + 1]["dofs"] > normalized[index]["dofs"]
        for index in range(len(normalized) - 1)
    ]
    changes = []
    for index in range(len(normalized) - 1):
        old, new = normalized[index]["output"], normalized[index + 1]["output"]
        denominator = max(abs(new), abs(old), 1e-12)
        changes.append(abs(new - old) / denominator * 100.0)
    final_change = changes[-1]
    return {
        "kind": "mesh_convergence_assessment",
        "output_name": output_name,
        "records": normalized,
        "relative_change_percent": changes,
        "threshold_percent": relative_change_threshold_percent,
        "refinement_sequence_valid": all(refinements),
        "passed": all(refinements) and final_change <= relative_change_threshold_percent,
        "guidance": "Passing this record only shows the declared output changed little across the final refinements. It does not validate boundary conditions, material data, solver convergence, or all field quantities.",
    }
