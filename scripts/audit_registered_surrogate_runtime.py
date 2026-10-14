"""Audit every registered surrogate that is approved for scoped prediction."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from comsol_small_model.surrogate_runtime_audit import (  # noqa: E402
    audit_registered_surrogates,
    write_runtime_audit,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--registry",
        type=Path,
        default=ROOT / "generated" / "models" / "surrogate_registry.json",
        help="代理模型注册表路径。",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "generated" / "models" / "surrogate_runtime_audit.json",
        help="JSON 审计报告输出路径。",
    )
    parser.add_argument(
        "--simulate-relocation",
        action="store_true",
        help="在临时目录内模拟模型包迁移和原训练 CSV 不可用。",
    )
    args = parser.parse_args()

    report = audit_registered_surrogates(
        args.registry,
        simulate_relocation=args.simulate_relocation,
    )
    destination = write_runtime_audit(report, args.output)
    print(
        f"registered={report['registered_models']} validated={report['validated_models']} "
        f"superseded={report['superseded_models']} "
        f"active_unvalidated={report['active_unvalidated_models']} "
        f"passed={report['passed']} failed={report['failed']} "
        f"warnings={report['warning_count']} "
        f"feature_name_warnings={report['feature_name_warning_count']} "
        f"missing_artifacts={report['missing_artifacts']}"
    )
    print(f"report={destination}")
    return 0 if report["overall_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
