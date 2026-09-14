"""Tier 1 — OpenClaw Phase-3.2 passive web arm. Hermetic.

Scrapling-first with an httpx fallback, all network injected: the httpx
path runs on MockTransport, the scrapling path on a fake module in
sys.modules. No test performs a real request — ever.
"""

import sys
import types

import httpx
import pytest

from bridge.openclaw import fetch_arm
from bridge.openclaw.fetch_arm import (
    FETCH_MAX_CHARS,
    FETCH_TIMEOUT_S,
    FetchBackendMissing,
    FetchError,
    check_url,
    default_fetcher,
    fetch,
    fetch_httpx,
    html_to_markdown,
)

HTML = """<html><head><title>Test Page</title>
<script>evil()</script><style>.x{}</style></head>
<body><h1>Hello &amp; bye</h1>
<p>First <a href="/x">link text</a> here.</p>
<ul><li>one</li><li>two</li></ul>
</body></html>"""


def test_timeout_budget():
    assert FETCH_TIMEOUT_S <= 10.0


def test_html_to_markdown_structure():
    md = html_to_markdown(HTML, "https://example.com/p")
    assert "# Test Page" in md or "Test Page" in md
    assert "Hello & bye" in md
    assert "[link text](https://example.com/x)" in md
    assert "- one" in md and "- two" in md
    assert "evil()" not in md and ".x{}" not in md


def test_html_to_markdown_caps_length():
    md = html_to_markdown("<p>" + ("word " * 5000) + "</p>", "https://example.com")
    assert len(md) <= FETCH_MAX_CHARS


async def test_fetch_httpx_serves_markdown():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["user-agent"]
        return httpx.Response(200, text=HTML)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        md = await fetch_httpx("https://example.com/p", client=client)
    assert "Hello & bye" in md
    assert "[link text](https://example.com/x)" in md


async def test_fetch_httpx_raises_on_bad_status():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, text="nope")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(FetchError):
            await fetch_httpx("https://example.com/missing", client=client)


def _fake_scrapling(monkeypatch, html_body=HTML, calls=None):
    page_calls = calls if calls is not None else []

    class FakePage:
        status = 200

    FakePage.html = html_body

    class FakeFetcher:
        @staticmethod
        def get(url, **kw):
            page_calls.append((url, kw))
            return FakePage()

    fake = types.ModuleType("scrapling")
    fetchers = types.ModuleType("scrapling.fetchers")
    fetchers.Fetcher = FakeFetcher
    fake.fetchers = fetchers
    monkeypatch.setitem(sys.modules, "scrapling", fake)
    monkeypatch.setitem(sys.modules, "scrapling.fetchers", fetchers)
    return page_calls


async def test_default_prefers_scrapling(monkeypatch):
    calls = _fake_scrapling(monkeypatch)

    async def _no_http(url, **kw):  # pragma: no cover -- must never run
        raise AssertionError("httpx fallback must not run when scrapling serves")

    monkeypatch.setattr(fetch_arm, "fetch_httpx", _no_http)
    md = await default_fetcher("https://example.com/p")
    assert "Hello & bye" in md
    assert calls and calls[0][0] == "https://example.com/p"


async def test_default_falls_back_when_scrapling_missing(monkeypatch):
    monkeypatch.delitem(sys.modules, "scrapling", raising=False)
    monkeypatch.delitem(sys.modules, "scrapling.fetchers", raising=False)
    seen = []

    async def _fake_http(url, **kw):
        seen.append(url)
        return "# fallback"

    monkeypatch.setattr(fetch_arm, "fetch_httpx", _fake_http)
    assert await default_fetcher("https://example.com/p") == "# fallback"
    assert seen == ["https://example.com/p"]


async def test_default_falls_back_when_scrapling_fails(monkeypatch):
    class Boom:
        status = 500
        html = ""

    class BadFetcher:
        @staticmethod
        def get(url, **kw):
            return Boom()

    fake = types.ModuleType("scrapling")
    fetchers = types.ModuleType("scrapling.fetchers")
    fetchers.Fetcher = BadFetcher
    fake.fetchers = fetchers
    monkeypatch.setitem(sys.modules, "scrapling", fake)
    monkeypatch.setitem(sys.modules, "scrapling.fetchers", fetchers)

    async def _fake_http(url, **kw):
        return "# fallback"

    monkeypatch.setattr(fetch_arm, "fetch_httpx", _fake_http)
    assert await default_fetcher("https://example.com/p") == "# fallback"


async def test_fetch_uses_default_chain_and_validates():
    with pytest.raises(ValueError):
        await fetch("file:///etc/passwd", fetcher=None)


async def test_check_url_shapes():
    assert check_url("https://example.com/x") == "https://example.com/x"
    assert check_url("  http://a.b/  ") == "http://a.b/"
    assert check_url("ftp://x/y") is None
    assert check_url("javascript:alert(1)") is None
    assert check_url("") is None


async def test_fetch_backend_missing_without_any_backend(monkeypatch):
    monkeypatch.delitem(sys.modules, "scrapling", raising=False)
    monkeypatch.delitem(sys.modules, "scrapling.fetchers", raising=False)

    async def _no_http(url, **kw):
        raise FetchBackendMissing("no HTTP client available")

    monkeypatch.setattr(fetch_arm, "fetch_httpx", _no_http)
    with pytest.raises(FetchBackendMissing):
        await default_fetcher("https://example.com/p")
