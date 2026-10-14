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


if __name__ == "__main__":
    unittest.main()
