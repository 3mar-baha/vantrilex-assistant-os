"""Sprint-1 §1.2 AC1-AC9: OmniRoute client — streaming, fallback, quota/retry, SSE edges.

All against httpx.MockTransport scripts; request order asserted via recorded model fields.
"""

import json

import httpx
import pytest
from loguru import logger

from src.gateway import GatewayError, OmniRouteClient, Tier

PRIMARY = "primary-x"
FAST = "fast-y"
AUTH = {"Authorization": "Bearer test-key"}


def _chunk(text: str) -> str:
    return "data: " + json.dumps({"choices": [{"delta": {"content": text}}]}) + "\n\n"


def _null_delta() -> str:
    return "data: " + json.dumps({"choices": [{"delta": {}}]}) + "\n\n"


def _sse(*lines: str, done: bool = True) -> bytes:
    lines = list(lines)
    if done:
        lines.append("data: [DONE]")
    return "".join(lines).encode()


class _Scripted:
    """Records requests; serves scripted responses in order."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        assert self.responses, "script exhausted — client made an unplanned request"
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
        chains={Tier.FAST: [PRIMARY, FAST], Tier.MEDIUM: ["medium-x"], Tier.HEAVY: ["heavy-x"]},
        transport=script.transport(),
    )


async def _collect(gen) -> list[str]:
    out = []
    async for delta in gen:
        out.append(delta)
    return out


@pytest.fixture
def logs():
    records: list = []
    sink_id = logger.add(records.append, level="DEBUG")
    yield records
    logger.remove(sink_id)


async def test_stream_yields_deltas_with_stream_true_and_bearer():
    """AC1: happy path deltas arrive in order; request carried stream=true + Bearer."""
    script = _Scripted(httpx.Response(200, content=_sse(_chunk("مرحبا"), _chunk(" يا صديقي"))))
    async with _client(script) as client:
        deltas = await _collect(client.stream_chat([{"role": "user", "content": "hi"}]))
    assert deltas == ["مرحبا", " يا صديقي"]
    request = script.requests[0]
    assert request.headers["authorization"] == AUTH["Authorization"]
    assert json.loads(request.content)["stream"] is True
    assert script.models() == [PRIMARY]


async def test_quota_on_primary_switches_to_fast_immediately():
    """AC2: primary 402/quota -> one primary attempt then FAST succeeds, zero retries burned."""
    script = _Scripted(
        httpx.Response(402, text='{"error": {"message": "quota exceeded for free pool"}}'),
        httpx.Response(200, content=_sse(_chunk("تم"))),
    )
    async with _client(script) as client:
        deltas = await _collect(client.stream_chat([{"role": "user", "content": "hi"}]))
    assert deltas == ["تم"]
    assert script.models() == [PRIMARY, FAST]


async def test_quota_on_streaming_error_body_falls_back():
    """Regression: non-200 body arrives as an unread stream (real-gateway shape) -> must be
    read before classification, not raise ResponseNotRead."""

    async def err_body():
        yield b'{"error": {"message": "quota exceeded for free pool"}}'

    script = _Scripted(
        httpx.Response(402, content=err_body()),
        httpx.Response(200, content=_sse(_chunk("تم"))),
    )
    async with _client(script) as client:
        deltas = await _collect(client.stream_chat([{"role": "user", "content": "hi"}]))
    assert deltas == ["تم"]
    assert script.models() == [PRIMARY, FAST]


async def test_transient_errors_retry_then_fallback(monkeypatch):
    """AC3: primary 500 x3 (backoff stubbed short) -> 3 attempts then FAST first-try success."""
    script = _Scripted(
        httpx.Response(500, text="boom"),
        httpx.Response(500, text="boom"),
        httpx.Response(500, text="boom"),
        httpx.Response(200, content=_sse(_chunk("خلاص"))),
    )

    async def instant(_seconds):
        return None

    monkeypatch.setattr("src.gateway._sleep", instant)
    async with _client(script) as client:
        deltas = await _collect(client.stream_chat([{"role": "user", "content": "hi"}]))
    assert deltas == ["خلاص"]
    assert script.models() == [PRIMARY, PRIMARY, PRIMARY, FAST]


async def test_fatal_auth_error_raises_without_fallback():
    """AC4: primary 401 -> GatewayError; FAST never contacted."""
    script = _Scripted(httpx.Response(401, text='{"error": {"message": "bad key"}}'))
    async with _client(script) as client:
        with pytest.raises(GatewayError, match="401"):
            await _collect(client.stream_chat([{"role": "user", "content": "hi"}]))
    assert script.models() == [PRIMARY]


async def test_both_models_exhausted_raises_gateway_error():
    """AC5: both models 503 across attempts -> GatewayError naming both."""
    script = _Scripted(*([httpx.Response(503, text="down")] * 6))
    async with _client(script) as client:
        with pytest.raises(GatewayError) as exc_info:
            await _collect(client.stream_chat([{"role": "user", "content": "hi"}]))
    assert PRIMARY in str(exc_info.value)
    assert FAST in str(exc_info.value)
    assert script.models() == [PRIMARY] * 3 + [FAST] * 3


async def test_sse_edge_cases_done_null_and_malformed(logs):
    """AC6: early [DONE]; null-delta skip; malformed-line skip-with-warning."""
    script = _Scripted(
        httpx.Response(200, content=_sse(done=True)),  # [DONE] first -> empty stream
        httpx.Response(
            200,
            content=_sse(
                _chunk("أهلا"),
                _null_delta(),
                "data: {{{not-json\n\n",
                _chunk("بك"),
            ),
        ),
    )
    async with _client(script) as client:
        gen = client.stream_chat([{"role": "user", "content": "hi"}])
        assert await _collect(gen) == []  # early [DONE] yields nothing
        gen = client.stream_chat([{"role": "user", "content": "hi"}])
        assert await _collect(gen) == ["أهلا", "بك"]  # null/malformed skipped
    assert any("malformed" in str(m).lower() for m in logs)


async def test_midstream_failure_after_first_delta_raises():
    """AC7: mid-stream disconnect after first delta raises immediately (no restart/fallback)."""

    async def torn_stream():
        yield _chunk("نصف").encode()
        raise httpx.RemoteProtocolError("peer closed connection")

    script = _Scripted(httpx.Response(200, content=torn_stream()))
    async with _client(script) as client:
        seen: list[str] = []
        with pytest.raises(GatewayError):
            async for delta in client.stream_chat([{"role": "user", "content": "hi"}]):
                seen.append(delta)
    assert seen == ["نصف"]
    assert script.models() == [PRIMARY]  # no fallback after first delta yielded


async def test_missing_done_marker_warns_and_delivers(logs):
    """AC8: stream ends WITHOUT [DONE]: warning binds received bytes; deltas still delivered."""
    script = _Scripted(
        httpx.Response(200, content=_sse(_chunk("واحد"), _chunk(" اثنين"), done=False))
    )
    async with _client(script) as client:
        deltas = await _collect(client.stream_chat([{"role": "user", "content": "hi"}]))
    assert deltas == ["واحد", " اثنين"]
    assert any("without [DONE]" in str(m) and "bytes=" in str(m) for m in logs)


async def test_chat_aggregates_deltas():
    """AC9: chat() concatenates streamed deltas."""
    script = _Scripted(
        httpx.Response(200, content=_sse(_chunk("أهلا"), _chunk(" بك"), _chunk(" يا أستاذ")))
    )
    async with _client(script) as client:
        reply = await client.chat([{"role": "user", "content": "hi"}])
    assert reply == "أهلا بك يا أستاذ"


async def test_sse_error_event_classified_loud_stop():
    """Regression (live 2026-08-29): mid-stream `data: {"error": ...}` events must never be
    swallowed — embedded status classifies (403 -> fatal -> loud stop, FAST never contacted)."""
    script = _Scripted(
        httpx.Response(
            200,
            content=_sse(
                _null_delta(),
                "data: "
                + json.dumps(
                    {"error": {"message": "[gemini/x] [403]: Your project has been denied access"}}
                ),
                done=False,
            ),
        ),
    )
    async with _client(script) as client:
        with pytest.raises(GatewayError, match="denied access"):
            await _collect(client.stream_chat([{"role": "user", "content": "hi"}]))
    assert script.models() == [PRIMARY]
