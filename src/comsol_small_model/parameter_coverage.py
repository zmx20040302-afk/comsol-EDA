from __future__ import annotations

from typing import Any

import pandas as pd


def assess_parameter_coverage(data: pd.DataFrame, parameter_ranges: dict[str, list[float] | tuple[float, float]], *, bins: int = 5) -> dict[str, Any]:
    """Report one-dimensional sample coverage for declared input ranges."""
    if bins < 2:
        raise ValueError("bins must be at least 2")
    results: dict[str, Any] = {}
    for name, raw_range in parameter_ranges.items():
        if name not in data.columns:
            raise ValueError(f"coverage input column not found: {name}")
        if len(raw_range) != 2:
            raise ValueError(f"coverage range for {name} must contain [minimum, maximum]")
        lower, upper = float(raw_range[0]), float(raw_range[1])
        if not lower < upper:
            raise ValueError(f"coverage range for {name} must have minimum < maximum")
        values = pd.to_numeric(data[name], errors="raise")
        out_of_range = int(((values < lower) | (values > upper)).sum())
        edges = [lower + (upper - lower) * index / bins for index in range(bins + 1)]
        counts = [int(((values >= edges[index]) & (values < edges[index + 1] if index < bins - 1 else values <= edges[index + 1])).sum()) for index in range(bins)]
        empty = [index for index, count in enumerate(counts) if count == 0]
        results[name] = {
            "declared_range": [lower, upper],
            "observed_range": [float(values.min()), float(values.max())],
            "bin_edges": edges,
            "bin_counts": counts,
            "empty_bins": empty,
            "out_of_range_rows": out_of_range,
            "coverage_fraction": (bins - len(empty)) / bins,
        }
    return {
        "kind": "parameter_coverage_assessment",
        "rows": int(len(data)),
        "bins": bins,
        "parameters": results,
        "passed": all(not item["empty_bins"] and item["out_of_range_rows"] == 0 for item in results.values()),
        "guidance": "This is a marginal coverage report. It does not prove multidimensional space-filling coverage; inspect coupled input combinations before surrogate release.",
    }
