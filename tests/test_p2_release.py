from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from comsol_small_model.requirement_conflicts import detect_requirement_conflicts
from comsol_small_model.requirement_parser import missing_categories, parse_modeling_requirement
from comsol_small_model.staged_modeling import (
    build_workflow_download_archive,
    create_staged_workflow,
    list_staged_workflows,
    retry_failed_stage,
    save_workflow,
)


ROOT = Path(__file__).resolve().parents[1]


class P2ReleaseTests(unittest.TestCase):
    def test_six_explicit_conflict_classes_are_blocked(self) -> None:
        tasks = [json.loads(line) for line in (ROOT / "benchmarks/end_to_end/tasks.jsonl").read_text(encoding="utf-8").splitlines()]
        conflicts = [task for task in tasks if task["category"] == "conflict"]
        self.assertEqual(6, len(conflicts))
        self.assertTrue(all(detect_requirement_conflicts(task["requirement"]) for task in conflicts))

    def test_complete_requirement_is_not_falsely_blocked_for_units(self) -> None:
        requirement = "建立二维钢梁稳态模型，长100 mm高20 mm，左端固定约束，右端100 N载荷，输出位移和应力。"
        contract = parse_modeling_requirement(requirement)
        self.assertNotIn("units", missing_categories(contract, critical_only=True))

    def test_conflicting_workflow_cannot_be_approved(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            workflow = create_staged_workflow(
                "建立一维铜导线稳态电流模型，长度200 mm，同一端子同时设置1 V和接地，输出电流密度。",
                output_dir=folder,
            )
            self.assertEqual("blocked_conflict", workflow["status"])
            self.assertTrue(workflow["conflicts"])

    def test_failed_stage_can_resume_and_archive(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            workflow = create_staged_workflow(
                "建立一维铜棒稳态传热模型，长度100 mm，左端固定温度300 K，右端固定温度350 K，输出最高温度和热流。",
                output_dir=root,
            )
            workflow["status"] = "validation_failed"
            workflow["current_step"] = 9
            workflow["steps"][9]["status"] = "validation_failed"
            path = Path(save_workflow(workflow, root)["workflow"])
            retried = retry_failed_stage(path)
            self.assertEqual("generated", retried["status"])
            self.assertEqual("pending_execution", retried["steps"][9]["status"])
            listed = list_staged_workflows(root)
            self.assertEqual(retried["workflow_id"], listed[0]["workflow_id"])
            archive = build_workflow_download_archive(path)
            self.assertTrue(archive.is_file())
            with zipfile.ZipFile(archive) as handle:
                self.assertIn(path.name, handle.namelist())

    def test_p2_benchmark_has_fixed_matrix_and_zero_false_safe(self) -> None:
        report = json.loads((ROOT / "generated/p2/end_to_end_benchmark.json").read_text(encoding="utf-8"))
        self.assertEqual(60, report["task_matrix"]["task_count"])
        self.assertEqual(6, report["task_matrix"]["domain_count"])
        self.assertEqual(0, report["metrics"]["false_safe_count"])
        self.assertEqual(1.0, report["metrics"]["critical_missing_recall"])
        self.assertEqual(1.0, report["metrics"]["critical_missing_precision"])

    def test_web_interface_exposes_p2_recovery_controls(self) -> None:
        text = (ROOT / "web_app.py").read_text(encoding="utf-8")
        for marker in ("stagedProgressCard", "stagedWorkflowSelect", "/api/staged-workflow/retry-failed", "/api/staged-workflow/download"):
            self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
