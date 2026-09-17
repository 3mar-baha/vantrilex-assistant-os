"""P6 coverage gap pins, batch 4a: dispatcher edges, decision-loop bounds,
cognition multi-task trace, coordinator close confirm flows, protocol ts."""

import httpx

from src.dispatcher import (
    FrontDoorDispatcher,
    _openclaw_net_entry,
    parse_rag_domains,
    repair_verdict,
)
from tests.test_dispatcher import FakeRegistry, _collect, _gateway, _tool_router
from tests.test_omniroute_gateway import _Scripted, _chunk, _sse


def test_repair_decode_failure_returns_none():
    assert repair_verdict('{"a": }') is None


def test_parse_domains_garbage_returns_none_tuple():
    assert parse_rag_domains("zzz-no-braces") == ("none",)


def test_unknown_openclaw_intent_key_error():
    import pytest

    with pytest.raises(KeyError):
        _openclaw_net_entry("bogus-tool-xyz")


async def test_gateway_seam_returns_client(make_settings):
    script = _Scripted()
    async with _gateway(script) as client:
        assert FrontDoorDispatcher(client, make_settings()).gateway is client


async def test_net_disagreement_keeps_cognition_tool(make_settings, monkeypatch):
    import src.cognition
    from src.cognition import IntentHypothesis

    def _gmail_only(text, trace=None):
        return IntentHypothesis(
            tool="gmail", arg="", confidence=0.9, rationale="t", root_goal="g"
        )

    monkeypatch.setattr(src.cognition, "deduce", _gmail_only)
    registry = FakeRegistry(result="بريدك فاضي")
    script = _Scripted(
        httpx.Response(200, content=_sse(_tool_router("gmail", "بشوف"))),
        httpx.Response(200, content=_sse(_chunk("تمام"))),
    )
    async with _gateway(script) as client:
        await _collect(
            FrontDoorDispatcher(client, make_settings()).handle(
                "افتحي الآلة الحاسبة", tools=registry
            )
        )
    assert registry.calls and registry.calls[0][0] == "gmail"


def test_parse_thought_malformed_json_returns_none():
    from src.decision_loop import SUMMARY_HEAD_AR, parse_thought

    assert parse_thought("{oops not json}") is None
    assert SUMMARY_HEAD_AR  # contract anchor used below


async def test_thought_gateway_error_breaks_to_summary():
    from src.decision_loop import SUMMARY_HEAD_AR, run_decision_loop
    from src.gateway import GatewayError

    from tests.suite.tier1_resilience.test_decision_loop import (
        FakeCoordinator,
        FakeFront,
        FakeGateway,
        FakeTools,
        make_pulse,
        router_json,
        thought_json,
    )

    gateway = FakeGateway(
        chats=[router_json(tool="calendar", arg="بكرا"), thought_json(tool="calendar", arg="بكرا")]
    )
    real_chat = gateway.chat

    async def _flaky_chat(messages, **kwargs):
        if len(gateway.chat_calls) >= 1:
            raise GatewayError("thought lane down")
        return await real_chat(messages, **kwargs)

    gateway.chat = _flaky_chat
    pulse, _ = make_pulse()
    out = [
        d
        async for d in run_decision_loop(
            gateway=gateway,
            tools=FakeTools({}),
            user_text="شو عندي بكرا",
            coordinator=FakeCoordinator(),
            front=FakeFront(),
            pulse_cb=pulse,
        )
    ]
    assert any(SUMMARY_HEAD_AR in delta for delta in out)


async def test_tool_call_cap_breaks_to_summary():
    from src.decision_loop import SUMMARY_HEAD_AR, LoopBudget, run_decision_loop

    from tests.suite.tier1_resilience.test_decision_loop import (
        FakeCoordinator,
        FakeFront,
        FakeGateway,
        FakeTools,
        make_pulse,
        router_json,
        thought_json,
    )

    gateway = FakeGateway(
        chats=[
            router_json(tool="calendar", arg="بكرا"),
            thought_json(tool="calendar", arg="بكرا"),
            thought_json(tool=None, final=True),
        ],
        streams=[["x"]],
    )
    pulse, _ = make_pulse()
    out = [
        d
        async for d in run_decision_loop(
            gateway=gateway,
            tools=FakeTools({"calendar": "موعد"}),
            user_text="شو عندي بكرا",
            coordinator=FakeCoordinator(),
            front=FakeFront(),
            pulse_cb=pulse,
            budget=LoopBudget(max_tool_calls=0),
        )
    ]
    assert any(SUMMARY_HEAD_AR in delta for delta in out)


async def test_tool_raise_belt_records_failed_observation():
    from src.decision_loop import SUMMARY_HEAD_AR, run_decision_loop

    from tests.suite.tier1_resilience.test_decision_loop import (
        FakeCoordinator,
        FakeFront,
        FakeGateway,
        FakeTools,
        make_pulse,
        router_json,
        thought_json,
    )

    tools = FakeTools({})
    tools.results["telemetry"] = RuntimeError("bridge exploded")
    gateway = FakeGateway(
        chats=[
            router_json(tool="telemetry", arg=""),
            thought_json(tool="telemetry", arg=""),
            thought_json(tool=None, final=True),
        ],
        streams=[["نarration"]],
    )
    pulse, _ = make_pulse()
    plan_out: dict = {}
    out = [
        d
        async for d in run_decision_loop(
            gateway=gateway,
            tools=tools,
            user_text="شو وضع الجهاز",
            coordinator=FakeCoordinator(),
            front=FakeFront(),
            pulse_cb=pulse,
            plan_out=plan_out,
        )
    ]
    assert out
    assert gateway.heavy_calls, "final narration must stream after the belt failure"
    assert tools.calls and tools.calls[0][0] == "telemetry"


def test_multitask_trace_penalty_branch():
    from src.cognition import ReflectiveTrace, evaluate_candidates

    trace = ReflectiveTrace()
    trace.record_outcome("multi_task", False, "miss")
    trace.record_outcome("multi_task", False, "miss again")
    ranked = evaluate_candidates("شغلي المتصفح وافتحي الكروم", trace=trace)
    assert ranked and ranked[0].tool


def test_close_error_branch_honest_line(tmp_path):
    import asyncio as _aio
    import json as _json

    from bridge.guard import Guard
    from src.pc_actions import LaunchStatus, PCActionCoordinator

    path = tmp_path / "whitelist.json"
    path.write_text(
        _json.dumps(
            {
                "allowed_apps": [{"name": "calc", "executable": "calc.exe", "auto_approve": True}],
                "restricted_actions": [],
            }
        ),
        encoding="utf-8",
    )

    class _Bridge:
        async def send_cmd(self, cmd, args, **kw):
            return {"status": "error", "detail": "daemon boom", "audit_code": "PC-9"}

    class _Notify:
        def __init__(self):
            self.sent = []

        async def notify(self, text):
            self.sent.append(text)

    class _Vault:
        async def upsert(self, *a, **k):
            pass

        async def read(self, *a, **k):
            raise FileNotFoundError

    coord = PCActionCoordinator(_Bridge(), _Vault(), _Notify(), guard=Guard(path))
    assert _aio.run(coord.request_close("calc", origin="owner_chat")) == LaunchStatus.REFUSED


def test_close_confirm_execute_and_failure(tmp_path):
    import asyncio as _aio
    import json as _json

    from bridge.guard import Guard
    from src.pc_actions import LaunchStatus, PCActionCoordinator

    path = tmp_path / "whitelist.json"
    path.write_text(
        _json.dumps(
            {
                "allowed_apps": [{"name": "calc", "executable": "calc.exe", "auto_approve": True}],
                "restricted_actions": [],
            }
        ),
        encoding="utf-8",
    )

    class _OkBridge:
        def __init__(self):
            self.commands = []

        async def send_cmd(self, cmd, args, **kw):
            self.commands.append((cmd, dict(args)))
            if "confirmation_id" in args:
                return {"status": "ok", "detail": "ok", "audit_code": "PC-1", "killed_processes": 1}
            return {"status": "error", "detail": "needs confirmation", "audit_code": "PC-1"}

    class _Notify:
        def __init__(self):
            self.sent = []

        async def notify(self, text):
            self.sent.append(text)

    class _Vault:
        def __init__(self):
            self.upserts = []

        async def upsert(self, *args, **kwargs):
            self.upserts.append((args, kwargs))

        async def read(self, *args, **kwargs):
            raise FileNotFoundError

    coord = PCActionCoordinator(_OkBridge(), _Vault(), _Notify(), guard=Guard(path))
    assert (
        _aio.run(coord.request_close("calc", origin="owner_chat"))
        == LaunchStatus.CONFIRMATION_REQUIRED
    )
    assert _aio.run(coord.handle_owner_reply("نعم")) == "calc"

    coord2 = PCActionCoordinator(_OkBridge(), _Vault(), _Notify(), guard=Guard(path))
    coord2._bridge = _FailBridge()
    assert (
        _aio.run(coord2.request_close("calc", origin="owner_chat"))
        == LaunchStatus.CONFIRMATION_REQUIRED
    )
    assert _aio.run(coord2.handle_owner_reply("نعم")) is None


class _FailBridge:
    async def send_cmd(self, cmd, args, **kw):
        if "confirmation_id" in args:
            return {"status": "error", "detail": "taskkill crashed", "audit_code": "PC-2"}
        return {"status": "error", "detail": "needs confirmation", "audit_code": "PC-2"}


def test_envelope_without_ts_gets_timestamp():
    import json

    from common.protocol import decode_frame

    msg = decode_frame(json.dumps({"v": 1, "id": "abc", "type": "heartbeat"}).encode())
    assert msg.ts is not None
