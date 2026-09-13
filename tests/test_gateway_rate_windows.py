"""STT-3 (owner 2026-09-04 evening, live 6:59-7:36pm log):

ROOT CAUSE 1 — a provider 429 with «Rate limit... try again in 17m25s» (TPD
Limit on groq, 200000/198825) was classified TRANSIENT because the body
carries no quota-marker word. The chain then burned 3 fast retries against
a 17-MINUTE server-side window, moved on, exhausted every model, and the
whole brain died for the turn — while the server had literally announced
the recovery time.

NEW CONTRACT:
- Retry-After / «try again in Xh Ym Zs» / «retry in Xs» in a 429 body or
  header = RATE-LIMIT WINDOW: parsed, carried in the error, and the tier's
  REMAINING models still serve the turn (model-level skip, not chain death).
  A 429 marks the MODEL hot for a cooldown; the next model in the chain
  serves immediately.
- Cooldown registry: a 429'd model is skipped for min(window, 20min)
  process-wide — later turns on the same hot model skip straight past it
  instead of burning three retries x three models every turn.

ROOT CAUSE 2 — voice synthesis: Fish died twice per turn (2s apart) and the
owner got the raw text. The retry loop's fixed 2.0s sleep does not honor a
server-announced wait either; when Fish's 429 carries a window, the voice
lane waits ONCE for a bounded slice of it (owner never hangs >8s), then the
honest text lands as it does today.
"""

from __future__ import annotations

import json

import httpx
import pytest

from src.gateway import OmniRouteClient, Tier

PRIMARY = "primary-x:free"
SECOND = "second-y:free"
AUTH = {"Authorization": "Bearer test-key"}

GROQ_TPD_BODY = (
    "Rate limit reached for model gpt-oss-120b on tokens per day (TPD): "
    "Limit 200000, Used 198825. Please try again in 17m25s"
)


@pytest.fixture(autouse=True)
def _clear_cooldowns():
    """The cooldown registry is process-wide by design — tests must not leak a
    hot model into each other (or into the sprint-1 gateway tests)."""
    from src.gateway import _MODEL_COOLDOWNS

    _MODEL_COOLDOWNS.clear()
    yield
    _MODEL_COOLDOWNS.clear()


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
    out = []
    async for delta in gen:
        out.append(delta)
    return out


# -- parsing the window ------------------------------------------------------


def test_parse_retry_window_from_body_and_header():
    """The window parser: «try again in 17m25s», «retry in 45s», Retry-After
    header (seconds, or HTTP-date ignored), plain «1h» — everything a real
    free pool announces."""
    from src.gateway import parse_retry_window_s

    assert parse_retry_window_s(f"... {GROQ_TPD_BODY}") == 17 * 60 + 25
    assert parse_retry_window_s("429: retry in 45s") == 45.0
    assert parse_retry_window_s("429: try again in 2h") == 7200.0
    assert parse_retry_window_s("429: try again in 1h 30m") == 5400.0
    assert parse_retry_window_s("no window here") is None
    # header form: the caller passes the header value when the body is silent
    assert parse_retry_window_s("", retry_after="30") == 30.0


async def test_tpd_429_skips_model_next_model_serves():
    """The live failure: a body-window 429 on the primary must NOT burn retries
    against a 17-minute wall — the NEXT model serves the turn immediately."""
    script = _Scripted(
        httpx.Response(429, text=GROQ_TPD_BODY),
        httpx.Response(200, content=_sse(_chunk("تمام"))),
    )
    async with _client(script) as client:
        deltas = await _collect(client.stream_chat([{"role": "user", "content": "hi"}]))
    assert deltas == ["تمام"]
    assert script.models() == [PRIMARY, SECOND]  # exactly one primary attempt


async def test_window_429_cooldown_skips_hot_model_next_turn():
    """After a window-429 the model is HOT for the window (capped): a later
    turn skips it without sending a single request to it."""
    script = _Scripted(
        httpx.Response(429, text=GROQ_TPD_BODY),
        httpx.Response(200, content=_sse(_chunk("أول"))),
        httpx.Response(200, content=_sse(_chunk("ثاني"))),
    )
    async with _client(script) as client:
        first = await _collect(client.stream_chat([{"role": "user", "content": "a"}]))
        second = await _collect(client.stream_chat([{"role": "user", "content": "b"}]))
    assert first == ["أول"] and second == ["ثاني"]
    # turn 1: primary 429 -> second serves; turn 2: primary SKIPPED (hot),
    # second serves directly — primary sees exactly one request total
    assert script.models() == [PRIMARY, SECOND, SECOND]


async def test_cooldown_expires_model_returns():
    """The cooldown is time-bounded, not permanent — after the window the
    model is probed again (a stuck-hot registry would retire it forever)."""
    from src.gateway import _MODEL_COOLDOWNS

    script = _Scripted(
        httpx.Response(429, text=GROQ_TPD_BODY),
        httpx.Response(200, content=_sse(_chunk("أول"))),
        httpx.Response(200, content=_sse(_chunk("ثاني"))),
    )
    async with _client(script) as client:
        await _collect(client.stream_chat([{"role": "user", "content": "a"}]))
        # force-expire the cooldown the first turn minted: a past instant is always cold
        _MODEL_COOLDOWNS[PRIMARY] = 0
        await _collect(client.stream_chat([{"role": "user", "content": "b"}]))
    # turn 1: primary 429 -> second serves; turn 2: cooldown expired -> primary serves
    assert script.models() == [PRIMARY, SECOND, PRIMARY]


async def test_all_models_window_429_raises_honest_error():
    """Every model in the chain returns a window-429 -> the honest loud stop
    (same as today's exhaustion), with the window carried in the message."""
    from src.gateway import GatewayError

    script = _Scripted(
        httpx.Response(429, text=GROQ_TPD_BODY),
        httpx.Response(429, text=GROQ_TPD_BODY),
    )
    async with _client(script) as client:
        try:
            await _collect(client.stream_chat([{"role": "user", "content": "hi"}]))
            raise AssertionError("should have raised")
        except GatewayError as exc:
            assert "17m25s" in str(exc) or "1045" in str(exc)


async def test_no_window_429_keeps_fast_retries():
    """A window-less 429 (burst limit) keeps the existing transient behavior —
    fast retries are exactly right for a seconds-scale blip."""
    import src.gateway as gw

    sleeps: list[float] = []
    original = gw._sleep

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)
        await original(0)

    gw._sleep = fake_sleep  # type: ignore[assignment]
    try:
        script = _Scripted(
            httpx.Response(429, text="too many requests"),
            httpx.Response(429, text="too many requests"),
            httpx.Response(429, text="too many requests"),
            httpx.Response(200, content=_sse(_chunk("تم"))),
        )
        async with _client(script) as client:
            deltas = await _collect(client.stream_chat([{"role": "user", "content": "hi"}]))
        assert deltas == ["تم"]
        assert script.models() == [PRIMARY, PRIMARY, PRIMARY, SECOND]
        assert len(sleeps) == 2  # 3 attempts, 2 sleeps between them
    finally:
        gw._sleep = original  # type: ignore[assignment]
