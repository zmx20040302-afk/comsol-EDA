from __future__ import annotations

import unittest
from pathlib import Path
import json
import zipfile

from scripts.run_p6_java_dual_path import public_class_name, runner_source
from web_app import _p6_status_payload


class P6ExternalEvidenceTests(unittest.TestCase):
    def test_exported_java_class_name_is_extracted(self) -> None:
        self.assertEqual(public_class_name("public class HeatBackup { }"), "HeatBackup")
        self.assertEqual(public_class_name("public final class FlowHeat_2D { }"), "FlowHeat_2D")

    def test_runner_rebuilds_solves_and_saves_model(self) -> None:
        source = runner_source("HeatBackup", "P6HeatRunner", Path("C:/work/heat rebuilt.mph"))
        self.assertIn("HeatBackup.run()", source)
        self.assertIn("model.study(studies[0]).run()", source)
        self.assertIn("model.save", source)
        self.assertIn("P6_JAVA_OK=1", source)
        self.assertIn("heat rebuilt.mph", source)

    def test_web_status_keeps_local_and_external_gates_separate(self) -> None:
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "p6.json"
            path.write_text(
                json.dumps(
                    {
                        "phase": "P6",
                        "local_readiness_passed": True,
                        "publication_external_gate_passed": False,
                        "gates": {"java_dual_path": True, "temperature_experiment": False},
                    }
                ),
                encoding="utf-8",
            )
            status = _p6_status_payload(path)
        self.assertTrue(status["ok"])
        self.assertTrue(status["local_readiness_passed"])
        self.assertFalse(status["publication_external_gate_passed"])

    def test_p6_release_package_preserves_pending_external_gate(self) -> None:
        root = Path(__file__).resolve().parents[1]
        summary_path = root / "generated" / "p6" / "release" / "release_summary.json"
        if not summary_path.is_file():
            self.skipTest("P6 release package has not been built")
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        archive_path = root / summary["archive"]
        self.assertTrue(summary["local_readiness_passed"])
        self.assertFalse(summary["publication_external_gate_passed"])
        self.assertTrue(summary["mph_class_logs_excluded"])
        with zipfile.ZipFile(archive_path) as archive:
            names = set(archive.namelist())
        self.assertIn("P6_RELEASE_MANIFEST.json", names)
        self.assertIn("P6_COMPLETION_REPORT.md", names)
        self.assertTrue(any(name.endswith("solid_heat_backup.java") for name in names))
        self.assertFalse(any(name.lower().endswith((".mph", ".class", ".log")) for name in names))


if __name__ == "__main__":
    unittest.main()
