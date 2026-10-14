"""Sequentially export and learn the MPH paths listed in a text manifest."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPORTER = ROOT / "scripts" / "export_mph_code_and_learn.py"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True, help="One absolute MPH path per line.")
    parser.add_argument("--timeout-per-case", type=int, default=900)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()

    paths = [Path(line.strip()) for line in args.manifest.read_text(encoding="utf-8").splitlines() if line.strip() and not line.lstrip().startswith("#")]
    report_path = args.report or ROOT / "generated" / "batch_exports" / f"batch_export_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {
        "kind": "batch_mph_code_export_and_learning",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "manifest": str(args.manifest.resolve()),
        "total": len(paths),
        "cases": [],
    }
    _write(report_path, report)

    for index, mph_path in enumerate(paths, start=1):
        entry: dict[str, object] = {"index": index, "mph_path": str(mph_path), "status": "running"}
        report["cases"].append(entry)
        _write(report_path, report)
        try:
            completed = subprocess.run(
                [sys.executable, str(EXPORTER), "--mph", str(mph_path), "--timeout", str(args.timeout_per_case)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                timeout=args.timeout_per_case + 120,
                check=False,
            )
            entry.update(
                {
                    "status": "completed" if completed.returncode == 0 else "failed",
                    "exit_code": completed.returncode,
                    "stdout_tail": completed.stdout[-3000:],
                    "stderr_tail": completed.stderr[-3000:],
                }
            )
        except subprocess.TimeoutExpired:
            entry.update({"status": "timeout", "error": f"Exceeded {args.timeout_per_case} seconds."})
        except OSError as exc:
            entry.update({"status": "failed", "error": str(exc)})
        _write(report_path, report)
        print(json.dumps(entry, ensure_ascii=False), flush=True)

    completed_count = sum(1 for item in report["cases"] if item.get("status") == "completed")
    report["completed"] = completed_count
    report["failed"] = len(paths) - completed_count
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    _write(report_path, report)
    print(json.dumps({"report": str(report_path), "completed": completed_count, "total": len(paths)}, ensure_ascii=False))
    return 0 if completed_count == len(paths) else 1


def _write(path: Path, report: dict[str, object]) -> None:
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
