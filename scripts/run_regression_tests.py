"""Run the COMSOL small model regression suite with the source directory configured."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    source = ROOT / "src"
    tests = ROOT / "tests"
    command = [sys.executable, "-m", "unittest", "discover", "-s", str(tests), "-p", "test_*.py", "-v"]
    environment = dict(__import__("os").environ)
    environment["PYTHONPATH"] = str(source) + (";" + environment["PYTHONPATH"] if environment.get("PYTHONPATH") else "")
    return subprocess.run(command, cwd=ROOT, env=environment, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
