from __future__ import annotations

import argparse
import json
import platform
import sys
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path


PACKAGES = [
    "cloudpickle",
    "joblib",
    "narwhals",
    "numpy",
    "pandas",
    "pypdf",
    "python-dateutil",
    "pytz",
    "scikit-learn",
    "scipy",
    "six",
    "threadpoolctl",
    "tzdata",
]


def _parse_lock(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "==" not in line:
            continue
        name, version = line.split("==", 1)
        result[name.lower()] = version
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify imports and versions in a rebuilt locked environment")
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    expected = _parse_lock(args.lock)
    observed = {name: metadata.version(name) for name in PACKAGES}
    mismatches = {
        name: {"expected": expected.get(name), "observed": version}
        for name, version in observed.items()
        if expected.get(name) != version
    }

    import joblib  # noqa: F401
    import numpy  # noqa: F401
    import pandas  # noqa: F401
    import pypdf  # noqa: F401
    import scipy  # noqa: F401
    import sklearn  # noqa: F401

    report = {
        "kind": "locked_environment_rebuild_smoke_test",
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "passed": not mismatches,
        "python": platform.python_version(),
        "python_executable": str(Path(sys.executable).resolve()),
        "platform": platform.platform(),
        "lock_path": str(args.lock.resolve()),
        "observed_packages": observed,
        "version_mismatches": mismatches,
        "imports_verified": ["joblib", "numpy", "pandas", "pypdf", "scipy", "sklearn"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if mismatches:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
