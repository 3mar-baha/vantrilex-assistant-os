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

# Owner architecture update (2026-09-01): two strong models only — the conversation
# lane (minimax, fb gpt-oss-120b) is Sara's exclusive speaker; the tool lane
# (nemotron-3-ultra) executes every Gmail/Calendar/Tasks/bridge call.
FAST_PIN = "openrouter/minimax/minimax-m2.7:free"
FAST_FB1 = "groq/openai/gpt-oss-120b"
MEDIUM_PIN = "groq/openai/gpt-oss-120b"
MEDIUM_FB1 = "openrouter/minimax/minimax-m2.7:free"
HEAVY_PIN = "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"
HEAVY_FB1 = "groq/openai/gpt-oss-120b"

CHAINS = {
    Tier.FAST: [FAST_PIN, FAST_FB1],
    Tier.MEDIUM: [MEDIUM_PIN, MEDIUM_FB1],
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
    assert s.medium_chain == [MEDIUM_PIN, MEDIUM_FB1]
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
        f"MEDIUM_MODEL_FALLBACKS={MEDIUM_FB1}",
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


# --- Tool lane (owner directive 2026-09-01): real tool execution behind the router;
# every tool narration streams at Tier.HEAVY (nemotron — the exclusive tool model). ----


class FakeRegistry:
    def __init__(self, result: str | None = "بريد غير مقروء: 3", error: Exception | None = None):
        self.result = result
        self.error = error
        self.calls: list[tuple[str, str]] = []

    async def call(self, tool: str, arg: str) -> str | None:
        self.calls.append((tool, arg))
        if self.error is not None:
            raise self.error
        return self.result


def _tool_router(tool: str, ack: str, arg: str = "") -> str:
    return _chunk(
        json.dumps({"route": "tier2", "tool": tool, "arg": arg, "ack": ack}, ensure_ascii=False)
    )


async def test_tool_verdict_executes_real_registry_and_narrates_at_heavy(make_settings):
    """Tool intent: router verdict carries tool+arg, the registry executes the REAL
    backend call, and the narration streams at the HEAVY tool lane (nemotron) with
    the result embedded as DATA."""
    registry = FakeRegistry(result="3 رسائل غير مقروءة: فاتورة، اجتماع، قسيمة")
    script = _Scripted(
        httpx.Response(200, content=_sse(_tool_router("gmail", "بعطيك الإيميلات"))),
        httpx.Response(200, content=_sse(_chunk("عندك"), _chunk(" 3 رسائل"))),
    )
    async with _gateway(script) as client:
        out = await _collect(
            FrontDoorDispatcher(client, make_settings()).handle(
                "افحصي اخر رسائل الجيميل", tools=registry
            )
        )
    assert registry.calls == [("gmail", "")]
    assert out == ["بعطيك الإيميلات", "عندك", " 3 رسائل"]
    assert script.models() == [FAST_PIN, HEAVY_PIN]  # tool lane narrates exclusively
    messages = json.loads(script.requests[-1].content)["messages"]
    assert any("3 رسائل غير مقروءة" in m["content"] for m in messages)
    assert any("افحصي اخر رسائل الجيميل" in m["content"] for m in messages)


async def test_launch_tool_notifies_directly_without_narration_stream(make_settings):
    """launch: the coordinator notifies the owner itself (audit code inside) — the
    dispatcher yields only the ack and never streams a narration."""
    registry = FakeRegistry(result=None)  # None = owner already notified
    script = _Scripted(
        httpx.Response(200, content=_sse(_tool_router("launch", "لحظة", "الآلة الحاسبة")))
    )
    async with _gateway(script) as client:
        out = await _collect(
            FrontDoorDispatcher(client, make_settings()).handle(
                "افتحي الآلة الحاسبة", tools=registry
            )
        )
    assert registry.calls == [("launch", "الآلة الحاسبة")]
    assert out == ["لحظة"]
    assert script.models() == [FAST_PIN]


async def test_registry_failure_degrades_to_plain_tier2(make_settings, logs):
    """A crashed tool call never hangs the chat: loud log + plain Tier 2 stream."""
    registry = FakeRegistry(error=RuntimeError("bridge exploded"))
    script = _Scripted(
        httpx.Response(200, content=_sse(_tool_router("telemetry", "بشوف"))),
        httpx.Response(200, content=_sse(_chunk("ما قدرت أوصل للجسر"))),
    )
    async with _gateway(script) as client:
        out = await _collect(
            FrontDoorDispatcher(client, make_settings()).handle("شو وضع الجهاز؟", tools=registry)
        )
    assert out == ["بشوف", "ما قدرت أوصل للجسر"]
    assert script.models() == [FAST_PIN, MEDIUM_PIN]
    messages = json.loads(script.requests[-1].content)["messages"]
    assert not any("bridge exploded" in m["content"] for m in messages)
    assert any("tool" in str(record).lower() for record in logs)


async def test_history_flows_into_narration_stream(make_settings):
    """Short-term memory: the dispatcher passes the rolling history through."""
    registry = FakeRegistry(result="المعالج 12%")
    history = [{"role": "user", "content": "مرحبا"}, {"role": "assistant", "content": "أهلا"}]
    script = _Scripted(
        httpx.Response(200, content=_sse(_tool_router("telemetry", "بشوف"))),
        httpx.Response(200, content=_sse(_chunk("المعالج 12%"))),
    )
    async with _gateway(script) as client:
        await _collect(
            FrontDoorDispatcher(client, make_settings()).handle(
                "شو وضع الجهاز؟", history=history, tools=registry
            )
        )
    messages = json.loads(script.requests[-1].content)["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant", "user"]
    assert messages[0]["content"] == "مرحبا"
    assert messages[1] == {"role": "assistant", "content": "أهلا"}


async def test_tool_verdict_without_registry_falls_back_to_plain_stream(make_settings):
    """No registry wired -> the verdict degrades to the plain tier2 text stream."""
    script = _Scripted(
        httpx.Response(200, content=_sse(_tool_router("gmail", "لحظة"))),
        httpx.Response(200, content=_sse(_chunk("رد عادي"))),
    )
    async with _gateway(script) as client:
        out = await _collect(FrontDoorDispatcher(client, make_settings()).handle("افحصي الجيميل"))
    assert out == ["لحظة", "رد عادي"]
    assert script.models() == [FAST_PIN, MEDIUM_PIN]
