"""Daily brief composer (sprint-2 §2.4): one warm Jordanian-Arabic digest per
day at BRIEF_LOCAL_TIME — today's events, tasks due today, mail picture.

Deterministic fixed template, no LLM in the hot path. Restart-safe
fire-once-per-local-day: the date persists to GmailState only after a
successful send, so a failed send retries the same day.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from aiogram import Bot
from loguru import logger
from pydantic import BaseModel

from src.config import Settings
from src.email_triage import escape_mdv2
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
