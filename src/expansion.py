"""M4 — dynamic capability expansion (sprint-4 4.2).

The owner hands Sara a credential env NAME in chat; Sara probes it, parses an
Arabic/English natural-language schedule, and registers a background async task
WITHOUT redeploy. Rules: secrets enter via env only (the VALUE never reaches any
log or error — only the NAME), failures disable loudly (no silent retry loops),
state survives restarts by re-deriving from the vault record (ADR-15), and the
clock zone is pinned to ``settings.tz``.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Any, Literal
from zoneinfo import ZoneInfo

from loguru import logger
from pydantic import BaseModel, Field

CAPABILITIES_STATE_PATH = "State/capabilities.json"
DEFAULT_MAX_TASKS = 8
CREDENTIAL_MIN_LENGTH = 16

# Names that must never be shadowed by an owner-registered task — these are the
# PC-control / triage / journaling internals Sara's core routes through.
RESERVED_TASK_NAMES = frozenset(
    {
        "pc",
        "bridge",
        "wol",
        "telemetry",
        "executor",
        "whitelist",
        "triage",
        "gmail",
        "gmail_watch",
        "calendar",
        "drive",
        "contacts",
        "daily_brief",
        "brief",
        "evening_journaler",
        "journaler",
        "vault",
        "expansion",
        "sara",
        "owner",
    }
)

Pipeline = Callable[..., Awaitable[None]]


class ExpansionError(RuntimeError):
    """Raised for any refusal or unsupported phrasing in capability expansion."""


class ScheduleSpec(BaseModel):
    kind: Literal["daily", "weekly", "hourly"]
    hour: int = Field(default=9, ge=0, le=23)
    minute: int = Field(default=0, ge=0, le=59)
    weekday: int | None = Field(default=None, ge=0, le=6)  # 0=Monday .. 6=Sunday
    tz: str = "Asia/Amman"

    def now_tz(self) -> datetime:
        return datetime.now(ZoneInfo(self.tz))

    def next_after(self, now: datetime) -> datetime:
        if self.kind == "hourly":
            candidate = now.replace(minute=self.minute, second=0, microsecond=0)
            if candidate <= now:
                candidate += timedelta(hours=1)
            return candidate
        candidate = now.replace(hour=self.hour, minute=self.minute, second=0, microsecond=0)
        if candidate <= now or (self.kind == "weekly" and candidate.weekday() != self.weekday):
            candidate += timedelta(days=1)
            while self.kind == "weekly" and candidate.weekday() != self.weekday:
                candidate += timedelta(days=1)
        return candidate


_DAILY_WORDS = (
    "كل صباح",
    "كل يوم",
    "يوميا",
    "daily",
    "every morning",
    "every day",
    "each morning",
    "each day",
)
_HOURLY_WORDS = ("كل ساعة", "كل ساعه", "hourly", "every hour")
_WEEKDAY_WORDS = {
    "monday": 0,
    "mon": 0,
    "tuesday": 1,
    "tue": 1,
    "wednesday": 2,
    "wed": 2,
    "thursday": 3,
    "thu": 3,
    "friday": 4,
    "fri": 4,
    "saturday": 5,
    "sat": 5,
    "sunday": 6,
    "sun": 6,
    "الاثنين": 0,
    "اثنين": 0,
    "الثلاثاء": 1,
    "ثلاثاء": 1,
    "التلاتاء": 1,
    "تلاتاء": 1,
    "الأربعاء": 2,
    "الاربعاء": 2,
    "اربعاء": 2,
    "الخميس": 3,
    "خميس": 3,
    "الجمعة": 4,
    "الجمعه": 4,
    "جمعه": 4,
    "السبت": 5,
    "سبت": 5,
    "الأحد": 6,
    "الاحد": 6,
    "احد": 6,
}
_PM_WORDS = ("مساء", "ليل", "بعد الظهر", "pm", "evening", "night")
_TIME_RE = re.compile(r"(\d{1,2})(?:[:.](\d{2}))?")
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def parse_nl_cron(text: str) -> ScheduleSpec:
    """Parse Arabic/English natural-language schedule phrasing into a ScheduleSpec.

    "كل صباح 7" -> daily 07:00. "كل اثنين 9" -> weekly Monday 09:00.
    "كل ساعة" -> hourly at :00. Unsupported phrasing raises ExpansionError.
    """
    text = (text or "").strip().translate(_ARABIC_DIGITS).lower()
    if not text:
        raise ExpansionError("empty schedule text")

    kind: str | None = None
    weekday: int | None = None
    for word in _HOURLY_WORDS:
        if word in text:
            kind = "hourly"
            break
    if kind is None:
        for word, wd in _WEEKDAY_WORDS.items():
            if word in text:
                kind, weekday = "weekly", wd
                break
    if kind is None:
        for word in _DAILY_WORDS:
            if word in text:
                kind = "daily"
                break
    if kind is None:
        raise ExpansionError(f"unsupported schedule phrasing: {text!r}")

    match = _TIME_RE.search(text)
    if kind == "hourly":
        minute = 0
        if match:
            minute = int(match.group(2)) if match.group(2) else int(match.group(1))
        if minute > 59:
            raise ExpansionError(f"minute out of range in schedule: {text!r}")
        return ScheduleSpec(kind="hourly", minute=minute)
    hour = minute = None
    if match:
        hour, minute = int(match.group(1)), int(match.group(2) or 0)
    if hour is None:
        hour, minute = 9, 0
    if hour > 23 or minute > 59:
        raise ExpansionError(f"time out of range in schedule: {text!r}")
    if any(word in text for word in _PM_WORDS) and hour < 12:
        hour += 12
    return ScheduleSpec(kind=kind, hour=hour, minute=minute, weekday=weekday)


class TaskHandle(BaseModel):
    name: str
    schedule_text: str
    spec: ScheduleSpec
    credential_env: str
    enabled: bool = True
    last_error: str | None = None


class CapabilityScheduler:
    """Registry + asyncio scheduler for owner-registered background tasks."""

    def __init__(
        self,
        *,
        vault: Any = None,
        notifier: Any = None,
        max_tasks: int = DEFAULT_MAX_TASKS,
        task_timeout_s: float = 60.0,
    ) -> None:
        self._vault = vault
        self._notifier = notifier
        self._max_tasks = max_tasks
        self._task_timeout_s = task_timeout_s
        self._tasks: dict[str, TaskHandle] = {}
        self._pipelines: dict[str, Pipeline] = {}
        self._jobs: dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    def inventory(self) -> list[str]:
        return sorted(self._tasks)

    def get(self, name: str) -> TaskHandle | None:
        return self._tasks.get(name)

    async def register_capability(
        self,
        *,
        name: str,
        schedule_text: str,
        credential_env: str,
        pipeline: Pipeline,
        settings: Any,
    ) -> TaskHandle:
        async with self._lock:
            name = (name or "").strip()
            if not name:
                raise ExpansionError("task name is empty")
            if name in RESERVED_TASK_NAMES:
                raise ExpansionError(f"task name {name!r} is reserved — pick another")
            if name in self._tasks:
                raise ExpansionError(f"task {name!r} is already registered")
            if len(self._tasks) >= self._max_tasks:
                raise ExpansionError(
                    f"max registered tasks reached ({self._max_tasks}) — disable one first"
                )
            self._probe_credential(credential_env)
            spec = parse_nl_cron(schedule_text).model_copy(update={"tz": settings.tz})
            handle = TaskHandle(
                name=name,
                schedule_text=schedule_text,
                spec=spec,
                credential_env=credential_env,
            )
            self._tasks[name] = handle
            self._pipelines[name] = pipeline
            await self._persist()
            self._start_job(name)
            logger.info("capability task registered: {} — {} ({})", name, schedule_text, spec.kind)
            return handle

    async def restore(self, pipelines: dict[str, Pipeline]) -> list[str]:
        """Re-derive the registered task set from the vault record after a restart."""
        restored: list[str] = []
        if self._vault is None:
            return restored
        try:
            raw = await self._vault.read(CAPABILITIES_STATE_PATH)
        except FileNotFoundError:
            logger.info("no capability registry in vault — nothing to restore")
            return restored
        try:
            data = json.loads(raw)
            entries = data["tasks"]
        except (ValueError, KeyError, TypeError):
            logger.warning("capability registry corrupt — ignoring (loud, no restore)")
            return restored
        for entry in entries:
            name = str(entry.get("name", "")).strip()
            if not entry.get("enabled", False):
                continue
            if name in RESERVED_TASK_NAMES or name in self._tasks:
                logger.warning("skipping reserved/duplicate task in registry: {}", name)
                continue
            if len(self._tasks) >= self._max_tasks:
                logger.warning("max tasks reached during restore — stopping")
                break
            pipeline = pipelines.get(name)
            if pipeline is None:
                logger.warning("no pipeline provided for {} — not restored", name)
                continue
            try:
                spec = parse_nl_cron(entry["schedule_text"]).model_copy(
                    update={"tz": entry["spec"]["tz"]}
                )
            except (ExpansionError, KeyError, TypeError):
                logger.warning("unparsable schedule for {} — not restored", name)
                continue
            handle = TaskHandle(
                name=name,
                schedule_text=entry["schedule_text"],
                spec=spec,
                credential_env=entry["credential_env"],
                enabled=True,
                last_error=entry.get("last_error"),
            )
            self._tasks[name] = handle
            self._pipelines[name] = pipeline
            self._start_job(name)
            restored.append(name)
            logger.info("capability task restored from vault: {}", name)
        return restored

    async def enable(self, name: str) -> TaskHandle:
        """Explicit owner re-enable after a failure disable."""
        handle = self._tasks.get(name)
        if handle is None:
            raise ExpansionError(f"unknown task {name!r}")
        self._probe_credential(handle.credential_env)
        handle.enabled = True
        handle.last_error = None
        await self._persist()
        self._start_job(name)
        logger.info("capability task re-enabled: {}", name)
        return handle

    async def run_once(self, name: str) -> bool:
        """Run a task immediately through the guarded path (timeout/disable/notify).

        Returns True when an attempt was made, False when the task is disabled
        (no-op) — re-enable is an explicit owner action.
        """
        handle = self._tasks.get(name)
        if handle is None:
            raise ExpansionError(f"unknown task {name!r}")
        if not handle.enabled:
            logger.info("capability task {} is disabled — skipping run", name)
            return False
        pipeline = self._pipelines[name]
        ctx: dict[str, Any] = {
            "name": handle.name,
            "credential_env": handle.credential_env,
            "vault": self._vault,
        }
        try:
            await asyncio.wait_for(pipeline(ctx), timeout=self._task_timeout_s)
        except TimeoutError:
            await self._disable(handle, f"timed out after {self._task_timeout_s}s — cancelled")
        except Exception as exc:  # noqa: BLE001 — any failure disables loudly, never retried
            await self._disable(handle, str(exc))
        else:
            logger.info("capability task ran: {}", name)
        return True

    async def _disable(self, handle: TaskHandle, reason: str) -> None:
        handle.enabled = False
        handle.last_error = reason
        logger.error("capability task '{}' disabled: {}", handle.name, reason)
        if self._notifier is not None:
            try:
                await self._notifier.notify(f"المهمة «{handle.name}» توقفت: {reason}")
            except Exception as exc:  # noqa: BLE001 — notify failure never masks the disable
                logger.warning("owner notify failed for {}: {}", handle.name, exc)
        await self._persist()

    def _start_job(self, name: str) -> None:
        job = self._jobs.get(name)
        if job is not None and not job.done():
            return
        self._jobs[name] = asyncio.create_task(self._loop(name))

    async def _loop(self, name: str) -> None:
        while True:
            handle = self._tasks.get(name)
            if handle is None or not handle.enabled:
                return
            now = handle.spec.now_tz()
            delay = max(0.0, (handle.spec.next_after(now) - now).total_seconds())
            await asyncio.sleep(delay)
            await self.run_once(name)

    @staticmethod
    def _probe_credential(credential_env: str) -> None:
        value = os.environ.get(credential_env)
        if (
            value is None
            or not value.strip()
            or len(value) < CREDENTIAL_MIN_LENGTH
            or any(ch.isspace() for ch in value)
        ):
            logger.warning(
                "credential env {!r} missing or bad format — set it in .env "
                "(the value itself is never logged)",
                credential_env,
            )
            raise ExpansionError(
                f"credential env {credential_env!r} missing or bad format — "
                "set it in .env (the value is never read into chat)"
            )

    async def _persist(self) -> None:
        if self._vault is None:
            return
        payload = {
            "tasks": [self._tasks[name].model_dump(mode="json") for name in sorted(self._tasks)]
        }
        await self._vault.upsert(
            CAPABILITIES_STATE_PATH,
            json.dumps(payload, ensure_ascii=False, indent=2),
            message="sara: update capability registry",
        )
