"""ToolRegistry (owner directive 2026-09-01): real backends behind the dispatcher's
tool lane — gmail/calendar/tasks/telemetry/launch/brief, honest offline lines."""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from src.daily_brief import BriefData
from src.gmail import EmailMessage
from src.google_suite import CalendarEvent, TaskItem
from src.pc_actions import LaunchStatus
from src.telemetry import OFFLINE_TEXT_AR
from src.tools import GOOGLE_OFFLINE_AR, TOOL_FAIL_AR, ToolRegistry

TZ = ZoneInfo("Asia/Amman")
NOW = datetime(2026, 9, 1, 15, 0, tzinfo=UTC)  # 18:00 Amman


class FakeInbox:
    def __init__(self, messages=None, error=None):
        self.messages = messages or []
        self.error = error

    async def peek_unread(self, max_n=25):
        if self.error:
            raise self.error
        return self.messages


class FakeSuite:
    def __init__(self, events=None, tasks=None, error=None):
        self.events = events or []
        self.tasks = tasks or []
        self.error = error

    async def list_events(self, start, end):
        if self.error:
            raise self.error
        return self.events

    async def list_tasks(self, tasklist="@default"):
        if self.error:
            raise self.error
        return self.tasks


class FakeTelemetry:
    def __init__(self, text="المعالج 12% والرام 40%", error=None):
        self.text = text
        self.error = error

    async def report(self, **kwargs):
        if self.error:
            raise self.error
        return self.text


class FakeCoordinator:
    def __init__(self, status=LaunchStatus.CONFIRMATION_REQUIRED):
        self.status = status
        self.calls = []

    async def request_launch(self, name, *, origin):
        self.calls.append((name, origin))
        return self.status


class FakeComposer:
    def __init__(self, data=None, error=None):
        self.data = data
        self.error = error

    async def collect(self, now):
        if self.error:
            raise self.error
        return self.data


def _email(subject="فاتورة", sender="billing@corp.com", name="Corporate"):
    return EmailMessage(
        id="1",
        thread_id="1",
        subject=subject,
        from_email=sender,
        from_name=name,
        received_at=NOW,
    )


def _event(summary="اجتماع الفريق", offset_h=2.0):
    return CalendarEvent(
        id="e1",
        summary=summary,
        start=NOW + timedelta(hours=offset_h),
        end=NOW + timedelta(hours=offset_h + 1),
    )


def _task(title="تسليم التقرير", due=NOW + timedelta(hours=3)):
    return TaskItem(id="t1", title=title, due=due)


# --- gmail ------------------------------------------------------------------------


async def test_gmail_digest_lists_messages_with_count():
    registry = ToolRegistry(
        inbox=FakeInbox([_email(), _email("شحن الطلب", "shop@x.com", "Shop")]), tz=TZ
    )
    out = await registry.call("gmail", "")
    assert "2" in out
    assert "فاتورة" in out and "Corporate" in out
    assert "شحن الطلب" in out and "Shop" in out


async def test_gmail_empty_inbox_is_explicit():
    registry = ToolRegistry(inbox=FakeInbox([]), tz=TZ)
    out = await registry.call("gmail", "")
    assert "ما في" in out  # explicit «no new mail», never a silent empty string


async def test_gmail_without_inbox_is_honest_google_offline():
    registry = ToolRegistry(tz=TZ)
    assert await registry.call("gmail", "") == GOOGLE_OFFLINE_AR


async def test_gmail_backend_failure_degrades_to_honest_line():
    registry = ToolRegistry(inbox=FakeInbox(error=RuntimeError("api down")), tz=TZ)
    assert await registry.call("gmail", "") == TOOL_FAIL_AR


# --- calendar / tasks ---------------------------------------------------------------


async def test_calendar_formats_next_24h_events_in_owner_tz():
    registry = ToolRegistry(suite=FakeSuite(events=[_event()]), tz=TZ, now_fn=lambda: NOW)
    out = await registry.call("calendar", "")
    assert "اجتماع الفريق" in out
    assert "20:00" in out  # NOW+2h = 17:00 UTC = 20:00 Amman


async def test_calendar_without_suite_is_honest_google_offline():
    registry = ToolRegistry(tz=TZ)
    assert await registry.call("calendar", "") == GOOGLE_OFFLINE_AR


async def test_tasks_filters_to_due_today():
    today = _task("تسليم التقرير", NOW + timedelta(hours=3))
    tomorrow = _task("بعيد", NOW + timedelta(days=1))
    registry = ToolRegistry(suite=FakeSuite(tasks=[today, tomorrow]), tz=TZ, now_fn=lambda: NOW)
    out = await registry.call("tasks", "")
    assert "تسليم التقرير" in out
    assert "بعيد" not in out


async def test_tasks_none_due_today_is_explicit():
    registry = ToolRegistry(
        suite=FakeSuite(tasks=[_task("بعيد", NOW + timedelta(days=2))]), tz=TZ, now_fn=lambda: NOW
    )
    out = await registry.call("tasks", "")
    assert "ما في" in out


# --- telemetry ----------------------------------------------------------------------


async def test_telemetry_passes_bridge_report_through():
    registry = ToolRegistry(telemetry=FakeTelemetry("المعالج 12% والرام 40%"))
    assert await registry.call("telemetry", "") == "المعالج 12% والرام 40%"


async def test_telemetry_without_bridge_says_so():
    registry = ToolRegistry()
    assert await registry.call("telemetry", "") == OFFLINE_TEXT_AR


async def test_telemetry_failure_says_bridge_offline():
    registry = ToolRegistry(telemetry=FakeTelemetry(error=RuntimeError("ws down")))
    assert await registry.call("telemetry", "") == OFFLINE_TEXT_AR


# --- launch --------------------------------------------------------------------------


async def test_launch_goes_through_coordinator_and_narrates_nothing():
    coordinator = FakeCoordinator()
    registry = ToolRegistry(coordinator=coordinator)
    assert await registry.call("launch", "الآلة الحاسبة") is None
    assert coordinator.calls == [("الآلة الحاسبة", "owner_chat")]


async def test_launch_without_coordinator_is_honest():
    registry = ToolRegistry()
    out = await registry.call("launch", "الآلة الحاسبة")
    assert out is not None and "الجسر" in out


async def test_launch_without_app_name_asks():
    registry = ToolRegistry(coordinator=FakeCoordinator())
    out = await registry.call("launch", "")
    assert out is not None and "برنامج" in out


# --- brief ---------------------------------------------------------------------------


async def test_brief_formats_composer_data_as_plain_text():
    data = BriefData(
        events=[_event()],
        tasks=[_task()],
        unread_total=12,
        important_items=[_email("عقد الشغل")],
    )
    registry = ToolRegistry(composer=FakeComposer(data), tz=TZ)
    out = await registry.call("brief", "")
    assert "اجتماع الفريق" in out
    assert "تسليم التقرير" in out
    assert "12" in out
    assert "عقد الشغل" in out


async def test_brief_degraded_sections_are_honest():
    data = BriefData(events=None, tasks=None, unread_total=None, important_items=[])
    registry = ToolRegistry(composer=FakeComposer(data), tz=TZ)
    out = await registry.call("brief", "")
    assert "تعذّر" in out


async def test_brief_without_composer_is_honest_google_offline():
    registry = ToolRegistry()
    assert await registry.call("brief", "") == GOOGLE_OFFLINE_AR


# --- defensive ------------------------------------------------------------------------


async def test_unknown_tool_returns_honest_line():
    registry = ToolRegistry()
    out = await registry.call("weather", "")
    assert out is not None
