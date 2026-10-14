"""Export COMSOL MPH geometry to binary STL for the browser observer."""

from __future__ import annotations

import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Any


_EXPORT_LOCK = threading.Lock()


class StlExportError(RuntimeError):
    """Raised when COMSOL cannot create an STL geometry preview."""


def export_mph_stl(
    model_path: str | Path,
    *,
    config: dict[str, Any],
    working_root: str | Path,
) -> dict[str, Any]:
    """Compile a one-shot COMSOL Java class and export final geometry as STL."""
    if not bool(config.get("allow_preview_export", False)):
        raise StlExportError("当前节点没有启用 COMSOL 三维预览导出。")

    model = Path(model_path).resolve()
    if not model.is_file() or model.suffix.lower() != ".mph":
        raise StlExportError("找不到要导出的 MPH 模型。")
    stl = model.with_name(f"{model.stem}_preview.stl")
    install_root = _comsol_install_root(config)
    javac = install_root / "java" / "win64" / "jre" / "bin" / "javac.exe"
    batch = install_root / "bin" / "win64" / "comsolbatch.exe"
    plugins = install_root / "plugins" / "*"
    if not javac.is_file() or not batch.is_file():
        raise StlExportError("找不到 COMSOL Java 编译器或批处理程序。")

    workdir = Path(working_root).resolve() / "comsol_3d_export"
    workdir.mkdir(parents=True, exist_ok=True)
    source = workdir / "ExportMphStlJob.java"
    class_file = workdir / "ExportMphStlJob.class"
    batch_log = workdir / "comsol_stl_export.log"
    source.write_text(_java_source(model, stl), encoding="utf-8")
    timeout = max(30, int(config.get("preview_export_timeout_seconds", 300)))
    started = time.monotonic()

    with _EXPORT_LOCK:
        stl.unlink(missing_ok=True)
        compile_result = _run(
            [str(javac), "-encoding", "UTF-8", "-proc:none", "-cp", str(plugins), str(source)],
            cwd=workdir,
            timeout=timeout,
        )
        if compile_result.returncode != 0 or not class_file.is_file():
            details = (compile_result.stderr or compile_result.stdout or "Java 编译没有生成 class 文件。")[-3000:].strip()
            raise StlExportError(f"COMSOL 三维导出器编译失败：{details}")
        batch_result = _run(
            [str(batch), "-inputfile", str(class_file), "-batchlog", str(batch_log)],
            cwd=workdir,
            timeout=timeout,
        )

    if not stl.is_file() or stl.stat().st_size < 84:
        log_text = batch_log.read_text(encoding="utf-8", errors="replace") if batch_log.is_file() else ""
        details = (log_text or batch_result.stderr or batch_result.stdout or "COMSOL 没有生成 STL 文件。")[-4000:].strip()
        raise StlExportError(f"COMSOL 三维几何导出失败：{details}")
    return {
        "model_path": str(model),
        "stl_path": str(stl),
        "size_bytes": stl.stat().st_size,
        "duration_seconds": round(time.monotonic() - started, 3),
        "batch_log": str(batch_log),
    }


def _run(command: list[str], *, cwd: Path, timeout: int) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
        )
    except subprocess.TimeoutExpired as exc:
        raise StlExportError(f"COMSOL 三维导出超过 {timeout} 秒。") from exc
    except OSError as exc:
        raise StlExportError(f"无法启动 COMSOL 三维导出程序：{exc}") from exc


def _comsol_install_root(config: dict[str, Any]) -> Path:
    executable = Path(str(config.get("comsol_executable", "")))
    if executable.is_file() and len(executable.parents) >= 3:
        return executable.resolve().parents[2]
    common = Path(r"D:\COMSOL64\Multiphysics")
    if common.is_dir():
        return common.resolve()
    raise StlExportError("找不到 COMSOL 安装目录，请配置 comsol_executable。")


def _java_source(model: Path, stl: Path) -> str:
    model_text = _java_quote(model.as_posix())
    stl_text = _java_quote(stl.as_posix())
    return f'''import com.comsol.model.Model;
import com.comsol.model.util.ModelUtil;

public final class ExportMphStlJob {{
    public static void main(String[] args) {{
        Model model = null;
        try {{
            ModelUtil.initStandalone(false);
            model = ModelUtil.load("WebPreviewModel", "{model_text}");
            String[] componentTags = model.component().tags();
            if (componentTags.length == 0) throw new IllegalStateException("No component");
            String componentTag = componentTags[0];
            String[] geometryTags = model.component(componentTag).geom().tags();
            if (geometryTags.length == 0) throw new IllegalStateException("No geometry");
            String geometryTag = geometryTags[0];
            model.component(componentTag).geom(geometryTag).run();
            model.component(componentTag).geom(geometryTag).export().setSTLFormat("binary");
            model.component(componentTag).geom(geometryTag).export("{stl_text}");
            System.out.println("COMSOL_PREVIEW_STL={stl_text}");
        }} catch (Throwable error) {{
            error.printStackTrace(System.err);
            System.exit(1);
        }} finally {{
            if (model != null) try {{ ModelUtil.remove(model.tag()); }} catch (Throwable ignored) {{}}
        }}
    }}
}}
'''


def _java_quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
