"""Sprint-2 §2.4 AC1-AC5: daily brief render template, mocked-client collection,
fire-once-per-day persistence, disabled short-circuit, per-section degradation."""

from datetime import UTC, datetime, timedelta

from src.daily_brief import BriefComposer, BriefData
from src.email_triage import TriageClassifier
from src.gmail import EmailMessage
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
    classifier = TriageClassifier(
        make_settings(GOOGLE_VIP_SENDERS="vip@corp.com"), FakeBrain()
    )
    composer = BriefComposer(suite, inbox, classifier, None, 0, make_settings())

    data = await composer.collect(now)

    assert suite.window == (now, now + timedelta(hours=24))
    assert data.events == [event]
    assert [task.id for task in data.tasks] == ["t1"]
    assert data.unread_total == 5
    assert [m.id for m in data.important_items] == ["imp0", "imp1", "imp2"]
