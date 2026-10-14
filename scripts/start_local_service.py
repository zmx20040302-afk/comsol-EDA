from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from comsol_small_model.comsol_server import ensure_comsol_server  # noqa: E402


def _log_tail(path: Path, max_chars: int = 5000) -> str:
    if not path.is_file():
        return "日志尚未生成。"
    return path.read_text(encoding="utf-8", errors="replace")[-max_chars:].strip()


def _reported_port(path: Path, start_offset: int) -> int | None:
    """Read the port selected by web_app.py from this launch's log section."""
    if not path.is_file():
        return None
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        handle.seek(start_offset)
        text = handle.read()
    matches = re.findall(r"COMSOL small model web app: http://[^:\s]+:(\d+)", text)
    return int(matches[-1]) if matches else None


def _healthy_port(start_port: int, span: int = 20, timeout: float = 3.0) -> int | None:
    for port in range(start_port, start_port + span):
        try:
            with urlopen(f"http://127.0.0.1:{port}/api/health", timeout=timeout) as response:
                if response.status == 200:
                    response.read()
                    return port
        except OSError:
            continue
    return None


def _dac_p0_intake_is_healthy(port: int = 8891, timeout: float = 2.0) -> bool:
    try:
        with urlopen(f"http://127.0.0.1:{port}/", timeout=timeout) as response:
            return response.status == 200 and b"DAC 2027 P0" in response.read(4096)
    except OSError:
        return False


def _start_dac_p0_intake(root: Path, port: int = 8891) -> dict[str, object]:
    if _dac_p0_intake_is_healthy(port):
        return {"started": False, "online": True, "port": port, "message": "P0 采集服务已在运行。"}
    log_path = root / "generated" / "dac2027" / "p0" / "intake_startup.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    flags = (
        getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
        | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
    )
    with log_path.open("a", encoding="utf-8") as log:
        kwargs: dict[str, object] = {
            "cwd": root,
            "stdin": subprocess.DEVNULL,
            "stdout": log,
            "stderr": subprocess.STDOUT,
            "close_fds": True,
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = flags
        else:
            kwargs["start_new_session"] = True
        process = subprocess.Popen(
            [sys.executable, "-u", str(root / "scripts" / "dac2027_p0_intake_server.py"), "--host", "127.0.0.1", "--port", str(port)],
            **kwargs,
        )
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        if _dac_p0_intake_is_healthy(port):
            return {"started": True, "online": True, "port": port, "pid": process.pid, "log_path": str(log_path)}
        exit_code = process.poll()
        if exit_code is not None:
            return {"started": True, "online": False, "port": port, "pid": process.pid, "exit_code": exit_code, "log_path": str(log_path)}
        time.sleep(0.2)
    return {"started": True, "online": False, "port": port, "pid": process.pid, "log_path": str(log_path)}


def _worker_is_online(root: Path) -> bool:
    status_path = root / "generated" / "execution_jobs" / "worker_status.json"
    if not status_path.is_file():
        return False
    try:
        status = json.loads(status_path.read_text(encoding="utf-8"))
        updated_at = datetime.fromisoformat(str(status.get("updated_at", "")).replace("Z", "+00:00"))
        age = (datetime.now(timezone.utc) - updated_at).total_seconds()
        return status.get("state") == "running" and 0 <= age <= 15
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return False


def _start_worker(root: Path) -> dict[str, object]:
    if _worker_is_online(root):
        return {"started": False, "online": True, "message": "COMSOL execution worker 已在运行。"}
    log_path = root / "generated" / "execution_jobs" / "worker_startup.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log:
        flags = (
            getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
        )
        kwargs: dict[str, object] = {
            "cwd": root,
            "stdin": subprocess.DEVNULL,
            "stdout": log,
            "stderr": subprocess.STDOUT,
            "close_fds": True,
        }
        if sys.platform == "win32":
            kwargs["creationflags"] = flags
        else:
            kwargs["start_new_session"] = True
        process = subprocess.Popen(
            [sys.executable, str(root / "execution_worker.py"), "--poll-seconds", "5"],
            **kwargs,
        )
    # Importing pandas/scikit-learn on a cold Windows start can take longer
    # than eight seconds, especially while COMSOL is acquiring a license.
    # Wait long enough to report the real worker state instead of a false
    # negative that becomes online a few seconds later.
    deadline = time.monotonic() + 30.0
    while time.monotonic() < deadline:
        if _worker_is_online(root):
            return {"started": True, "online": True, "pid": process.pid, "log_path": str(log_path)}
        exit_code = process.poll()
        if exit_code is not None:
            return {
                "started": True,
                "online": False,
                "pid": process.pid,
                "exit_code": exit_code,
                "log_path": str(log_path),
            }
        time.sleep(0.25)
    return {"started": True, "online": False, "pid": process.pid, "log_path": str(log_path)}


def _ensure_startup_server(root: Path) -> dict[str, object]:
    config_path = root / "configs" / "execution_node.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ready": False, "message": f"无法读取 COMSOL 执行配置：{exc}"}
    if not bool(config.get("allow_preview_export", False) or config.get("allow_external_execution", False)):
        return {
            "ready": False,
            "message": "COMSOL 预览和外部执行均未启用，未启动 mphserver。",
        }
    # ``--ensure-comsol-server`` is an explicit one-shot startup request.  It
    # may connect the read-only preview path even when persistent automatic
    # startup is disabled in execution_node.json.  Full solves remain guarded
    # independently by allow_external_execution.
    connect_config = dict(config)
    connect_config["start_comsol_server"] = True
    log_path = (
        root
        / "generated"
        / "training_runs"
        / f"comsol_mphserver_startup_{datetime.now().strftime('%Y%m%d%H%M%S')}.log"
    )
    return ensure_comsol_server(connect_config, log_path=log_path, detached=True)


def _browser_url(host: str, port: int) -> str:
    browser_host = "127.0.0.1" if host in {"0.0.0.0", "::"} else host
    return f"http://{browser_host}:{port}"


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the COMSOL small model web service detached on Windows")
    parser.add_argument("--port", type=int, default=8880)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--wait-seconds", type=float, default=90.0)
    parser.add_argument("--open", action="store_true", help="Open the ready local service in the default browser.")
    parser.add_argument("--with-worker", action="store_true", help="Start the single-instance local execution worker.")
    parser.add_argument("--with-dac-p0-intake", action="store_true", help="Start or reuse the DAC P0 intake service on port 8891.")
    parser.add_argument("--worker-only", action="store_true", help="Start only the local execution worker.")
    parser.add_argument(
        "--ensure-comsol-server",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Explicitly check and start COMSOL mphserver before launching.",
    )
    args = parser.parse_args()
    root = ROOT
    web_app = root / "web_app.py"
    run_worker = bool(args.with_worker or args.worker_only)
    print(f"launcher_python={sys.executable}", flush=True)
    print("launcher_stage=checking_existing_service", flush=True)
    ensure_server = bool(args.ensure_comsol_server)
    if ensure_server:
        server = _ensure_startup_server(root)
        if server.get("ready"):
            print(f"comsol_server_ready=true host={server.get('host')} port={server.get('port')}")
        else:
            print(f"comsol_server_ready=false message={server.get('message', '')}")
    if run_worker:
        worker = _start_worker(root)
        print(
            f"worker_started={str(bool(worker.get('started'))).lower()} "
            f"worker_online={str(bool(worker.get('online'))).lower()} "
            f"worker_pid={worker.get('pid', '')}"
        )
    if args.with_dac_p0_intake:
        intake = _start_dac_p0_intake(root)
        print(
            f"p0_intake_started={str(bool(intake.get('started'))).lower()} "
            f"p0_intake_online={str(bool(intake.get('online'))).lower()} "
            f"p0_intake_port={intake.get('port', '')} "
            f"p0_intake_pid={intake.get('pid', '')}"
        )
    if args.worker_only:
        return
    existing_port = _healthy_port(args.port, span=1)
    if existing_port is not None:
        print(f"reused=true port={existing_port} ready=true")
        if args.open:
            webbrowser.open(_browser_url(args.host, existing_port))
        return
    print("launcher_stage=starting_web_service", flush=True)
    # MATLAB R2023b can abort in its logging bootstrap when it is launched by
    # a DETACHED_PROCESS parent with no Windows console. Give the web service
    # its own hidden console so on-demand LiveLink preview exports remain
    # reliable while the launcher can still return immediately.
    web_flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
    web_startupinfo = None
    if sys.platform == "win32":
        web_flags |= getattr(subprocess, "CREATE_NEW_CONSOLE", 0x00000010)
        web_startupinfo = subprocess.STARTUPINFO()
        web_startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 0x00000001)
        web_startupinfo.wShowWindow = getattr(subprocess, "SW_HIDE", 0)
    web_log_path = root / "generated" / "training_runs" / "web_startup.log"
    web_log_path.parent.mkdir(parents=True, exist_ok=True)
    log_start_offset = web_log_path.stat().st_size if web_log_path.is_file() else 0
    with web_log_path.open("a", encoding="utf-8") as web_log:
        web_kwargs: dict[str, object] = {
            "cwd": root,
            "stdin": subprocess.DEVNULL,
            "stdout": web_log,
            "stderr": subprocess.STDOUT,
            "close_fds": True,
        }
        if sys.platform == "win32":
            web_kwargs["creationflags"] = web_flags
            web_kwargs["startupinfo"] = web_startupinfo
        else:
            web_kwargs["start_new_session"] = True
        process = subprocess.Popen(
            [sys.executable, "-u", str(web_app), "--host", args.host, "--port", str(args.port)],
            **web_kwargs,
        )
    deadline = time.monotonic() + args.wait_seconds
    started_at = time.monotonic()
    next_progress_at = started_at
    while time.monotonic() < deadline:
        exit_code = process.poll()
        if exit_code is not None:
            raise RuntimeError(
                "网页服务在就绪前退出"
                f"（退出码 {exit_code}）。\n日志：{web_log_path}\n{_log_tail(web_log_path)}"
            )
        reported_port = _reported_port(web_log_path, log_start_offset)
        candidate_port = reported_port or args.port
        # /api/health includes worker and surrogate-runtime status. On a cold
        # Windows filesystem scan it can take a few seconds even though the
        # HTTP listener is already healthy, so do not misclassify it with an
        # aggressively short client timeout.
        active_port = _healthy_port(candidate_port, span=1, timeout=5.0)
        if active_port is not None:
            print(f"started_pid={process.pid} port={active_port} ready=true")
            if args.open:
                webbrowser.open(_browser_url(args.host, active_port))
            return
        now = time.monotonic()
        if now >= next_progress_at:
            elapsed = int(now - started_at)
            print(
                f"launcher_stage=waiting_for_web_service elapsed_seconds={elapsed} "
                f"timeout_seconds={int(args.wait_seconds)}",
                flush=True,
            )
            next_progress_at = now + 5.0
        time.sleep(0.5)
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
    raise RuntimeError(
        f"网页服务在 {args.wait_seconds:g} 秒内没有就绪。\n"
        f"日志：{web_log_path}\n{_log_tail(web_log_path)}"
    )


if __name__ == "__main__":
    main()
