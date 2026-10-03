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

# Routing matrix (2026-09-12, FAST flipped to groq 2026-09-14): FAST groq
# (conversation+ACK+routing, ~0.6s cold), MEDIUM nex-mini (sub-agent fleet),
# HEAVY nex-pro base (master orchestrator <=3 tasks, escalates to
# nemotron-3-ultra MoE beyond). Gemma stays the FAST fallback behind the 4s
# guillotine + 15m quarantine. Test-local chains exercise the dispatcher
# logic; the canonical pins live in .env.example (test below).
# RE-PINNED 2026-10-03 (owner). The previous values were two DEAD nex-agi
# primaries (`KeyError: 'choices'` — no completions returned) and a DEAD FAST
# fallback (`google/gemma-4-31b-it:free` is absent from the catalog; the slug
# moved under the `openrouter/` prefix). Measured against the live 1,482-model
# catalog; see the Phase-A commit message for every probe.
#
# These constants double as the dispatcher's TEST-LOCAL chains, so they must be
# real, dispatchable, free-tier slugs — a pin that cannot serve traffic is not a
# useful fixture. `tests/test_env_model_slugs.py` now asserts the canonical
# template against the LIVE catalog instead of against a snapshot.
FAST_PIN = "gemini/gemini-3.8-flash"
FAST_FB1 = "groq/openai/gpt-oss-120b"
MEDIUM_PIN = "gemini/gemini-3.8-flash"
MEDIUM_FB1 = "groq/openai/gpt-oss-120b"
HEAVY_PIN = "gemini/gemini-3.8-flash"
HEAVY_FB1 = "openrouter/poolside/laguna-s-2.1:free"
HEAVY_ESC_PIN = "openrouter/poolside/laguna-s-2.1:free"

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
    # Chains are now MULTI-entry (owner 2026-10-03): each tier carries its primary
    # plus a latency-ordered free-tier fallback set. What this guard owns is that
    # the primary leads and the fallbacks parse — the exact fallback ORDER is the
    # latency law, owned by `tests/test_env_model_slugs.py`.
    assert s.fast_chain[0] == FAST_PIN and s.fast_chain[1] == FAST_FB1
    assert s.medium_chain[0] == MEDIUM_PIN and s.medium_chain[1] == MEDIUM_FB1
    assert s.heavy_chain[0] == HEAVY_PIN and s.heavy_chain[1] == HEAVY_FB1
    for chain in (s.fast_chain, s.medium_chain, s.heavy_chain):
        assert len(chain) >= 2, f"a single-entry chain is a single point of failure: {chain}"
    # blank fallbacks -> pin-only chain
    assert make_settings(FAST_MODEL_FALLBACKS="").fast_chain == [FAST_PIN]
    # missing tier pin -> boot fails fast
    with pytest.raises(ValidationError):
        make_settings(MEDIUM_MODEL="__REMOVE__")


def test_env_pins_match_adr16():
    """AC2: template carries the exact routing-matrix IDs incl. escalation."""
    template = (Path(__file__).parents[1] / ".env.example").read_text(encoding="utf-8")
    for line in (
        f"FAST_MODEL={FAST_PIN}",
        f"FAST_MODEL_FALLBACKS={FAST_FB1}",
        f"MEDIUM_MODEL={MEDIUM_PIN}",
        f"MEDIUM_MODEL_FALLBACKS={MEDIUM_FB1}",
        f"HEAVY_MODEL={HEAVY_PIN}",
        f"HEAVY_ESCALATION_MODEL={HEAVY_ESC_PIN}",
        "HEAVY_CONCURRENCY_THRESHOLD=3",
    ):
        assert line in template
    # 2026-09-13 tuning: HEAVY carries TWO fallbacks (MoE escalation first,
    # groq last) so nex-agi credential gaps never crash narration.
    heavy_fb = next(
        line.split("=", 1)[1]
        for line in template.splitlines()
        if line.startswith("HEAVY_MODEL_FALLBACKS=")
    )
    # 2026-10-03 (owner): HEAVY now carries THREE free-tier fallbacks, ordered by
    # measured latency — laguna 8.0 s, nemotron 19.7 s, gemma 42.2 s last. The old
    # two-entry assertion pinned a two-entry chain whose second slot was the
    # escalation model; the chain is now latency-ordered per tier role, and
    # `tests/test_env_model_slugs.py` owns the ordering law.
    assert heavy_fb.split(",")[0] == HEAVY_ESC_PIN
    assert len(heavy_fb.split(",")) >= 2
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
    """AC4 (amended 2026-09-01 live-debug): simple chat acks at Tier 1 then streams the
    FAST conversation lane WITH the full memory envelope (system + history). The
    history-less router never speaks alone — Tier 2/3 remain untouched."""
    script = _Scripted(
        httpx.Response(200, content=_sse(_router_json("direct", DEFAULT_ACK_AR))),
        httpx.Response(200, content=_sse(_chunk("أول رقم"), _chunk(" كان 1"))),
    )
    history = [
        {"role": "user", "content": "الرسالة الأولى"},
        {"role": "assistant", "content": "رد أول"},
    ]
    async with _gateway(script) as client:
        out = await _collect(
            FrontDoorDispatcher(client, make_settings()).handle(
                "شو أول رقم أرسلته؟", system="أنت سارة", history=history
            )
        )
    assert out == [DEFAULT_ACK_AR, "أول رقم", " كان 1"]
    assert script.models() == [FAST_PIN, FAST_PIN]  # router AND answer both on the FAST chain
    messages = json.loads(script.requests[-1].content)["messages"]
    assert [m["role"] for m in messages] == ["system", "user", "assistant", "user"]
    assert messages[0]["content"] == "أنت سارة"
    assert messages[-1]["content"] == "شو أول رقم أرسلته؟"


async def test_overlong_router_ack_discarded_for_default_placeholder(make_settings):
    """Live 2026-09-01: the router wrote mini-answers into "ack" -> the owner saw two
    contradicting answers in one bubble. An ack over MAX_ACK_CHARS is router drift —
    discard it for the standard placeholder; only the stream answer speaks."""
    script = _Scripted(
        httpx.Response(
            200,
            content=_sse(
                _router_json(
                    "direct",
                    "أهلاً! تمكنت من فهم طلبك، هذا تعريف بصوتي بنفسي وسأشرح لك الآن بالتفصيل الممل",
                )
            ),
        ),
        httpx.Response(200, content=_sse(_chunk("الجواب"), _chunk(" الحقيقي"))),
    )
    async with _gateway(script) as client:
        out = await _collect(FrontDoorDispatcher(client, make_settings()).handle("ابعثلي فويس"))
    assert out == [DEFAULT_ACK_AR, "الجواب", " الحقيقي"]
    assert script.models() == [FAST_PIN, FAST_PIN]


# --- Remediation 1.3: the ack is Sara's voice — never a gateway identity, never a
# --- claim of completed action. Content guard sits beside the length guard. ---------


@pytest.mark.parametrize(
    "bad_ack",
    [
        "أنا بوابة سارة الأمامية",  # gateway identity leak (audit C-5)
        "أنا مساعد آلي جاهز لخدمتك",
        "هذا البوت جاهز",
        "تم فتح البرنامج بنجاح",  # claimed completed action (audit C-4/C-5)
        "بعت الإيميل لك",
        "جدولت الموعد وهلا كله تمام",
    ],
)
async def test_identity_or_claim_ack_replaced_by_default(make_settings, bad_ack):
    """An ack carrying gateway identity or a claimed completed action is router
    drift — replace it with DEFAULT_ACK_AR (remediation 1.3 content guard)."""
    script = _Scripted(
        httpx.Response(200, content=_sse(_router_json("direct", bad_ack))),
        httpx.Response(200, content=_sse(_chunk("الجواب"))),
    )
    async with _gateway(script) as client:
        out = await _collect(FrontDoorDispatcher(client, make_settings()).handle("طلب عادي"))
    assert out[0] == DEFAULT_ACK_AR
    assert bad_ack not in "".join(out)


async def test_clean_ack_passes_unchanged(make_settings):
    """A clean two-word Jordanian ack within budget passes the content guard as-is."""
    script = _Scripted(
        httpx.Response(200, content=_sse(_router_json("direct", "من عيوني هسا"))),
        httpx.Response(200, content=_sse(_chunk("الجواب"))),
    )
    async with _gateway(script) as client:
        out = await _collect(FrontDoorDispatcher(client, make_settings()).handle("طلب عادي"))
    assert out[0] == "من عيوني هسا"


async def test_router_prompt_has_no_gateway_identity(make_settings):
    """The router prompt must not introduce Sara as a «بوابة» — the third-person
    framing was the mechanical source of the owner-reported identity leaks."""
    from src.dispatcher import _ROUTER_PROMPT_AR

    assert "بوابة" not in _ROUTER_PROMPT_AR


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


# --- Remediation 2.1 (owner directive 2026-09-03, audit C-1): anti-hallucination -----
# --- keyword net. The router stays the primary classifier; this deterministic net is
# --- the defense line BEHIND it — a text that clearly names a tool never degrades
# --- to plain chat even when the router hallucinates tool="none". Every coercion is
# --- logged loudly. Red (أ/ب/ج) per docs/REMEDIATION_PLAN.md §2.1. -------------------


def test_keyword_net_unit_maps_and_guards():
    """Direct unit contract: colloquial tool words map to real tools with a clean
    launch arg; near-miss words (الشغل the noun, افتحت past tense) never coerce."""
    from src.dispatcher import _keyword_net

    assert _keyword_net("افحصلي الجيميل") == ("gmail", "")
    assert _keyword_net("فحص بريدي بليز") == ("gmail", "")
    assert _keyword_net("شو وضع الجهاز؟") == ("telemetry", "")
    assert _keyword_net("شو مواعيدي بكرة؟") == ("calendar", "")
    assert _keyword_net("شو مهامي اليوم؟") == ("tasks", "")
    assert _keyword_net("اعطيني الإحاطة") == ("brief", "")
    assert _keyword_net("افتحي الآلة الحاسبة على جهازي") == ("launch", "الآلة الحاسبة")
    assert _keyword_net("افتحيلي الآلة الحاسبة لو سمحت") == ("launch", "الآلة الحاسبة")
    assert _keyword_net("شغّل سبوتيفاي") == ("launch", "سبوتيفاي")
    # guards — never a false launch
    assert _keyword_net("رايح ع الشغل بكره") == ("none", "")
    assert _keyword_net("افتحت الملف امبارح") == ("none", "")
    assert _keyword_net("شو أخبارك اليوم؟") == ("none", "")
    assert _keyword_net("شو النتيجة؟") == ("none", "")  # النتيجة is not النت


async def test_keyword_net_rescues_router_miss_gmail(make_settings, logs):
    """Red (أ): «افحصلي الجيميل» + router says tool=none -> the REAL gmail
    executes at the HEAVY tool lane; the coercion is logged loudly (audit C-1)."""
    registry = FakeRegistry(result="3 رسائل غير مقروءة")
    script = _Scripted(
        httpx.Response(200, content=_sse(_router_json("direct", DEFAULT_ACK_AR))),
        httpx.Response(200, content=_sse(_chunk("عندك"), _chunk(" بريد"))),
    )
    async with _gateway(script) as client:
        out = await _collect(
            FrontDoorDispatcher(client, make_settings()).handle("افحصلي الجيميل", tools=registry)
        )
    assert registry.calls == [("gmail", "")]
    assert out == [DEFAULT_ACK_AR, "عندك", " بريد"]
    assert script.models() == [FAST_PIN, HEAVY_PIN]
    assert any("keyword net" in str(m) for m in logs)


async def test_keyword_net_rescues_router_miss_telemetry(make_settings, logs):
    """Red (ب): «شو وضع الجهاز؟» + router miss -> telemetry executes for real."""
    registry = FakeRegistry(result="المعالج 12%")
    script = _Scripted(
        httpx.Response(200, content=_sse(_router_json("direct", DEFAULT_ACK_AR))),
        httpx.Response(200, content=_sse(_chunk("المعالج"), _chunk(" 12%"))),
    )
    async with _gateway(script) as client:
        out = await _collect(
            FrontDoorDispatcher(client, make_settings()).handle("شو وضع الجهاز؟", tools=registry)
        )
    assert registry.calls == [("telemetry", "")]
    assert out == [DEFAULT_ACK_AR, "المعالج", " 12%"]
    assert script.models() == [FAST_PIN, HEAVY_PIN]
    assert any("keyword net" in str(m) for m in logs)


async def test_keyword_net_launch_captures_clean_app_name(make_settings, logs):
    """The live calculator failure (07:04, audit C-1/C-7): «افتحي الآلة الحاسبة
    على جهازي» + router miss -> launch carries the CLEAN app name (device clause
    stripped); the owner notification comes from the coordinator itself."""
    registry = FakeRegistry(result=None)
    script = _Scripted(
        httpx.Response(200, content=_sse(_router_json("direct", DEFAULT_ACK_AR))),
    )
    async with _gateway(script) as client:
        out = await _collect(
            FrontDoorDispatcher(client, make_settings()).handle(
                "افتحي الآلة الحاسبة على جهازي", tools=registry
            )
        )
    assert registry.calls == [("launch", "الآلة الحاسبة")]
    assert out == [DEFAULT_ACK_AR]
    assert any("keyword net" in str(m) for m in logs)


async def test_unknown_router_tool_string_coerced_loudly_not_silent(make_settings, logs):
    """Red (ج): the router emits an UNKNOWN tool string -> never silent: the
    unknown-tool coercion logs loudly, then the net recovers the real intent."""
    registry = FakeRegistry(result=None)
    script = _Scripted(
        httpx.Response(200, content=_sse(_tool_router("spotify", DEFAULT_ACK_AR))),
    )
    async with _gateway(script) as client:
        out = await _collect(
            FrontDoorDispatcher(client, make_settings()).handle("شغّل سبوتيفاي", tools=registry)
        )
    assert registry.calls == [("launch", "سبوتيفاي")]
    assert out == [DEFAULT_ACK_AR]
    assert any("unknown tool" in str(m) for m in logs)
    assert any("keyword net" in str(m) for m in logs)


async def test_keyword_net_silent_on_plain_chat(make_settings, logs):
    """Plain chat with no tool words: the net stays silent — no coercion, no log,
    the answer streams on the FAST conversation lane."""
    script = _Scripted(
        httpx.Response(200, content=_sse(_router_json("direct", "من عيوني"))),
        httpx.Response(200, content=_sse(_chunk("تمام"))),
    )
    async with _gateway(script) as client:
        out = await _collect(FrontDoorDispatcher(client, make_settings()).handle("كيفك اليوم؟"))
    assert out == ["من عيوني", "تمام"]
    assert script.models() == [FAST_PIN, FAST_PIN]
    assert not any("keyword net" in str(m) for m in logs)
