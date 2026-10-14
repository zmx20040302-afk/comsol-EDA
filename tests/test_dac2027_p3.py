from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from comsol_small_model.dac2027_p3_evaluation import (
    evaluate_p3,
    expected_response_keys,
    prepare_response_rows,
    validate_case_isolation,
    validate_frozen_assets,
)


class Dac2027P3Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.protocol = json.loads((ROOT / "configs" / "dac2027_p3_protocol.json").read_text(encoding="utf-8"))
        self.tasks = []
        for family_index in range(8):
            for status in ("complete", "missing", "conflict"):
                self.tasks.append({
                    "id": f"external-{family_index}-{status}",
                    "family": f"new_external_family_{family_index}",
                    "status": status,
                    "requirement": f"external requirement {family_index} {status}",
                    "domains": [],
                    "interfaces": ["heat_transfer_solids"],
                    "couplings": [],
                    "study": "Stationary",
                    "expected_blocked": status != "complete",
                    "record_status": "measured",
                    "author_id": f"author-{family_index}",
                    "author_affiliation": f"external-lab-{family_index}",
                    "adjudicator_id": f"judge-{family_index}",
                    "independence_attestation": True,
                })

    def _perfect_rows(self) -> list[dict]:
        task_by_id = {row["id"]: row for row in self.tasks}
        rows = prepare_response_rows(self.tasks, self.protocol)
        for row in rows:
            task = task_by_id[row["task_id"]]
            row.update({
                "record_status": "measured",
                "parse_valid": True,
                "predicted_interfaces": task["interfaces"],
                "predicted_couplings": task["couplings"],
                "predicted_study": task["study"],
                "predicted_blocked": task["expected_blocked"],
                "completion_seconds": 1.0,
                "interactions": 1,
                "human_edits": 0,
                "provider": "test",
                "model_id": "test-model",
                "model_version": "test-version",
                "operator_id": "test-operator",
                "run_at": "2026-10-14T00:00:00+08:00",
            })
        return rows

    def test_frozen_assets_and_expected_size(self) -> None:
        self.assertTrue(validate_frozen_assets(ROOT, self.protocol)["valid"])
        self.assertEqual(len(expected_response_keys(self.tasks, self.protocol)), 192)

    def test_perfect_repeated_evaluation(self) -> None:
        report = evaluate_p3(ROOT, self.tasks, self._perfect_rows(), self.protocol)
        self.assertEqual(report["measured_observation_count"], 192)
        self.assertEqual(report["family_count"], 8)
        self.assertTrue(all(summary["gate_accuracy"] == 1.0 for summary in report["methods"].values()))
        self.assertEqual(report["repeat_stability"]["direct_llm"]["unanimous_task_count"], 24)

    def test_repeat_variation_is_reported(self) -> None:
        rows = self._perfect_rows()
        target = next(row for row in rows if row["method"] == "direct_llm" and row["repeat_index"] == 3)
        target["predicted_blocked"] = not target["predicted_blocked"]
        report = evaluate_p3(ROOT, self.tasks, rows, self.protocol)
        self.assertEqual(report["repeat_stability"]["direct_llm"]["varying_task_count"], 1)

    def test_invalid_llm_output_counts_as_method_failure(self) -> None:
        rows = self._perfect_rows()
        targets = [row for row in rows if row["method"] == "direct_llm" and row["task_id"] == self.tasks[0]["id"]]
        for target in targets:
            target.update({
                "parse_valid": False,
                "predicted_interfaces": [],
                "predicted_couplings": [],
                "predicted_study": "__invalid__",
                "predicted_blocked": True,
            })
        report = evaluate_p3(ROOT, self.tasks, rows, self.protocol)
        self.assertEqual(report["methods"]["direct_llm"]["failure_taxonomy"]["invalid_output"], 1)
        self.assertEqual(report["methods"]["direct_llm"]["gate_correct_count"], 23)

    def test_family_leakage_is_rejected(self) -> None:
        leaked = copy.deepcopy(self.tasks)
        leaked[0]["family"] = "chip_package"
        with self.assertRaises(ValueError):
            validate_case_isolation(leaked, {"chip_package"})

    def test_missing_repeat_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            evaluate_p3(ROOT, self.tasks, self._perfect_rows()[:-1], self.protocol)


if __name__ == "__main__":
    unittest.main()
