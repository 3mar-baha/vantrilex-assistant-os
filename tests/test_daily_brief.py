"""Sprint-2 §2.4 AC1-AC5: daily brief render template, mocked-client collection,
fire-once-per-day persistence, disabled short-circuit, per-section degradation."""

from datetime import UTC, datetime, timedelta

from src.daily_brief import BriefComposer, BriefData
from src.gmail import EmailMessage
from src.google_suite import CalendarEvent, TaskItem


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
