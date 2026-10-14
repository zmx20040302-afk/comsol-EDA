from __future__ import annotations

import socket
import tempfile
import unittest
from pathlib import Path

from comsol_small_model.comsol_server import ensure_comsol_server, launch_details


class ComsolServerTests(unittest.TestCase):
    def test_reuses_an_already_listening_server(self) -> None:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        try:
            result = ensure_comsol_server(
                {
                    "comsol_server_host": "127.0.0.1",
                    "comsol_server_port": listener.getsockname()[1],
                    "start_comsol_server": True,
                }
            )
        finally:
            listener.close()
        self.assertTrue(result["ready"])
        self.assertFalse(result["started"])

    def test_disabled_auto_start_is_reported_without_launching(self) -> None:
        result = ensure_comsol_server(
            {
                "comsol_server_host": "127.0.0.1",
                "comsol_server_port": 1,
                "start_comsol_server": False,
            }
        )
        self.assertFalse(result["ready"])
        self.assertFalse(result["started"])
        self.assertIn("start_comsol_server=false", result["message"])

    def test_dedicated_server_binary_is_preferred(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dedicated = root / "comsolmphserver.exe"
            fallback = root / "comsol.exe"
            dedicated.write_text("", encoding="ascii")
            fallback.write_text("", encoding="ascii")
            command, workdir = launch_details(
                {
                    "comsol_server_executable": str(dedicated),
                    "comsol_executable": str(fallback),
                    "comsol_server_multi_connection": True,
                    "comsol_server_silent": True,
                },
                2036,
            )
        self.assertEqual(command[:3], [str(dedicated), "-port", "2036"])
        self.assertIn("-multi", command)
        self.assertIn("-silent", command)
        self.assertEqual(workdir, root)

    def test_comsol_executable_fallback_includes_mphserver_subcommand(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "comsol.exe"
            executable.write_text("", encoding="ascii")
            command, _ = launch_details(
                {"comsol_executable": str(executable), "comsol_server_silent": False},
                2037,
            )
        self.assertEqual(command[:4], [str(executable), "mphserver", "-port", "2037"])

    def test_missing_executables_are_reported(self) -> None:
        self.assertIsNone(launch_details({}, 2036))


if __name__ == "__main__":
    unittest.main()
