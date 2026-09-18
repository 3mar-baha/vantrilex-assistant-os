"""P2 dispatcher wiring: arg healing, transient retry, resolution cache.

Seams: FrontDoorDispatcher.handle / _tool_lane (public behavior).
"""

from __future__ import annotations

import httpx

from src.dispatcher import FrontDoorDispatcher
from tests.test_dispatcher import CHAINS, FAST_PIN, HEAVY_PIN, _tool_router
from tests.test_omniroute_gateway import _chunk, _collect, _Scripted, _sse


def _gateway(script: _Scripted):
    from src.gateway import OmniRouteClient

    return OmniRouteClient(
        "http://gw.test/v1", "test-key", chains=CHAINS, transport=script.transport()
    )


class FakeRegistry:
    def __init__(self, result="ok", error=None):
        self.result = result
        self.error = error
        self.calls: list[tuple[str, str]] = []

    async def call(self, tool: str, arg: str):
        self.calls.append((tool, arg))
        if self.error is not None:
            raise self.error
        return self.result


class FlakyRegistry(FakeRegistry):
    async def call(self, tool: str, arg: str):
        self.calls.append((tool, arg))
        if len(self.calls) == 1:
            raise TimeoutError("transient dial stall")
        return self.result


async def test_tool_lane_normalizes_arg_before_call(make_settings) -> None:
    """Dictated quotes + Arabic-Indic digits never reach the backend."""
    registry = FakeRegistry(result="تم")
    script = _Scripted(
        httpx.Response(200, content=_sse(_tool_router("gmail", "بشوف", '" ٥ "'))),
        httpx.Response(200, content=_sse(_chunk("تم"))),
    )
    async with _gateway(script) as client:
        await _collect(FrontDoorDispatcher(client, make_settings()).handle("شوف", tools=registry))
    assert registry.calls == [("gmail", "5")]


async def test_transient_tool_failure_retries_once_normalized(make_settings) -> None:
    """Healed arg leads every attempt; one bounded retry on transient stall."""
    registry = FlakyRegistry(result="تم")
    script = _Scripted(
        httpx.Response(200, content=_sse(_tool_router("gmail", "بشوف", '"٦"'))),
        httpx.Response(200, content=_sse(_chunk("تم"))),
    )
    async with _gateway(script) as client:
        out = await _collect(
            FrontDoorDispatcher(client, make_settings()).handle("شوف", tools=registry)
        )
    assert registry.calls == [("gmail", "6"), ("gmail", "6")]
    assert out == ["بشوف", "تم"]


async def test_permanent_tool_failure_no_retry_plain_fallback(make_settings) -> None:
    """Non-transient errors never burn a retry: one call, honest fallback."""
    registry = FakeRegistry(error=ValueError("bad shape"))
    script = _Scripted(
        httpx.Response(200, content=_sse(_tool_router("gmail", "بشوف"))),
        httpx.Response(200, content=_sse(_chunk("ما قدرت"))),
    )
    async with _gateway(script) as client:
        out = await _collect(
            FrontDoorDispatcher(client, make_settings()).handle("شوف", tools=registry)
        )
    assert len(registry.calls) == 1
    assert out == ["بشوف", "ما قدرت"]


async def test_repeated_read_only_request_skips_router(make_settings) -> None:
    """Second identical read replays the cached verdict: zero router tokens."""
    registry = FakeRegistry(result="3 رسائل")
    script = _Scripted(
        httpx.Response(200, content=_sse(_tool_router("gmail", "بعطيك"))),
        httpx.Response(200, content=_sse(_chunk("3 رسائل"))),
        httpx.Response(200, content=_sse(_chunk("3 رسائل"))),
    )
    async with _gateway(script) as client:
        disp = FrontDoorDispatcher(client, make_settings())
        first = await _collect(disp.handle("شو في ايميلات؟", tools=registry))
        second = await _collect(disp.handle("شو في ايميلات؟", tools=registry))
    assert first == second == ["بعطيك", "3 رسائل"]
    assert script.models() == [FAST_PIN, HEAVY_PIN, HEAVY_PIN]


async def test_immediacy_marker_bypasses_cache(make_settings) -> None:
    """هسا forces fresh routing both times (stale reads are worse than tokens)."""
    registry = FakeRegistry(result="تم")
    script = _Scripted(
        httpx.Response(200, content=_sse(_tool_router("gmail", "بشوف"))),
        httpx.Response(200, content=_sse(_chunk("تم"))),
        httpx.Response(200, content=_sse(_tool_router("gmail", "بشوف"))),
        httpx.Response(200, content=_sse(_chunk("تم"))),
    )
    async with _gateway(script) as client:
        disp = FrontDoorDispatcher(client, make_settings())
        await _collect(disp.handle("شوف الايميلات هسا", tools=registry))
        await _collect(disp.handle("شوف الايميلات هسا", tools=registry))
    assert script.models() == [FAST_PIN, HEAVY_PIN, FAST_PIN, HEAVY_PIN]


async def test_write_tool_never_cached(make_settings) -> None:
    """launch replays the router every time — side effects never replay."""
    registry = FakeRegistry(result=None)
    script = _Scripted(
        httpx.Response(200, content=_sse(_tool_router("launch", "لحظة", "الحاسبة"))),
        httpx.Response(200, content=_sse(_tool_router("launch", "لحظة", "الحاسبة"))),
    )
    async with _gateway(script) as client:
        disp = FrontDoorDispatcher(client, make_settings())
        await _collect(disp.handle("افتحي الحاسبة", tools=registry))
        await _collect(disp.handle("افتحي الحاسبة", tools=registry))
    assert script.models() == [FAST_PIN, FAST_PIN]


async def test_unparsable_router_reply_keeps_defaults_no_crash(make_settings) -> None:
    """Adjacent fix 2026-09-18: prose router replies must not UnboundLocalError
    on voice_hint — defaults hold, tier2 chats."""
    from src.dispatcher import DEFAULT_ACK_AR

    script = _Scripted(
        httpx.Response(200, content=_sse(_chunk("just some prose, no JSON"))),
        httpx.Response(200, content=_sse(_chunk("أهلين"))),
    )
    async with _gateway(script) as client:
        disp = FrontDoorDispatcher(client, make_settings())
        out = await _collect(disp.handle("مرحبا", tools=FakeRegistry()))
    assert out == [DEFAULT_ACK_AR, "أهلين"]
    assert disp.voice_hint is False
