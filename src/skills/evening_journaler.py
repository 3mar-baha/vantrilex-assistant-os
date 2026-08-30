"""Evening proactive journaler (sprint-2 §2.6): once per local day Sara writes
the activity ledger to ``Daily_Logs/YYYY-MM-DD.md`` and sends ONE Jordanian
check-in inside a randomized [18:00, 19:30) Asia/Amman window — skipped when
the calendar shows the owner busy (the ledger still lands). Zero LLM in the
hot path: template plus collected facts. Stdlib scheduling only (zoneinfo +
asyncio.sleep). Send failure never persists the check-in state, so it retries
the next tick — at-most-once per successful send.
"""

import asyncio
import json
import os
import random
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from aiogram import Bot
from loguru import logger
from pydantic import BaseModel

from src.config import Settings
from src.email_triage import Tier
from src.google_suite import CalendarEvent

DEGRADED_TEXT = "غير متوفر حالياً"
POLL_TICK_SECONDS = 30


class LedgerData(BaseModel):
    """None sections mean «source failed -> section degraded» (spec error modes)."""

    date: str
    events: list[CalendarEvent] | None = None
    tasks_done: int | None = None
    critical_mail_count: int | None = None
    memos_filed: int | None = None
    checkin_sent: bool = False


class EveningJournaler:
    def __init__(
        self,
        suite,
        bot: Bot,
        chat_id: int,
        settings: Settings,
        vault_dir: Path,
        *,
        inbox=None,
        classifier=None,
        rng=random.uniform,
    ) -> None:
        self._suite = suite
        self._bot = bot
        self._chat_id = chat_id
        self._settings = settings
        self._vault_dir = vault_dir
        self._inbox = inbox
        self._classifier = classifier
        self._rng = rng
        try:
            self._tz = ZoneInfo(settings.tz or "UTC")
        except (KeyError, ValueError):  # missing tz key -> UTC fallback + warning
            logger.warning("unknown tz '{}' -> UTC fallback for evening journaler", settings.tz)
            self._tz = ZoneInfo("UTC")
        self._slot: datetime | None = None
        self._slot_date: date | None = None
        self._state_path = vault_dir / "State" / "journaler.json"

    def _window_edge(self, day: date, hhmm: str) -> datetime:
        return datetime.combine(day, time.fromisoformat(hhmm), tzinfo=self._tz)

    def pick_slot(self, now: datetime) -> datetime:
        """Uniform-random instant in [window_start, window_end) of now's local day."""
        local = now.astimezone(self._tz)
        start = self._window_edge(local.date(), self._settings.journaler_window_start)
        end = self._window_edge(local.date(), self._settings.journaler_window_end)
        return start + timedelta(seconds=self._rng(0, (end - start).total_seconds()))

    def _slot_for(self, now: datetime) -> datetime:
        """Reroll once per local day (restarts inside the window are fine)."""
        local = now.astimezone(self._tz)
        if self._slot is None or self._slot_date != local.date():
            self._slot = self.pick_slot(now)
            self._slot_date = local.date()
        return self._slot

    async def collect(self, now: datetime) -> LedgerData:
        """Per-source isolation: one failing section degrades alone."""
        local = now.astimezone(self._tz)
        day_start = datetime.combine(local.date(), time.min, tzinfo=self._tz)
        day_end = day_start + timedelta(days=1)

        events: list | None = None
        try:
            events = await self._suite.list_events(day_start, day_end)
        except Exception as error:  # noqa: BLE001 — section isolation (spec error mode)
            logger.error("journaler events section degraded: {}", error)

        tasks_done: int | None = None
        try:
            all_tasks = await self._suite.list_tasks()
            tasks_done = sum(1 for task in all_tasks if task.completed)
        except Exception as error:  # noqa: BLE001 — section isolation
            logger.error("journaler tasks section degraded: {}", error)

        critical_mail_count: int | None = None
        if self._inbox is not None and self._classifier is not None:
            try:
                messages = await self._inbox.peek_unread()
                critical_mail_count = sum(
                    1
                    for message in messages
                    if self._classifier.heuristic(message).tier == Tier.CRITICAL
                )
            except Exception as error:  # noqa: BLE001 — section isolation
                logger.error("journaler mail section degraded: {}", error)

        memos_filed: int | None = None
        try:
            memos_dir = self._vault_dir / self._settings.voice_memos_dir
            memos_filed = len(list(memos_dir.glob(f"{local.date():%Y-%m-%d}-*.md")))
        except OSError as error:
            logger.error("journaler memos section degraded: {}", error)

        return LedgerData(
            date=local.date().isoformat(),
            events=events,
            tasks_done=tasks_done,
            critical_mail_count=critical_mail_count,
            memos_filed=memos_filed,
        )

    def render_ledger(self, data: LedgerData) -> str:
        """PURE Arabic Markdown note (vault file, not chat — no MarkdownV2 escaping)."""
        lines = [
            "---",
            f"date: {data.date}",
            f"checkin_sent: {'true' if data.checkin_sent else 'false'}",
            "---",
            "",
            f"# 🌙 سجل يوم {data.date}",
            "",
            "## المواعيد",
        ]
        if data.events is None:
            lines.append(f"- {DEGRADED_TEXT}")
        elif data.events:
            lines.extend(
                f"- {event.start.astimezone(self._tz).strftime('%H:%M')}"
                f"–{event.end.astimezone(self._tz).strftime('%H:%M')}"
                f" {event.summary}"
                for event in data.events
            )
        else:
            lines.append("- لا مواعيد مسجلة")

        lines += ["", "## البريد"]
        if data.critical_mail_count is None:
            lines.append(f"- {DEGRADED_TEXT}")
        elif data.critical_mail_count:
            lines.append(f"- {data.critical_mail_count} رسائل حرجة تحتاج نظرة")
        else:
            lines.append("- لا بريد حرج اليوم")

        lines += ["", "## المذكرات الصوتية"]
        if data.memos_filed is None:
            lines.append(f"- {DEGRADED_TEXT}")
        else:
            lines.append(f"- {data.memos_filed} مذكرات مسجلة اليوم")

        return "\n".join(lines + ["", "## ملاحظات", ""])

    def _checkin_text(self, data: LedgerData) -> str:
        def part(label: str, count: int | None) -> str:
            return f"{label}: {DEGRADED_TEXT}" if count is None else f"{label}: {count}"

        return (
            "🌙 مساء الخير! خلاصة اليوم — "
            f"{part('مهام منجزة', data.tasks_done)} · "
            f"{part('بريد حرج', data.critical_mail_count)} · "
            f"{part('مذكرات صوتية', data.memos_filed)}\n"
            "شو آخر شي ببالك اليوم، حابب نضيفه عالسجل قبل ما نغلق الصفحة؟"
        )

    def _load_state(self) -> dict:
        try:
            return json.loads(self._state_path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (ValueError, OSError):
            logger.warning("journaler state corrupt -> treating absent")
            return {}

    def _save_state(self, state: dict) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")

    def _write_ledger(self, data: LedgerData) -> None:
        ledger_dir = self._vault_dir / self._settings.daily_logs_dir
        ledger_dir.mkdir(parents=True, exist_ok=True)
        path = ledger_dir / f"{data.date}.md"
        if path.exists():  # same-day state-loss re-run: corrigenda, never a duplicate
            with path.open("a", encoding="utf-8") as handle:
                handle.write(f"- تصحيح: أُعيد توليد السجل {datetime.now(self._tz):%H:%M}\n")
            return
        tmp = path.with_suffix(".md.tmp")
        tmp.write_text(self.render_ledger(data), encoding="utf-8")
        os.replace(tmp, path)

    async def _owner_busy(self, now: datetime) -> bool:
        """Any event overlapping [now, window_end) -> booked through the window."""
        try:
            window_end = self._window_edge(
                now.astimezone(self._tz).date(), self._settings.journaler_window_end
            )
            return bool(await self._suite.list_events(now, window_end))
        except Exception as error:  # noqa: BLE001 — degrade to «not busy» (spec)
            logger.error("journaler busy-check degraded -> assuming free: {}", error)
            return False

    async def fire_once(self, now: datetime) -> bool:
        """True iff a check-in message went out this call. Ledger date persists
        even when the send is skipped/busy; check-in date only on send success."""
        if not self._settings.journaler_enabled:
            return False
        local_now = now.astimezone(self._tz)
        today = local_now.date().isoformat()
        state = self._load_state()
        if state.get("last_ledger_date") == today and state.get("last_checkin_sent") == today:
            return False
        if now < self._slot_for(now):
            return False

        data = await self.collect(now)
        sent = False
        if state.get("last_checkin_sent") != today and not await self._owner_busy(now):
            try:
                await self._bot.send_message(self._chat_id, self._checkin_text(data))
                state["last_checkin_sent"] = today
                sent = True
            except Exception:  # noqa: BLE001 — send failure retries next tick (no persist)
                logger.error("evening check-in send failed -> state not persisted")
        if state.get("last_ledger_date") != today:
            self._write_ledger(data.model_copy(update={"checkin_sent": sent}))
            state["last_ledger_date"] = today
        self._save_state(state)
        return sent

    async def run_forever(self) -> None:
        """Tick loop — fire_once gates all work, so idle ticks cost nothing."""
        while True:
            try:
                await self.fire_once(datetime.now(UTC))
            except Exception:  # noqa: BLE001 — loop must survive anything (spec)
                logger.exception("evening journaler cycle failed, continuing")
            await asyncio.sleep(POLL_TICK_SECONDS)
