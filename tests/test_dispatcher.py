"""Sprint-1 §1.5 AC1-AC9: 3-tier brain + Fast Front-Door Dispatcher (ADR-16/18)."""

import asyncio
import json
from pathlib import Path
from time import perf_counter

import httpx
import pytest
from loguru import logger
from pydantic import ValidationError

from src.dispatcher import DEFAULT_ACK_AR, FrontDoorDispatcher
from src.gateway import OmniRouteClient, Tier
from tests.test_omniroute_gateway import _chunk, _collect, _Scripted, _sse

FAST_PIN = "groq/openai/gpt-oss-20b"
FAST_FB1 = "openrouter/minimax/minimax-m2.7:free"
MEDIUM_PIN = "groq/openai/gpt-oss-20b"
MEDIUM_FB1 = "openrouter/minimax/minimax-m2.7:free"
MEDIUM_FB2 = "groq/openai/gpt-oss-120b"
HEAVY_PIN = "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"
HEAVY_FB1 = "groq/openai/gpt-oss-120b"

CHAINS = {
    Tier.FAST: [FAST_PIN, FAST_FB1],
    Tier.MEDIUM: [MEDIUM_PIN, MEDIUM_FB1, MEDIUM_FB2],
    Tier.HEAVY: [HEAVY_PIN, HEAVY_FB1],
}


def _router_json(route: str, ack: str) -> str:
    return _chunk(json.dumps({"route": route, "ack": ack}, ensure_ascii=False))


def _quota() -> httpx.Response:
    return httpx.Response(402, text='{"error": {"message": "quota exceeded for free pool"}}')


def _gateway(script: _Scripted) -> OmniRouteClient:
    return OmniRouteClient(
        "http://gw.test/v1", "test-key", chains=CHAINS, transport=script.transport()
    )


@pytest.fixture
def logs():
    records: list = []
    sink_id = logger.add(records.append, level="DEBUG")
    yield records
    logger.remove(sink_id)


def test_settings_carries_tier_pins(make_settings):
    """AC1: Settings carries the 3-tier pins, parses fallback lists, fails fast on gaps."""
    s = make_settings()
    assert (s.fast_model, s.medium_model, s.heavy_model) == (FAST_PIN, MEDIUM_PIN, HEAVY_PIN)
    assert s.fast_chain == [FAST_PIN, FAST_FB1]
    assert s.medium_chain == [MEDIUM_PIN, MEDIUM_FB1, MEDIUM_FB2]
    assert s.heavy_chain == [HEAVY_PIN, HEAVY_FB1]
    # blank fallbacks -> pin-only chain
    assert make_settings(FAST_MODEL_FALLBACKS="").fast_chain == [FAST_PIN]
    # missing tier pin -> boot fails fast
    with pytest.raises(ValidationError):
        make_settings(MEDIUM_MODEL="__REMOVE__")


def test_env_pins_match_adr16():
    """AC2: template carries the exact ADR-16 IDs; the retired 2-slot pin is gone."""
    template = (Path(__file__).parents[1] / ".env.example").read_text(encoding="utf-8")
    for line in (
        f"FAST_MODEL={FAST_PIN}",
        f"FAST_MODEL_FALLBACKS={FAST_FB1}",
        f"MEDIUM_MODEL={MEDIUM_PIN}",
        f"MEDIUM_MODEL_FALLBACKS={MEDIUM_FB1},{MEDIUM_FB2}",
        f"HEAVY_MODEL={HEAVY_PIN}",
        f"HEAVY_MODEL_FALLBACKS={HEAVY_FB1}",
    ):
        assert line in template
    assert "PRIMARY_MODEL" not in template


async def test_tier_fallback_chain_ordering():
    """AC3: each tier's chain walks in ADR-16 order on quota (immediate advance)."""
    for tier, chain in (
        (Tier.FAST, CHAINS[Tier.FAST]),
        (Tier.MEDIUM, CHAINS[Tier.MEDIUM]),
        (Tier.HEAVY, CHAINS[Tier.HEAVY]),
    ):
        script = _Scripted(
            *(_quota() for _ in chain[:-1]), httpx.Response(200, content=_sse(_chunk("تم")))
        )
        async with _gateway(script) as client:
            deltas = await _collect(
                client.stream_chat([{"role": "user", "content": "hi"}], tier=tier)
            )
        assert deltas == ["تم"]
        assert script.models() == chain


async def test_simple_chat_stays_tier1(make_settings):
    """AC4: simple chat is answered entirely at Tier 1; Tier 2/3 never contacted."""
    script = _Scripted(
        httpx.Response(200, content=_sse(_router_json("direct", "أهلا عمر، كل شي منيح")))
    )
    async with _gateway(script) as client:
        out = await _collect(FrontDoorDispatcher(client, make_settings()).handle("شو الأخبار؟"))
    assert out == ["أهلا عمر، كل شي منيح"]
    assert script.models() == [FAST_PIN]


async def test_tool_intent_routes_tier2(make_settings):
    """AC5: single/dual-tool intent acks at Tier 1 then streams Tier 2."""
    script = _Scripted(
        httpx.Response(200, content=_sse(_router_json("tier2", DEFAULT_ACK_AR))),
        httpx.Response(200, content=_sse(_chunk("سجّلت"), _chunk(" الموعد"))),
    )
    async with _gateway(script) as client:
        out = await _collect(FrontDoorDispatcher(client, make_settings()).handle("حدّد موعد بكره"))
    assert out == [DEFAULT_ACK_AR, "سجّلت", " الموعد"]
    assert script.models() == [FAST_PIN, MEDIUM_PIN]


async def test_dag_intent_routes_tier3(make_settings):
    """AC6: multi-step DAG intent acks at Tier 1 then streams Tier 3."""
    script = _Scripted(
        httpx.Response(200, content=_sse(_router_json("tier3", DEFAULT_ACK_AR))),
        httpx.Response(200, content=_sse(_chunk("خطة"), _chunk(" الدراسة"))),
    )
    async with _gateway(script) as client:
        out = await _collect(
            FrontDoorDispatcher(client, make_settings()).handle("صمم لي خطة مراجعة")
        )
    assert out == [DEFAULT_ACK_AR, "خطة", " الدراسة"]
    assert script.models() == [FAST_PIN, HEAVY_PIN]


async def test_router_failure_defaults_tier2(make_settings, logs):
    """AC7: unparsable reply AND hard router failure both degrade to Tier 2, loudly."""
    script = _Scripted(
        httpx.Response(200, content=_sse(_chunk("أهلا! كيف فيني ساعدك"))),  # prose, not JSON
        httpx.Response(200, content=_sse(_chunk("جاهز"))),
    )
    async with _gateway(script) as client:
        out = await _collect(FrontDoorDispatcher(client, make_settings()).handle("جهزلي تقرير"))
    assert out == [DEFAULT_ACK_AR, "جاهز"]
    assert script.models() == [FAST_PIN, MEDIUM_PIN]

    script2 = _Scripted(
        httpx.Response(401, text='{"error": {"message": "bad key"}}'),
        httpx.Response(200, content=_sse(_chunk("شغالة"))),
    )
    async with _gateway(script2) as client:
        out = await _collect(FrontDoorDispatcher(client, make_settings()).handle("اجمعلي الملخصات"))
    assert out == [DEFAULT_ACK_AR, "شغالة"]
    assert script2.models() == [FAST_PIN, MEDIUM_PIN]
    assert any("dispatcher" in str(m) and "default tier2" in str(m) for m in logs)


async def test_ack_first_delta_budget(make_settings):
    """AC8: the Tier-1 ack IS the first delta; TTFT budget asserted with scripted latency."""
    router_json = json.dumps({"route": "tier2", "ack": DEFAULT_ACK_AR}, ensure_ascii=False)

    async def slow_router_body():
        await asyncio.sleep(0.1)
        yield _chunk(router_json).encode()

    script = _Scripted(
        httpx.Response(200, content=slow_router_body()),
        httpx.Response(200, content=_sse(_chunk("بدأت"))),
    )
    async with _gateway(script) as client:
        gen = FrontDoorDispatcher(client, make_settings()).handle("بحث مطوّل")
        start = perf_counter()
        first = await anext(gen)
        ttft = perf_counter() - start
        rest = await _collect(gen)
    assert first == DEFAULT_ACK_AR
    assert ttft < 0.250
    assert rest == ["بدأت"]


async def test_gateway_regression_green():
    """AC9: 1.2 SSE + auth contract preserved through the tier API."""
    script = _Scripted(httpx.Response(200, content=_sse(_chunk("مرحبا"), _chunk(" يا صديقي"))))
    async with _gateway(script) as client:
        deltas = await _collect(
            client.stream_chat([{"role": "user", "content": "hi"}], tier=Tier.MEDIUM)
        )
    assert deltas == ["مرحبا", " يا صديقي"]
    request = script.requests[0]
    assert request.headers["authorization"] == "Bearer test-key"
    assert json.loads(request.content)["stream"] is True
    assert script.models() == [MEDIUM_PIN]
