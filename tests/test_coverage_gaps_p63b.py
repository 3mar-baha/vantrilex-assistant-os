"""P6 coverage gap pins, batch 3b: memory lanes + associative edges.

Only previously uncovered branches: dead history hooks, malformed verdict
JSON, vault-read failures, empty summaries, run_forever survival, tag-shape
edges, unreadable vault files, empty queries, slice/domain edges, digest
failures, and the inject outer guard.
"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Asia/Amman")
NOW = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)


class FakeBrain:
    def __init__(self, reply=""):
        self.reply = reply

    async def chat(self, messages, **kwargs):
        return self.reply


class FakeVault:
    def __init__(self, reads=None, append_error=None):
        self.reads = dict(reads or {})
        self.appends = []
        self.append_error = append_error

    async def read(self, path):
        if path not in self.reads:
            raise FileNotFoundError(path)
        value = self.reads[path]
        if isinstance(value, Exception):
            raise value
        return value

    async def append_section(self, path, heading, lines, commit_prefix=""):
        if self.append_error is not None:
            raise self.append_error
        self.appends.append((path, heading, tuple(lines), commit_prefix))
        return f"written:{path}"


def test_live_history_hook_failure_reads_empty():
    from src.memory import AffectiveStateTracker

    def _boom():
        raise RuntimeError("hook dead")

    tracker = AffectiveStateTracker(brain=FakeBrain("{}"), history_fn=_boom)
    assert tracker._live_history() == []


def test_guide_malformed_verdict_json_neutral():
    from src.memory import AffectiveStateTracker

    tracker = AffectiveStateTracker(brain=FakeBrain("{oops}"))
    import asyncio as _aio

    assert _aio.run(tracker.guide("مرحبا")) == ""
    assert tracker.mode == "neutral"


def test_maybe_learn_malformed_json_no_write():
    from src.memory import VaultMemoryWriter

    writer = VaultMemoryWriter(FakeVault(), FakeBrain("{broken json}"), tz=TZ)
    import asyncio as _aio

    assert _aio.run(writer.maybe_learn("بحب القهوة", now=NOW)) is None


def test_summarize_vault_read_error_returns_none():
    from src.memory import DailySummarizer

    vault = FakeVault()
    summarizer = DailySummarizer(vault, FakeBrain("x"), tz=TZ)

    async def _run():
        import src.vault as vault_mod

        real = vault_mod.read_daily_log

        async def _boom(v, day):
            raise RuntimeError("disk gone")

        vault_mod.read_daily_log = _boom
        try:
            return await summarizer.summarize_day(NOW.date(), now=NOW)
        finally:
            vault_mod.read_daily_log = real

    import asyncio as _aio

    assert _aio.run(_run()) is None


def _ledger_note(body: str) -> dict:
    return {"Daily_Logs/2026/09/2026-09-17.md": "---\n---\n" + body}


def test_summarize_empty_reply_returns_none():
    from src.memory import DailySummarizer

    vault = FakeVault(_ledger_note("**المالك:** مرحبا\n**سارة:** أهلين\n"))
    summarizer = DailySummarizer(vault, FakeBrain("   "), tz=TZ)
    import asyncio as _aio

    assert _aio.run(summarizer.summarize_day(NOW.date(), now=NOW)) is None


def test_run_forever_summarizes_until_cancelled(monkeypatch):
    import asyncio as _aio

    from src.memory import DailySummarizer

    async def _instant(delay):
        return None

    monkeypatch.setattr(_aio, "sleep", _instant)

    vault = FakeVault(_ledger_note("**المالك:** مرحبا\n**سارة:** أهلين\n"))
    summarizer = DailySummarizer(vault, FakeBrain("ملخص اليوم"), tz=TZ)
    calls = {"due": 0}

    def _due(now):
        calls["due"] += 1
        if calls["due"] > 3:
            raise _aio.CancelledError()
        return True

    async def _run():
        summarizer.due = _due
        try:
            # Frozen clock: run_forever must not depend on the real calendar day.
            await summarizer.run_forever(now_fn=lambda: NOW)
        except _aio.CancelledError:
            pass

    _aio.run(_run())
    assert vault.appends, "one daily summary must land before cancel"
    assert calls["due"] >= 1


def test_run_forever_survives_writer_errors(monkeypatch):
    import asyncio as _aio

    from src.memory import DailySummarizer

    async def _instant(delay):
        return None

    monkeypatch.setattr(_aio, "sleep", _instant)

    vault = FakeVault(
        _ledger_note("**المالك:** مرحبا\n**سارة:** أهلين\n"),
        append_error=RuntimeError("vault down"),
    )
    summarizer = DailySummarizer(vault, FakeBrain("ملخص"), tz=TZ)
    calls = {"due": 0}

    def _due(now):
        calls["due"] += 1
        if calls["due"] > 1:
            raise _aio.CancelledError()
        return True

    async def _run():
        summarizer.due = _due
        try:
            # Frozen clock: the writer-error path must actually be reached.
            await summarizer.run_forever(now_fn=lambda: NOW)
        except _aio.CancelledError:
            pass

    _aio.run(_run())  # must not raise: the loop survives anything
    assert calls["due"] >= 1


def test_tags_of_shapes():
    from src.associative import _tags_of

    assert _tags_of(None) == []
    assert _tags_of("solo") == []
    assert _tags_of({"tags": "solo"}) == ["solo"]
    assert _tags_of({"tags": 42}) == []


def test_dir_mtime_missing_root_returns_none(tmp_path):
    from src.associative import VaultIndex

    assert VaultIndex(tmp_path / "nope").refresh_if_stale() is False


def test_scan_stat_failure_skipped(tmp_path, monkeypatch):
    import os as _os

    from src.associative import VaultIndex

    root = tmp_path / "v"
    (root / "sub").mkdir(parents=True)
    (root / "sub" / "a.md").write_text("# A\n\ntext here\n", encoding="utf-8")
    real_stat = _os.stat
    calls = {"n": 0}

    def _flaky(path, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise OSError("vanished mid-walk")
        return real_stat(path, *args, **kwargs)

    monkeypatch.setattr("os.stat", _flaky)
    index = VaultIndex(root)
    assert index.refresh_if_stale() is True


def test_refresh_scan_failure_returns_false(tmp_path, monkeypatch):
    from src.associative import VaultIndex

    root = tmp_path / "v"
    root.mkdir()
    (root / "a.md").write_text("# A\n", encoding="utf-8")
    index = VaultIndex(root)

    def _boom():
        raise RuntimeError("scan down")

    monkeypatch.setattr(index, "_scan", _boom)
    assert index.refresh_if_stale() is False


def test_scan_unreadable_file_skipped(tmp_path, monkeypatch):
    import pathlib

    from src.associative import VaultIndex

    root = tmp_path / "v"
    root.mkdir()
    (root / "a.md").write_text("# A\n\nreadable body here\n", encoding="utf-8")
    real_read = pathlib.Path.read_text

    def _flaky(self, *args, **kwargs):
        if self.name == "a.md":
            raise UnicodeError("bad bytes")
        return real_read(self, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "read_text", _flaky)
    index = VaultIndex(root)
    assert index.refresh_if_stale() is True
    assert index.size == 0


def test_query_empty_returns_nothing(tmp_path):
    from src.associative import VaultIndex

    root = tmp_path / "v"
    root.mkdir()
    (root / "a.md").write_text("# A\n\nbody\n", encoding="utf-8")
    index = VaultIndex(root)
    index.refresh_if_stale()
    assert index.query("") == []


def test_slice_empty_domains():
    from src.associative import slice_budgets

    assert slice_budgets(()) == []
    assert slice_budgets(("none",)) == []


def test_domains_for_intent_none_default():
    from src.associative import domains_for_intent

    assert domains_for_intent(None) == ("dialect", "personal")


def test_domain_of_backslash_and_unknown():
    from src.associative import domain_of

    assert domain_of("vault\\Dialect_Encyclopedia\\f.md") == "dialect"
    assert domain_of("zzz-unknown") is None
    assert domain_of("") is None


def test_compose_empty_sections():
    from src.associative import compose_rag_block

    assert compose_rag_block([], domains=("kb",)) == ""


def test_compose_unmapped_tail_no_regression():
    from src.associative import compose_rag_block

    out = compose_rag_block(
        [("Misc/random.md", "كلمات مميزة للاسترجاع هنا")],
        domains=("kb",),
    )
    assert "كلمات مميزة" in out


def test_digest_missing_root_empty(tmp_path):
    from src.associative import load_digest_block

    assert load_digest_block(tmp_path / "nope") == ""


def test_split_frontmatter_safe_fallback(monkeypatch):
    import src.vault as vault_mod
    from src.associative import _split_frontmatter_safe

    def _boom(text):
        raise RuntimeError("parser down")

    monkeypatch.setattr(vault_mod, "split_frontmatter", _boom)
    assert _split_frontmatter_safe("anything") == ({}, "anything")


def test_inject_outer_guard_returns_empty(monkeypatch, tmp_path):
    import src.associative as assoc

    def _boom(root):
        raise RuntimeError("index down")

    monkeypatch.setattr(assoc, "VaultIndex", _boom)
    assert assoc.inject("كلمات مميزة للاسترجاع", tmp_path) == ""
