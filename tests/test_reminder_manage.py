"""Gap-أ (owner 2026-09-05): reminder LIST + CANCEL — the owner can arm a
reminder but never see or remove what's armed. «سجلتها» then silence forever.

Contract:
- Orchestrator.list_for_owner(): the pending jobs, one line each (id + when
  local + message), ordered by when — the numbering the owner will cancel by.
- Orchestrator.cancel(job_id): removes + persists; unknown id -> None (the
  caller answers honestly); cancel_all() -> count removed.
- Tools `list_reminders` / `cancel_reminder` (arg = job id or «الكل»).
- Net entries: «شو تذكيراتي» -> list_reminders; «الغي التذكير (N/الكل)» ->
  cancel_reminder with the arg — BEFORE schedule (a cancel verb is an
  imperative, not an arm request).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

AMMAN = ZoneInfo("Asia/Amman")


class _Bot:
    def __init__(self):
        self.sent: list[str] = []

    async def send_message(self, chat_id, text):
        self.sent.append(text)


async def _armed(tmp_path, *, count=2):
    from src.task_orchestrator import Orchestrator

    orch = Orchestrator(bot=_Bot(), chat_id=1, tz=AMMAN)
    orch.bind_state_path(tmp_path)
    now = datetime.now(AMMAN)
    await orch.schedule_wallclock("⏰ تذكير: اشتري بيض", when=now + timedelta(hours=1), title="بيض")
    await orch.schedule_wallclock(
        "⏰ تذكير: المكالمة مع الفريق", when=now + timedelta(hours=2), title="مكالمة"
    )
    if count == 1:
        await orch.cancel(orch.pending[1].id)
    return orch


# -- engine ---------------------------------------------------------------------


async def test_list_for_owner_shows_ids_times_messages(tmp_path):
    """The list the owner reads: one line per pending job — id, local time,
    message — ordered soonest-first (cancel targets ride the id)."""
    orch = await _armed(tmp_path)
    lines = orch.list_for_owner()
    assert len(lines) == 2
    assert "بيض" in lines[0] and "مكالمة" in lines[1]  # soonest first
    assert orch.pending[0].id in lines[0]  # the id is IN the line (cancel target)
    assert "1" in lines[0]  # a human time (hour digits), not ISO soup


async def test_cancel_removes_and_persists(tmp_path):
    """cancel(id) removes the job NOW and persists — a restart must not
    resurrect a cancelled reminder (the live 3:48pm vanishing lesson)."""
    orch = await _armed(tmp_path)
    first_id = orch.pending[0].id
    assert await orch.cancel(first_id) is True
    assert all(job.id != first_id for job in orch.pending)

    # persisted state on disk no longer carries the cancelled job
    import json

    from src.task_orchestrator import reminder_state_path

    data = json.loads(reminder_state_path(tmp_path).read_text(encoding="utf-8"))
    assert all(entry["id"] != first_id for entry in data)


async def test_cancel_unknown_id_returns_false(tmp_path):
    """An unknown id is None/False — the CALLER answers honestly; the engine
    never fabricates a removal."""
    orch = await _armed(tmp_path, count=1)
    assert await orch.cancel("job-999") is False
    assert len(orch.pending) == 1  # nothing was harmed


async def test_cancel_all_clears_every_job(tmp_path):
    """«الغي كل التذكيرات» — the full sweep returns the removed count."""
    orch = await _armed(tmp_path)
    removed = await orch.cancel_all()
    assert removed == 2
    assert orch.pending == []


# -- tools ------------------------------------------------------------------------


async def test_list_reminders_tool_honest_answers(tmp_path):
    """The tool: empty -> the honest none-line; armed -> the full list joined;
    no orchestrator -> the honest unavailable line."""
    from src.tools import ToolRegistry

    class _Orch:
        def __init__(self, lines=None, exc=None):
            self._lines = lines
            self._exc = exc

        def list_for_owner(self):
            if self._exc:
                raise self._exc
            return self._lines or []

    armed = ToolRegistry(orchestrator=_Orch(lines=["job-1 13:00 بيض"]))
    out = await armed.call("list_reminders", "")
    assert "job-1" in out and "بيض" in out

    empty = ToolRegistry(orchestrator=_Orch(lines=[]))
    assert "ما في" in await empty.call("list_reminders", "")

    dead = ToolRegistry(orchestrator=_Orch(exc=RuntimeError("boom")))
    assert "ما في" in await dead.call("list_reminders", "")  # degrades, never hangs

    unbound = ToolRegistry()
    assert "ما في" in await unbound.call("list_reminders", "")


async def test_cancel_reminder_tool_routes_arg(tmp_path):
    """The tool passes the arg (job id or «الكل») to the engine's cancel /
    cancel_all and speaks the honest result both ways."""
    from src.tools import ToolRegistry

    class _Orch:
        def __init__(self):
            self.cancelled: list[str] = []
            self.all_called = False

        async def cancel(self, job_id):
            self.cancelled.append(job_id)
            return job_id == "job-1"

        async def cancel_all(self):
            self.all_called = True
            return 3

        def list_for_owner(self):
            return []

    orch = _Orch()
    registry = ToolRegistry(orchestrator=orch)

    ok = await registry.call("cancel_reminder", "job-1")
    assert "job-1" in ok and "✅" in ok

    unknown = await registry.call("cancel_reminder", "job-9")
    assert "ما لقيت" in unknown or "ما في" in unknown

    everything = await registry.call("cancel_reminder", "الكل")
    assert orch.all_called is True
    assert "3" in everything


def test_net_routes_list_and_cancel():
    """The net: «شو تذكيراتي» lists; «الغي التذكير N/الكل» cancels with the
    arg — and the cancel verb never falls into schedule's arm verbs."""
    from src.dispatcher import _VALID_TOOLS, _keyword_net

    assert "list_reminders" in _VALID_TOOLS
    assert "cancel_reminder" in _VALID_TOOLS

    tool, arg = _keyword_net("شو تذكيراتي")
    assert tool == "list_reminders"

    tool, arg = _keyword_net("الغي التذكير job-1")
    assert (tool, arg) == ("cancel_reminder", "job-1")

    tool, arg = _keyword_net("الغي كل التذكيرات")
    assert (tool, arg) == ("cancel_reminder", "الكل")

    # the arm verbs still arm — nothing stolen
    assert _keyword_net("ذكريني بعد ساعة اشتري بيض")[0] == "schedule"
