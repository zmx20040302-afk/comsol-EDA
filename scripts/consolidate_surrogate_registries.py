"""Safely consolidate a legacy surrogate registry into the canonical registry."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from comsol_small_model.surrogate_model_card import consolidate_surrogate_registries  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--canonical",
        type=Path,
        default=ROOT / "generated" / "models" / "surrogate_registry.json",
    )
    parser.add_argument(
        "--legacy",
        type=Path,
        default=ROOT / "generated" / "surrogate_registry.json",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    result = consolidate_surrogate_registries(
        args.canonical,
        args.legacy,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
