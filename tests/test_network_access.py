from __future__ import annotations

import tempfile
from pathlib import Path

import web_app


def test_non_loopback_binding_is_fail_closed() -> None:
    assert web_app.check_bind("127.0.0.1", None) is None
    assert web_app.check_bind("0.0.0.0", None) is not None
    assert web_app.check_bind("0.0.0.0", "short") is not None
    assert web_app.check_bind("0.0.0.0", "x" * 24) is None


def test_access_token_is_generated_once_and_reused() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        path = Path(temporary) / "lan-token.txt"
        first = web_app._read_or_create_access_token(path)
        second = web_app._read_or_create_access_token(path)
        assert first == second
        assert len(first) >= 16


def test_page_forwards_access_token_to_fetch_requests() -> None:
    for page in (web_app.INDEX_HTML, web_app.CONVERSATIONAL_INDEX):
        assert "comsol_eda_lan_token" in page
        assert 'next.headers.set("Authorization", `Bearer ${ACCESS_TOKEN}`)' in page
        assert "function authenticatedUrl(input)" in page
    assert "window.location.href = authenticatedUrl(" in web_app.CONVERSATIONAL_INDEX
    assert "image.src = authenticatedUrl(" in web_app.CONVERSATIONAL_INDEX
