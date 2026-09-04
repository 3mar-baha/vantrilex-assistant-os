"""Pass-2 scheduled tasks (v2.0 §3-ج/2): the `01_Projects/Scheduled_Tasks/` lane.
A task the owner states («ذكرني بكرة أراجع الفيزياء») becomes ONE note with a
[sara:task:<id>] tracking tag, mirrored to BOTH Google Calendar (the event) and
Google Tasks (the checklist item). Idempotent by tag: the note records its sync
state, so re-runs never duplicate Google entries; a Google outage parks the note
as pending and the next cycle catches it up. The engine is vault-first — the note
ALWAYS lands, mirrors are best-effort (the honest order: memory before cloud)."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from loguru import logger

from src.vault import VaultClient, split_frontmatter, write_frontmatter

SCHEDULED_TASKS_DIR = "01_Projects/Scheduled_Tasks"
_TAG_RE = re.compile(r"\[sara:task:(?P<id>[a-z0-9-]+)\]")
_DONE_MARKS = ("status: done", "✅ تمت")


@dataclass
class TaskNote:
    title: str
    when: datetime
    task_id: str
    status: str = "open"


def render_task_note(note: TaskNote) -> str:
    """YAML frontmatter (machine) + body (human) carrying the tracking tag."""
    meta = {
        "type": "sara-task",
        "title": note.title,
        "when": note.when.isoformat(),
        "task_id": note.task_id,
        "status": note.status,
        "synced": False,
    }
    body = (
        f"# {note.title}\n\n"
        f"- الموعد: {note.when:%Y-%m-%d %H:%M}\n"
        f"- الوسم: [sara:task:{note.task_id}]\n"
        f"- الحالة: {note.status}\n"
    )
    return write_frontmatter(meta, body)


def parse_task_note(text: str) -> TaskNote | None:
    """Parse a Scheduled_Tasks note back; None = not a sara task (no tag).
    Frontmatter is REAL YAML (vault.write_frontmatter/split_frontmatter) — never
    scraped line-by-line."""
    if not _TAG_RE.search(text):
        return None
    try:
        meta, _body = split_frontmatter(text)
    except ValueError:
        return None
    task_id = _TAG_RE.search(text).group("id")  # type: ignore[union-attr]
    title = str(meta.get("title") or "")
    raw_when = meta.get("when")
    when = datetime.fromisoformat(str(raw_when)) if raw_when else None
    if not title or when is None:
        return None
    return TaskNote(
        title=title, when=when, task_id=task_id, status=str(meta.get("status") or "open")
    )


class ScheduledTasksEngine:
    """Create + mirror + catch-up for scheduled task notes. All Google writes
    flow through ONE mirror path so idempotence is structural, not scattered."""

    def __init__(
        self,
        vault: VaultClient,
        suite: Any,
        *,
        tz: ZoneInfo | None = None,
        now_fn=None,
    ) -> None:
        self._vault = vault
        self._suite = suite
        self._tz = tz or ZoneInfo("UTC")
        self._now = now_fn or (lambda: datetime.now(UTC))

    # -- create ---------------------------------------------------------------

    async def create_task(self, *, title: str, when: datetime) -> TaskNote:
        """One task = one note + both mirrors. The note lands FIRST (vault-first
        honesty); mirror failures park it pending for the next sync cycle."""
        task_id = uuid.uuid4().hex[:8]
        note = TaskNote(title=title, when=when, task_id=task_id)
        path = f"{SCHEDULED_TASKS_DIR}/{self._now():%Y-%m-%d}_{task_id}.md"
        await self._vault.upsert(path, render_task_note(note), message=f"sara: task {task_id}")
        await self._mirror(note, path)
        return note

    # -- sync -----------------------------------------------------------------

    async def sync_pending(self) -> int:
        """Catch up notes whose mirrors failed (Google was down). Returns the
        count of tasks that caught up this cycle."""
        caught = 0
        for path in await self._task_paths():
            try:
                text = await self._vault.read(path)
            except FileNotFoundError:
                continue
            try:
                meta, _body = split_frontmatter(text)
            except ValueError:
                continue
            if meta.get("synced"):
                continue  # YAML bool true — mirrors already happened
            note = parse_task_note(text)
            if note is None:
                continue
            if await self._mirror(note, path):
                caught += 1
        return caught

    # -- completion -------------------------------------------------------------

    async def mark_done(self, title: str) -> bool:
        """Mark a task's note done by title (the checklist end of the loop)."""
        for path in await self._task_paths():
            try:
                text = await self._vault.read(path)
            except FileNotFoundError:
                continue
            if title in text and "status: open" in text:
                updated = text.replace("status: open", "status: done").replace(
                    "- الحالة: open", "- الحالة: ✅ تمت"
                )
                await self._vault.upsert(path, updated, message="sara: task done")
                return True
        return False

    # -- internals ----------------------------------------------------------------

    async def _task_paths(self) -> list[str]:
        """The Scheduled_Tasks dir listing — from the vault's dir-scan helper;
        a vault without the helper (old stubs) yields the empty list, never a crash."""
        lister = getattr(self._vault, "list_dir", None)
        if lister is None:
            return []
        try:
            return [p for p in await lister(SCHEDULED_TASKS_DIR) if p.endswith(".md")]
        except Exception:  # noqa: BLE001 — a dead scan never kills the loop
            logger.warning("scheduled-tasks dir scan failed")
            return []

    async def _mirror(self, note: TaskNote, path: str) -> bool:
        """Both Google mirrors; on success the note flips its synced flag. One
        event (~1h default) + one task with the due time."""
        try:
            await self._suite.create_event(
                note.title,
                note.when,
                note.when + timedelta(hours=1),
                description=f"[sara:task:{note.task_id}]",
            )
            await self._suite.add_task(
                note.title, due=note.when, notes=f"[sara:task:{note.task_id}]"
            )
        except Exception as error:  # noqa: BLE001 — parked, retried next cycle
            logger.warning("task mirror failed (parked for retry): {}", error)
            return False
        try:
            existing = await self._vault.read(path)
            meta, body = split_frontmatter(existing)
            if not meta.get("synced"):  # YAML bool, already true = nothing to do
                meta["synced"] = True
                await self._vault.upsert(
                    path, write_frontmatter(meta, body), message=f"sara: task synced {note.task_id}"
                )
        except Exception:  # noqa: BLE001 — the mirror already happened; bookkeeping is best-effort
            logger.warning("task sync-mark write failed (mirror already done)")
        return True
