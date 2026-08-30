"""Sprint-2 §2.6 AC10: randomized once-daily evening check-in inside the
[18:00, 19:30) Asia/Amman window, calendar-guarded (busy -> no message, ledger
still written); ledger created exactly once per local day (corrigenda on a
state-loss re-run); section degradation; send failure never persists state."""

import asyncio
import json
import random
from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

import pytest
from src.email_triage import TriageClassifier
from src.gmail import EmailMessage
from src.google_suite import CalendarEvent, TaskItem
from src.skills.evening_journaler import EveningJournaler

import src.skills.evening_journaler as journaler_module
from tests.conftest import OWNER_ID
from tests.test_daily_brief import FakeInbox
from tests.test_email_triage import FakeBrain

AMMAN = ZoneInfo("Asia/Amman")
TODAY = "2026-08-30"
NOW = datetime(2026, 8, 30, 15, 35, tzinfo=UTC)  # Amman 18:35 — inside the window
EARLY = datetime(2026, 8, 30, 14, 0, tzinfo=UTC)  # Amman 17:00 — before the window
_PIN = lambda lo, hi: lo  # noqa: E731 — slot pinned to window start (deterministic fire)


class FakeSuite:
    def __init__(self, events=(), tasks=(), error=None):
        self.events = list(events)
        self.tasks = list(tasks)
        self.error = error
        self.windows: list[tuple] = []

    async def list_events(self, start, end):
        self.windows.append((start, end))
        if self.error is not None:
            raise self.error
        return [event for event in self.events if event.end > start and event.start < end]

    async def list_tasks(self):
        if self.error is not None:
            raise self.error
        return list(self.tasks)


def _journaler(make_settings, vault_root, suite, bot, *, env=None, rng=None, **kw):
    return EveningJournaler(
        suite,
        bot,
        OWNER_ID,
        make_settings(**(env or {})),
        vault_root / "vault",
        rng=_PIN if rng is None else rng,
        **kw,
    )


def _state(vault_root) -> dict:
    return json.loads((vault_root / "vault" / "State" / "journaler.json").read_text("utf-8"))


def _ledger_path(vault_root) -> Path:
    return vault_root / "vault" / "Daily_Logs" / f"{TODAY}.md"


def _ledger(vault_root) -> str:
    return _ledger_path(vault_root).read_text("utf-8")


def _mail(id_: str, sender: str = "news@corp.com") -> EmailMessage:
    return EmailMessage(
        id=id_,
        thread_id=id_,
        from_email=sender,
        from_name="s",
        subject="نشرة",
        received_at=datetime(2026, 8, 30, 6, 0, tzinfo=UTC),
    )


async def test_checkin_window_randomized_calendar_guarded(make_settings, fake_bot, tmp_path):
    """AC10a: slots land inside [18:00, 19:30) Amman (same local day); a booked
    owner gets NO check-in but the ledger still lands (checkin_sent: false); a
    free owner gets exactly one check-in with persisted state."""
    journaler = _journaler(
        make_settings, tmp_path / "bounds", FakeSuite(), fake_bot(), rng=random.uniform
    )
    for _ in range(25):
        slot = journaler.pick_slot(datetime(2026, 8, 30, 12, 0, tzinfo=UTC))
        local = slot.astimezone(AMMAN)
        assert local.date() == date(2026, 8, 30)
        assert time(18, 0) <= local.time() < time(19, 30)

    # booked through the check-in window -> no message, ledger still written
    bot = fake_bot()
    event = CalendarEvent(
        id="e1",
        summary="متابعة",
        start=datetime(2026, 8, 30, 18, 30, tzinfo=AMMAN),
        end=datetime(2026, 8, 30, 19, 0, tzinfo=AMMAN),
    )
    busy = _journaler(make_settings, tmp_path / "busy", FakeSuite(events=[event]), bot)
    assert await busy.fire_once(NOW) is False
    assert bot.session.sent("SendMessage") == []
    assert "checkin_sent: false" in _ledger(tmp_path / "busy")

    # free calendar -> check-in message + state persisted only on success
    bot2 = fake_bot()
    suite = FakeSuite(tasks=[TaskItem(id="t1", title="تقرير", completed=True)])
    journaler2 = _journaler(make_settings, tmp_path / "free", suite, bot2)
    assert await journaler2.fire_once(EARLY) is False  # before the rolled slot: no-op
    assert bot2.session.calls == []
    assert await journaler2.fire_once(NOW) is True
    sent = bot2.session.sent("SendMessage")
    assert len(sent) == 1
    checkin = sent[0].method.text
    assert "مساء الخير" in checkin and checkin.rstrip().endswith("؟")  # open question
    assert _state(tmp_path / "free")["last_checkin_sent"] == TODAY
    assert _state(tmp_path / "free")["last_ledger_date"] == TODAY
    assert await journaler2.fire_once(NOW) is False  # same-day no-op


async def test_daily_ledger_created_once(make_settings, fake_bot, tmp_path):
    """AC10b: ledger created exactly once per local day; a state-loss same-day
    second run appends ONE corrigenda line instead of duplicating the note."""
    journaler = _journaler(make_settings, tmp_path, FakeSuite(), fake_bot())
    assert await journaler.fire_once(NOW) is True
    ledger = _ledger_path(tmp_path)
    first = ledger.read_text("utf-8")
    assert first.count("date: 2026-08-30") == 1
    assert "checkin_sent: true" in first

    assert await journaler.fire_once(NOW) is False  # stateful same-day: untouched
    assert ledger.read_text("utf-8") == first

    (tmp_path / "vault" / "State" / "journaler.json").unlink()  # state loss
    journaler2 = _journaler(make_settings, tmp_path, FakeSuite(), fake_bot())
    await journaler2.fire_once(NOW)
    second = ledger.read_text("utf-8")
    assert second.count("date: 2026-08-30") == 1  # frontmatter never duplicated
    assert second.count("تصحيح") == 1  # exactly one corrigenda line


async def test_section_failure_degrades_but_ledger_lands(make_settings, fake_bot, tmp_path):
    """Error mode: failing suite -> «غير متوفر حالياً» sections, ledger + check-in
    still land (degraded busy-check defaults to free)."""
    bot = fake_bot()
    journaler = _journaler(
        make_settings, tmp_path, FakeSuite(error=ValueError("google down")), bot
    )
    assert await journaler.fire_once(NOW) is True
    ledger = _ledger(tmp_path)
    assert ledger.count("غير متوفر حالياً") == 2  # calendar + mail degraded
    assert "## المذكرات الصوتية" in ledger  # healthy local section intact
    assert len(bot.session.sent("SendMessage")) == 1


async def test_send_failure_does_not_persist_checkin(make_settings, fake_bot, tmp_path):
    """Error mode: send failure -> no last_checkin_sent; healed retry succeeds."""
    bot = fake_bot(fail_send_indices={1})  # first send refuses (conftest contract)
    journaler = _journaler(make_settings, tmp_path, FakeSuite(), bot)
    assert await journaler.fire_once(NOW) is False
    assert "last_checkin_sent" not in _state(tmp_path)
    assert _ledger_path(tmp_path).exists()  # ledger lands regardless
    assert await journaler.fire_once(NOW) is True  # retried next tick
    assert _state(tmp_path)["last_checkin_sent"] == TODAY


async def test_collect_counts_today_facts(make_settings, fake_bot, tmp_path):
    """collect: today's events, completed tasks, CRITICAL mail via heuristic
    classifier, and only TODAY's Voice_Memos files."""
    event = CalendarEvent(
        id="e1",
        summary="اجتماع",
        start=datetime(2026, 8, 30, 9, 0, tzinfo=AMMAN),
        end=datetime(2026, 8, 30, 10, 0, tzinfo=AMMAN),
    )
    suite = FakeSuite(
        events=[event],
        tasks=[
            TaskItem(id="t1", title="منجزة", completed=True),
            TaskItem(id="t2", title="مفتوحة", completed=False),
        ],
    )
    inbox = FakeInbox(total=2, messages=[_mail("vip", "vip@corp.com"), _mail("m2")])
    classifier = TriageClassifier(make_settings(GOOGLE_VIP_SENDERS="vip@corp.com"), FakeBrain())
    memos = tmp_path / "vault" / "Voice_Memos"
    memos.mkdir(parents=True)
    (memos / "2026-08-30-1805.md").write_text("a", encoding="utf-8")
    (memos / "2026-08-30-1901.md").write_text("b", encoding="utf-8")
    (memos / "2026-08-29-1700.md").write_text("stale", encoding="utf-8")

    journaler = _journaler(
        make_settings, tmp_path, suite, fake_bot(), inbox=inbox, classifier=classifier
    )
    data = await journaler.collect(NOW)
    assert data.date == TODAY
    assert data.events == [event]
    assert data.tasks_done == 1
    assert data.critical_mail_count == 1
    assert data.memos_filed == 2

    ledger = journaler.render_ledger(data)
    assert "## المواعيد" in ledger and "09:00" in ledger
    assert "## المذكرات الصوتية" in ledger and "2" in ledger


async def test_invalid_window_fails_loud(make_settings):
    """Error mode: invalid window strings -> loud settings failure."""
    with pytest.raises(ValidationError):
        make_settings(JOURNALER_WINDOW_START="25:00")
    with pytest.raises(ValidationError):
        make_settings(JOURNALER_WINDOW_END="abc")


async def test_disabled_journaler_is_inert(make_settings, fake_bot, tmp_path):
    """journaler_enabled=false -> zero suite/bot calls, no state written."""
    suite = FakeSuite(events=[])
    bot = fake_bot()
    journaler = _journaler(
        make_settings, tmp_path, suite, bot, env={"JOURNALER_ENABLED": "false"}
    )
    assert await journaler.fire_once(NOW) is False
    assert suite.windows == []
    assert bot.session.calls == []
    assert not (tmp_path / "vault" / "State" / "journaler.json").exists()


async def test_loop_survives_exceptions(make_settings, fake_bot, tmp_path, monkeypatch):
    """Error mode: run_forever survives a raising cycle (logged, never wedged)."""
    journaler = _journaler(make_settings, tmp_path, FakeSuite(), fake_bot())
    monkeypatch.setattr(journaler_module, "POLL_TICK_SECONDS", 0)
    calls = 0

    async def flaky(_now):
        nonlocal calls
        calls += 1
        raise RuntimeError("boom")

    monkeypatch.setattr(journaler, "fire_once", flaky)
    task = asyncio.create_task(journaler.run_forever())
    for _ in range(200):
        if calls >= 2:
            break
        await asyncio.sleep(0.005)
    task.cancel()
    assert calls >= 2  # two full cycles despite the RuntimeError
