from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


DEFAULT_SETTINGS: dict[str, Any] = {
    "mode": "api",
    "active_provider": "codex_local",
    "auto_fallback": False,
    "timeout_seconds": 120,
    "providers": {
        "codex_local": {
            "label": "本机 Codex（免密钥）",
            "base_url": "local://codex",
            "model": "default",
            "reasoning_effort": "medium",
        },
        "openai": {
            "label": "Codex / OpenAI",
            "base_url": "https://api.openai.com/v1",
            "model": "gpt-6-sol",
            "reasoning_effort": "medium",
        },
        "deepseek": {
            "label": "DeepSeek",
            "base_url": "https://api.deepseek.com",
            "model": "deepseek-flash",
            "reasoning_effort": "medium",
        },
    },
}

PROVIDERS = ("codex_local", "openai", "deepseek")
REASONING_EFFORTS = ("low", "medium", "high")
_SECRET_WORDS = ("api_key", "apikey", "token", "secret", "password", "authorization", "credential")


class RemoteAssistantError(RuntimeError):
    """A safe, user-facing remote assistant error."""


def redact_secrets(value: Any) -> Any:
    """Recursively hide likely credentials before logging or remote transmission."""
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            result[str(key)] = "[已隐藏]" if any(word in normalized for word in _SECRET_WORDS) else redact_secrets(item)
        return result
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, tuple):
        return [redact_secrets(item) for item in value]
    return value


def load_public_config(settings_path: Path, keys_path: Path) -> dict[str, Any]:
    settings = _load_settings(settings_path)
    keys = _load_json(keys_path, {})
    providers: dict[str, Any] = {}
    for provider in PROVIDERS:
        item = dict(settings["providers"][provider])
        if provider == "codex_local":
            available = _find_codex_executable() is not None
            item["api_key_configured"] = available
            item["available"] = available
            item["requires_api_key"] = False
        else:
            item["api_key_configured"] = bool(str(keys.get(provider, "")).strip())
            item["available"] = True
            item["requires_api_key"] = True
        providers[provider] = item
    return {
        "mode": settings["mode"],
        "active_provider": settings["active_provider"],
        "auto_fallback": settings["auto_fallback"],
        "timeout_seconds": settings["timeout_seconds"],
        "providers": providers,
    }


def save_config(payload: dict[str, Any], settings_path: Path, keys_path: Path) -> dict[str, Any]:
    current = _load_settings(settings_path)
    mode = str(payload.get("mode", current["mode"])).strip().lower()
    provider = str(payload.get("active_provider", current["active_provider"])).strip().lower()
    if mode not in {"offline", "api"}:
        raise ValueError("mode 必须是 offline 或 api")
    if provider not in PROVIDERS:
        raise ValueError("active_provider 必须是 codex_local、openai 或 deepseek")

    updated = deepcopy(current)
    updated["mode"] = mode
    updated["active_provider"] = provider
    updated["auto_fallback"] = bool(payload.get("auto_fallback", current["auto_fallback"]))
    timeout = int(payload.get("timeout_seconds", current["timeout_seconds"]))
    if not 10 <= timeout <= 600:
        raise ValueError("timeout_seconds 必须在 10 到 600 之间")
    updated["timeout_seconds"] = timeout

    incoming_providers = payload.get("providers", {})
    if incoming_providers is not None and not isinstance(incoming_providers, dict):
        raise ValueError("providers 必须是对象")
    incoming_providers = incoming_providers or {}
    keys = _load_json(keys_path, {})
    for name in PROVIDERS:
        incoming = incoming_providers.get(name, {})
        if incoming is not None and not isinstance(incoming, dict):
            raise ValueError(f"providers.{name} 必须是对象")
        incoming = incoming or {}
        target = updated["providers"][name]
        if "base_url" in incoming and name != "codex_local":
            target["base_url"] = _validate_base_url(str(incoming["base_url"]))
        if "model" in incoming:
            target["model"] = _validate_model(str(incoming["model"]))
        if "reasoning_effort" in incoming:
            effort = str(incoming["reasoning_effort"]).strip().lower()
            if effort not in REASONING_EFFORTS:
                raise ValueError("reasoning_effort 必须是 low、medium 或 high")
            target["reasoning_effort"] = effort
        new_key = str(incoming.get("api_key", "")).strip()
        if new_key:
            keys[name] = new_key
        if bool(incoming.get("clear_api_key", False)):
            keys.pop(name, None)

    _write_json(settings_path, updated)
    _write_secret_json(keys_path, keys)
    return load_public_config(settings_path, keys_path)


def complete_task(
    task: str,
    context: Any,
    settings_path: Path,
    keys_path: Path,
    *,
    provider_override: str | None = None,
) -> dict[str, Any]:
    clean_task = str(task).strip()
    if not clean_task:
        raise ValueError("task 不能为空")
    settings = _load_settings(settings_path)
    provider = str(provider_override or settings["active_provider"]).strip().lower()
    if provider not in PROVIDERS:
        raise ValueError("provider 必须是 codex_local、openai 或 deepseek")
    keys = _load_json(keys_path, {})
    api_key = str(keys.get(provider, "")).strip()
    if provider != "codex_local" and not api_key:
        label = settings["providers"][provider]["label"]
        raise RemoteAssistantError(f"尚未配置 {label} API 密钥，请先在“AI 接入设置”中保存密钥。")

    safe_context = redact_secrets(context if context is not None else {})
    context_text = json.dumps(safe_context, ensure_ascii=False, indent=2, default=str)
    if len(context_text) > 12_000:
        context_text = context_text[:12_000] + "\n[上下文已截断]"
    prompt = (
        "你是 COMSOL 本地建模工作台的任务完善助手。请根据任务和本地执行信息，给出可直接采用的补充方案。\n"
        "请明确区分已完成、失败原因、建议修改和下一步验证。不要声称已经修改本地文件或运行本机程序。\n\n"
        f"任务：\n{clean_task}\n\n本地执行信息（已脱敏）：\n{context_text}"
    )
    provider_config = settings["providers"][provider]
    actual_model = str(provider_config["model"])
    if provider == "codex_local":
        answer, actual_model = _call_local_codex(
            prompt,
            provider_config,
            settings["timeout_seconds"],
            settings_path.resolve().parents[1],
        )
    elif provider == "openai":
        answer = _call_openai(prompt, provider_config, api_key, settings["timeout_seconds"])
    else:
        answer = _call_deepseek(prompt, provider_config, api_key, settings["timeout_seconds"])
    return {
        "ok": True,
        "provider": provider,
        "provider_label": provider_config["label"],
        "model": actual_model,
        "answer": answer,
    }


def _call_local_codex(
    prompt: str,
    config: dict[str, Any],
    timeout: int,
    workspace_root: Path,
) -> tuple[str, str]:
    executable = _find_codex_executable()
    if executable is None:
        raise RemoteAssistantError("未找到本机 Codex。请先安装并登录 Codex，或改用自定义 OpenAI / DeepSeek API。")

    output_handle = tempfile.NamedTemporaryFile(prefix="comsol_codex_", suffix=".txt", delete=False)
    output_path = Path(output_handle.name)
    output_handle.close()
    command = [
        str(executable),
        "exec",
        "--ephemeral",
        "--sandbox",
        "read-only",
        "--skip-git-repo-check",
        "--color",
        "never",
        "-C",
        str(workspace_root),
        "-o",
        str(output_path),
    ]
    model = str(config.get("model", "default")).strip()
    if model and model.lower() != "default":
        command.extend(["-m", model])
    effort = str(config.get("reasoning_effort", "medium")).strip().lower()
    if effort in REASONING_EFFORTS:
        command.extend(["-c", f'model_reasoning_effort="{effort}"'])
    command.append("-")

    environment = os.environ.copy()
    environment.setdefault("CODEX_HOME", str(Path.home() / ".codex"))
    try:
        completed = subprocess.run(
            command,
            input=prompt,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout + 15,
            check=False,
            env=environment,
        )
        answer = output_path.read_text(encoding="utf-8", errors="replace").strip() if output_path.is_file() else ""
        diagnostic = f"{completed.stdout}\n{completed.stderr}"
        model_match = re.search(r"(?m)^model:\s*([^\s]+)", diagnostic)
        actual_model = model_match.group(1) if model_match else (model if model.lower() != "default" else "Codex 默认 GPT")
        if completed.returncode != 0:
            raise RemoteAssistantError("本机 Codex 调用失败。请确认 Codex 已登录且网络可用，然后重试。")
        if not answer:
            raise RemoteAssistantError("本机 Codex 已完成请求，但没有返回可显示的文本。")
        return answer, actual_model
    except subprocess.TimeoutExpired as exc:
        raise RemoteAssistantError("本机 Codex 请求超时，请稍后重试或增大超时时间。") from exc
    except OSError as exc:
        raise RemoteAssistantError(f"无法启动本机 Codex：{exc}") from exc
    finally:
        try:
            output_path.unlink(missing_ok=True)
        except OSError:
            pass


def _find_codex_executable() -> Path | None:
    direct = shutil.which("codex")
    if direct:
        return Path(direct)
    local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
    if not local_app_data:
        return None
    bin_root = Path(local_app_data) / "OpenAI" / "Codex" / "bin"
    candidates = sorted(bin_root.glob("*/codex.exe"), key=lambda path: path.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def _call_openai(prompt: str, config: dict[str, Any], api_key: str, timeout: int) -> str:
    payload = {
        "model": config["model"],
        "input": prompt,
        "reasoning": {"effort": config["reasoning_effort"]},
    }
    data = _post_json(f"{config['base_url'].rstrip('/')}/responses", payload, api_key, timeout)
    direct = str(data.get("output_text", "")).strip()
    if direct:
        return direct
    parts: list[str] = []
    for output in data.get("output", []) if isinstance(data.get("output"), list) else []:
        if not isinstance(output, dict):
            continue
        for content in output.get("content", []) if isinstance(output.get("content"), list) else []:
            if isinstance(content, dict) and str(content.get("text", "")).strip():
                parts.append(str(content["text"]).strip())
    if not parts:
        raise RemoteAssistantError("Codex / OpenAI 返回成功，但响应中没有可显示的文本。")
    return "\n\n".join(parts)


def _call_deepseek(prompt: str, config: dict[str, Any], api_key: str, timeout: int) -> str:
    payload = {
        "model": config["model"],
        "messages": [
            {"role": "system", "content": "你是严谨的 COMSOL 建模与 Python 工程助手。"},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
    }
    data = _post_json(f"{config['base_url'].rstrip('/')}/chat/completions", payload, api_key, timeout)
    choices = data.get("choices", [])
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        raise RemoteAssistantError("DeepSeek 返回成功，但响应中没有 choices。")
    message = choices[0].get("message", {})
    answer = str(message.get("content", "")).strip() if isinstance(message, dict) else ""
    if not answer:
        raise RemoteAssistantError("DeepSeek 返回成功，但响应中没有可显示的文本。")
    return answer


def _post_json(url: str, payload: dict[str, Any], api_key: str, timeout: int) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - URL is validated in saved config.
            raw = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = _safe_http_error(exc)
        raise RemoteAssistantError(f"远程 API 请求失败（HTTP {exc.code}）：{detail}") from exc
    except URLError as exc:
        raise RemoteAssistantError(f"无法连接远程 API：{getattr(exc, 'reason', exc)}") from exc
    except TimeoutError as exc:
        raise RemoteAssistantError("远程 API 请求超时，请检查网络或增大超时时间。") from exc
    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RemoteAssistantError("远程 API 返回了无法解析的数据。") from exc
    if not isinstance(result, dict):
        raise RemoteAssistantError("远程 API 返回格式不正确。")
    return result


def _safe_http_error(exc: HTTPError) -> str:
    try:
        raw = exc.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
        if isinstance(data, dict):
            error = data.get("error")
            if isinstance(error, dict):
                return str(error.get("message", "请求被拒绝"))[:500]
            if error:
                return str(error)[:500]
    except Exception:  # noqa: BLE001
        pass
    return "请检查密钥、模型名称、额度和接口地址。"


def _load_settings(path: Path) -> dict[str, Any]:
    loaded = _load_json(path, {})
    result = deepcopy(DEFAULT_SETTINGS)
    if isinstance(loaded, dict):
        if loaded.get("mode") in {"offline", "api"}:
            result["mode"] = loaded["mode"]
        if loaded.get("active_provider") in PROVIDERS:
            result["active_provider"] = loaded["active_provider"]
        result["auto_fallback"] = bool(loaded.get("auto_fallback", result["auto_fallback"]))
        try:
            result["timeout_seconds"] = min(600, max(10, int(loaded.get("timeout_seconds", 120))))
        except (TypeError, ValueError):
            pass
        source_providers = loaded.get("providers", {})
        if isinstance(source_providers, dict):
            for name in PROVIDERS:
                source = source_providers.get(name, {})
                if not isinstance(source, dict):
                    continue
                for field in ("base_url", "model", "reasoning_effort"):
                    if source.get(field):
                        result["providers"][name][field] = source[field]
    return result


def _validate_base_url(value: str) -> str:
    value = value.strip().rstrip("/")
    parsed = urlparse(value)
    if not parsed.hostname or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ValueError("API 地址格式不正确")
    is_local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
    if parsed.scheme != "https" and not (is_local and parsed.scheme == "http"):
        raise ValueError("远程 API 地址必须使用 HTTPS；本机 localhost 可使用 HTTP")
    return value


def _validate_model(value: str) -> str:
    value = value.strip()
    if not value or len(value) > 100 or not re.fullmatch(r"[A-Za-z0-9._:/-]+", value):
        raise ValueError("模型名称格式不正确")
    return value


def _load_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return deepcopy(default)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return deepcopy(default)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_secret_json(path: Path, value: Any) -> None:
    _write_json(path, value)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
