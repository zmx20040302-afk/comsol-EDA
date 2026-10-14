"""Shared COMSOL mphserver discovery and lifecycle helpers."""

from __future__ import annotations

import os
import socket
import subprocess
import time
from pathlib import Path
from typing import Any


def can_connect(host: str, port: int, timeout: float = 1.0) -> bool:
    """Return whether a TCP listener accepts connections at ``host:port``."""
    try:
        with socket.create_connection((host, int(port)), timeout=timeout):
            return True
    except (OSError, TypeError, ValueError):
        return False


def launch_details(config: dict[str, Any], port: int) -> tuple[list[str], Path] | None:
    """Build the configured mphserver command, preferring the dedicated binary."""
    server_executable = Path(str(config.get("comsol_server_executable", "")))
    comsol_executable = Path(str(config.get("comsol_executable", "")))
    if server_executable.is_file():
        command = [str(server_executable), "-port", str(port)]
        workdir = server_executable.parent
    elif comsol_executable.is_file():
        command = [str(comsol_executable), "mphserver", "-port", str(port)]
        workdir = comsol_executable.parent
    else:
        return None
    if bool(config.get("comsol_server_multi_connection", True)):
        command.extend(["-multi", "on"])
    if bool(config.get("comsol_server_silent", True)):
        command.append("-silent")
    return command, workdir


def ensure_comsol_server(
    config: dict[str, Any],
    *,
    log_path: str | Path | None = None,
    detached: bool = False,
) -> dict[str, Any]:
    """Connect to or start the configured COMSOL mphserver.

    This function only starts the server when the configured port is not
    reachable. It does not stop an existing server, so it is safe for the web
    launcher and execution worker to share one COMSOL instance.
    """
    host = str(config.get("comsol_server_host", "localhost"))
    port = int(config.get("comsol_server_port", 2036))
    base: dict[str, Any] = {"host": host, "port": port, "started": False}
    if can_connect(host, port):
        return {"ready": True, **base, "message": "COMSOL mphserver 已可连接。"}
    if not bool(config.get("start_comsol_server", True)):
        return {
            "ready": False,
            **base,
            "message": "COMSOL mphserver 未运行，且 start_comsol_server=false。",
        }

    launch = launch_details(config, port)
    if launch is None:
        return {"ready": False, **base, "message": "找不到 COMSOL mphserver 可执行文件。"}
    command, workdir = launch
    resolved_log: Path | None = Path(log_path) if log_path else None
    output = subprocess.DEVNULL
    log_handle = None
    try:
        if resolved_log is not None:
            resolved_log.parent.mkdir(parents=True, exist_ok=True)
            log_handle = resolved_log.open("a", encoding="utf-8")
            output = log_handle
        popen_kwargs: dict[str, Any] = {
            "cwd": workdir,
            "stdout": output,
            "stderr": subprocess.STDOUT,
        }
        if os.name == "nt":
            if detached:
                popen_kwargs["creationflags"] = (
                    getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
                    | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
                )
            else:
                popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        elif detached:
            popen_kwargs["start_new_session"] = True
        process = subprocess.Popen(command, **popen_kwargs)
    except OSError as exc:
        return {
            "ready": False,
            **base,
            "log_path": str(resolved_log) if resolved_log else "",
            "message": f"启动 COMSOL mphserver 失败：{exc}",
        }
    finally:
        if log_handle is not None:
            log_handle.close()

    deadline = time.monotonic() + max(5, int(config.get("comsol_server_startup_timeout_seconds", 60)))
    while time.monotonic() < deadline:
        if can_connect(host, port):
            return {
                "ready": True,
                **base,
                "started": True,
                "pid": process.pid,
                "log_path": str(resolved_log) if resolved_log else "",
                "message": "COMSOL mphserver 已启动并可连接。",
            }
        if process.poll() is not None:
            return {
                "ready": False,
                **base,
                "pid": process.pid,
                "log_path": str(resolved_log) if resolved_log else "",
                "message": f"COMSOL mphserver 提前退出，退出码为 {process.returncode}。",
            }
        time.sleep(1)
    return {
        "ready": False,
        **base,
        "pid": process.pid,
        "log_path": str(resolved_log) if resolved_log else "",
        "message": "COMSOL mphserver 启动超时；请检查许可证和日志。",
    }
