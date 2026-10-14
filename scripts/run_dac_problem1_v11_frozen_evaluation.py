from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from comsol_small_model.physics_dependency_graph import compile_physics_dependency_plan
from comsol_small_model.physics_dependency_graph_v11 import compile_physics_dependency_plan_v11


PROTOCOL = ROOT / "configs" / "dac_problem1_v11_frozen_protocol.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _verify_freeze(protocol: dict[str, Any]) -> None:
    mismatches = []
    for section in ("method_files_sha256", "datasets_sha256"):
        for relative, expected in protocol[section].items():
            actual = _sha256(ROOT / relative)
            if actual != expected:
                mismatches.append({"path": relative, "expected": expected, "actual": actual})
    if mismatches:
        raise RuntimeError("frozen artifact hash mismatch: " + json.dumps(mismatches, ensure_ascii=False))


def _wilson(successes: int, total: int) -> list[float]:
    if total == 0:
        return [0.0, 0.0]
    z = 1.959963984540054
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denominator
    return [round(max(0.0, center - margin), 4), round(min(1.0, center + margin), 4)]


def evaluate(split: str) -> dict[str, Any]:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    _verify_freeze(protocol)
    task_path = ROOT / "benchmarks" / "dac_problem1_v11" / f"{split}_tasks.jsonl"
    tasks = [json.loads(line) for line in task_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    actual_families = {row["family"] for row in tasks}
    expected_families = set(protocol["split_policy"][f"{split}_families"])
    if actual_families != expected_families:
        raise ValueError(f"{split} family declaration mismatch")
    other_families = set(protocol["split_policy"]["development_families"])
    if split == "final":
        other_families.update(protocol["split_policy"]["validation_families"])
    if actual_families & other_families:
        raise ValueError("device-family leakage across splits")
    details = []
    for task in tasks:
        old = compile_physics_dependency_plan(task["requirement"], task.get("domains", []))
        new = compile_physics_dependency_plan_v11(task["requirement"], task.get("domains", []))
        old_blocked = bool(old["decision"]["blocked"] or old["clarification_questions"])
        new_blocked = bool(new["decision"]["blocked"])
        expected = bool(task["expected_blocked"])
        details.append({
            "id": task["id"], "family": task["family"], "status": task["status"],
            "expected_blocked": expected, "v10_blocked": old_blocked, "v11_blocked": new_blocked,
            "v10_gate_ok": old_blocked == expected, "v11_gate_ok": new_blocked == expected,
            "v11_reason_codes": new["decision"]["reason_codes"],
            "v11_missing_fields": new["completeness"]["missing_fields"],
            "v11_selection_exact": set(new["interface_ids"]) == set(task["interfaces"]) and set(new["coupling_ids"]) == set(task["couplings"]),
            "v11_study_exact": new["study"]["type"] == task["study"],
        })
    blocked = [row for row in details if row["expected_blocked"]]
    ready = [row for row in details if not row["expected_blocked"]]
    def gate_summary(prefix: str) -> dict[str, Any]:
        false_safe = sum(not row[f"{prefix}_blocked"] for row in blocked)
        false_block = sum(row[f"{prefix}_blocked"] for row in ready)
        return {
            "gate_accuracy": round(sum(row[f"{prefix}_gate_ok"] for row in details) / len(details), 4),
            "false_safe_count": false_safe,
            "false_safe_rate": round(false_safe / len(blocked), 4),
            "false_safe_wilson95": _wilson(false_safe, len(blocked)),
            "false_block_count": false_block,
            "false_block_rate": round(false_block / len(ready), 4),
            "false_block_wilson95": _wilson(false_block, len(ready)),
        }
    exact = sum(row["v11_selection_exact"] for row in details)
    study = sum(row["v11_study_exact"] for row in details)
    return {
        "schema": "dac-problem1-v11-frozen-evaluation", "schemaVersion": "1.0.0",
        "method_version": protocol["method_version"], "split": split, "post_freeze": True,
        "independently_authored_or_blinded": False, "task_file_sha256": _sha256(task_path),
        "device_families": sorted(actual_families), "task_count": len(tasks),
        "v10_gate": gate_summary("v10"), "v11_gate": gate_summary("v11"),
        "v11_selection": {
            "physics_and_coupling_exact_count": exact,
            "physics_and_coupling_exact_accuracy": round(exact / len(details), 4),
            "study_exact_count": study, "study_exact_accuracy": round(study / len(details), 4),
        },
        "details": details,
        "interpretation_limit": "Post-freeze and family-disjoint by project labels; tasks were project-authored and were neither blinded nor independently adjudicated.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("validation", "final"), required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or ROOT / "generated" / "dac" / f"problem1_v11_{args.split}_report.json"
    if args.split == "final" and output.exists():
        raise RuntimeError("v1.1 final report already exists; one-time evaluation will not overwrite it")
    report = evaluate(args.split)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"split": args.split, "v10_gate": report["v10_gate"], "v11_gate": report["v11_gate"], "v11_selection": report["v11_selection"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
