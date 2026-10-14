"""Record a successful COMSOL baseline-output preflight in a case knowledge card."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

from comsol_small_model.case_memory import remember_case


DEFAULT_OUTPUT_UNITS = {
    "_K": "K",
    "_m": "m",
    "_W": "W",
    "_V": "V",
    "_A": "A",
    "_Pa": "Pa",
    "_Hz": "Hz",
}


def _output_units(columns: list[str], overrides: list[str]) -> dict[str, str]:
    units: dict[str, str] = {}
    for item in overrides:
        name, separator, unit = item.partition("=")
        if not separator or not name.strip() or not unit.strip():
            raise ValueError("--output-unit must use COLUMN=UNIT")
        units[name.strip()] = unit.strip()
    for column in columns:
        if column in units:
            continue
        unit = next((value for suffix, value in DEFAULT_OUTPUT_UNITS.items() if column.endswith(suffix)), "")
        if not unit:
            raise ValueError(f"missing explicit unit for baseline output: {column}")
        units[column] = unit
    return units


def main() -> int:
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--card", type=Path, required=True)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--memory-path", type=Path, default=Path("generated/case_memory/case_memory.json"))
    parser.add_argument("--output-unit", action="append", default=[], help="Explicit unit override in COLUMN=UNIT form.")
    args = parser.parse_args()
    card_path = args.card.resolve()
    csv_path = args.csv.resolve()
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
        columns = list(rows[0]) if rows else []
    if len(rows) != 1 or not columns:
        raise ValueError("baseline preflight CSV must contain exactly one data row")
    values: dict[str, float] = {}
    for column in columns:
        value = float(rows[0][column])
        if not math.isfinite(value):
            raise ValueError(f"baseline output {column} is not finite")
        values[column] = value
    units = _output_units(columns, args.output_unit)
    card = json.loads(card_path.read_text(encoding="utf-8"))
    content = dict(card.get("case_content", {}))
    results = list(content.get("results", []))
    for column in columns:
        if column not in results:
            results.append(column)
    content["results"] = results
    card["case_content"] = content
    card["comsol_preflight"] = {
        "kind": "comsol_baseline_scalar_output_preflight",
        "status": "baseline_outputs_available",
        "csv_path": str(csv_path),
        "outputs": values,
        "output_units": units,
        "unit_status": "explicit_or_column_suffix_verified",
        "row_count": 1,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "next_step": "Generate a bounded parametric sweep and keep independent COMSOL holdout points before surrogate training.",
    }
    note = "已通过原始 MPH 基准解确认可导出标量输出；该单点仅用于预检，不能直接训练代理模型。"
    if note not in card.setdefault("thoughts", []):
        card["thoughts"].append(note)
    card["training_stage"] = "scalar_output_preflight_ready"
    card_path.write_text(json.dumps(card, ensure_ascii=False, indent=2), encoding="utf-8")
    memory = remember_case(card, args.memory_path)
    print(json.dumps({"card": str(card_path), "outputs": values, "memory_path": str(args.memory_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

