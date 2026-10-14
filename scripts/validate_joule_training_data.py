"""Validate the narrow COMSOL Joule-heating benchmark CSV before training."""

from __future__ import annotations

import argparse
import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COPPER_MELTING_POINT_K = 1357.77


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv",
        type=Path,
        default=ROOT / "generated" / "staged_workflows" / "final_code" / "joule_rectangle_auto_solve_results.csv",
    )
    args = parser.parse_args()
    source = args.csv.resolve()
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    values = [(float(row["Vtot_V"]), float(row["Tmax_K"]), float(row["Tavg_K"])) for row in rows]
    finite = bool(values) and all(math.isfinite(value) for row in values for value in row)
    monotonic_temperature = all(values[index][1] >= values[index - 1][1] for index in range(1, len(values)))
    below_melting = finite and max(row[1] for row in values) < COPPER_MELTING_POINT_K
    report = {
        "kind": "joule_rectangle_training_data_validation",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "csv": str(source),
        "sample_count": len(values),
        "checks": {
            "finite_values": finite,
            "tmax_monotonic_with_voltage": monotonic_temperature,
            "below_copper_melting_point": below_melting,
        },
        "ranges": {
            "voltage_v": [min(row[0] for row in values), max(row[0] for row in values)] if values else [],
            "tmax_k": [min(row[1] for row in values), max(row[1] for row in values)] if values else [],
        },
        "training_eligible": finite and monotonic_temperature and below_melting,
        "scope": "Verified 2D copper rectangle Joule-heating benchmark only; do not use as a universal COMSOL dataset.",
    }
    destination = source.with_name(f"{source.stem}_validation.json")
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["training_eligible"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
