"""Live-2 findings 2026-09-05 (7:00-7:05am session):

1. «شو تذكيراتي» answered «التذكير المسجل عندك هو 7:10 الصبح لتشرب ميّ» —
   a RE-NARRATED summary WITHOUT the job ids. The tool's deterministic
   list (job-1 — time — title) was swallowed by the HEAVY narration round,
   so the owner had nothing to cancel BY.
2. «الغي التذكير 7:10» -> «ما في تذكير بساعة 7:10» — cancel by TIME (the
   natural way the owner speaks) is unsupported; only job-N ids work.
3. «شغلي تذكير بعد 30 ثانية...» inside a multi-task request: the sub-agent
   MAPPED «تذكير» to the Google-tasks path («سجلت المهمة "30 seconds" بموعدها
   2026-09-06 03:58») — the literal English "30 seconds" as the task TITLE and
   a TOMORROW deadline instead of a 30-second timer.

Contract:
- list_reminders results pass to the owner AS-IS (no HEAVY re-narration) —
  the ids are the cancel targets; narration may drop them.
- cancel accepts a TIME phrase too («الغي التذكير 7:10/3:47 مساء») — the
  engine cancels the job whose local time matches the spoken hour[:minute].
- The schedule STEPS inside multi_task use the ORIGINAL LINE TEXT as the
  schedule arg (the parsers read the Arabic timing words), never a
  translated/regurgitated variant.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from bridge.executor import mint_confirmation_id

AMMAN = ZoneInfo("Asia/Amman")

LINE_30S = "شغلي تذكير بعد 30 ثانية اشرب ماء"


# -- finding 1: the list must reach the owner verbatim ---------------------------


async def test_list_reminders_result_streams_as_is():
    """list_reminders joins multi_task's exemption: the deterministic list —
    ids, times, titles — is the answer. A HEAVY narration round may DROP the
    ids (live: the owner got a prose summary with nothing to cancel by)."""
    from src.dispatcher import FrontDoorDispatcher

    verdict = json.dumps(
        {
            "route": "tier2",
            "tool": "list_reminders",
            "arg": "",
            "ack": "ثواني",
            "voice_reply": False,
        },
        ensure_ascii=False,
    )

    class _Gateway:
        async def chat(self, messages, *, tier, **kw):
            return verdict

        async def stream_chat(self, *a, **kw):  # pragma: no cover -- must not run
            yield "narration"
            raise AssertionError("list_reminders must not re-narrate")

    class _Tools:
        async def call(self, tool, arg=""):
            assert tool == "list_reminders"
            return "تذكيراتك المسجلة هسا:\n• job-1 — 07:10 — ⏰ تذكير: اشرب ماء"

    dispatcher = FrontDoorDispatcher(_Gateway(), settings=None)
    out = []
    async for delta in dispatcher.handle("شو تذكيراتي", tools=_Tools()):
        out.append(delta)
    assert any("job-1" in d for d in out)  # the id survived verbatim
    assert any("تذكيراتك المسجلة" in d for d in out)


# -- finding 2: cancel by spoken time -------------------------------------------


def test_cancel_by_time_real():
    from src.task_orchestrator import Orchestrator

    class _Bot:
        async def send_message(self, chat_id, text):
            pass

    orch = Orchestrator(bot=_Bot(), chat_id=1, tz=AMMAN)
    now = datetime.now(AMMAN)
    from src.task_orchestrator import _Job

    orch._jobs["job-1"] = _Job("job-1", now.replace(hour=7, minute=10), "⏰ تذكير: اشرب ماء")
    orch._jobs["job-2"] = _Job("job-2", now.replace(hour=9, minute=0), "⏰ تذكير: دراسة")

    # by hour:minute
    assert orch.find_by_time("7:10") == "job-1"
    assert orch.find_by_time("9") == "job-2"
    # no match -> None (the caller answers honestly)
    assert orch.find_by_time("11:30") is None
    # 24h form + pm marker
    assert orch.find_by_time("19:00") is None


async def test_cancel_reminder_tool_accepts_time():
    """The tool: a job-N arg cancels by id (gap-أ); a time-looking arg cancels
    by the matching job; neither matches -> the honest line."""
    from src.task_orchestrator import Orchestrator, _Job
    from src.tools import ToolRegistry

    class _Bot:
        async def send_message(self, chat_id, text):
            pass

    orch = Orchestrator(bot=_Bot(), chat_id=1, tz=AMMAN)
    now = datetime.now(AMMAN)
    orch._jobs["job-1"] = _Job("job-1", now.replace(hour=7, minute=10), "⏰ تذكير: اشرب ماء")

    registry = ToolRegistry(orchestrator=orch)
    # F-1: cancelling a reminder cannot be undone, so this drove a real
    # cancellation with NO confirmation and expected it. Updated, not weakened:
    # the time-matching path is asserted end to end, now behind a genuine
    # approval, which is the only way to reach the handler at all.
    out = await registry.call("cancel_reminder", "7:10", confirmation_id=mint_confirmation_id())
    assert "✅" in out and "job-1" in out
    assert orch.pending == []  # actually cancelled

    # a time with no match answers honestly
    orch._jobs["job-2"] = _Job("job-2", now.replace(hour=12, minute=0), "x")
    out = await registry.call("cancel_reminder", "3:47", confirmation_id=mint_confirmation_id())
    assert "ما لقيت" in out


# -- finding 3: schedule steps use the ORIGINAL line text -------------------------


async def test_subagent_schedule_step_uses_original_text():
    """A schedule step inside a multi-task line carries the ORIGINAL Arabic
    line text as the arg — the timing parsers read Arabic («بعد 30 ثانية»),
    never a regurgitated English variant («30 seconds»). The live bug armed a
    TOMORROW 3:58am deadline for a 30-second reminder."""
    from src.agent_manager import AgentManager

    planner = json.dumps(
        {"lines": [{"mode": "sequential", "text": LINE_30S}]},
        ensure_ascii=False,
    )
    subagent = json.dumps(
        {"steps": [{"tool": "schedule", "arg": LINE_30S}]},
        ensure_ascii=False,
    )

    class _Gateway:
        async def chat(self, messages, *, tier, **kw):
            if str(tier).endswith("heavy") or getattr(tier, "value", "") == "heavy":
                return planner
            return subagent

    scheduled_args: list[str] = []

    class _Tools:
        async def call(self, tool, arg=""):
            if tool == "schedule":
                scheduled_args.append(arg)
                return None
            return "ok"

    manager = AgentManager(gateway=_Gateway(), tools=_Tools())
    report = await manager.run(LINE_30S)
    assert scheduled_args == [LINE_30S]  # the ORIGINAL text, verbatim
    assert "schedule" in report


def test_schedule_parser_reads_the_original_30s_text():
    """The 30-second timing IS what parse_delay_ar reads from the original
    text — the live bug (tomorrow-3:58am Google task) can never recur when
    the original text rides the arg."""
    from src.task_orchestrator import parse_delay_ar

    delayed = parse_delay_ar(LINE_30S, now=datetime.now(AMMAN))
    assert delayed is not None
    delay, _title = delayed
    assert delay == timedelta(seconds=30)
