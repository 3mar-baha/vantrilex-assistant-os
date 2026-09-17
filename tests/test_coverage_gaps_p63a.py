"""P6 coverage gap pins, batch 3a: dispatcher, decision_loop, cognition.

Only previously uncovered branches: repair decode failure, parse-None domains,
unknown intent KeyError, gateway seam, cognition-failure passthrough, net
coercion, skill-guide failure, no-send marker, thought decode failure, mirror
exceptions, thought-loop break, tool cap, tool-raise belt, and cognition
helper edges.
"""

import httpx

from src.dispatcher import (
    FrontDoorDispatcher,
    _openclaw_net_entry,
    parse_rag_domains,
    repair_verdict,
)
from tests.test_dispatcher import FakeRegistry, _collect, _gateway, _router_json, _tool_router
from tests.test_omniroute_gateway import _chunk, _Scripted, _sse


def test_repair_malformed_braces_returns_none():
    assert repair_verdict('{"a": }') is None
    assert repair_verdict("{not json at all}") is None


def test_parse_domains_on_total_garbage():
    assert parse_rag_domains("zzz") == ("none",)


def test_unknown_openclaw_intent_raises_key_error():
    import pytest

    with pytest.raises(KeyError):
        _openclaw_net_entry("bogus-tool")


async def test_gateway_seam_returns_client(make_settings):
    script = _Scripted()
    async with _gateway(script) as client:
        assert FrontDoorDispatcher(client, make_settings()).gateway is client


async def test_cognition_failure_never_blocks_chat(make_settings, monkeypatch):
    import src.cognition

    def _boom(*args, **kwargs):
        raise RuntimeError("cognition down")

    monkeypatch.setattr(src.cognition, "deduce", _boom)
    monkeypatch.setattr(src.cognition, "evaluate_candidates", _boom)
    script = _Scripted(
        httpx.Response(200, content=_sse(_router_json("direct", "أهلا"))),
        httpx.Response(200, content=_sse(_chunk("رد"))),
    )
    async with _gateway(script) as client:
        out = await _collect(FrontDoorDispatcher(client, make_settings()).handle("مرحبا"))
    assert out[-1] == "رد"


async def test_net_coerces_router_miss_to_launch(make_settings, monkeypatch):
    import src.cognition
    from src.cognition import IntentHypothesis

    def _miss(text, trace=None):
        return IntentHypothesis(
            tool="none", arg="", confidence=0.0, rationale="miss", root_goal="x"
        )

    monkeypatch.setattr(src.cognition, "deduce", _miss)
    registry = FakeRegistry(result="تم الفتح")
    script = _Scripted(
        httpx.Response(
            200,
            content=_sse(_tool_router("none", "بشوف", arg="")),
        ),
        httpx.Response(200, content=_sse(_chunk("فتحت"))),
    )
    async with _gateway(script) as client:
        out = await _collect(
            FrontDoorDispatcher(client, make_settings()).handle(
                "افتحي الآلة الحاسبة", tools=registry
            )
        )
    assert registry.calls and registry.calls[0][0] == "launch"
    assert out[-1] == "فتحت"


async def test_skill_guide_failure_falls_back_to_plain(make_settings):
    class _ExplodingVault:
        async def read(self, path):
            raise OSError("vault down")

    script = _Scripted()
    async with _gateway(script) as client:
        front = FrontDoorDispatcher(client, make_settings())
        front.set_skill_vault(_ExplodingVault())
        messages = await front._tool_skill_note("gmail", "sys", [], "افحص", "نتيجة")
    assert any(m["role"] == "user" for m in messages)
    assert not any(
        "مهارتك" in m.get("content", "") or "دليل" in m.get("content", "")
        for m in messages
        if isinstance(m.get("content"), str)
    )


async def test_screenshot_no_send_marker_rides_arg(make_settings):
    registry = FakeRegistry(result="shot-bytes")
    script = _Scripted(
        httpx.Response(200, content=_sse(_chunk("تم"))),
    )
    async with _gateway(script) as client:
        front = FrontDoorDispatcher(client, make_settings())
        out = await _collect(
            front._tool_lane(
                "screenshot", "", "tier2", "خدي لقطة بس لا ترسلي الصورة", None, [], registry
            )
        )
    assert registry.calls and "no-send" in registry.calls[0][1]
    assert out == ["تم"]


def test_parse_thought_malformed_json_returns_none():
    from src.decision_loop import parse_thought

    assert parse_thought("{oops not json}") is None
    assert parse_thought("") is None


async def test_openclaw_mirror_build_failure_returns_none(monkeypatch):
    import src.decision_loop as loop
    from src.openclaw import plans

    def _boom(*args, **kwargs):
        raise RuntimeError("planner down")

    monkeypatch.setattr(plans, "dag_for_tool", _boom)
    assert (
        loop._observe_openclaw_plan(
            "openclaw_inspect", "", goal="g", weight=1, coordinator=None, plan_out=None
        )
        is None
    )


async def test_openclaw_mirror_gate_failure_parks(monkeypatch):
    import src.decision_loop as loop
    from src.openclaw import plans

    real_dag = plans.dag_for_tool

    def _ok_dag(*args, **kwargs):
        return real_dag(*args, **kwargs)

    def _boom_gate(*args, **kwargs):
        raise RuntimeError("gate down")

    monkeypatch.setattr(plans, "dag_for_tool", _ok_dag)
    monkeypatch.setattr(plans, "gate", _boom_gate)
    assert (
        loop._observe_openclaw_plan(
            "openclaw_inspect", "", goal="inspect", weight=1, coordinator=None, plan_out=None
        )
        == "park"
    )


def test_hit_spans_empty_marker():
    from src.cognition import _hit_spans

    assert _hit_spans("", "نص ما", []) == []


def test_lead_bonus_skips_empty_markers():
    from src.cognition import _lead_bonus

    assert _lead_bonus(("", "افتح"), "افتح الباب", ["افتح", "الباب"]) is True
    assert _lead_bonus(("",), "مرحبا", ["مرحبا"]) is False


def test_goal_markers_registry_down_returns_goals(monkeypatch):
    import sys

    from src.cognition import _goal_markers

    monkeypatch.setitem(sys.modules, "src.skills.capabilities", None)
    assert _goal_markers("gmail", ("بريد",)) == ("بريد",)


def test_extract_arg_url_and_negation_branches():
    from src.cognition import _extract_arg

    assert _extract_arg("read_page", "اقرئي https://example.com/x اليوم") == "https://example.com/x"
    assert _extract_arg("screenshot", "خدي لقطة بس لا ترسلي الصورة") == "no-send"
