"""P6 coverage, tools part A (master transformation plan, Phase P6).

Rich-backend legs for workspace, bridge-verb, vault, and orchestration
handlers — every double sits at a system boundary (inbox, suite, tunnel,
vault, engine); assertions target user-visible Arabic outcomes.
"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from src.bridge_server import BridgeOffline
from src.daily_brief import BriefData
from src.gmail import EmailMessage
from src.google_suite import CalendarEvent, DriveFile, TaskItem
from src.tools import TOOL_FAIL_AR, ToolRegistry

TZ = ZoneInfo("Asia/Amman")
NOW = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)


class FakeInbox:
    def __init__(self, messages=None, error=None):
        self.messages = messages or []
        self.error = error

    async def peek_unread(self, max_n=25):
        if self.error:
            raise self.error
        return self.messages


class FakeSuite:
    def __init__(self, events=None, tasks=None, drive=None, contacts=None, error=None):
        self.events = events or []
        self.tasks = tasks or []
        self.drive = drive or []
        self.contacts = contacts or []
        self.error = error
        self.created_events = []
        self.added_tasks = []

    async def list_events(self, start, end):
        if self.error:
            raise self.error
        return self.events

    async def list_tasks(self, tasklist="@default"):
        if self.error:
            raise self.error
        return self.tasks

    async def list_drive_files(self, query=None, page_size=5):
        if self.error:
            raise self.error
        return self.drive

    async def search_contacts(self, query):
        if self.error:
            raise self.error
        return self.contacts

    async def create_event(self, summary, start, end):
        self.created_events.append(summary)

    async def add_task(self, title):
        self.added_tasks.append(title)


class FakeTelemetry:
    def __init__(self, text="ok", error=None):
        self.text = text
        self.error = error

    async def report(self, **kwargs):
        if self.error:
            raise self.error
        return self.text


class FakeBridge:
    def __init__(self, payloads=None, error=None):
        self.payloads = payloads or {}
        self.error = error
        self.sent = []

    async def send_cmd(self, cmd, args, **kw):
        self.sent.append((cmd, args))
        if self.error is not None:
            raise self.error
        return self.payloads.get(cmd, {"status": "error", "detail": ""})


class FakeVision:
    def __init__(self, reply="وصف", error=None):
        self.reply = reply
        self.error = error

    async def chat(self, messages):
        if self.error is not None:
            raise self.error
        return self.reply


def _email(subject="فاتورة", name="Corporate"):
    return EmailMessage(
        id="1",
        thread_id="1",
        subject=subject,
        from_email="a@b.c",
        from_name=name,
        received_at=NOW,
    )


def _event(summary="اجتماع", offset_h=2.0):
    return CalendarEvent(
        id="e1",
        summary=summary,
        start=NOW + timedelta(hours=offset_h),
        end=NOW + timedelta(hours=offset_h + 1),
    )


def test_unknown_tool_fails_honestly():
    import asyncio as _aio

    assert _aio.run(ToolRegistry().call("nope", "")) == TOOL_FAIL_AR


def test_handler_exception_converts_to_fail():
    import asyncio as _aio

    class _Boom:
        async def peek_unread(self, max_n=25):
            raise RuntimeError("inbox exploded")

    assert _aio.run(ToolRegistry(inbox=_Boom()).call("gmail", "")) == TOOL_FAIL_AR


def test_gmail_rich_digest():
    import asyncio as _aio

    reg = ToolRegistry(inbox=FakeInbox([_email(), _email("شحن", "Shop")]), tz=TZ)
    out = _aio.run(reg.call("gmail", ""))
    assert "2" in out and "فاتورة" in out and "شحن" in out


def test_calendar_rich_and_empty():
    import asyncio as _aio

    reg = ToolRegistry(suite=FakeSuite(events=[_event()]), tz=TZ, now_fn=lambda: NOW)
    assert "اجتماع" in _aio.run(reg.call("calendar", ""))
    reg2 = ToolRegistry(suite=FakeSuite(events=[]), tz=TZ, now_fn=lambda: NOW)
    assert "ما في" in _aio.run(reg2.call("calendar", ""))


def test_tasks_due_today_and_empty():
    import asyncio as _aio

    due = TaskItem(id="t1", title="تقرير", due=NOW + timedelta(hours=1))
    reg = ToolRegistry(suite=FakeSuite(tasks=[due]), tz=TZ, now_fn=lambda: NOW)
    assert "تقرير" in _aio.run(reg.call("tasks", ""))
    reg2 = ToolRegistry(suite=FakeSuite(tasks=[]), tz=TZ, now_fn=lambda: NOW)
    assert "ما في" in _aio.run(reg2.call("tasks", ""))


def test_telemetry_ok_and_failure():
    import asyncio as _aio

    assert "ok" in _aio.run(ToolRegistry(telemetry=FakeTelemetry("ok")).call("telemetry", ""))
    assert "متصل" in _aio.run(
        ToolRegistry(telemetry=FakeTelemetry(error=RuntimeError("x"))).call("telemetry", "")
    )


def test_launch_empty_asks_and_coordinator_none_offline():
    import asyncio as _aio

    assert "البرنامج" in _aio.run(ToolRegistry().call("launch", "   "))
    assert "الجسر" in _aio.run(ToolRegistry().call("launch", "calc"))


def test_launch_bridge_offline_line():
    import asyncio as _aio

    class _Coord:
        async def request_launch(self, name, *, origin):
            raise BridgeOffline("down")

    out = _aio.run(ToolRegistry(coordinator=_Coord()).call("launch", "calc"))
    assert "الجسر" in out


def test_screenshot_full_and_variants():
    import asyncio as _aio
    import base64 as _b64

    jpeg = _b64.b64encode(b"\xff\xd8shot").decode()
    bridge = FakeBridge({"exec.screenshot": {"status": "ok", "detail": jpeg}})
    reg = ToolRegistry(bridge=bridge, vision=FakeVision("صورة مكتب"))
    assert "مكتب" in _aio.run(reg.call("screenshot", ""))
    sent = []

    async def _photo(data):
        sent.append(data)

    reg2 = ToolRegistry(bridge=bridge, vision=FakeVision("x"), photo_sender=_photo)
    _aio.run(reg2.call("screenshot", "ابعثيلي"))
    assert sent and sent[0].startswith(b"\xff\xd8")

    async def _dead_photo(data):
        raise RuntimeError("send down")

    reg3 = ToolRegistry(bridge=bridge, vision=FakeVision("وصف"), photo_sender=_dead_photo)
    assert "وصف" in _aio.run(reg3.call("screenshot", "ابعثيلي"))
    reg4 = ToolRegistry(
        bridge=FakeBridge({"exec.screenshot": {"status": "error", "detail": ""}}),
        vision=FakeVision("x"),
    )
    assert _aio.run(reg4.call("screenshot", "")) == TOOL_FAIL_AR


def test_app_sessions_variants():
    import asyncio as _aio

    full = {
        "apps": [{"name": "Chrome", "minutes": 90}, {"name": "Notepad", "minutes": 20}],
        "total_minutes": 110,
        "categories": {"work": 90},
        "screen_hours": 2.0,
    }
    reg = ToolRegistry(bridge=FakeBridge({"telemetry.app_sessions": full}), vision=None)
    out = _aio.run(reg.call("app_sessions", ""))
    assert "Chrome" in out and "ساعة شاشة" in out
    reg2 = ToolRegistry(
        bridge=FakeBridge({"telemetry.app_sessions": {"status": "error", "detail": "x"}})
    )
    assert _aio.run(reg2.call("app_sessions", "")) == TOOL_FAIL_AR
    reg3 = ToolRegistry(bridge=FakeBridge({"telemetry.app_sessions": {"apps": []}}))
    assert "ما سجلت" in _aio.run(reg3.call("app_sessions", ""))
    reg4 = ToolRegistry(
        bridge=FakeBridge({"telemetry.app_sessions": full}), vision=FakeVision("يوم شغل")
    )
    assert "شغل" in _aio.run(reg4.call("app_sessions", ""))
    reg5 = ToolRegistry(
        bridge=FakeBridge({"telemetry.app_sessions": full}),
        vision=FakeVision(error=RuntimeError("v")),
    )
    assert "Chrome" in _aio.run(reg5.call("app_sessions", ""))


def test_running_apps_variants():
    import asyncio as _aio

    rich = {
        "owner_apps": [{"name": "Chrome"}, {"name": "Notepad"}]
        + [{"name": f"App{i}"} for i in range(10)],
        "background": [{"name": "AV"}],
    }
    out = _aio.run(
        ToolRegistry(bridge=FakeBridge({"exec.list_apps": rich})).call("running_apps", "")
    )
    assert "Chrome" in out and "غيرهم" in out and "الخلفية" in out
    flat = {"apps": [{"name": "Solo"}]}
    assert "Solo" in _aio.run(
        ToolRegistry(bridge=FakeBridge({"exec.list_apps": flat})).call("running_apps", "")
    )
    assert "ما في" in _aio.run(
        ToolRegistry(
            bridge=FakeBridge({"exec.list_apps": {"owner_apps": [], "background": []}})
        ).call("running_apps", "")
    )
    assert (
        _aio.run(
            ToolRegistry(bridge=FakeBridge({"exec.list_apps": [1, 2]})).call("running_apps", "")
        )
        == TOOL_FAIL_AR
    )


def test_whitelist_apps_variants(tmp_path):
    import asyncio as _aio
    import json as _json

    path = tmp_path / "whitelist.json"
    path.write_text(
        _json.dumps(
            {"allowed_apps": [{"name": f"App{i}", "executable": f"a{i}.exe"} for i in range(10)]}
        ),
        encoding="utf-8",
    )
    reg = ToolRegistry()
    reg.bind_whitelist_path(path)
    out = _aio.run(reg.call("whitelist_apps", ""))
    assert "10" in out and "غيرهم" in out
    assert "قائمة التطبيقات" in _aio.run(ToolRegistry().call("whitelist_apps", ""))
    path.write_text("not json{{", encoding="utf-8")
    assert "عطل" in _aio.run(reg.call("whitelist_apps", ""))
    path.write_text(_json.dumps({"allowed_apps": []}), encoding="utf-8")
    assert "فاضية" in _aio.run(reg.call("whitelist_apps", ""))


def test_multi_task_variants():
    import asyncio as _aio

    class _Manager:
        def __init__(self, error=None):
            self.error = error

        async def run(self, arg):
            if self.error is not None:
                raise self.error
            return "done: " + arg

    reg = ToolRegistry()
    reg.bind_agent_manager(_Manager())
    assert "done" in _aio.run(reg.call("multi_task", "اعملي أ وب"))
    assert _aio.run(reg.call("multi_task", "   ")) != ""
    reg2 = ToolRegistry()
    reg2.bind_agent_manager(_Manager(error=RuntimeError("boom")))
    assert _aio.run(reg2.call("multi_task", "اعملي أ")) != ""


def test_brief_sections_rich():
    import asyncio as _aio

    class _Composer:
        async def collect(self, now):
            return BriefData(
                events=[_event()],
                tasks=[],
                unread_total=2,
                important_items=[_email()],
            )

    out = _aio.run(ToolRegistry(composer=_Composer(), tz=TZ, now_fn=lambda: NOW).call("brief", ""))
    assert "اجتماع" in out and "2" in out and "فاتورة" in out


def test_brief_empty_sections():
    import asyncio as _aio

    class _Composer:
        async def collect(self, now):
            return BriefData(events=None, tasks=None, unread_total=None, important_items=[])

    out = _aio.run(ToolRegistry(composer=_Composer(), tz=TZ, now_fn=lambda: NOW).call("brief", ""))
    assert "تعذّر" in out


def test_drive_contacts_create_variants():
    import asyncio as _aio

    drive = [DriveFile(id="d1", name="تقرير", mimeType="text/plain")]
    contacts = [SimpleNamespace(display_name="أحمد", email="a@b.c", phones=["079"])]

    class _Suite(FakeSuite):
        async def create_event(self, summary, start, end):
            self.created_events.append(summary)

        async def add_task(self, title):
            self.added_tasks.append(title)

    suite = _Suite(drive=drive, contacts=contacts)
    reg = ToolRegistry(suite=suite, tz=TZ, now_fn=lambda: NOW)
    assert "تقرير" in _aio.run(reg.call("drive", "ملاحظات"))
    assert not _aio.run(reg.call("drive", "x")).strip() == ""
    out = _aio.run(reg.call("contacts", "أحمد"))
    assert "أحمد" in out and "079" in out and "a@b.c" in out
    assert "اسم الشخص" in _aio.run(reg.call("contacts", "   "))
    assert "ما لقيت" in _aio.run(
        ToolRegistry(suite=_Suite(contacts=[]), tz=TZ).call("contacts", "زيد")
    )
    assert "سجّلت الموعد" in _aio.run(reg.call("create_event", "اجتماع التخطيط"))
    assert "تفاصيل الموعد" in _aio.run(reg.call("create_event", "   "))
    assert "ضفت المهمة" in _aio.run(reg.call("create_task", "مراجعة العرض"))
    assert "المهمة" in _aio.run(reg.call("create_task", "   "))
    err = _Suite()
    err.error = RuntimeError("down")
    reg_err = ToolRegistry(suite=err, tz=TZ)
    assert "غوغل" in _aio.run(reg_err.call("drive", "x"))
