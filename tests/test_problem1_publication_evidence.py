from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from comsol_small_model.problem1_publication_evidence import (  # noqa: E402
    evaluate_external_regeneration,
    prepare_external_regeneration_template,
    validate_blind_task_submission,
    write_jsonl,
)


class Problem1PublicationEvidenceTests(unittest.TestCase):
    def test_templates_do_not_count_as_external_measurements(self) -> None:
        tasks = ROOT / "benchmarks" / "dac_problem1_publication" / "external_regeneration_tasks.jsonl"
        (ROOT / "generated" / "test_tmp").mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / "generated" / "test_tmp") as directory:
            response = Path(directory) / "responses.jsonl"
            prepare_external_regeneration_template(tasks, response)
            report = evaluate_external_regeneration(tasks, response)
        self.assertEqual(report["status"], "awaiting_external_model_observations")
        self.assertEqual(report["measured_count"], 0)
        self.assertFalse(report["passed"])

    def test_prepare_preserves_existing_response_file(self) -> None:
        tasks = ROOT / "benchmarks" / "dac_problem1_publication" / "external_regeneration_tasks.jsonl"
        (ROOT / "generated" / "test_tmp").mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / "generated" / "test_tmp") as directory:
            response = Path(directory) / "responses.jsonl"
            prepare_external_regeneration_template(tasks, response)
            before = response.read_bytes()
            second = prepare_external_regeneration_template(tasks, response)
            after = response.read_bytes()
        self.assertEqual(before, after)
        self.assertTrue(second["preserved_existing_file"])

    def test_project_authored_blind_task_is_rejected(self) -> None:
        row = {
            "record_status": "measured",
            "id": "x",
            "family": "f",
            "requirement": "r",
            "expected_interfaces": ["heat_transfer_solids"],
            "expected_couplings": [],
            "expected_study": "Stationary",
            "expected_blocked": False,
            "author_id": "a",
            "author_affiliation": "project_team",
            "authored_at": "2026-10-12T00:00:00Z",
            "adjudicator_id": "b",
            "adjudicated_at": "2026-10-12T01:00:00Z",
        }
        (ROOT / "generated" / "test_tmp").mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=ROOT / "generated" / "test_tmp") as directory:
            path = write_jsonl(Path(directory) / "blind.jsonl", [row])
            report = validate_blind_task_submission(path, minimum_tasks=1, minimum_families=1)
        self.assertFalse(report["passed"])
        self.assertTrue(any("不是外部独立作者" in value for value in report["errors"]))

    def test_end_to_end_contracts_are_frozen_six_unique_templates(self) -> None:
        path = ROOT / "benchmarks" / "dac_problem1_publication" / "end_to_end_contracts.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertEqual(len(rows), 6)
        self.assertEqual(len({row["template_id"] for row in rows}), 6)


if __name__ == "__main__":
    unittest.main()
