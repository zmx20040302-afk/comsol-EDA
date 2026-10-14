"""Mark historical surrogate attempts as superseded by a validated replacement."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from comsol_small_model.surrogate_model_card import mark_surrogates_superseded  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("replacement_id", help="已通过独立 COMSOL 验证的替代模型 ID。")
    parser.add_argument("model_ids", nargs="+", help="要标记为历史版本的模型 ID。")
    parser.add_argument("--reason", required=True, help="明确的替代依据。")
    parser.add_argument(
        "--registry",
        type=Path,
        default=ROOT / "generated" / "models" / "surrogate_registry.json",
    )
    args = parser.parse_args()
    result = mark_surrogates_superseded(
        args.registry,
        args.model_ids,
        replacement_id=args.replacement_id,
        reason=args.reason,
    )
    print(f"replacement={result['replacement_id']}")
    print("superseded=" + ",".join(result["superseded_ids"]))
    print(f"registry={result['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
