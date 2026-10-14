from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from comsol_small_model.p6_baseline_evaluation import evaluate_baselines, prepare_baseline_template


class P6BaselineEvaluationTests(unittest.TestCase):
    def _assets(self, root: Path, task_count: int = 2) -> tuple[Path, Path, Path]:
        task_report = root / "tasks.json"
        task_report.write_text(
            json.dumps({"rows": [{"id": f"task-{index}", "domain": "heat", "category": "complete"} for index in range(task_count)]}),
            encoding="utf-8",
        )
        config = root / "config.json"
        config.write_text(
            json.dumps(
                {
                    "comparison_methods": ["human_comsol", "direct_llm", "staged_platform"],
                    "required_task_count_per_method": task_count,
                    "fixed_task_report": str(task_report),
                }
            ),
            encoding="utf-8",
        )
        template = root / "template.csv"
        return task_report, config, template

    def test_template_rows_do_not_count_as_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task_report, config, template = self._assets(root)
            prepare_baseline_template(task_report, config, template)
            report = evaluate_baselines(template, config)
        self.assertEqual(report["status"], "awaiting_measurements")
        self.assertFalse(report["passed"])

    def test_complete_paired_evidence_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task_report, config, template = self._assets(root)
            prepare_baseline_template(task_report, config, template)
            frame = pd.read_csv(template, dtype="string")
            frame["record_status"] = "measured"
            for column in ("completed", "physics_correct", "build_passed", "solve_passed", "validation_passed"):
                frame[column] = "true"
            frame["false_safe"] = "false"
            frame["completion_seconds"] = "10"
            frame["human_edits"] = "1"
            frame["interactions"] = "2"
            frame["evaluator_id"] = "blind-evaluator"
            frame["run_id"] = "frozen-run"
            frame.to_csv(template, index=False)
            report = evaluate_baselines(template, config)
        self.assertTrue(report["passed"])
        self.assertEqual(report["measured_row_count"], 6)
        self.assertTrue(all(row["coverage_complete"] for row in report["methods"].values()))

    def test_unknown_task_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            task_report, config, template = self._assets(root)
            prepare_baseline_template(task_report, config, template)
            frame = pd.read_csv(template, dtype="string").iloc[:1].copy()
            frame.loc[:, "record_status"] = "measured"
            frame.loc[:, "task_id"] = "invented-task"
            frame.to_csv(template, index=False)
            with self.assertRaisesRegex(ValueError, "固定任务集之外"):
                evaluate_baselines(template, config)


if __name__ == "__main__":
    unittest.main()
