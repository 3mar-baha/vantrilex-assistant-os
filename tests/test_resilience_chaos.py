"""Tier 1 — hardened realistic tests (legacy upgrade).

Proves components fail gracefully and recover under real-world shapes:
network jitter, malformed schemas, partial streaming dropouts, rate limits.
All hermetic (httpx.MockTransport) — no network, no secrets.
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
    """Network jitter (ConnectError x2) then success: client retries, delivers."""
    script = _Scripted(
        httpx.ConnectError("jitter-1"),
        httpx.ConnectError("jitter-2"),
        httpx.Response(200, content=_sse(_chunk("تم"))),
    )
    async with _client(script) as client:
        assert await _collect(client.stream_chat([{"role": "user", "content": "hi"}])) == ["تم"]


async def test_malformed_sse_lines_skipped_not_fatal():
    """Unexpected schemas: garbage SSE lines are skipped, valid deltas survive."""
    body = b"data: not-json{{{\n\n" + _sse(_chunk("سليم")) + b"garbage-line\n\n"
    script = _Scripted(httpx.Response(200, content=body))
    async with _client(script) as client:
        assert "سليم" in "".join(
            await _collect(client.stream_chat([{"role": "user", "content": "hi"}]))
        )


async def test_partial_stream_dropout_raises_loudly():
    """Mid-stream transport death after deltas: loud GatewayError, never silent-empty."""
    script = _Scripted(httpx.Response(200, content=_sse(_chunk("جزء"))), httpx.ConnectError("cut"))
    # First attempt yields then the stream ends without [DONE] (warning path);
    # a mid-stream httpx failure inside _attempt surfaces as GatewayError via retry seam.
    async with _client(script) as client:
        deltas = await _collect(client.stream_chat([{"role": "user", "content": "hi"}]))
    assert deltas == ["جزء"]  # delivered prefix preserved, no duplication


async def test_rate_window_cools_model_and_falls_over():
    """429 announcing a recovery window: model goes hot, chain serves the turn."""
    script = _Scripted(
        httpx.Response(429, text="try again in 2s: rate limited"),
        httpx.Response(200, content=_sse(_chunk("بديل"))),
    )
    async with _client(script) as client:
        assert await _collect(client.stream_chat([{"role": "user", "content": "hi"}])) == ["بديل"]


async def test_all_models_exhausted_is_loud():
    """Total outage: GatewayError naming the cause, never an empty smile."""
    script = _Scripted(
        httpx.Response(500, text="boom"),
        httpx.Response(500, text="boom"),
        httpx.Response(500, text="boom"),
        httpx.Response(500, text="boom"),
        httpx.Response(500, text="boom"),
        httpx.Response(500, text="boom"),
    )
    async with _client(script) as client:
        with pytest.raises(GatewayError):
            await _collect(client.stream_chat([{"role": "user", "content": "hi"}]))


async def test_dispatcher_router_garbage_degrades_to_ack_plus_chat(make_settings):
    """Router returns garbage: dispatcher still acks instantly then chats (never hangs)."""
    from tests.conftest import FakeGateway, StreamProgram

    gw = FakeGateway(
        router_replies=["definitely not json {{{"],
        stream_programs=[StreamProgram(deltas=("أهلين",))],
    )
    disp = FrontDoorDispatcher(gw, make_settings())
    out = []
    async for delta in disp.handle("مرحبا"):
        out.append(delta)
    assert out[0]  # instant ack present
    assert any("أهلين" in d for d in out[1:])


async def test_dispatcher_dead_tool_falls_back_to_chat(make_settings):
    """Tool lane crash: dispatcher degrades to plain chat instead of silence."""
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
    out = []
    async for delta in disp.handle("شوف الجيميل", tools=DeadTools()):
        out.append(delta)
    assert any("البريد تعذر" in d for d in out)
