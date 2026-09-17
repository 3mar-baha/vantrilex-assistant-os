"""P6 batch 7d — src/task_orchestrator.py uncovered edges: wallclock no-match,
find_by_time digitless, run_forever generic-error survival, fire_due re-arm +
steps-without-message, parallel double-failure stickiness, notify failure,
persist OSError, load_pending no-dir + malformed-entry skips.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from src.task_orchestrator import (
    Orchestrator,
    parse_wallclock_ar,
    reminder_state_path,
)

AMMAN = ZoneInfo("Asia/Amman")
NOW = datetime(2026, 9, 17, 9, 0, tzinfo=AMMAN)


class _Bot:
    def __init__(self, boom=False):
        self.boom = boom
        self.sent: list[str] = []

    async def send_message(self, chat_id, text):
        if self.boom:
            raise RuntimeError("telegram down")
        self.sent.append(text)


def _orch(bot=None, state_dir=None):
    orch = Orchestrator(bot=bot or _Bot(), chat_id=1, tz=AMMAN)
    if state_dir is not None:
        orch.bind_state_path(state_dir)
    return orch


def test_wallclock_without_time_is_none():
    assert parse_wallclock_ar("ذكريني أشتري بيض", now=NOW) is None


def test_find_by_time_digitless_is_none():
    assert _orch().find_by_time("الغي التذكير") is None


async def test_run_forever_survives_generic_tick_error(monkeypatch):
    orch = _orch()
    calls = {"n": 0}

    async def _flaky():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("transient")
        raise asyncio.CancelledError

    monkeypatch.setattr(orch, "_fire_due", _flaky)
    with pytest.raises(asyncio.CancelledError):
        await orch.run_forever(tick_s=0)
    assert calls["n"] == 2  # the loop outlived the first failure


async def test_fire_due_dispatch_failure_re_arms():
    orch = _orch(_Bot(boom=True))
    past = datetime.now(AMMAN) - timedelta(minutes=5)
    await orch.schedule_wallclock("ذكرني", when=past)
    await orch._fire_due()
    assert len(orch.pending) == 1  # re-armed, never lost
    assert orch.pending[0].when > datetime.now(AMMAN)


async def test_fire_due_steps_without_message_run_chain():
    orch = _orch()
    ran = []

    async def _step():
        ran.append(1)

    past = datetime.now(AMMAN) - timedelta(minutes=5)
    await orch.schedule_wallclock(None, when=past, steps=[("خطوة", _step)])
    await orch._fire_due()
    assert ran == [1] and orch.pending == []


async def test_parallel_double_failure_names_first():
    orch = _orch()

    async def _bad1():
        raise RuntimeError("one")

    async def _bad2():
        raise ValueError("two")

    report = await orch.run_parallel("سلة", [("أول", _bad1), ("ثاني", _bad2)])
    assert report.ok is False and report.failed_at == "أول"
    assert report.completed == []


async def test_notify_failure_never_blocks():
    await _orch(_Bot(boom=True))._tell("ping")  # logs, never raises


async def test_persist_oserror_is_best_effort(tmp_path, monkeypatch):
    from pathlib import Path as _Path

    orch = _orch(state_dir=tmp_path)
    monkeypatch.setattr(
        _Path, "write_text", lambda self, *a, **k: (_ for _ in ()).throw(OSError("read-only"))
    )
    await orch.schedule_delay("x", delay=timedelta(minutes=1))  # persists loudly, no raise


def test_load_pending_without_state_dir_is_zero():
    assert _orch().load_pending() == 0


def test_load_pending_skips_malformed_entries(tmp_path):
    orch = _orch(state_dir=tmp_path)
    reminder_state_path(tmp_path).write_text(
        json.dumps([{"when": "not-a-date"}, {"no-when": True}]), encoding="utf-8"
    )
    assert orch.load_pending() == 0 and orch.pending == []
