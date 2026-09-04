"""STT-4 (owner 2026-09-04 evening): the agent manager — multi-task requests
«شغلي المتصفح وحطي قائمة التشغيل ووقفي الفيديو وشغل روكت ليج» executed as
LINES, not just the first action.

Owner's design, implemented as specified:
- HEAVY (nemotron) is the PLANNER: decomposes the request into independent
  lines (parallel) / ordered lines (sequential steps inside one line).
- Each line runs via a sub-agent call on MEDIUM (gpt-oss-120b): the line text
  -> concrete steps [{tool, arg}] validated against the REAL tool set.
- Lines execute concurrently (gather); a sequential line's steps run in order.
- Tool calls are the REAL ToolRegistry handlers (launch/close guards and
  confirmation gates untouched). Hallucinated tool names NEVER execute.
- ONE unified Arabic report reaches the owner.
- Single tasks never enter this path (router/net require 2+ action verbs).
"""

from __future__ import annotations

import json

from src.gateway import GatewayError, Tier

LINE_BROWSER = "شغلي المتصفح وحطي قائمة التشغيل ووقفي الفيديو"
LINE_ROCKET = "شغل روكت ليج"


class _Gateway:
    """Scripted double: HEAVY planner reply + per-line MEDIUM sub-agent replies."""

    def __init__(self, *, heavy_reply=None, heavy_error=None, medium_by_line=None):
        self.heavy_reply = heavy_reply
        self.heavy_error = heavy_error
        self.medium_by_line = medium_by_line or {}
        self.calls: list[tuple[str, str]] = []  # (tier, last user text)

    async def chat(self, messages, *, tier, temperature=0.7, max_tokens=2048):
        user = messages[-1]["content"] if messages else ""
        self.calls.append((tier.value if hasattr(tier, "value") else str(tier), user))
        if tier is Tier.HEAVY:
            if self.heavy_error is not None:
                raise self.heavy_error
            return self.heavy_reply
        # longest scripted line first: «شغل روكت ليج» contains no other, but
        # specific-before-generic guards any nested pair
        for line in sorted(self.medium_by_line, key=len, reverse=True):
            if line in user:
                reply = self.medium_by_line[line]
                if isinstance(reply, Exception):
                    raise reply
                return reply
        raise AssertionError(f"unscripted medium call: {user[:80]}")


class _Tools:
    """Double of the real registry: records every call, serves scripted results."""

    def __init__(self, results=None, fail_tools=()):
        self.calls: list[tuple[str, str]] = []
        self._results = results or {}
        self._fail = set(fail_tools)

    async def call(self, tool: str, arg: str = ""):
        self.calls.append((tool, arg))
        if tool in self._fail:
            raise RuntimeError(f"{tool} exploded")
        return self._results.get((tool, arg))


def _plan_json(*lines) -> str:
    return json.dumps(
        {"lines": [{"mode": mode, "text": text} for mode, text in lines]},
        ensure_ascii=False,
    )


def _manager(gateway, tools):
    from src.agent_manager import AgentManager

    return AgentManager(gateway=gateway, tools=tools)


HEAVY_PLAN = _plan_json(("sequential", LINE_BROWSER), ("parallel", LINE_ROCKET))


async def test_heavy_plan_decomposes_two_lines():
    """HEAVY returns the lines JSON -> the plan carries both lines with modes."""
    manager = _manager(_Gateway(heavy_reply=HEAVY_PLAN), _Tools())
    lines = await manager._plan("أي نص")
    assert [(line.mode, line.text) for line in lines] == [
        ("sequential", LINE_BROWSER),
        ("parallel", LINE_ROCKET),
    ]


async def test_subagent_maps_line_and_hallucinated_tools_drop():
    """A sub-agent mapping containing a REAL tool + a hallucinated name: the
    real one executes, the hallucination NEVER calls the registry and the
    report names the drop (no silent loss, no fake success)."""
    mapping = json.dumps(
        {
            "steps": [
                {"tool": "launch", "arg": "chrome"},
                {"tool": "rm_rf_everything", "arg": "C:\\"},
            ]
        },
        ensure_ascii=False,
    )
    gateway = _Gateway(heavy_reply=HEAVY_PLAN, medium_by_line={LINE_ROCKET: mapping})
    tools = _Tools()
    manager = _manager(gateway, tools)
    report = await manager.run("شغلي روكت ليج")
    assert ("launch", "chrome") in tools.calls
    assert all(tool != "rm_rf_everything" for tool, _ in tools.calls)
    assert "rm_rf_everything" in report  # the drop is named, not hidden


async def test_lines_run_concurrently_and_sequential_steps_in_order():
    """Lines gather (both ran); a sequential line's steps run in recorded
    ORDER — the dependency the planner marked is respected."""
    gateway = _Gateway(
        heavy_reply=HEAVY_PLAN,
        medium_by_line={
            LINE_BROWSER: json.dumps(
                {
                    "steps": [
                        {"tool": "launch", "arg": "chrome"},
                        {"tool": "screenshot", "arg": ""},
                        {"tool": "youtube", "arg": "قائمة تشغيل"},
                    ]
                },
                ensure_ascii=False,
            ),
            LINE_ROCKET: json.dumps({"steps": [{"tool": "launch", "arg": "rocket"}]}),
        },
    )
    tools = _Tools()
    manager = _manager(gateway, tools)
    report = await manager.run(LINE_BROWSER + " و" + LINE_ROCKET)
    assert ("launch", "rocket") in tools.calls  # both lines executed
    seq = [arg for tool, arg in tools.calls if tool in ("launch", "screenshot", "youtube")]
    assert seq.index("chrome") < seq.index("قائمة تشغيل")  # order kept
    assert isinstance(report, str) and report.strip()
    assert "روكت ليج" in report and "المتصفح" in report  # ONE unified report


async def test_plan_failure_degrades_honestly_no_tool_runs():
    """HEAVY dead (GatewayError or unparseable) -> the honest fail line; the
    registry is NEVER touched (no half-executed multi-task)."""
    tools = _Tools()
    manager = _manager(_Gateway(heavy_error=GatewayError("all models exhausted")), tools)
    fail = await manager.run("شغلي شي وشي")
    assert "ما قدرت" in fail
    assert tools.calls == []

    manager2 = _manager(_Gateway(heavy_reply="سأفعل كل شيء فوراً!"), _Tools())
    fail2 = await manager2.run("شغلي شي وشي")
    assert "ما قدرت" in fail2


async def test_one_line_failure_never_kills_the_other():
    """A dead sub-agent on one line is that line's honest failure — the other
    line still executes and reports (isolation by design)."""
    gateway = _Gateway(
        heavy_reply=HEAVY_PLAN,
        medium_by_line={
            LINE_BROWSER: GatewayError("medium down"),
            LINE_ROCKET: json.dumps({"steps": [{"tool": "launch", "arg": "rocket"}]}),
        },
    )
    tools = _Tools()
    manager = _manager(gateway, tools)
    report = await manager.run(LINE_BROWSER + " و" + LINE_ROCKET)
    assert ("launch", "rocket") in tools.calls  # the healthy line ran
    assert "ما قدرت" in report  # the dead line reported honestly


async def test_line_and_step_caps_trim_not_crash():
    """A planner that returns absurd counts is trimmed to the cap — and the
    overflow is NAMED in the report (audit 2026-09-05: silent drops are
    claimed-completions' quiet sibling). The free pools and the owner's
    patience are bounded."""
    many_lines = json.dumps(
        {"lines": [{"mode": "parallel", "text": f"مهمة {i}"} for i in range(9)]},
        ensure_ascii=False,
    )
    gateway = _Gateway(heavy_reply=many_lines, medium_by_line={})
    tools = _Tools()
    manager = _manager(gateway, tools)
    report = await manager.run("شغلي شي وكتير")
    # only MAX_LINES lines ran (each honestly failing its unscripted mapping)
    assert report.count("ما قدرت أنفذها") == 4
    # the trimmed 5 are named, never silently dropped
    assert "5 منهم ما اخدتوها" in report


def test_dispatcher_routes_and_net_multi_task():
    """multi_task is a valid tool; the net coerces 2+ imperative-verb texts to
    multi_task (the router-miss backstop) while a single-verb launch stays
    launch — single tasks keep the direct path."""
    from src.dispatcher import _VALID_TOOLS, _keyword_net

    assert "multi_task" in _VALID_TOOLS
    for phrase in (
        "شغلي المتصفح وافتحي روكت ليج",
        "افتحي المتصفح وحطي قائمة تشغيل ووقفي الفيديو وشغل روكت ليج",
        "سكري كروم وافتحي الآلة الحاسبة",
        "افتحي الآلة الحاسبة بعدها خذي لقطة شاشة",  # the live 7:15pm failure
    ):
        tool, arg = _keyword_net(phrase)
        assert tool == "multi_task", phrase
        assert arg == phrase  # the FULL text rides the arg for decomposition
    assert _keyword_net("افتحي كروم")[0] == "launch"


async def test_registry_multi_task_tool_delegates_and_fails_honestly():
    """ToolRegistry.multi_task: unbound manager -> the honest unavailable
    line; bound -> full-text delegation (one call)."""
    from src.tools import ToolRegistry

    registry = ToolRegistry()
    unbound = await registry.call("multi_task", "شغلي أ و ب")
    assert "ما قدرت" in unbound

    recorded = []

    class _Manager:
        async def run(self, text):
            recorded.append(text)
            return "تقرير موحد"

    registry.bind_agent_manager(_Manager())
    answer = await registry.call("multi_task", "شغلي أ و ب")
    assert recorded == ["شغلي أ و ب"]
    assert answer == "تقرير موحد"


def test_router_prompt_names_multi_task():
    """The router vocabulary teaches multi_task — the primary detector."""
    from src.dispatcher import _ROUTER_PROMPT_AR

    assert "multi_task" in _ROUTER_PROMPT_AR


async def test_no_recursion_step_drops():
    """A sub-agent that maps to multi_task itself (or none) is invalid — the
    recursion guard drops it before any execution."""
    gateway = _Gateway(
        heavy_reply=HEAVY_PLAN,
        medium_by_line={
            LINE_ROCKET: json.dumps(
                {"steps": [{"tool": "multi_task", "arg": "شغلي كل شي"}]},
                ensure_ascii=False,
            )
        },
    )
    tools = _Tools()
    manager = _manager(gateway, tools)
    report = await manager.run(LINE_ROCKET)
    assert tools.calls == []  # nothing executed
    assert "multi_task" in report  # the drop named
