"""Gap-ب (owner 2026-09-05): the multi_task report re-passes through a SECOND
HEAVY narration round — the manager's report is already honest, already
Sara-voiced Arabic («✅/📤/⚠️» per line). Re-narrating it burns a full
nemotron call per multi-task request (latency + free-pool quota) and risks
the narrator REWRITING the manager's honest markers.

Contract (dispatcher._tool_lane):
- multi_task results stream to the owner AS-IS (the launch-tool contract:
  the result IS the answer); every other tool keeps its HEAVY narration.
"""

from __future__ import annotations

import json


class _Tools:
    def __init__(self, result):
        self._result = result
        self.calls: list[str] = []

    async def call(self, tool, arg=""):
        self.calls.append(tool)
        return self._result


class _Gateway:
    """Scripted router verdict + streamed answer deltas; records stream tiers."""

    def __init__(self, *, verdict: str, deltas: tuple = ()):
        self._verdict = verdict
        self._deltas = deltas
        self.streamed_tiers: list = []

    async def chat(self, messages, *, tier, **kw):
        return self._verdict  # the router verdict (.chat, always FAST)

    async def stream_chat(self, messages, *, tier, temperature=0.7, max_tokens=2048):
        self.streamed_tiers.append(tier)
        for delta in self._deltas:
            yield delta

    async def stream_heavy(self, messages, *, n_tasks=1, **kw):
        from src.gateway import Tier as _Tier

        self.streamed_tiers.append(_Tier.HEAVY)
        for delta in self._deltas:
            yield delta


_MULTI_VERDICT = json.dumps(
    {
        "route": "tier2",
        "tool": "multi_task",
        "arg": "شغلي كروم وافتحي روكت ليج",
        "ack": "من عيوني",
        "voice_reply": False,
    },
    ensure_ascii=False,
)
_TELEMETRY_VERDICT = json.dumps(
    {
        "route": "tier2",
        "tool": "telemetry",
        "arg": "",
        "ack": "لحظة بفحصلك",
        "voice_reply": False,
    },
    ensure_ascii=False,
)


async def test_multi_task_result_streams_as_is_no_narration():
    """THE contract: a multi_task result reaches the owner VERBATIM — zero
    narration rounds (the manager's report is the final voice)."""
    from src.dispatcher import FrontDoorDispatcher

    gateway = _Gateway(verdict=_MULTI_VERDICT)  # NO answer deltas scripted
    tools = _Tools("«شغلي كروم» — ✅ launch:chrome")
    dispatcher = FrontDoorDispatcher(gateway, settings=None)
    out = []
    async for delta in dispatcher.handle("شغلي كروم وافتحي روكت ليج", tools=tools):
        out.append(delta)
    assert tools.calls == ["multi_task"]
    assert any("✅ launch:chrome" in d for d in out)  # the result verbatim
    assert gateway.streamed_tiers == []  # ZERO narration stream rounds


async def test_other_tools_keep_heavy_narration():
    """Only multi_task is exempt — telemetry & co. still narrate at HEAVY
    (the compression prompt contract is untouched for them)."""
    from src.dispatcher import FrontDoorDispatcher
    from src.gateway import Tier

    gateway = _Gateway(verdict=_TELEMETRY_VERDICT, deltas=("المعالج 23% والرام تمام.",))
    tools = _Tools("المعالج 23% والرام 5.2/16 جيجا")
    dispatcher = FrontDoorDispatcher(gateway, settings=None)
    out = []
    async for delta in dispatcher.handle("شو وضع الجهاز", tools=tools):
        out.append(delta)
    assert tools.calls == ["telemetry"]
    assert gateway.streamed_tiers == [Tier.HEAVY]  # narration round happened
    assert any("23%" in d for d in out)


def test_multi_task_router_miss_falls_to_net():
    """Router says none; the net coerces the 2-verb text to multi_task and the
    result still streams as-is (the backstop path shares the exemption)."""
    from src.dispatcher import _keyword_net

    assert _keyword_net("شغلي كروم وافتحي روكت ليج")[0] == "multi_task"
