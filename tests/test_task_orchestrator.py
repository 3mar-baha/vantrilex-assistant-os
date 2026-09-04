"""Directive §5 (owner 2026-09-04, live failures 3:46-3:50pm): the dual task
engine — timed scheduling (the «بعد 60 ثانية ذكريني» that never fired), plus
sequential DAG, parallel gather, and composite scheduled workflows. Timers are
asyncio jobs tied to Amman tz; when a timer fires, the message is dispatched
PROACTIVELY to the owner's chat — never dropped silently (the live reminders
vanished)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from src.task_orchestrator import (
    Orchestrator,
    parse_delay_ar,
    parse_wallclock_ar,
)


class FakeBot:
    def __init__(self) -> None:
        self.sent: list[str] = []

    async def send_message(self, chat_id: int, text: str, **kw) -> None:
        self.sent.append(text)


AMMAN = ZoneInfo("Asia/Amman")


def _orch(bot: FakeBot) -> Orchestrator:
    return Orchestrator(bot=bot, chat_id=111, tz=AMMAN)


# GENERAL capability matrices — the live phrases were ONE instance; the
# contract is the ABILITY (any number, any unit, any clock time, any day).
# Live-phrase rows stay as anchors, matrices prove the general case.
import pytest

DELAY_CASES = [
    # (phrase, expected_seconds) — unit table x digit spaces x word orders
    ("بعد 60 ثانية ذكريني اشتري بيض", 60),
    ("بعد ٥ ثواني افحص الفرن", 5),  # Arabic-Indic digits
    ("بعد 7 دقايق ذكريني افتح المسجد", 420),
    ("بعد 15 دقيقة نبهيني", 900),
    ("بعد ساعتين ذكريني اتصل", 7200),
    ("بعد 3 ساعات جربيني", 10800),
    ("بعد نصف ساعة", None),  # unsupported shape -> honest None (no guessing)
]


@pytest.mark.parametrize(("phrase", "expected"), DELAY_CASES)
def test_parse_delay_ar_general_matrix(phrase, expected):
    now = datetime(2026, 9, 4, 15, 46, tzinfo=AMMAN)
    result = parse_delay_ar(phrase, now=now)
    if expected is None:
        assert result is None  # honest refuse, never a guessed time
        return
    delay, _title = result
    assert abs(delay.total_seconds() - expected) < 1


WALLCLOCK_CASES = [
    # (phrase, expected_hour24, expected_minute) — any h[:m] + صباح/مساء
    ("على الساعة 3:47 مساء ذكريني اشتري بيض", 15, 47),  # the live anchor
    ("الساعة 9 صباحا ذكريني الدواء", 9, 0),
    ("على الساعة 11:30 مساء", 23, 30),
    ("على الساعة 12 مساء ذكريني الغدا", 12, 0),  # noon
    ("على الساعة 12 صباح تذكير", 0, 0),  # midnight
    ("الساعة ٦:٣٠ مساء افحص", 18, 30),  # Arabic-Indic digits + مساء
    ("الساعة 6:30 مساء", 18, 30),
    ("ذكريني الساعة 8:15 مساء اغلاق الباب", 20, 15),  # clock AFTER the verb
]


@pytest.mark.parametrize(("phrase", "hour24", "minute"), WALLCLOCK_CASES)
def test_parse_wallclock_ar_general_matrix(phrase, hour24, minute):
    now = datetime(2026, 9, 4, 15, 46, tzinfo=AMMAN)
    result = parse_wallclock_ar(phrase, now=now)
    assert result is not None, f"unparsed: {phrase}"
    when, _title = result
    assert when.hour == hour24 and when.minute == minute, phrase
    # a time already passed today lands TOMORROW (never silently dropped)
    if when.date() == now.date():
        assert when > now, f"must fire in the future: {phrase}"


async def test_reminder_fires_and_dispatches_proactively():
    """The live 3:47pm failure: the registered timer ACTUALLY fires and sends
    to the owner's chat — never dropped silently."""
    bot = FakeBot()
    orch = _orch(bot)
    task = asyncio.create_task(orch.run_forever(tick_s=0.05))
    try:
        await orch.schedule_delay(
            "ذكريني اشتري بيض", delay=timedelta(seconds=0.2), title="اشتري بيض"
        )
        await asyncio.sleep(0.8)
        assert any("بيض" in s for s in bot.sent), "the reminder never dispatched"
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_reminder_persists_past_restart(tmp_path):
    """A registered reminder survives a restart (the live 3:48pm death: the
    reminder was 'registered' and vanished) — reminders persist to disk."""
    import json

    from src.task_orchestrator import reminder_state_path

    bot = FakeBot()
    orch = _orch(bot)
    orch.bind_state_path(tmp_path)
    await orch.schedule_wallclock(
        "على الساعة 3:47 مساء ذكريني اشتري بيض",
        when=datetime.now(AMMAN) + timedelta(hours=1),
        title="اشتري بيض",
    )
    state = json.loads(reminder_state_path(tmp_path).read_text(encoding="utf-8"))
    assert len(state) == 1 and "بيض" in state[0]["message"]

    # a fresh orchestrator reloads and re-arms the pending reminder
    orch2 = _orch(FakeBot())
    orch2.bind_state_path(tmp_path)
    orch2.load_pending()
    assert len(orch2.pending) == 1


async def test_sequential_engine_executes_steps_in_order():
    """«شغلي الجهاز -> افتحي كروم -> افتحي يوتيوب»: steps run IN ORDER, each
    completes before the next starts; ONE structured status report at the end."""
    bot = FakeBot()
    orch = _orch(bot)
    order: list[str] = []

    async def step_a():
        await asyncio.sleep(0.05)
        order.append("a")

    async def step_b():
        order.append("b")

    report = await orch.run_sequential(
        "الشغلة الكبيرة", [("الخطوة أ", step_a), ("الخطوة ب", step_b)]
    )
    assert order == ["a", "b"]
    assert any("الخطوة أ" in s for s in bot.sent)  # the report landed
    assert report.ok


async def test_sequential_failure_reports_honestly():
    """A failed step STOPS the chain and the report says exactly where it died
    — no hallucinated completion (live lesson: claimed closes that never ran)."""
    bot = FakeBot()
    orch = _orch(bot)
    ran: list[str] = []

    async def good():
        ran.append("good")

    async def bad():
        raise RuntimeError("البرنامج مش موجود")

    async def never():
        ran.append("never")

    report = await orch.run_sequential(
        "سلسلة فاشلة", [("الأولى", good), ("الثانية", bad), ("الثالثة", never)]
    )
    assert not report.ok
    assert ran == ["good"]  # the chain stopped at the failure
    assert any("الثانية" in s for s in bot.sent)


async def test_parallel_engine_runs_concurrently():
    """«شغلي كروم مع اللعبة بنفس الوقت»: gather-concurrent; ONE unified
    confirmation when both finish."""
    bot = FakeBot()
    orch = _orch(bot)
    started: list[float] = []

    async def one():
        started.append(asyncio.get_event_loop().time())
        await asyncio.sleep(0.2)

    async def two():
        started.append(asyncio.get_event_loop().time())
        await asyncio.sleep(0.2)

    report = await orch.run_parallel("المهام المتوازية", [("مهمة ١", one), ("مهمة ٢", two)])
    assert report.ok
    # CONCURRENT: both started within 0.1s of each other (sequential would gap 0.2)
    assert abs(started[1] - started[0]) < 0.1
    assert len(bot.sent) >= 1  # the unified confirmation


async def test_composite_scheduled_sequential():
    """«بعد ساعة شغلي الجهاز ثم شغلي اللعبة»: a scheduled sequential DAG —
    the timer fires, THEN the chain runs step-by-step."""
    bot = FakeBot()
    orch = _orch(bot)
    task = asyncio.create_task(orch.run_forever(tick_s=0.05))
    try:
        executed: list[str] = []

        async def do_a():
            executed.append("a")

        async def do_b():
            executed.append("b")

        await orch.schedule_delay(
            "بعد شوي", delay=timedelta(seconds=0.2), steps=[("أ", do_a), ("ب", do_b)]
        )
        await asyncio.sleep(1.0)
        assert executed == ["a", "b"]  # fired THEN ran in order
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_schedule_tool_timed_lane_hits_orchestrator():
    """§5: the schedule tool routes «بعد 60 ثانية ذكريني ...» to the
    orchestrator (None contract — the orchestrator confirmed itself); a plain
    day-phrase still lands the vault-note lane."""
    from src.tools import ToolRegistry

    class _Orch:
        def __init__(self):
            self.armed = []

        async def schedule_delay(self, message, *, delay, title="", steps=None):
            self.armed.append(("delay", delay, title))
            return "job-1"

    orch = _Orch()
    tools = ToolRegistry(orchestrator=orch, tz=AMMAN)
    result = await tools.call("schedule", "بعد 60 ثانية ذكريني اشتري بيض")
    assert result is None  # launch-tool contract: the orchestrator confirmed
    assert len(orch.armed) == 1
    assert abs(orch.armed[0][1].total_seconds() - 60) < 1


def test_keyword_net_still_routes_reminders():
    from src.dispatcher import _keyword_net

    tool, arg = _keyword_net("بعد 60 ثانية ذكريني اشتري بيض")
    assert tool == "schedule"
    assert "60" in arg
    tool2, _arg2 = _keyword_net("على الساعة 3:47 مساء ذكريني اشتري بيض")
    assert tool2 == "schedule"
