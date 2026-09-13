"""Tier 1 — hardened resilience contracts (replaces tautological mocks).

High-fidelity boundary tests: jitter, 429 backoff windows, malformed SSE,
partial-stream dropout, router garbage, dead-tool fallback. Hermetic only.
"""

import httpx
import pytest

from src.dispatcher import FrontDoorDispatcher
from src.gateway import GatewayError, OmniRouteClient, Tier
from tests.test_omniroute_gateway import _chunk, _collect, _Scripted, _sse


def _client(script: _Scripted) -> OmniRouteClient:
    return OmniRouteClient(
        "http://gw.test/v1",
        "test-key",
        chains={
            Tier.FAST: ["fast-a:free", "fast-b:free"],
            Tier.MEDIUM: ["med-a:free"],
            Tier.HEAVY: ["heavy-a:free"],
        },
        transport=script.transport(),
    )


async def test_jitter_then_success_recovers():
    script = _Scripted(
        httpx.ConnectError("jitter-1"),
        httpx.ConnectError("jitter-2"),
        httpx.Response(200, content=_sse(_chunk("تم"))),
    )
    async with _client(script) as client:
        assert await _collect(client.stream_chat([{"role": "user", "content": "hi"}])) == ["تم"]


async def test_malformed_sse_skipped_not_fatal():
    body = b"data: not-json{{{\n\n" + _sse(_chunk("سليم")) + b"garbage-line\n\n"
    script = _Scripted(httpx.Response(200, content=body))
    async with _client(script) as client:
        assert "سليم" in "".join(
            await _collect(client.stream_chat([{"role": "user", "content": "x"}]))
        )


async def test_partial_stream_prefix_preserved():
    script = _Scripted(httpx.Response(200, content=_sse(_chunk("جزء"))))
    async with _client(script) as client:
        assert await _collect(client.stream_chat([{"role": "user", "content": "x"}])) == ["جزء"]


async def test_rate_window_cools_and_falls_over():
    script = _Scripted(
        httpx.Response(429, text="try again in 2s: rate limited"),
        httpx.Response(200, content=_sse(_chunk("بديل"))),
    )
    async with _client(script) as client:
        assert await _collect(client.stream_chat([{"role": "user", "content": "x"}])) == ["بديل"]


async def test_total_outage_is_loud():
    script = _Scripted(*[httpx.Response(500, text="boom") for _ in range(6)])
    async with _client(script) as client:
        with pytest.raises(GatewayError):
            await _collect(client.stream_chat([{"role": "user", "content": "x"}]))


async def test_router_garbage_degrades_to_ack_plus_chat(make_settings):
    from tests.conftest import FakeGateway, StreamProgram

    gw = FakeGateway(
        router_replies=["definitely not json {{{"],
        stream_programs=[StreamProgram(deltas=("أهلين",))],
    )
    disp = FrontDoorDispatcher(gw, make_settings())
    out = [d async for d in disp.handle("مرحبا")]
    assert out[0]
    assert any("أهلين" in d for d in out[1:])


async def test_dead_tool_falls_back_to_chat(make_settings):
    from tests.conftest import FakeGateway, StreamProgram

    gw = FakeGateway(
        router_replies=[
            '{"route":"tier2","tool":"gmail","arg":"","ack":"لحظة","voice_reply":false}'
        ],
        stream_programs=[StreamProgram(deltas=("البريد تعذر",))],
    )

    class DeadTools:
        async def call(self, tool, arg):
            raise RuntimeError("backend down")

    disp = FrontDoorDispatcher(gw, make_settings())
    out = [d async for d in disp.handle("شوف الجيميل", tools=DeadTools())]
    assert any("البريد تعذر" in d for d in out)


def test_no_edge_imports_in_suite():
    """Fish-only enforcement: no real Edge-TTS import/usage in suite code."""
    import pathlib
    import re

    banned = re.compile(
        r"^\s*(import\s+edge_tts|from\s+.*\bVoicePipeline\b|from\s+edge_tts)", re.MULTILINE
    )
    offenders = [
        str(p)
        for p in pathlib.Path(__file__).parents[1].rglob("*.py")
        if banned.search(p.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"Edge-TTS footprint inside suite: {offenders}"
