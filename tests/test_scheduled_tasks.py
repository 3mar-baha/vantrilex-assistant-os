"""Pass-2 scheduled tasks (v2.0 §3-ج/2): `01_Projects/Scheduled_Tasks/` notes carry
task metadata in frontmatter + [sara:task:...] tracking tags; the sync engine
mirrors them to Google Calendar + Google Tasks. One note = one task. Sync is
idempotent (re-running never duplicates Google entries) and bidirectionally keyed
by the sara task id tag. Google down -> the note still lands, sync retries next
cycle (staged, honest)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from src.skills.scheduled_tasks import (
    SCHEDULED_TASKS_DIR,
    ScheduledTasksEngine,
    TaskNote,
    parse_task_note,
    render_task_note,
)


class FakeVault:
    """In-memory vault: upsert/append/read semantics like VaultClient."""

    def __init__(self) -> None:
        self.files: dict[str, str] = {}

    async def read(self, path: str) -> str:
        if path not in self.files:
            raise FileNotFoundError(path)
        return self.files[path]

    async def list_dir(self, path: str, *, recursive: bool = False) -> list[str]:
        prefix = f"{path}/"
        return [p for p in self.files if p.startswith(prefix) and p.endswith(".md")]

    async def upsert(self, path: str, content: str, *, message: str, merge=None) -> object:
        if merge is not None:
            content = merge(path, self.files.get(path, ""))
        self.files[path] = content
        return content

    async def upsert_note(self, note, *, message: str) -> object:
        self.files[note.path] = note.body
        return note


class FakeSuite:
    def __init__(self) -> None:
        self.events: list[dict] = []
        self.tasks: list[dict] = []
        self.fail = False

    async def create_event(self, summary, start, end, **kw) -> object:
        if self.fail:
            raise RuntimeError("google down")
        self.events.append({"summary": summary, "start": start, "end": end})
        return object()

    async def add_task(self, title, *, due=None, notes=None, tasklist="@default") -> object:
        if self.fail:
            raise RuntimeError("google down")
        self.tasks.append({"title": title, "due": due})
        return object()


NOW = datetime(2026, 9, 4, 12, 0, tzinfo=UTC)


def _engine(vault=None, suite=None, tz=None) -> ScheduledTasksEngine:
    return ScheduledTasksEngine(
        vault or FakeVault(),
        suite or FakeSuite(),
        tz=tz,
        now_fn=lambda: NOW,
    )


def test_render_note_has_sara_task_tag_and_frontmatter():
    note = TaskNote(
        title="مراجعة الفيزياء",
        when=NOW + timedelta(days=1),
        task_id="phys-rev-1",
    )
    text = render_task_note(note)
    assert "[sara:task:phys-rev-1]" in text
    assert "مراجعة الفيزياء" in text
    assert "2026-09-05" in text


def test_parse_roundtrip():
    note = TaskNote(title="X", when=NOW, task_id="abc")
    parsed = parse_task_note(render_task_note(note))
    assert parsed is not None
    assert parsed.task_id == "abc"
    assert parsed.title == "X"


def test_parse_rejects_notes_without_sara_tag():
    assert parse_task_note("---\ntitle: عادي\n---\n\nملاحظة بدون وسم") is None


async def test_create_task_writes_note_and_mirrors_to_google():
    vault, suite = FakeVault(), FakeSuite()
    engine = _engine(vault, suite)
    await engine.create_task(title="جلسة مذاكرة", when=NOW + timedelta(hours=3))
    # 1) the note landed in the Scheduled_Tasks dir with the tracking tag
    notes = [p for p in vault.files if p.startswith(SCHEDULED_TASKS_DIR)]
    assert len(notes) == 1
    assert "[sara:task:" in vault.files[notes[0]]
    # 2) BOTH mirrors fired: a calendar event + a tasks entry with the same title
    assert len(suite.events) == 1
    assert len(suite.tasks) == 1
    assert suite.tasks[0]["title"] == "جلسة مذاكرة"


async def test_sync_is_idempotent_no_duplicates():
    """Re-syncing the same note never duplicates Google entries."""
    vault, suite = FakeVault(), FakeSuite()
    engine = _engine(vault, suite)
    await engine.create_task(title="تمرين رياضة", when=NOW + timedelta(days=2))
    # task ids already synced are recorded in the note itself — a fresh engine
    # reading the same vault must skip, not re-create
    engine2 = ScheduledTasksEngine(vault, suite, now_fn=lambda: NOW)
    await engine2.sync_pending()
    assert len(suite.events) == 1
    assert len(suite.tasks) == 1


async def test_google_down_note_survives_sync_retries():
    """Google failure: the note is written, sync marks pending, next cycle retries."""
    vault, suite = FakeVault(), FakeSuite()
    engine = _engine(vault, suite)
    await engine.create_task(title="موعد دكتور", when=NOW + timedelta(days=3))
    # now google dies; a NEW task syncs its note but fails the mirror
    suite.fail = True
    created = await engine.create_task(title="موعد صيانة", when=NOW + timedelta(days=4))
    assert created is not None
    notes = [p for p in vault.files if p.startswith(SCHEDULED_TASKS_DIR)]
    assert len(notes) == 2  # both notes exist
    # google recovers; sync_pending catches the missed mirror up
    suite.fail = False
    synced = await engine.sync_pending()
    assert synced >= 1
    assert len(suite.events) == 2
    assert len(suite.tasks) == 2


async def test_completed_task_marks_done_in_note():
    vault, suite = FakeVault(), FakeSuite()
    engine = _engine(vault, suite)
    await engine.create_task(title="قراءة فصل", when=NOW + timedelta(hours=6))
    path = next(p for p in vault.files if p.startswith(SCHEDULED_TASKS_DIR))
    await engine.mark_done("قراءة فصل")
    assert "status: done" in vault.files[path] or "تمت" in vault.files[path]
