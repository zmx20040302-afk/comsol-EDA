"""Run one queued local COMSOL execution job without shell quoting issues."""

from __future__ import annotations

import json

from comsol_small_model.execution_jobs import process_next_job


def main() -> None:
    result = process_next_job(job_dir="generated/jobs")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
