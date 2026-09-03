"""ToolRegistry (owner directive 2026-09-01): the real backends behind the
dispatcher's tool lane. Every tool answers with honest plain-Arabic text —
never silence, never a hallucinated success — and the launch tool notifies the
owner through PCActionCoordinator (audit code included), returning None so the
dispatcher skips narration. Google/bridge outages degrade to explicit offline
lines; backend failures degrade loudly to a plain apology line.
"""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from loguru import logger

from src.bridge_server import BridgeOffline
from src.telemetry import OFFLINE_TEXT_AR

GOOGLE_OFFLINE_AR = "الجيميل والتقويم مو متصلين هسا — ما قدرت أوصل لحسابك بغوغل"
TOOL_FAIL_AR = "حصل عطل بسيط وما قدرت أكمّل الطلب — جرب مرة ثانية"
LAUNCH_OFFLINE_AR = "ما بقدر أتحكم بالجهاز هسا — الجسر مو متصل"
NO_MAIL_AR = "ما في بريد جديد هسا، كل شي مقروء"
NO_EVENTS_AR = "ما في مواعيد بالـ24 ساعة الجاية"
NO_TASKS_TODAY_AR = "ما في مهام مستحقة اليوم"
ASK_APP_AR = "شو البرنامج اللي بدك تفتحه؟ قولي الاسم وبشغّله فوراً"
MAX_LINES = 8


class ToolRegistry:
    def __init__(
        self,
        *,
        inbox: Any = None,
        suite: Any = None,
        telemetry: Any = None,
        coordinator: Any = None,
        composer: Any = None,
        tz: ZoneInfo | None = None,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        self._inbox = inbox
        self._suite = suite
        self._telemetry = telemetry
        self._coordinator = coordinator
        self._composer = composer
        self._tz = tz or ZoneInfo("UTC")
        # Injectable clock: the frozen-date test bomb (2026-09-01 -> 2026-09-02) showed
        # wall-clock reads inside handlers make tests die at midnight rollovers.
        self._now = now_fn or (lambda: datetime.now(UTC))

    async def call(self, tool: str, arg: str = "") -> str | None:
        handler = getattr(self, f"_do_{tool}", None)
        if handler is None:
            logger.warning("tool registry got unknown tool {!r}", tool)
            return TOOL_FAIL_AR
        try:
            return await handler(arg)
        except Exception as error:  # noqa: BLE001 — honest failure, never a hang
            logger.exception("tool {!r} failed: {}", tool, error)
            return TOOL_FAIL_AR

    async def _do_gmail(self, arg: str) -> str:
        if self._inbox is None:
            return GOOGLE_OFFLINE_AR
        messages = await self._inbox.peek_unread()
        if not messages:
            return NO_MAIL_AR
        lines = [f"عندك {len(messages)} رسائل غير مقروءة:"]
        for message in messages[:MAX_LINES]:
            sender = message.from_name or message.from_email
            lines.append(f"• {sender}: {message.subject}")
        return "\n".join(lines)

    async def _do_calendar(self, arg: str) -> str:
        if self._suite is None:
            return GOOGLE_OFFLINE_AR
        now = self._now()
        events = await self._suite.list_events(now, now + timedelta(days=1))
        if not events:
            return NO_EVENTS_AR
        lines = ["مواعيد الـ24 ساعة الجاية:"]
        for event in events[:MAX_LINES]:
            local = event.start.astimezone(self._tz)
            lines.append(f"• {event.summary} — {local:%m-%d %H:%M}")
        return "\n".join(lines)

    async def _do_tasks(self, arg: str) -> str:
        if self._suite is None:
            return GOOGLE_OFFLINE_AR
        tasks = await self._suite.list_tasks()
        today = self._now().astimezone(self._tz).date()
        due_today = [
            task
            for task in tasks
            if task.due is not None and task.due.astimezone(self._tz).date() == today
        ]
        if not due_today:
            return NO_TASKS_TODAY_AR
        lines = ["مهامك المستحقة اليوم:"]
        for task in due_today[:MAX_LINES]:
            lines.append(f"• {task.title} — {task.due.astimezone(self._tz):%H:%M}")
        return "\n".join(lines)

    async def _do_telemetry(self, arg: str) -> str:
        if self._telemetry is None:
            return OFFLINE_TEXT_AR
        try:
            return await self._telemetry.report()
        except Exception as error:  # noqa: BLE001 — the bridge line is the honest answer
            logger.warning("telemetry report failed: {}", error)
            return OFFLINE_TEXT_AR

    async def _do_launch(self, arg: str) -> str | None:
        name = arg.strip()
        if not name:
            return ASK_APP_AR
        if self._coordinator is None:
            return LAUNCH_OFFLINE_AR
        try:
            await self._coordinator.request_launch(name, origin="owner_chat")
        except BridgeOffline:
            # live 2026-09-03 22:16: a missing bridge session deserves its OWN
            # honest line, not the generic «عطل بسيط» — the owner knows to
            # start the daemon.
            return LAUNCH_OFFLINE_AR
        return None  # the coordinator notifies the owner itself (audit code inside)

    async def _do_brief(self, arg: str) -> str:
        if self._composer is None:
            return GOOGLE_OFFLINE_AR
        data = await self._composer.collect(self._now())
        lines = ["الإحاطة اليومية:"]
        if data.events is None:
            lines.append("المواعيد: تعذّر الوصول للتقويم")
        elif data.events:
            names = "، ".join(event.summary for event in data.events[:5])
            lines.append(f"المواعيد ({len(data.events)}): {names}")
        else:
            lines.append("المواعيد: ما في")
        if data.tasks is None:
            lines.append("المهام: تعذّر الوصول لقائمة المهام")
        elif data.tasks:
            names = "، ".join(task.title for task in data.tasks[:5])
            lines.append(f"المهام ({len(data.tasks)}): {names}")
        else:
            lines.append("المهام: ما في")
        if data.unread_total is None:
            lines.append("البريد: تعذّر الوصول للبريد")
        else:
            lines.append(f"البريد غير المقروء: {data.unread_total}")
        for item in data.important_items[:3]:
            sender = item.from_name or item.from_email
            lines.append(f"• مهم: {item.subject} من {sender}")
        return "\n".join(lines)
