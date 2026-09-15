"""Tier 1 — ReAct decision-loop skeleton contracts (Phase-1 foundations).

Hermetic: scripted fake gateway/tools/coordinator/clock, zero network.
The loop ships behind SARA_REACT_LOOP=off; these tests pin bounds (no
runaway), the pivot policy, the confirmation park, and the ack protocol.
"""

import json

import pytest

from src.decision_loop import (
    INFORMATION_TOOLS,
    PARK_LINE_AR,
    SUMMARY_HEAD_AR,
    LoopBudget,
    parse_thought,
    react_loop_enabled,
    run_decision_loop,
)
from src.gateway import GatewayError, Tier
from src.tools import TOOL_FAIL_AR


def router_json(tool="calendar", arg="غدا", ack="لحظة بفحصلك"):
    return json.dumps(
        {"route": "tier2", "tool": tool, "arg": arg, "ack": ack, "voice_reply": False},
        ensure_ascii=False,
    )


def thought_json(tool=None, arg="", final=False):
    action = None if tool is None else {"tool": tool, "arg": arg}
    return json.dumps({"action": action, "final": final})


class FakeGateway:
    """Scripted chat() replies + stream_chat() deltas; records every call."""

    def __init__(self, chats=None, streams=None, chat_error=None):
        self.chats = list(chats or [])
        self.streams = list(streams or [])
        self.chat_error = chat_error
        self.chat_calls = []
        self.stream_calls = []
        self.heavy_calls = []

    async def chat(self, messages, *, tier, **kwargs):
        self.chat_calls.append({"tier": tier, "messages": messages})
        if self.chat_error is not None:
            raise self.chat_error
        return self.chats.pop(0)

    async def stream_chat(self, messages, *, tier, **kwargs):
        self.stream_calls.append({"tier": tier, "messages": messages})
        for delta in self.streams.pop(0):
            yield delta

    async def stream_heavy(self, messages, *, n_tasks=1, **kwargs):
        self.heavy_calls.append({"n_tasks": n_tasks, "messages": messages})
        for delta in self.streams.pop(0):
            yield delta


class FakeTools:
    def __init__(self, results):
        self.results = dict(results)
        self.calls = []

    async def call(self, tool, arg=""):
        self.calls.append((tool, arg))
        result = self.results.get(tool, "")
        if isinstance(result, Exception):
            raise result
        return result


class FakeCoordinator:
    def __init__(self, confirmed=()):
        self.confirmed = set(confirmed)

    def has_confirmation(self, tool, arg):
        return (tool, arg) in self.confirmed


class FakeFront:
    def __init__(self):
        self.voice_hint = False


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        self.t += 5.0  # every read advances: pulses fire each stage
        return self.t


def make_pulse():
    calls = []

    async def pulse():
        calls.append(1)

    return pulse, calls


async def collect(gen):
    return [d async for d in gen]


def run(loop_kwargs):
    return collect(run_decision_loop(**loop_kwargs))


def base_kwargs(gateway, tools, **over):
    kw = {
        "gateway": gateway,
        "tools": tools,
        "user_text": "شو عندي بكرا؟",
        "system": "sys",
        "coordinator": FakeCoordinator(confirmed={("close", "x")}),
    }
    kw.update(over)
    return kw


def test_flag_defaults_off(monkeypatch):
    monkeypatch.delenv("SARA_REACT_LOOP", raising=False)
    assert react_loop_enabled() is False


@pytest.mark.parametrize("value", ["1", "on", "true", "yes", " ON "])
def test_flag_enables(monkeypatch, value):
    monkeypatch.setenv("SARA_REACT_LOOP", value)
    assert react_loop_enabled() is True


def test_parse_thought_rejects_unknown_tool():
    assert parse_thought('{"action": {"tool": "rm_rf", "arg": ""}, "final": false}') is None
    assert parse_thought("not json") is None
    parsed = parse_thought(thought_json("calendar", "غدا"))
    assert parsed == {"action": {"tool": "calendar", "arg": "غدا"}, "final": False}


async def test_ack_first_and_plain_path():
    gw = FakeGateway(
        chats=[router_json("none", "", "أهلا فيك")],
        streams=[["plain reply"]],
    )
    tools = FakeTools({})
    deltas = await run(base_kwargs(gw, tools))
    assert deltas[0] == "أهلا فيك"
    assert deltas[1:] == ["plain reply"]
    assert tools.calls == []


async def test_router_error_degrades_to_plain_chat():
    gw = FakeGateway(chat_error=GatewayError("down"), streams=[["plain"]])
    tools = FakeTools({})
    deltas = await run(base_kwargs(gw, tools))
    assert "plain" in deltas
    assert tools.calls == []


async def test_chains_two_tools_then_narrates():
    gw = FakeGateway(
        chats=[
            router_json("calendar", "غدا", "لحظة"),
            thought_json("tasks", "اليوم"),
            thought_json(final=True),
        ],
        streams=[["سرد نهائي"]],
    )
    tools = FakeTools({"calendar": "موعد 9ص", "tasks": "مهمتان"})
    front = FakeFront()
    pulse, pulses = make_pulse()
    deltas = await run(base_kwargs(gw, tools, front=front, pulse_cb=pulse, now_fn=Clock()))
    assert deltas[0] == "لحظة"
    assert deltas[-1] == "سرد نهائي"
    assert tools.calls == [("calendar", "غدا"), ("tasks", "اليوم")]
    assert len(pulses) >= 3  # router + thought + narration stages pulsed
    narrated = gw.heavy_calls[-1]["messages"]
    assert gw.heavy_calls[-1]["n_tasks"] == 2
    blob = " ".join(m["content"] if isinstance(m.get("content"), str) else "" for m in narrated)
    assert "موعد 9ص" in blob and "مهمتان" in blob


async def test_empty_observation_pivots_once_to_web_search():
    gw = FakeGateway(
        chats=[router_json("calendar", "غدا", "لحظة"), thought_json(final=True)],
        streams=[["سرد"]],
    )
    tools = FakeTools({"calendar": TOOL_FAIL_AR, "web_search": "نتائج بحث"})
    deltas = await run(base_kwargs(gw, tools))
    assert tools.calls == [("calendar", "غدا"), ("web_search", "غدا")]
    assert deltas[-1] == "سرد"


async def test_non_information_tool_never_pivots():
    gw = FakeGateway(
        chats=[router_json("telemetry", "", "لحظة"), thought_json(final=True)],
        streams=[["سرد"]],
    )
    assert "telemetry" not in INFORMATION_TOOLS
    tools = FakeTools({"telemetry": TOOL_FAIL_AR})
    await run(base_kwargs(gw, tools))
    assert tools.calls == [("telemetry", "")]


async def test_same_tool_repeat_halts_to_summary():
    gw = FakeGateway(
        chats=[router_json("calendar", "غدا", "لحظة")] + [thought_json("calendar", "غدا")] * 6
    )
    tools = FakeTools({"calendar": "موعد"})
    deltas = await run(base_kwargs(gw, tools, budget=LoopBudget()))
    assert tools.calls == [("calendar", "غدا"), ("calendar", "غدا")]  # capped at 2
    assert deltas[0] == "لحظة"
    assert SUMMARY_HEAD_AR in deltas[-1]
    assert "موعد" in deltas[-1]


async def test_iteration_budget_caps_and_summarizes():
    gw = FakeGateway(
        chats=[router_json("calendar", "غدا", "لحظة")] + [thought_json("tasks", "x")] * 4
    )
    tools = FakeTools({"calendar": "c", "tasks": "t"})
    deltas = await run(base_kwargs(gw, tools, budget=LoopBudget(max_iterations=2)))
    assert len(tools.calls) <= 2
    assert SUMMARY_HEAD_AR in deltas[-1]


async def test_irreversible_without_confirmation_parks():
    gw = FakeGateway(chats=[router_json("close", "notepad", "لحظة")])
    tools = FakeTools({"close": "SHOULD-NOT-RUN"})
    deltas = await run(base_kwargs(gw, tools, coordinator=FakeCoordinator()))
    assert deltas == ["لحظة", PARK_LINE_AR]
    assert tools.calls == []


async def test_irreversible_with_confirmation_executes():
    gw = FakeGateway(
        chats=[router_json("close", "x", "لحظة"), thought_json(final=True)],
        streams=[["سرد"]],
    )
    tools = FakeTools({"close": "اتقفل"})
    deltas = await run(base_kwargs(gw, tools))
    assert tools.calls == [("close", "x")]
    assert deltas[-1] == "سرد"


async def test_invalid_thought_tool_treated_as_final():
    gw = FakeGateway(
        chats=[
            router_json("calendar", "غدا", "لحظة"),
            '{"action": {"tool": "nope", "arg": ""}, "final": false}',
        ],
        streams=[["سرد"]],
    )
    tools = FakeTools({"calendar": "موعد"})
    deltas = await run(base_kwargs(gw, tools))
    assert tools.calls == [("calendar", "غدا")]
    assert deltas[-1] == "سرد"


async def test_tier_mapping_plain_paths():
    for route, tier in [("direct", Tier.FAST), ("tier2", Tier.MEDIUM), ("tier3", Tier.HEAVY)]:
        payload = json.loads(router_json("none", "", "تمام"))
        payload["route"] = route
        gw = FakeGateway(
            chats=[json.dumps(payload, ensure_ascii=False)],
            streams=[["p"]],
        )
        await run(base_kwargs(gw, FakeTools({})))
        assert gw.stream_calls[-1]["tier"] is tier


async def test_plan_recorded_and_flushed_without_touching_yields():
    """Mission DAG hooks: plan_out receives plan + checked transcript while the
    streamed deltas stay byte-identical to the unobserved run."""
    from src.cognitive_dag import EphemeralTodo

    async def _run(plan_out):
        gw = FakeGateway(
            chats=[router_json("calendar", "غدا", "لحظة"), thought_json(final=True)],
            streams=[["سرد"]],
        )
        tools = FakeTools({"calendar": "موعد 9ص"})
        kw = base_kwargs(gw, tools, user_text="شو عندي مواعيد بكرا؟")
        if plan_out is not None:
            kw["plan_out"] = plan_out
        return await run(kw), tools

    plain_deltas, _ = await _run(None)
    holder: dict = {}
    obs_deltas, tools = await _run(holder)
    assert obs_deltas == plain_deltas  # yields untouched by observation
    assert holder["plan"].weight == 2
    assert isinstance(holder["todo"], EphemeralTodo)
    assert "[x] calendar" in holder["transcript"]
    assert "[x] synthesis" in holder["transcript"]
    assert tools.calls == [("calendar", "غدا")]


async def test_plan_flushes_on_park():
    holder: dict = {}
    gw = FakeGateway(chats=[router_json("close", "notepad", "لحظة")])
    tools = FakeTools({"close": "SHOULD-NOT-RUN"})
    kw = base_kwargs(gw, tools, coordinator=FakeCoordinator(), plan_out=holder)
    kw["user_text"] = "شو عندي مواعيد بكرا؟"  # plan names calendar; router parks close
    deltas = await run(kw)
    assert deltas == ["لحظة", PARK_LINE_AR]
    assert "[ ] calendar" in holder["transcript"]  # planned, never executed
    assert "[ ] synthesis" in holder["transcript"]
    assert holder["todo"].items == []  # memory freed


async def test_openclaw_turn_records_dag_observability():
    """Step-7 adapter: an openclaw verdict DAG-builds + gate-consults into
    plan_out without changing yields (fetch probe is reversible → executes)."""
    from src.openclaw.protocol import OpKind

    holder: dict = {}
    gw = FakeGateway(
        chats=[router_json("openclaw_fetch", "https://x", "لحظة"), thought_json(final=True)],
        streams=[["سرد"]],
    )
    tools = FakeTools({"openclaw_fetch": "نص"})
    deltas = await run(base_kwargs(gw, tools, plan_out=holder))
    assert deltas[-1] == "سرد"
    dag = holder["openclaw_dag"]
    assert dag.ops[0].op == OpKind.EXTRACT
    assert holder["openclaw_gate"] == "go"


async def test_non_openclaw_turn_records_no_dag():
    holder: dict = {}
    gw = FakeGateway(
        chats=[router_json("calendar", "غدا", "لحظة"), thought_json(final=True)],
        streams=[["سرد"]],
    )
    tools = FakeTools({"calendar": "موعد"})
    await run(base_kwargs(gw, tools, plan_out=holder))
    assert "openclaw_dag" not in holder
    assert "openclaw_gate" not in holder


async def test_openclaw_park_still_parks_with_dag_recorded():
    """The adapter never softens enforcement: unconfirmed desktop parks AND
    records its (reversible-probe) DAG side by side."""
    holder: dict = {}
    gw = FakeGateway(chats=[router_json("openclaw_desktop", "x", "لحظة")])
    tools = FakeTools({"openclaw_desktop": "SHOULD-NOT-RUN"})
    deltas = await run(base_kwargs(gw, tools, coordinator=FakeCoordinator(), plan_out=holder))
    assert deltas == ["لحظة", PARK_LINE_AR]
    assert tools.calls == []
    assert holder["openclaw_dag"].ops[0].op.value == "screenshot"


async def test_thought_prompt_names_opkind_vocabulary():
    from src.decision_loop import THOUGHT_PROMPT_AR

    for verb in ("inspect_tree", "type_text", "navigate", "hotkey"):
        assert verb in THOUGHT_PROMPT_AR


async def test_final_narration_rides_stream_heavy_with_call_count():
    """Step-10 escalation wiring: FINAL narration streams through
    stream_heavy with n_tasks = tool calls made (MoE past threshold)."""
    gw = FakeGateway(
        chats=[
            router_json("calendar", "غدا", "لحظة"),
            thought_json("tasks", "x"),
            thought_json(final=True),
        ],
        streams=[["سرد"]],
    )
    tools = FakeTools({"calendar": "c", "tasks": "t"})
    deltas = await run(base_kwargs(gw, tools))
    assert deltas[-1] == "سرد"
    assert len(gw.heavy_calls) == 1
    assert gw.heavy_calls[0]["n_tasks"] == 2
    assert gw.stream_calls == []


async def test_park_warning_dynamic_when_gateway_serves():
    """Spontaneity doctrine: a serving gateway authors the PARK ask from
    the pending action — the static line is the floor, not the voice."""
    gw = FakeGateway(
        chats=[
            router_json("close", "notepad", "لحظة"),
            "عمر، رح أسكّر المفكرة، أكّدلي بـ«نعم» لو موافق.",
        ]
    )
    tools = FakeTools({"close": "SHOULD-NOT-RUN"})
    deltas = await run(base_kwargs(gw, tools, coordinator=FakeCoordinator()))
    assert deltas == ["لحظة", "عمر، رح أسكّر المفكرة، أكّدلي بـ«نعم» لو موافق."]
    assert tools.calls == []


async def test_park_warning_static_on_empty_reply():
    gw = FakeGateway(chats=[router_json("close", "notepad", "لحظة"), "   "])
    tools = FakeTools({"close": "SHOULD-NOT-RUN"})
    deltas = await run(base_kwargs(gw, tools, coordinator=FakeCoordinator()))
    assert deltas == ["لحظة", PARK_LINE_AR]
    assert tools.calls == []


async def test_park_warning_static_on_gateway_error():
    """Router serves, warning call dies → static floor, still parked."""

    class FlakyGateway(FakeGateway):
        async def chat(self, messages, *, tier, **kwargs):
            self.chat_calls.append({"tier": tier, "messages": messages})
            if len(self.chat_calls) > 1:
                raise GatewayError("brain down")
            return self.chats.pop(0)

    gw = FlakyGateway(chats=[router_json("close", "notepad", "لحظة")])
    tools = FakeTools({"close": "SHOULD-NOT-RUN"})
    deltas = await run(base_kwargs(gw, tools, coordinator=FakeCoordinator()))
    assert deltas == ["لحظة", PARK_LINE_AR]
    assert tools.calls == []
