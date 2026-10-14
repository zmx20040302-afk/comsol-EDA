from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from comsol_small_model.remote_assistant import (
    RemoteAssistantError,
    complete_task,
    load_public_config,
    redact_secrets,
    save_config,
)


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class RemoteAssistantTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.settings = root / "assistant.json"
        self.keys = root / "keys.json"

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_save_config_masks_and_preserves_key(self) -> None:
        first = save_config(
            {
                "mode": "api",
                "active_provider": "openai",
                "providers": {"openai": {"api_key": "sk-private", "model": "gpt-6-sol"}},
            },
            self.settings,
            self.keys,
        )
        self.assertTrue(first["providers"]["openai"]["api_key_configured"])
        self.assertNotIn("sk-private", json.dumps(first))
        save_config({"providers": {"openai": {"api_key": ""}}}, self.settings, self.keys)
        self.assertEqual(json.loads(self.keys.read_text(encoding="utf-8"))["openai"], "sk-private")
        self.assertEqual(load_public_config(self.settings, self.keys)["mode"], "api")

    def test_remote_http_url_is_rejected_but_local_http_is_allowed(self) -> None:
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            save_config(
                {"providers": {"openai": {"base_url": "http://example.com/v1"}}},
                self.settings,
                self.keys,
            )
        saved = save_config(
            {"providers": {"openai": {"base_url": "http://127.0.0.1:9999/v1"}}},
            self.settings,
            self.keys,
        )
        self.assertEqual(saved["providers"]["openai"]["base_url"], "http://127.0.0.1:9999/v1")

    def test_redact_secrets_recurses(self) -> None:
        clean = redact_secrets({"api_key": "one", "nested": {"Authorization": "Bearer two", "value": 3}})
        self.assertEqual(clean, {"api_key": "[已隐藏]", "nested": {"Authorization": "[已隐藏]", "value": 3}})

    def test_openai_responses_adapter(self) -> None:
        save_config(
            {"mode": "api", "active_provider": "openai", "providers": {"openai": {"api_key": "secret"}}},
            self.settings,
            self.keys,
        )
        captured: dict[str, object] = {}

        def fake_urlopen(request: object, timeout: int) -> _FakeResponse:
            captured["url"] = getattr(request, "full_url")
            captured["body"] = json.loads(getattr(request, "data").decode("utf-8"))
            captured["timeout"] = timeout
            return _FakeResponse({"output": [{"content": [{"type": "output_text", "text": "完善建议"}]}]})

        with patch("comsol_small_model.remote_assistant.urlopen", fake_urlopen):
            result = complete_task("修复任务", {"password": "do-not-send"}, self.settings, self.keys)
        self.assertEqual(result["answer"], "完善建议")
        self.assertTrue(str(captured["url"]).endswith("/v1/responses"))
        self.assertEqual(captured["body"]["model"], "gpt-6-sol")  # type: ignore[index]
        self.assertNotIn("do-not-send", str(captured["body"]))

    def test_deepseek_chat_completions_adapter(self) -> None:
        save_config(
            {"mode": "api", "active_provider": "deepseek", "providers": {"deepseek": {"api_key": "secret"}}},
            self.settings,
            self.keys,
        )
        captured: dict[str, object] = {}

        def fake_urlopen(request: object, timeout: int) -> _FakeResponse:
            captured["url"] = getattr(request, "full_url")
            captured["body"] = json.loads(getattr(request, "data").decode("utf-8"))
            return _FakeResponse({"choices": [{"message": {"content": "DeepSeek 建议"}}]})

        with patch("comsol_small_model.remote_assistant.urlopen", fake_urlopen):
            result = complete_task("补充任务", {}, self.settings, self.keys)
        self.assertEqual(result["answer"], "DeepSeek 建议")
        self.assertTrue(str(captured["url"]).endswith("/chat/completions"))
        self.assertEqual(captured["body"]["model"], "deepseek-flash")  # type: ignore[index]

    def test_missing_key_has_safe_error(self) -> None:
        with self.assertRaisesRegex(RemoteAssistantError, "尚未配置"):
            complete_task("任务", {}, self.settings, self.keys, provider_override="openai")

    def test_local_codex_needs_no_api_key(self) -> None:
        save_config(
            {"mode": "api", "active_provider": "codex_local"},
            self.settings,
            self.keys,
        )
        with patch(
            "comsol_small_model.remote_assistant._call_local_codex",
            return_value=("本机 Codex 建议", "gpt-test"),
        ):
            result = complete_task("补充任务", {}, self.settings, self.keys)
        self.assertEqual(result["answer"], "本机 Codex 建议")
        self.assertEqual(result["model"], "gpt-test")
        self.assertEqual(result["provider"], "codex_local")


if __name__ == "__main__":
    unittest.main()
