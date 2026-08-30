"""Sprint-2 §2.4 AC1-AC5: daily brief render template, mocked-client collection,
fire-once-per-day persistence, disabled short-circuit, per-section degradation."""

from datetime import UTC, datetime, timedelta

from src.daily_brief import BriefComposer, BriefData
from src.email_triage import TriageClassifier
from src.gmail import EmailMessage, GmailState
from src.google_suite import CalendarEvent, TaskItem
from tests.test_email_triage import FakeBrain


class FakeSuite:
    def __init__(self, events=None, tasks=None):
        self.events = events or []
        self.tasks = tasks or []
        self.window = None
        self.calls = 0

    async def list_events(self, start, end):
        self.calls += 1
        self.window = (start, end)
        return self.events

    async def list_tasks(self):
        self.calls += 1
        return self.tasks


class FakeInbox:
    def __init__(self, total=0, messages=None):
        self.total = total
        self.messages = messages or []
        self.peeked = 0
        self.state = GmailState()
        self.saved = 0

    def save_state(self):
        self.saved += 1

    async def unread_digest(self):
        return self.total, 0

    async def peek_unread(self, max_n=25):
        self.peeked += 1
        return self.messages


def _important_msg(i: int) -> EmailMessage:
    return _msg(
        id=f"imp{i}",
        subject=f"urgent asap {i}",
        body_text="critical deadline",
        received_at=datetime(2026, 8, 31, 6, 0, tzinfo=UTC),
    )


def _msg(**kw) -> EmailMessage:
    defaults = {
        "id": "m1",
        "thread_id": "t1",
        "from_email": "boss@corp.com",
        "from_name": "مديري",
        "subject": "تحديث",
        "received_at": datetime(2026, 8, 31, 6, 0, tzinfo=UTC),
    }
    return EmailMessage(**(defaults | kw))


def _composer(make_settings, **env) -> BriefComposer:
    return BriefComposer(None, None, None, None, 0, make_settings(**env))


def test_render_template_with_fixtures(make_settings):
    """AC1: exact template structure, Amman-localized times, escaped dynamics."""
    composer = _composer(make_settings)
    now = datetime(2026, 8, 31, 7, 0, tzinfo=UTC)  # Amman: Monday 10:00, 31 آب
    data = BriefData(
        events=[
            CalendarEvent(
                id="e1",
                summary="اجتماع *مهم*",
                start=now,
                end=now + timedelta(hours=1),
            )
        ],
        tasks=[TaskItem(id="t1", title="تقرير _نهائي_", due=now)],
        unread_total=5,
        important_items=[_msg(subject="عاجل جداً!")],
    )
    expected = (
        "☀️ صباح الخير\\! موجز يوم الاثنين 31 آب\n"
        "📅 مواعيد اليوم \\(1\\):\n• 10:00–11:00 اجتماع \\*مهم\\*\n"
        "✅ مهام مستحقة اليوم \\(1\\):\n• تقرير \\_نهائي\\_\n"
        "📥 البريد: 5 غير مقروءة · مهمة: 1 — أبرزها: «عاجل جداً\\!» من مديري"
    )
    assert composer.render(data, now) == expected

    empty = composer.render(BriefData(events=[], tasks=[], unread_total=0), now)
    assert "📅 لا مواعيد اليوم" in empty
    assert "✅ لا مهام مستحقة اليوم" in empty
    assert "📥 البريد: 0 غير مقروءة · مهمة: 0" in empty


async def test_collect_from_mocked_clients(make_settings):
    """AC2: 24h event window passed through, today's uncompleted tasks only,
    IMPORTANT+ highlights capped at 3 via heuristic."""
    now = datetime(2026, 8, 31, 7, 0, tzinfo=UTC)
    event = CalendarEvent(id="e1", summary="اجتماع", start=now, end=now + timedelta(hours=1))
    suite = FakeSuite(
        events=[event],
        tasks=[
            TaskItem(id="t1", title="اليوم", due=now),
            TaskItem(id="t2", title="غداً", due=now + timedelta(days=1)),
            TaskItem(id="t3", title="منجز", due=now, completed=True),
        ],
    )
    inbox = FakeInbox(
        total=5,
        messages=[
            *(_important_msg(i) for i in range(4)),  # 4 candidates -> cap 3
            _msg(id="semi", subject="عاجل"),  # SEMI: below threshold
            _msg(id="drop", subject="نشرة"),  # DROP
        ],
    )
    classifier = TriageClassifier(make_settings(GOOGLE_VIP_SENDERS="vip@corp.com"), FakeBrain())
    composer = BriefComposer(suite, inbox, classifier, None, 0, make_settings())

    data = await composer.collect(now)

    assert suite.window == (now, now + timedelta(hours=24))
    assert data.events == [event]
    assert [task.id for task in data.tasks] == ["t1"]
    assert data.unread_total == 5
    assert [m.id for m in data.important_items] == ["imp0", "imp1", "imp2"]


async def test_fire_if_due_once_per_day(make_settings, fake_bot):
    """AC3: fires once per local day past brief time; same-day no-op; next day
    fires again; send failure does not persist the date."""
    from tests.conftest import OWNER_ID

    now = datetime(2026, 8, 31, 7, 0, tzinfo=UTC)  # Amman 10:00 — past 07:30
    early = datetime(2026, 8, 31, 4, 0, tzinfo=UTC)  # Amman 07:00 — before brief
    inbox = FakeInbox()
    composer = BriefComposer(FakeSuite(), inbox, None, fake_bot(), OWNER_ID, make_settings())

    assert await composer.fire_once(early) is False
    assert inbox.state.last_brief_date is None  # zero persistence before brief time

    assert await composer.fire_once(now) is True
    assert inbox.state.last_brief_date == "2026-08-31"
    assert await composer.fire_once(now) is False  # same-day no-op

    next_day = datetime(2026, 9, 1, 7, 0, tzinfo=UTC)
    assert await composer.fire_once(next_day) is True
    assert inbox.state.last_brief_date == "2026-09-01"


async def test_brief_send_failure_skips_persistence(make_settings, fake_bot):
    """AC3 error mode: send failure -> False, date NOT persisted (same-day retry)."""
    from tests.conftest import OWNER_ID

    now = datetime(2026, 8, 31, 7, 0, tzinfo=UTC)
    bot = fake_bot(fail_send_indices={1})  # 1-based send index (conftest contract)
    composer = BriefComposer(FakeSuite(), FakeInbox(), None, bot, OWNER_ID, make_settings())
    assert await composer.fire_once(now) is False
    assert len(bot.session.sent("SendMessage")) == 1  # attempted
    assert composer._inbox.state.last_brief_date is None  # not persisted
    assert await composer.fire_once(now) is True  # retries same day once bot heals


async def test_brief_disabled_sends_nothing(make_settings, fake_bot):
    """AC4: brief_enabled=false -> fire_if_due False, zero client + bot calls."""
    from tests.conftest import OWNER_ID

    suite, inbox, bot = FakeSuite(), FakeInbox(), fake_bot()
    composer = BriefComposer(
        suite, inbox, None, bot, OWNER_ID, make_settings(BRIEF_ENABLED="false")
    )
    now = datetime(2026, 8, 31, 7, 0, tzinfo=UTC)
    assert await composer.fire_once(now) is False
    assert composer.fire_if_due(now) is False
    assert bot.session.calls == []
    assert suite.calls == 0 and inbox.peeked == 0


async def test_source_failure_degrades_section_not_brief(make_settings, fake_bot):
    """AC5: a failing source degrades its section («غير متوفر حالياً»); the brief
    still sends, healthy sections stay intact, date persists on success."""
    from src.daily_brief import DEGRADED_TEXT
    from tests.conftest import OWNER_ID

    class BrokenCalendar(FakeSuite):
        async def list_events(self, start, end):
            raise ValueError("calendar down")

    class BrokenGmail(FakeInbox):
        async def unread_digest(self):
            raise ValueError("gmail down")

    now = datetime(2026, 8, 31, 7, 0, tzinfo=UTC)

    inbox = FakeInbox()
    bot = fake_bot()
    composer = BriefComposer(BrokenCalendar(), inbox, None, bot, OWNER_ID, make_settings())
    assert await composer.fire_once(now) is True
    text = bot.session.sent("SendMessage")[0].method.text
    assert f"📅 المواعيد: {DEGRADED_TEXT}" in text
    assert "✅ لا مهام مستحقة اليوم" in text  # healthy section intact
    assert inbox.state.last_brief_date == "2026-08-31"  # send succeeded -> persisted

    bot2 = fake_bot()
    composer2 = BriefComposer(FakeSuite(), BrokenGmail(), None, bot2, OWNER_ID, make_settings())
    assert await composer2.fire_once(now) is True
    text2 = bot2.session.sent("SendMessage")[0].method.text
    assert f"📥 البريد: {DEGRADED_TEXT}" in text2
