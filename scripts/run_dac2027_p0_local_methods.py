from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from comsol_small_model.dac2027_p0_evaluation import prepare_method_response_rows, validate_blind_tasks
from comsol_small_model.physics_dependency_graph_v11 import compile_physics_dependency_plan_v11
from comsol_small_model.physics_selection import select_modeling_intent


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the two deterministic local methods on validated DAC P0 blind tasks.")
    parser.add_argument("--tasks", type=Path, default=ROOT / "benchmarks" / "dac2027_p0" / "blind_tasks.measured.jsonl")
    parser.add_argument("--responses", type=Path, default=ROOT / "benchmarks" / "dac2027_p0" / "method_responses.measured.jsonl")
    parser.add_argument("--force-local", action="store_true")
    args = parser.parse_args()
    protocol = json.loads((ROOT / "configs" / "dac2027_p0_protocol.json").read_text(encoding="utf-8"))
    tasks = load_jsonl(args.tasks)
    validate_blind_tasks(tasks, protocol)
    rows = load_jsonl(args.responses) if args.responses.exists() else prepare_method_response_rows(tasks, protocol)
    by_key = {(row["task_id"], row["method"]): row for row in rows}
    for task in tasks:
        for method in ("existing_selector", "contract_dependency_v11"):
            target = by_key[(task["id"], method)]
            if target.get("record_status") == "measured" and not args.force_local:
                raise RuntimeError(f"refusing to overwrite measured row: {task['id']} / {method}")
            started = time.perf_counter()
            if method == "existing_selector":
                result = select_modeling_intent(task["requirement"], task.get("domains", []))
                interfaces = result["selected_interface_ids"]
                couplings = result["coupling_ids"]
                study = result["study"]["type"]
                blocked = bool(result["abstained"] or result["missing_information"])
                version = str(result["schemaVersion"])
            else:
                result = compile_physics_dependency_plan_v11(task["requirement"], task.get("domains", []))
                interfaces = result["interface_ids"]
                couplings = result["coupling_ids"]
                study = result["study"]["type"]
                blocked = bool(result["decision"]["blocked"])
                version = str(result["schemaVersion"])
            elapsed = time.perf_counter() - started
            target.update({
                "record_status": "measured",
                "predicted_interfaces": interfaces,
                "predicted_couplings": couplings,
                "predicted_study": study,
                "predicted_blocked": blocked,
                "completion_seconds": round(elapsed, 6),
                "interactions": 0,
                "human_edits": 0,
                "provider": "local_deterministic",
                "model_id": method,
                "model_version": version,
                "operator_id": "automated-local-runner",
                "run_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            })
    write_jsonl(args.responses, rows)
    print(json.dumps({"output": str(args.responses), "local_measured_rows": 48, "external_rows_pending": 48}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
