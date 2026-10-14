from __future__ import annotations

import json
import os
import re
from pathlib import Path, PurePosixPath
from typing import Any


DEFAULT_CONFIG_PATH = Path("configs/case_sources.json")


class CaseSourceUnavailableError(FileNotFoundError):
    """Raised when a configured case source cannot be reached on this host."""


def load_case_sources(config_path: str | Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    path = Path(config_path)
    if not path.is_file():
        return {"schema": "comsol-case-sources", "schemaVersion": "1.0.0", "sources": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "comsol-case-sources":
        raise ValueError("case source configuration schema is invalid")
    payload.setdefault("sources", [])
    return payload


def resolve_case_source_path(
    value: str,
    *,
    project_root: str | Path = ".",
    config_path: str | Path = DEFAULT_CONFIG_PATH,
) -> Path:
    """Resolve local, POSIX, Windows mirror, or WSL case paths without changing meaning."""
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("path is empty")
    root = Path(project_root).resolve()
    config_file = Path(config_path)
    if not config_file.is_absolute():
        config_file = root / config_file

    # A Windows Path treats /home/... as rooted on the current drive.  Only use
    # Path directly when it really exists, otherwise preserve the POSIX path for
    # source matching and for deployments where the web service runs on Linux.
    direct = Path(raw).expanduser()
    if direct.exists():
        return direct.resolve()
    if not _is_posix_absolute(raw):
        candidate = (root / direct).resolve()
        if candidate.exists():
            return candidate
        raise FileNotFoundError(str(candidate))

    config = load_case_sources(config_file)
    source = _matching_source(raw, config.get("sources", []))
    candidates: list[tuple[str, Path]] = []
    if source:
        mirror = str(source.get("windows_mirror", "")).strip()
        if mirror:
            candidates.append(("Windows 镜像", _map_source_path(raw, source, Path(mirror))))
        distro = str(source.get("wsl_distribution", "")).strip()
        if os.name == "nt" and distro:
            suffix = PurePosixPath(raw).relative_to(PurePosixPath(str(source["source_path"])))
            unc_root = Path(rf"\\wsl.localhost\{distro}") / Path(*PurePosixPath(str(source["source_path"])).parts[1:])
            candidates.append(("WSL", unc_root / Path(*suffix.parts)))
        cache = str(source.get("cache_dir", "")).strip()
        if cache:
            cache_root = Path(cache)
            if not cache_root.is_absolute():
                cache_root = root / cache_root
            candidates.append(("SSH 缓存", _map_source_path(raw, source, cache_root)))
    for _, candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    details = "、".join(label for label, _ in candidates) or "本地目录"
    remote_hint = ""
    if source and not str(source.get("ssh_host", "")).strip():
        remote_hint = "；SSH 主机尚未配置"
    raise CaseSourceUnavailableError(
        f"案例源 {raw} 在当前主机不可访问；已检查 {details}{remote_hint}。"
        "在 Linux 主机运行服务，或在 configs/case_sources.json 配置 Windows 镜像/WSL/SSH 后再读取。"
    )


def case_source_status(
    *,
    project_root: str | Path = ".",
    config_path: str | Path = DEFAULT_CONFIG_PATH,
) -> dict[str, Any]:
    root = Path(project_root).resolve()
    config_file = Path(config_path)
    if not config_file.is_absolute():
        config_file = root / config_file
    config = load_case_sources(config_file)
    rows: list[dict[str, Any]] = []
    for source in config.get("sources", []):
        item = dict(source)
        path = str(item.get("source_path", ""))
        try:
            resolved = resolve_case_source_path(path, project_root=root, config_path=config_file)
            item.update({"available": True, "resolved_path": str(resolved), "message": "案例源可直接读取。"})
        except (OSError, ValueError) as exc:
            item.update({"available": False, "resolved_path": "", "message": str(exc)})
        item["ssh_configured"] = bool(str(item.get("ssh_host", "")).strip())
        rows.append(item)
    return {
        "schema": "comsol-case-source-status",
        "schemaVersion": "1.0.0",
        "platform": os.name,
        "default_source_id": config.get("default_source_id", ""),
        "sources": rows,
    }


def _is_posix_absolute(value: str) -> bool:
    return value.startswith("/") and not re.match(r"^/[A-Za-z]:", value)


def _normal_posix(value: str) -> str:
    return "/" + str(PurePosixPath(value)).lstrip("/")


def _matching_source(value: str, sources: list[Any]) -> dict[str, Any] | None:
    target = _normal_posix(value).rstrip("/")
    for row in sources:
        if not isinstance(row, dict):
            continue
        base = _normal_posix(str(row.get("source_path", ""))).rstrip("/")
        if base and (target == base or target.startswith(base + "/")):
            return row
    return None


def _map_source_path(value: str, source: dict[str, Any], destination_root: Path) -> Path:
    source_root = PurePosixPath(str(source.get("source_path", "/")))
    suffix = PurePosixPath(value).relative_to(source_root)
    return destination_root / Path(*suffix.parts)
