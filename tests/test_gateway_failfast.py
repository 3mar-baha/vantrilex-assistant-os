"""Gateway fail-fast (live 2026-09-14: a simple «كيفك سارة» stalled ~3min on a
throttled Gemma endpoint before Groq served). Hermetic MockTransport scripts.

NEW CONTRACT:
- Tier.FAST: no content delta within FIRST_TOKEN_TIMEOUT_S (4.0s) -> abort
  the attempt, quarantine the stalled model, cascade immediately (no retry).
- Any 429 quarantine and any empty-stream quarantine last 15 minutes
  (THROTTLE_QUARANTINE_S): later turns skip the model at turn zero with
  zero network calls, so the stable candidate (Groq) serves FAST turns.
"""

from __future__ import annotations

import asyncio
import json
import time

import httpx
import pytest

from src.gateway import OmniRouteClient, Tier

PRIMARY = "primary-x:free"
SECOND = "second-y:free"


@pytest.fixture(autouse=True)
def _clear_cooldowns():
    """Process-wide registries must not leak between tests (or modules)."""
    from src.gateway import _429_STREAK, _MODEL_COOLDOWNS

    _MODEL_COOLDOWNS.clear()
    _429_STREAK.clear()
    yield
    _MODEL_COOLDOWNS.clear()
    _429_STREAK.clear()


def _chunk(text: str) -> str:
    return "data: " + json.dumps({"choices": [{"delta": {"content": text}}]}) + "\n\n"


def _sse(*lines: str) -> bytes:
    return ("".join([*lines, "data: [DONE]\n\n"])).encode()


class _Scripted:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        assert self.responses, "script exhausted — unplanned request"
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)

    def models(self) -> list[str]:
        return [json.loads(r.content)["model"] for r in self.requests]


def _client(script: _Scripted) -> OmniRouteClient:
    return OmniRouteClient(
        "http://gw.test/v1",
        "test-key",
        chains={Tier.FAST: [PRIMARY, SECOND], Tier.MEDIUM: ["m:free"], Tier.HEAVY: ["h:free"]},
        transport=script.transport(),
    )


async def _collect(gen) -> list[str]:
    return [delta async for delta in gen]


async def test_fast_first_token_timeout_cascades(monkeypatch):
    """A FAST attempt that stalls with zero deltas aborts fast and the next
    model serves — the turn never hangs on a throttled endpoint."""
    from src.gateway import _MODEL_COOLDOWNS

    monkeypatch.setattr("src.gateway.FIRST_TOKEN_TIMEOUT_S", 0.05)
    script = _Scripted(httpx.Response(200, content=_sse(_chunk("سريع"))))

    async with _client(script) as client:
        orig_attempt = client._attempt

        async def stalled(self, model, payload):
            if model == PRIMARY:
                await asyncio.sleep(60.0)
                yield "late"  # pragma: no cover -- guillotine always fires first by design
            else:
                async for content in orig_attempt(model, payload):
                    yield content

        monkeypatch.setattr(client, "_attempt", stalled.__get__(client))
        t0 = time.perf_counter()
        deltas = await _collect(client.stream_chat([{"role": "user", "content": "hi"}]))
        elapsed = time.perf_counter() - t0
    assert deltas == ["سريع"]
    assert script.models() == [SECOND]  # primary aborted pre-wire, never hit network
    assert elapsed < 5.0, f"fail-fast took {elapsed:.2f}s"
    assert PRIMARY in _MODEL_COOLDOWNS  # stalled model quarantined


async def test_fast_timeout_does_not_touch_medium(monkeypatch):
    """The 4s guillotine is FAST-only: a MEDIUM first token slower than the
    patched FAST timeout still serves (long-form lanes keep their patience)."""
    monkeypatch.setattr("src.gateway.FIRST_TOKEN_TIMEOUT_S", 0.05)
    script = _Scripted()

    async def slowish(self, model, payload):
        await asyncio.sleep(0.15)
        yield "صبور"

    client = OmniRouteClient(
        "http://gw.test/v1",
        "test-key",
        chains={Tier.MEDIUM: ["m:free"]},
        transport=script.transport(),
    )
    async with client:
        monkeypatch.setattr(client, "_attempt", slowish.__get__(client))
        deltas = await _collect(
            client.stream_chat([{"role": "user", "content": "hi"}], tier=Tier.MEDIUM)
        )
    assert deltas == ["صبور"]
    assert script.models() == []


async def test_bare_429_quarantine_is_fifteen_minutes():
    """The 429 quarantine lasts 15 minutes, not 90 seconds."""
    from src.gateway import BARE_429_COOLDOWN_S

    assert BARE_429_COOLDOWN_S == 15 * 60


async def test_streak_tripped_model_skipped_with_zero_calls_next_turn():
    """After the streak trip, the NEXT turn skips the hot model at turn zero —
    no request leaves the machine for it (Groq serves FAST straight away)."""
    from src.gateway import _model_hot

    script = _Scripted(
        httpx.Response(429, text="Provider returned error"),
        httpx.Response(429, text="Provider returned error"),
        httpx.Response(200, content=_sse(_chunk("one"))),
        httpx.Response(200, content=_sse(_chunk("two"))),
    )
    async with _client(script) as client:
        assert await _collect(client.stream_chat([{"role": "user", "content": "hi"}])) == ["one"]
        assert _model_hot(PRIMARY) is not None and _model_hot(PRIMARY) > 800
        assert await _collect(client.stream_chat([{"role": "user", "content": "hi"}])) == ["two"]
    assert script.models() == [PRIMARY, PRIMARY, SECOND, SECOND]


async def test_empty_reply_quarantines_model_fifteen_minutes():
    """A streamed [DONE] with zero content deltas now parks the model for
    15 minutes too — a blank-serving model stops eating a turn every time."""
    from src.gateway import _model_hot

    script = _Scripted(
        httpx.Response(200, content=_sse()),
        httpx.Response(200, content=_sse(_chunk("بديل"))),
        httpx.Response(200, content=_sse(_chunk("تالي"))),
    )
    async with _client(script) as client:
        assert await _collect(client.stream_chat([{"role": "user", "content": "hi"}])) == ["بديل"]
        assert _model_hot(PRIMARY) is not None and _model_hot(PRIMARY) > 800
        assert await _collect(client.stream_chat([{"role": "user", "content": "hi"}])) == ["تالي"]
    assert script.models() == [PRIMARY, SECOND, SECOND]
