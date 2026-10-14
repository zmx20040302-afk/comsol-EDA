from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from comsol_small_model.dac2027_p2_comparison import (
    evaluate_p2,
    load_jsonl,
    parse_llm_output,
    validate_frozen_inputs,
    validate_internal_tasks,
)


class Dac2027P2Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.protocol = json.loads((ROOT / "configs" / "dac2027_p2_protocol.json").read_text(encoding="utf-8"))
        self.tasks = load_jsonl(ROOT / self.protocol["task_set"]["path"])

    def test_frozen_inputs_and_tasks_are_valid(self) -> None:
        self.assertTrue(validate_frozen_inputs(ROOT, self.protocol)["valid"])
        self.assertEqual(validate_internal_tasks(self.tasks, self.protocol)["task_count"], 24)

    def test_llm_json_parser_accepts_fenced_json(self) -> None:
        parsed = parse_llm_output(
            '```json\n{"predicted_interfaces":["solid_mechanics"],"predicted_couplings":[],"predicted_study":"Stationary","predicted_blocked":false}\n```'
        )
        self.assertEqual(parsed["predicted_interfaces"], ["solid_mechanics"])
        self.assertFalse(parsed["predicted_blocked"])

    def test_perfect_four_method_table_evaluates(self) -> None:
        rows = []
        for task in self.tasks:
            for method in self.protocol["methods"]:
                rows.append({
                    "task_id": task["id"], "method": method, "record_status": "measured", "parse_valid": True,
                    "predicted_interfaces": task["interfaces"], "predicted_couplings": task["couplings"],
                    "predicted_study": task["study"], "predicted_blocked": task["expected_blocked"],
                    "completion_seconds": 1.0, "interactions": 1, "human_edits": 0,
                    "provider": "test", "model_id": "test", "model_version": "test",
                    "operator_id": "test", "run_at": "2026-10-13T00:00:00+08:00",
                })
        report = evaluate_p2(self.tasks, rows, self.protocol)
        self.assertEqual(report["measured_response_count"], 96)
        self.assertTrue(all(row["gate_accuracy"] == 1.0 for row in report["methods"].values()))


if __name__ == "__main__":
    unittest.main()

