"""Feature 4 (v1.1 roadmap): Sara's autonomous self-improvement & linguistic
evolution. A nightly reflection worker reads Daily_Logs/ + Dialect_Notes.md,
discovers recurring colloquial Jordanian idioms and phrasings SHE keeps
missing, and files proposed learnings to the vault (proposals only — the
owner's «تعلمي:» law and the vault's append-only discipline stay intact).
"""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from src.skills.self_evolution import SelfEvolutionWorker

AMMAN = ZoneInfo("Asia/Amman")
# 23:30 UTC on Sep 3 = 02:30 Sep 4 AMMAN — the worker's local day is Sep 4,
# so the test fixtures live on the LOCAL day (the midnight-rollover lesson).
NOW = datetime(2026, 9, 3, 23, 30, tzinfo=UTC)
LOCAL_DAY = "2026-09-04"


class FakeVault:
    def __init__(self, files=None, fail=False):
        self.files = dict(files or {})
        self.fail = fail
        self.writes: list[tuple[str, str]] = []

    async def read(self, path):
        if self.fail:
            raise RuntimeError("vault down")
        if path not in self.files:
            raise FileNotFoundError(path)
        return self.files[path]

    async def upsert(self, path, content, *, message):
        self.writes.append((path, content))
        self.files[path] = content


class FakeBrain:
    def __init__(self, reply):
        self.reply = reply
        self.calls = 0

    async def chat(self, messages, *, tier, **kwargs):
        self.calls += 1
        return self.reply


def _worker(brain, vault, **kw):
    return SelfEvolutionWorker(
        brain=brain,
        vault=vault,
        tz=AMMAN,
        now_fn=lambda: NOW,
        **kw,
    )


async def test_discovers_and_files_idiom_proposal():
    """The nightly reflection reads the day's ledger + the current dialect
    notes; a discovered recurring idiom lands as a PROPOSAL section in
    Dialect_Notes (never silently learned — the owner reviews)."""
    brain = FakeBrain(
        '{"discoveries": [{"term": "شقحط", "phonetic": "شُقحِط", '
        '"context": "سارة نطقتها غلط 3 مرات اليوم", "confidence": 0.9}]}'
    )
    vault = FakeVault(
        {
            "Daily_Logs/"
            + LOCAL_DAY
            + ".md": "---\n---\n## دردشة 21:00\n\n**المالك:** شو يعني شقحط",
            "02_Areas/Profile/Dialect_Notes.md": "---\nnotes:\n---\n",
        }
    )
    worker = _worker(brain, vault)
    found = await worker.reflect_once()
    assert found == 1
    # the proposal landed in Dialect_Notes as a REVIEW section
    path, content = vault.writes[0]
    assert "Dialect_Notes" in path
    assert "شقحط" in content
    assert "مقترح" in content  # a PROPOSAL marker, not a silent learning


async def test_no_discoveries_write_nothing():
    brain = FakeBrain('{"discoveries": []}')
    vault = FakeVault(
        {
            "Daily_Logs/" + LOCAL_DAY + ".md": "---\n---\n**المالك:** مرحبا",
            "02_Areas/Profile/Dialect_Notes.md": "---\nnotes:\n---\n",
        }
    )
    worker = _worker(brain, vault)
    assert await worker.reflect_once() == 0
    assert vault.writes == []


async def test_dead_vault_or_brain_never_breaks():
    """Any failure = silent skip; the worker survives to the next night."""
    brain = FakeBrain('{"discoveries": []}')
    vault = FakeVault(fail=True)
    worker = _worker(brain, vault)
    assert await worker.reflect_once() == 0  # no raise

    class DeadBrain(FakeBrain):
        async def chat(self, messages, *, tier, **kwargs):
            raise RuntimeError("pool down")

    worker2 = _worker(DeadBrain("x"), FakeVault({"Daily_Logs/" + LOCAL_DAY + ".md": "x"}))
    assert await worker2.reflect_once() == 0


async def test_reflection_reads_real_context():
    """The judgement prompt carries the day's ledger + the CURRENT notes —
    proposals build on what she already knows (no duplicate proposals)."""
    brain = FakeBrain('{"discoveries": []}')
    vault = FakeVault(
        {
            "Daily_Logs/" + LOCAL_DAY + ".md": "---\n---\n**المالك:** بدي أياك تعلمي شقحط",
            "02_Areas/Profile/Dialect_Notes.md": "---\nnotes:\n  - term: هسا\n    phonetic: هسَّا\n---\n",
        }
    )
    worker = _worker(brain, vault)
    await worker.reflect_once()
    assert brain.calls == 1


async def test_proposal_dedupe_by_term():
    """A term already PROPOSED today is not re-proposed — the reflection is
    idempotent within a day."""
    brain = FakeBrain(
        '{"discoveries": [{"term": "شقحط", "phonetic": "شُقحِط", "context": "", "confidence": 0.9}]}'
    )
    vault = FakeVault(
        {
            "Daily_Logs/" + LOCAL_DAY + ".md": "---\n---\n**المالك:** حكي",
            "02_Areas/Profile/Dialect_Notes.md": (
                "---\nnotes:\n---\n\n## مقترحات تعلم 2026-09-04\n\n- شقحط -> شُقحِط\n"
            ),
        }
    )
    worker = _worker(brain, vault)
    assert await worker.reflect_once() == 0  # already proposed today
    assert vault.writes == []


def test_due_at_night_once_per_day():
    """The worker fires ~23:40 local (after the summarizer), once per day."""
    brain = FakeBrain('{"discoveries": []}')
    worker = _worker(brain, FakeVault())
    late = datetime(2026, 9, 3, 20, 45, tzinfo=UTC)  # 23:45 Amman
    assert worker.due(late) is True
    early = datetime(2026, 9, 3, 10, 0, tzinfo=UTC)  # 13:00 Amman
    assert worker.due(early) is False
