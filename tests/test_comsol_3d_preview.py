from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from comsol_small_model.comsol_3d_preview import export_mph_stl


class Comsol3dPreviewTests(unittest.TestCase):
    def test_export_compiles_fixed_path_job_and_requires_stl(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            install = root / "Multiphysics"
            javac = install / "java" / "win64" / "jre" / "bin" / "javac.exe"
            batch = install / "bin" / "win64" / "comsolbatch.exe"
            comsol = install / "bin" / "win64" / "comsol.exe"
            for executable in (javac, batch, comsol):
                executable.parent.mkdir(parents=True, exist_ok=True)
                executable.write_bytes(b"exe")
            (install / "plugins").mkdir()
            model = root / "sample model.mph"
            model.write_bytes(b"mph")
            calls = []

            def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                calls.append(command)
                workdir = Path(str(kwargs["cwd"]))
                if command[0] == str(javac):
                    (workdir / "ExportMphStlJob.class").write_bytes(b"class")
                else:
                    model.with_name("sample model_preview.stl").write_bytes(b"0" * 84)
                return subprocess.CompletedProcess(command, 0, "", "")

            with patch("comsol_small_model.comsol_3d_preview.subprocess.run", side_effect=fake_run):
                result = export_mph_stl(
                    model,
                    config={"allow_preview_export": True, "comsol_executable": str(comsol)},
                    working_root=root / "generated",
                )

            self.assertEqual(result["size_bytes"], 84)
            self.assertEqual(len(calls), 2)
            source = (root / "generated" / "comsol_3d_export" / "ExportMphStlJob.java").read_text(encoding="utf-8")
            self.assertIn("sample model.mph", source)
            self.assertNotIn("System.getenv", source)


if __name__ == "__main__":
    unittest.main()
