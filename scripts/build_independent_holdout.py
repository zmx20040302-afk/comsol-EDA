from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from comsol_small_model.thermal_sweep import load_thermal_sweep_spec  # noqa: E402
from comsol_small_model.validation_design import write_independent_thermal_holdout  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an untouched COMSOL validation design.")
    parser.add_argument("--spec", default="configs/thermal_plate_sweep_training.json")
    parser.add_argument("--output-dir", default="generated/validation/thermal_plate")
    parser.add_argument("--count", type=int, default=18)
    parser.add_argument("--seed", type=int, default=20261008)
    args = parser.parse_args()
    result = write_independent_thermal_holdout(
        load_thermal_sweep_spec(args.spec),
        args.output_dir,
        count=args.count,
        seed=args.seed,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
