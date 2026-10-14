from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "start_local_service.py"
SPEC = importlib.util.spec_from_file_location("start_local_service", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
start_local_service = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(start_local_service)


class StartLocalServiceTests(unittest.TestCase):
    def test_windows_launchers_start_worker_and_preview_server(self) -> None:
        root = SCRIPT.parents[1]
        for launcher_name in ("start_windows.bat", "start_local_8880.bat"):
            launcher = (root / launcher_name).read_text(encoding="utf-8")
            self.assertIn("--with-worker", launcher, launcher_name)
            self.assertIn("--ensure-comsol-server", launcher, launcher_name)

    def test_explicit_server_start_supports_preview_without_enabling_full_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            config_dir = root / "configs"
            config_dir.mkdir()
            (config_dir / "execution_node.json").write_text(
                '{"allow_preview_export": true, "allow_external_execution": false, '
                '"start_comsol_server": false}',
                encoding="utf-8",
            )
            with patch.object(start_local_service, "ensure_comsol_server") as ensure:
                ensure.return_value = {"ready": True}
                result = start_local_service._ensure_startup_server(root)
            self.assertTrue(result["ready"])
            called_config = ensure.call_args.args[0]
            self.assertTrue(called_config["start_comsol_server"])
            self.assertFalse(called_config["allow_external_execution"])

    def test_reported_port_only_reads_current_launch_log_section(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            log_path = Path(temporary) / "web_startup.log"
            log_path.write_text("COMSOL small model web app: http://127.0.0.1:8881\n", encoding="utf-8")
            start_offset = log_path.stat().st_size
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write("COMSOL small model web app: http://127.0.0.1:8880\n")
            self.assertEqual(start_local_service._reported_port(log_path, start_offset), 8880)

    def test_log_tail_handles_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            self.assertIn("尚未生成", start_local_service._log_tail(Path(temporary) / "missing.log"))


if __name__ == "__main__":
    unittest.main()
