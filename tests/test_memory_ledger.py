"""Tier 1 — async self-expanding write-back (Step 11, durability doctrine).

Dual trigger only (weight >= 4 OR explicit owner intent); routine chitchat
schedules nothing. Milestones land in the nested daily ledger; the Tier-1
digest refresh is hard-capped. Everything is total — background tasks only.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from src.memory_ledger import (
    MASTER_DIGEST_PATH,
    maybe_write_back,
    refresh_digest,
    render_milestone,
    schedule_write_back,
    should_write_back,
)

NOW = datetime(2026, 9, 14, 12, 0, tzinfo=ZoneInfo("Asia/Amman"))


class FakeVault:
    def __init__(self, reads=None, fail=None):
        self.reads = dict(reads or {})
        self.appends = []
        self.upserts = []
        self.fail = fail

    async def read(self, path):
        if self.fail:
            raise self.fail
        try:
            return self.reads[path]
        except KeyError:
            raise FileNotFoundError(path) from None

    async def append_section(self, path, heading, lines, *, commit_prefix):
        if self.fail:
            raise self.fail
        self.appends.append((path, heading, tuple(lines), commit_prefix))
        return f"written:{path}"

    async def upsert(self, path, content, *, message=""):
        if self.fail:
            raise self.fail
        self.upserts.append((path, content, message))
        return object()


def test_trigger_weight_threshold():
    assert should_write_back("anything at all here", weight=4) is True
    assert should_write_back("anything at all here", weight=5) is True
    assert should_write_back("anything at all here", weight=3) is False
    assert should_write_back("مرحبا", weight=1) is False


def test_trigger_explicit_owner_intent():
    for text in (
        "remember this decision",
        "we decided to ship Friday",
        "تذكر هالشي",
        "سجل عندك الملاحظة",
        "اتفقنا نبلش بكرا",
    ):
        assert should_write_back(text, weight=1) is True, text


def test_trigger_chitchat_skipped():
    assert should_write_back("مرحبا سارة") is False
    assert should_write_back("") is False


def test_trigger_survives_classifier_crash(monkeypatch):
    import src.cognitive_dag as dag

    def _boom(text):
        raise RuntimeError("classifier down")

    monkeypatch.setattr(dag, "classify_weight", _boom)
    assert should_write_back("شو الأخبار؟") is False


def test_render_milestone_dated_single_line():
    line = render_milestone("قررنا  إطلاق  النسخة\nالجمعة", day=NOW.date())
    assert line.startswith("- 2026-09-14: ")
    assert "\n" not in line


async def test_append_milestone_nested_path():
    vault = FakeVault()
    path = await vault_append(vault)
    assert path == "Daily_Logs/2026/09/2026-09-14.md"
    assert vault.appends and vault.appends[0][0] == path


async def vault_append(vault):
    from src.memory_ledger import append_milestone

    return await append_milestone(vault, "قرار مهم", now=NOW)


async def test_maybe_write_back_full_pass():
    vault = FakeVault({MASTER_DIGEST_PATH: "---\ntitle: D\n---\nنبض اليوم: شغل."})
    out = await maybe_write_back(vault, "remember this architecture call", now=NOW)
    assert out is not None
    assert out["milestone_path"] == "Daily_Logs/2026/09/2026-09-14.md"
    assert out["digest_refreshed"] is True
    assert "Milestone log" in vault.upserts[0][1]


async def test_maybe_write_back_skips_routine():
    vault = FakeVault()
    assert await maybe_write_back(vault, "مرحبا", now=NOW) is None
    assert vault.appends == [] and vault.upserts == []


async def test_maybe_write_back_never_raises():
    vault = FakeVault(fail=RuntimeError("vault down"))
    out = await maybe_write_back(vault, "remember this now", now=NOW)
    assert out is not None  # partial honesty, never an exception
    assert out["milestone_path"] is None
    assert out["digest_refreshed"] is False


async def test_refresh_digest_missing_is_honest_false():
    assert await refresh_digest(FakeVault(), "- x") is False


async def test_refresh_digest_cap_enforced():
    body = "word " * 795
    vault = FakeVault({MASTER_DIGEST_PATH: body})
    assert await refresh_digest(vault, "- one more milestone line here") is False
    assert vault.upserts == []


async def test_schedule_returns_none_on_routine():
    assert schedule_write_back(FakeVault(), "مرحبا") is None
    assert schedule_write_back(None, "remember this") is None


async def test_schedule_spawns_background_task():
    import asyncio

    vault = FakeVault({MASTER_DIGEST_PATH: "نبض."})
    task = schedule_write_back(vault, "we decided the schema", tz=ZoneInfo("Asia/Amman"))
    assert isinstance(task, asyncio.Task)
    out = await task
    assert out is not None and out["digest_refreshed"] is True
