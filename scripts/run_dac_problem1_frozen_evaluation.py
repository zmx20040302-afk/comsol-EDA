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
from comsol_small_model.physics_selection import select_modeling_intent


PROTOCOL = ROOT / "configs" / "dac_problem1_frozen_protocol.json"


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


def _score_selection(task: dict[str, Any], interfaces: set[str], couplings: set[str], study: str) -> dict[str, bool]:
    return {
        "selection_ok": interfaces == set(task["interfaces"]) and couplings == set(task["couplings"]),
        "study_ok": study == task["study"],
    }


def _summarize(details: list[dict[str, Any]], name: str) -> dict[str, Any]:
    exact = sum(row[name]["selection_ok"] for row in details)
    study = sum(row[name]["study_ok"] for row in details)
    total = len(details)
    return {
        "task_count": total,
        "physics_and_coupling_exact_count": exact,
        "physics_and_coupling_exact_accuracy": round(exact / total, 4),
        "physics_and_coupling_exact_wilson95": _wilson(exact, total),
        "study_exact_count": study,
        "study_exact_accuracy": round(study / total, 4),
        "study_exact_wilson95": _wilson(study, total),
    }


def evaluate(split: str) -> dict[str, Any]:
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    _verify_freeze(protocol)
    task_path = ROOT / "benchmarks" / "dac_problem1" / f"{split}_tasks.jsonl"
    tasks = [json.loads(line) for line in task_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    expected_families = set(protocol["split_policy"][f"{split}_families"])
    actual_families = {row["family"] for row in tasks}
    if actual_families != expected_families:
        raise ValueError(f"{split} family declaration mismatch")
    dev = set(protocol["split_policy"]["development_families"])
    if dev & actual_families:
        raise ValueError("device-family leakage from development split")
    if len({row["id"] for row in tasks}) != len(tasks):
        raise ValueError("task ids must be unique")

    details = []
    for task in tasks:
        base = select_modeling_intent(task["requirement"], task.get("domains", []))
        graph = compile_physics_dependency_plan(task["requirement"], task.get("domains", []))
        full_blocked = bool(graph["decision"]["blocked"] or graph["clarification_questions"])
        details.append({
            "id": task["id"],
            "family": task["family"],
            "status": task["status"],
            "expected_blocked": task["expected_blocked"],
            "existing_selector": _score_selection(task, set(base["selected_interface_ids"]), set(base["coupling_ids"]), base["study"]["type"]),
            "dependency_graph": _score_selection(task, set(graph["interface_ids"]), set(graph["coupling_ids"]), graph["study"]["type"]),
            "ungated_accepts": True,
            "full_method_blocked": full_blocked,
            "gate_ok": full_blocked == bool(task["expected_blocked"]),
            "reason_codes": graph["decision"]["reason_codes"],
            "clarification_questions": graph["clarification_questions"],
        })

    blocked = [row for row in details if row["expected_blocked"]]
    complete = [row for row in details if not row["expected_blocked"]]
    false_safe_ungated = sum(row["ungated_accepts"] for row in blocked)
    false_safe_full = sum(not row["full_method_blocked"] for row in blocked)
    false_block_full = sum(row["full_method_blocked"] for row in complete)
    return {
        "schema": "dac-problem1-frozen-evaluation",
        "schemaVersion": "1.0.0",
        "method_version": protocol["method_version"],
        "split": split,
        "post_freeze": True,
        "independently_authored_or_blinded": False,
        "task_file_sha256": _sha256(task_path),
        "device_families": sorted(actual_families),
        "methods": {
            "existing_selector": _summarize(details, "existing_selector"),
            "dependency_graph": _summarize(details, "dependency_graph"),
        },
        "gating": {
            "blocked_task_count": len(blocked),
            "complete_task_count": len(complete),
            "ungated_false_safe_count": false_safe_ungated,
            "ungated_false_safe_rate": round(false_safe_ungated / len(blocked), 4),
            "full_method_false_safe_count": false_safe_full,
            "full_method_false_safe_rate": round(false_safe_full / len(blocked), 4),
            "full_method_false_safe_wilson95": _wilson(false_safe_full, len(blocked)),
            "full_method_false_block_count": false_block_full,
            "full_method_false_block_rate": round(false_block_full / len(complete), 4),
            "full_method_false_block_wilson95": _wilson(false_block_full, len(complete)),
        },
        "details": details,
        "interpretation_limit": "Prospective post-freeze and device-family-disjoint from development by declared labels; tasks were authored within this project and were not blinded or independently adjudicated.",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("validation", "final"), required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or ROOT / "generated" / "dac" / f"problem1_{args.split}_report.json"
    if args.split == "final" and output.exists():
        raise RuntimeError("final report already exists; one-time evaluation will not overwrite it")
    report = evaluate(args.split)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"split": args.split, "methods": report["methods"], "gating": report["gating"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
