"""Daily brief composer (sprint-2 §2.4): one warm Jordanian-Arabic digest per
day at BRIEF_LOCAL_TIME — today's events, tasks due today, mail picture.

Deterministic fixed template, no LLM in the hot path. Restart-safe
fire-once-per-local-day: the date persists to GmailState only after a
successful send, so a failed send retries the same day.
"""

import asyncio
from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from aiogram import Bot
from loguru import logger
from pydantic import BaseModel

from src.config import Settings
from src.email_triage import Tier, escape_mdv2
from src.gmail import EmailMessage, GmailInbox
from src.google_suite import CalendarEvent, GoogleSuite, TaskItem

DEGRADED_TEXT = "غير متوفر حالياً"
HIGHLIGHT_CAP = 3
POLL_TICK_SECONDS = 30

_WEEKDAYS_AR = ("الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد")
_MONTHS_AR = (
    "كانون الثاني",
    "شباط",
    "آذار",
    "نيسان",
    "أيار",
    "حزيران",
    "تموز",
    "آب",
    "أيلول",
    "تشرين الأول",
    "تشرين الثاني",
    "كانون الأول",
)


class BriefData(BaseModel):
    """None sections mean «source failed -> section degraded» (AC5)."""

    events: list[CalendarEvent] | None = None
    tasks: list[TaskItem] | None = None
    unread_total: int | None = None
    important_items: list[EmailMessage] = []


class BriefComposer:
    def __init__(
        self,
        suite: GoogleSuite,
        inbox: GmailInbox,
        classifier,
        bot: Bot,
        chat_id: int,
        settings: Settings,
    ) -> None:
        self._suite = suite
        self._inbox = inbox
        self._classifier = classifier
        self._bot = bot
        self._chat_id = chat_id
        self._settings = settings
        try:
            self._tz = ZoneInfo(settings.tz or "UTC")
        except (KeyError, ValueError):  # missing tz key -> UTC fallback + warning
            logger.warning("unknown tz '{}' -> UTC fallback for daily brief", settings.tz)
            self._tz = ZoneInfo("UTC")

    def render(self, data: BriefData, now: datetime) -> str:
        """PURE MarkdownV2 Arabic template; all times Amman-local."""
        local = now.astimezone(self._tz)
        date_label = f"{_WEEKDAYS_AR[local.weekday()]} {local.day} {_MONTHS_AR[local.month - 1]}"
        lines = [f"☀️ صباح الخير\\! موجز يوم {date_label}"]

        if data.events is None:
            lines.append(f"📅 المواعيد: {DEGRADED_TEXT}")
        elif data.events:
            body = "\n".join(
                f"• {event.start.astimezone(self._tz).strftime('%H:%M')}"
                f"–{event.end.astimezone(self._tz).strftime('%H:%M')}"
                f" {escape_mdv2(event.summary)}"
                for event in data.events
            )
            lines.append(f"📅 مواعيد اليوم \\({len(data.events)}\\):\n{body}")
        else:
            lines.append("📅 لا مواعيد اليوم")

        if data.tasks is None:
            lines.append(f"✅ المهام: {DEGRADED_TEXT}")
        elif data.tasks:
            body = "\n".join(f"• {escape_mdv2(task.title)}" for task in data.tasks)
            lines.append(f"✅ مهام مستحقة اليوم \\({len(data.tasks)}\\):\n{body}")
        else:
            lines.append("✅ لا مهام مستحقة اليوم")

        if data.unread_total is None:
            lines.append(f"📥 البريد: {DEGRADED_TEXT}")
        else:
            mail = (
                f"📥 البريد: {data.unread_total} غير مقروءة"
                f" · مهمة: {len(data.important_items)}"
            )
            if data.important_items:
                first = data.important_items[0]
                sender = first.from_name or first.from_email
                mail += f" — أبرزها: «{escape_mdv2(first.subject)}» من {escape_mdv2(sender)}"
            lines.append(mail)
        return "\n".join(lines)

    async def collect(self, now: datetime) -> BriefData:
        """Assemble the mail picture deterministically — heuristic only, no LLM.
        Per-source isolation: one failing section degrades alone (AC5)."""
        events: list[CalendarEvent] | None = None
        try:
            events = await self._suite.list_events(now, now + timedelta(hours=24))
        except Exception as error:  # noqa: BLE001 — section isolation (spec error mode)
            logger.error("brief events section degraded: {}", error)

        tasks: list[TaskItem] | None = None
        try:
            all_tasks = await self._suite.list_tasks()
            local_today = now.astimezone(self._tz).date()
            tasks = [
                task
                for task in all_tasks
                if not task.completed
                and task.due is not None
                and task.due.astimezone(self._tz).date() == local_today
            ]
        except Exception as error:  # noqa: BLE001 — section isolation
            logger.error("brief tasks section degraded: {}", error)

        unread_total: int | None = None
        important: list[EmailMessage] = []
        try:
            unread_total, _unseen = await self._inbox.unread_digest()
            for message in await self._inbox.peek_unread():
                decision = self._classifier.heuristic(message)
                if decision.tier in (Tier.IMPORTANT, Tier.CRITICAL):
                    important.append(message)
                if len(important) >= HIGHLIGHT_CAP:
                    break
        except Exception as error:  # noqa: BLE001 — section isolation
            logger.error("brief mail section degraded: {}", error)
        return BriefData(
            events=events, tasks=tasks, unread_total=unread_total, important_items=important
        )

    def fire_if_due(self, now: datetime) -> bool:
        """Due when past BRIEF_LOCAL_TIME AND last_brief_date != today (local)."""
        if not self._settings.brief_enabled:
            return False
        local_now = now.astimezone(self._tz)
        brief_at = time.fromisoformat(self._settings.brief_local_time)
        if (local_now.hour, local_now.minute) < (brief_at.hour, brief_at.minute):
            return False
        return self._inbox.state.last_brief_date != local_now.date().isoformat()

    async def fire_once(self, now: datetime) -> bool:
        """Collect -> render -> send; persist the date only on send success."""
        if not self.fire_if_due(now):
            return False
        data = await self.collect(now)
        try:
            await self._bot.send_message(
                self._chat_id, self.render(data, now), parse_mode="MarkdownV2"
            )
        except Exception:  # noqa: BLE001 — send failure retries same day (no persist)
            logger.error("daily brief send failed -> date not persisted, will retry")
            return False
        self._inbox.state.last_brief_date = now.astimezone(self._tz).date().isoformat()
        self._inbox.save_state()
        return True

    async def run_forever(self) -> None:
        """Tick loop — fire_if_due gates all work, so idle ticks cost nothing."""
        while True:
            try:
                await self.fire_once(datetime.now(UTC))
            except Exception:  # noqa: BLE001 — loop must survive anything (spec error mode)
                logger.exception("daily brief cycle failed, continuing")
            await asyncio.sleep(POLL_TICK_SECONDS)
