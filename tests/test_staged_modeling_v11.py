from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from comsol_small_model.staged_modeling_v11 import approve_current_step_v11, create_staged_workflow_v11


class StagedModelingV11Tests(unittest.TestCase):
    def test_missing_thermal_boundary_blocks_workflow_and_approval(self) -> None:
        root = Path(__file__).resolve().parents[1] / "tmp" / "test_staged_v11"
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as directory:
            workflow = create_staged_workflow_v11(
                "建立三维散热板稳态固体传热模型，输出最高温度，但环境温度和散热边界尚未给出。",
                memory_path=Path(directory) / "missing_memory.json",
                output_dir=directory,
            )
            self.assertEqual(workflow["status"], "blocked_missing_information")
            self.assertIn("MISSING_THERMAL_BOUNDARY", workflow["requirement_gate_v11"]["reason_codes"])
            with self.assertRaisesRegex(ValueError, "v1.1 requirement completeness gate"):
                approve_current_step_v11(workflow["outputs"]["workflow"], True, output_dir=directory)

    def test_fixed_temperature_ready_case_has_no_stale_question(self) -> None:
        root = Path(__file__).resolve().parents[1] / "tmp" / "test_staged_v11"
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=root) as directory:
            workflow = create_staged_workflow_v11(
                "建立BGA稳态热应力模型，芯片侧保持353 K且板侧保持293 K，板底固定，输出温度和最大应力。",
                memory_path=Path(directory) / "missing_memory.json",
                output_dir=directory,
            )
            self.assertFalse(workflow["requirement_gate_v11"]["blocked"])
            self.assertEqual(workflow["requirement_gate_v11"]["clarification_questions"], [])


if __name__ == "__main__":
    unittest.main()
