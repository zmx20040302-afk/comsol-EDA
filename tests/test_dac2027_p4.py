from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str, relative: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {relative}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


prepare = load_script("prepare_dac2027_p4", "scripts/prepare_dac2027_p4.py")
finalize = load_script("finalize_dac2027_p4", "scripts/finalize_dac2027_p4.py")


class Dac2027P4Tests(unittest.TestCase):
    def test_pdf_format_sections_and_anonymity(self) -> None:
        report = prepare.inspect_pdf()
        self.assertTrue(report["passed"], report.get("errors"))
        self.assertLessEqual(report["body_page_count"], 6)
        self.assertEqual(report["reference_page_count"], 1)
        self.assertTrue(report["checks"]["letter_page_size"])
        self.assertTrue(report["checks"]["anonymous_metadata"])
        self.assertTrue(report["checks"]["no_personal_path_or_email"])

    def test_reproducibility_archive_matches_manifest(self) -> None:
        report = prepare.verify_reproducibility_package()
        self.assertTrue(report["passed"], report.get("errors"))
        self.assertGreaterEqual(report["checked_file_count"], 20)

    def test_p4_infrastructure_and_evidence_boundary(self) -> None:
        status = prepare.build_status()
        self.assertTrue(status["p4_infrastructure_gate_passed"])
        self.assertTrue(status["p1_submission_gate_passed"])
        self.assertTrue(status["p2_development_gate_passed"])
        p3 = json.loads((ROOT / "generated" / "dac2027" / "p3" / "readiness_status.json").read_text(encoding="utf-8"))
        self.assertEqual(status["p3_external_main_result_gate_passed"], bool(p3.get("p3_main_result_gate_passed")))
        self.assertFalse(status["p4_final_submission_gate_passed"])
        self.assertFalse(status["human_author_approval_recorded"])

    def test_approval_requires_hashes_and_every_human_check(self) -> None:
        approval = finalize.approval_template("a" * 64, "b" * 64)
        approval.update({"approved": True, "approved_by": "Author", "approved_at": "2026-10-14T12:00:00+08:00"})
        incomplete = prepare.validate_human_approval(approval, "a" * 64, "b" * 64)
        self.assertFalse(incomplete["passed"])
        self.assertIn("claims_verified", incomplete["errors"])
        approval["checks"] = {name: True for name in prepare.REQUIRED_APPROVAL_CHECKS}
        complete = prepare.validate_human_approval(approval, "a" * 64, "b" * 64)
        self.assertTrue(complete["passed"], complete["errors"])
        self.assertFalse(prepare.validate_human_approval(approval, "c" * 64, "b" * 64)["passed"])

    def test_finalization_is_explicitly_blocked_without_external_evidence(self) -> None:
        status = finalize.build_finalization_status()
        self.assertEqual(status["status"], "blocked_by_external_evidence")
        self.assertFalse(status["finalization_ready"])
        self.assertEqual(status["p3_task_count"], 0)
        self.assertEqual(status["p3_observation_count"], 0)
        self.assertFalse(status["approval_template_generated"])

    def test_finalizer_rejects_unverified_p3_result(self) -> None:
        readiness = json.loads((ROOT / "generated" / "dac2027" / "p3" / "readiness_status.json").read_text(encoding="utf-8"))
        report_path, error = finalize.verified_p3_report(ROOT, readiness)
        self.assertIsNone(report_path)
        self.assertIn("closed", error)


if __name__ == "__main__":
    unittest.main()
