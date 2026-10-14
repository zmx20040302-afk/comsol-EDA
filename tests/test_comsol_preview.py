from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from comsol_small_model.comsol_preview import PreviewExportError, export_mph_preview, resolve_generated_mph


class ComsolPreviewTests(unittest.TestCase):
    def test_resolve_generated_mph_rejects_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "generated"
            root.mkdir()
            with self.assertRaises(PreviewExportError):
                resolve_generated_mph(root, "../outside.mph")

    def test_export_runs_matlab_and_requires_created_png(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            model = root / "model.mph"
            model.write_bytes(b"mph")
            matlab = root / "matlab.exe"
            matlab.write_bytes(b"exe")
            livelink = root / "mli"
            livelink.mkdir()
            scripts = root / "scripts"
            scripts.mkdir()
            (scripts / "export_mph_preview.m").write_text("function x=export_mph_preview(varargin), x=''; end", encoding="utf-8")

            def create_preview(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
                model.with_name("model_preview.png").write_bytes(b"png")
                return subprocess.CompletedProcess(args=[], returncode=0, stdout="COMSOL_PREVIEW_PNG=ok", stderr="")

            config = {
                "allow_preview_export": True,
                "matlab_executable": str(matlab),
                "livelink_matlab_path": str(livelink),
                "comsol_server_host": "localhost",
                "comsol_server_port": 2036,
            }
            with patch("comsol_small_model.comsol_preview.subprocess.run", side_effect=create_preview) as runner:
                result = export_mph_preview(model, config=config, matlab_script_dir=scripts)

            self.assertTrue(Path(result["preview_path"]).is_file())
            command = runner.call_args.args[0]
            self.assertEqual(command[0], str(matlab.resolve()))
            self.assertEqual(command[-2], "-batch")
            self.assertIn("localhost',2036", command[-1])


if __name__ == "__main__":
    unittest.main()
