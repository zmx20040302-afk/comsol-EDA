"""On-demand browser preview export for existing COMSOL MPH models."""

from __future__ import annotations

import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any


_EXPORT_LOCK = threading.Lock()


class PreviewExportError(RuntimeError):
    """Raised when COMSOL cannot create a browser preview image."""


def resolve_generated_mph(generated_root: str | Path, relative_path: str) -> Path:
    """Resolve an observer MPH path while keeping access inside generated/."""
    root = Path(generated_root).resolve()
    candidate = (root / str(relative_path)).resolve()
    if not candidate.is_relative_to(root) or candidate.suffix.lower() != ".mph":
        raise PreviewExportError("模型路径不在允许的 generated 目录中。")
    if not candidate.is_file():
        raise PreviewExportError("找不到所选 MPH 模型文件。")
    return candidate


def export_mph_preview(
    model_path: str | Path,
    *,
    config: dict[str, Any],
    matlab_script_dir: str | Path,
) -> dict[str, Any]:
    """Use MATLAB LiveLink and an existing mphserver to export one PNG."""
    if not bool(config.get("allow_preview_export", False)):
        raise PreviewExportError("当前节点没有启用 COMSOL 预览导出。")

    model = Path(model_path).resolve()
    matlab = _configured_matlab(config)
    livelink = Path(str(config.get("livelink_matlab_path", ""))).resolve()
    script_dir = Path(matlab_script_dir).resolve()
    exporter = script_dir / "export_mph_preview.m"
    if not livelink.is_dir():
        raise PreviewExportError("找不到 LiveLink for MATLAB 目录。")
    if not exporter.is_file():
        raise PreviewExportError("找不到 export_mph_preview.m。")

    preview = model.with_name(f"{model.stem}_preview.png")
    stl = preview.with_suffix(".stl")
    host = str(config.get("comsol_server_host", "localhost"))
    port = int(config.get("comsol_server_port", 2036))
    expression = (
        f"addpath('{_matlab_quote(livelink)}'); "
        f"addpath('{_matlab_quote(script_dir)}'); "
        f"export_mph_preview('{_matlab_quote(model)}',"
        f"'{_matlab_quote(preview)}','{_matlab_quote(host)}',{port});"
    )
    environment = os.environ.copy()
    environment["COMSOL_MPH_HOST"] = host
    environment["COMSOL_MPH_PORT"] = str(port)
    prefdir = Path(str(config.get("matlab_prefdir", "generated/matlab_prefs")))
    if not prefdir.is_absolute():
        prefdir = script_dir.parent / prefdir
    prefdir = prefdir / f"preview_service_{os.getpid()}"
    prefdir.mkdir(parents=True, exist_ok=True)
    environment["MATLAB_PREFDIR"] = str(prefdir.resolve())
    timeout = max(30, int(config.get("preview_export_timeout_seconds", 300)))

    command = [str(matlab)]
    if os.name == "nt":
        command.append("-wait")
    command.extend(["-batch", expression])
    started = time.monotonic()
    with _EXPORT_LOCK:
        try:
            completed = subprocess.run(
                command,
                cwd=script_dir,
                text=True,
                capture_output=True,
                env=environment,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise PreviewExportError(f"COMSOL 预览导出超过 {timeout} 秒。") from exc
        except OSError as exc:
            raise PreviewExportError(f"无法启动 MATLAB：{exc}") from exc

    stdout = completed.stdout or ""
    stderr = completed.stderr or ""
    if completed.returncode != 0 or not preview.is_file() or preview.stat().st_size == 0:
        details = (stderr or stdout or "MATLAB 没有生成预览文件。")[-3000:].strip()
        raise PreviewExportError(f"COMSOL 预览导出失败（MATLAB 退出码 {completed.returncode}）：{details}")
    return {
        "model_path": str(model),
        "preview_path": str(preview),
        "stl_path": str(stl) if stl.is_file() and stl.stat().st_size else "",
        "stl_size_bytes": stl.stat().st_size if stl.is_file() else 0,
        "size_bytes": preview.stat().st_size,
        "duration_seconds": round(time.monotonic() - started, 3),
        "matlab_output": stdout[-2000:].strip(),
    }


def _configured_matlab(config: dict[str, Any]) -> Path:
    configured = Path(str(config.get("matlab_executable", "")))
    if configured.is_file():
        return configured.resolve()
    common = Path(r"D:\matlab\bin\matlab.exe")
    if common.is_file():
        return common.resolve()
    raise PreviewExportError("找不到 MATLAB 可执行文件，请配置 matlab_executable。")


def _matlab_quote(value: str | Path) -> str:
    return Path(value).as_posix().replace("'", "''") if isinstance(value, Path) else str(value).replace("'", "''")
