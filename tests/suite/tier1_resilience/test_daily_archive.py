"""Tier 1 — nested daily archive contracts (durability Solution B).

Canonical shape `Daily_Logs/YYYY/MM/YYYY-MM-DD.md`, flat legacy as
read-fallback. Writers go nested; readers try nested-first; the 90-day hot
window enumerates the local mirror newest-first.
"""

from datetime import date

from src.vault import (
    daily_log_candidates,
    daily_log_local_path,
    daily_log_path,
    iter_recent_daily_logs,
    read_daily_log,
)


class _FakeVault:
    def __init__(self, files):
        self.files = dict(files)

    async def read(self, path):
        try:
            return self.files[path]
        except KeyError:
            raise FileNotFoundError(path) from None


def test_nested_canonical_shape():
    assert daily_log_path(date(2026, 9, 14)) == "Daily_Logs/2026/09/2026-09-14.md"
    assert daily_log_path(date(2026, 1, 5)) == "Daily_Logs/2026/01/2026-01-05.md"


def test_candidates_nested_first_flat_legacy():
    assert daily_log_candidates(date(2026, 9, 14)) == [
        "Daily_Logs/2026/09/2026-09-14.md",
        "Daily_Logs/2026-09-14.md",
    ]


async def test_read_prefers_nested():
    vault = _FakeVault(
        {
            "Daily_Logs/2026/09/2026-09-14.md": "nested",
            "Daily_Logs/2026-09-14.md": "legacy",
        }
    )
    assert await read_daily_log(vault, date(2026, 9, 14)) == (
        "Daily_Logs/2026/09/2026-09-14.md",
        "nested",
    )


async def test_read_falls_back_to_legacy():
    vault = _FakeVault({"Daily_Logs/2026-09-14.md": "legacy"})
    assert await read_daily_log(vault, date(2026, 9, 14)) == (
        "Daily_Logs/2026-09-14.md",
        "legacy",
    )


async def test_read_both_missing_raises():
    import pytest

    with pytest.raises(FileNotFoundError):
        await read_daily_log(_FakeVault({}), date(2026, 9, 14))


def test_local_path_nested(tmp_path):
    assert daily_log_local_path(tmp_path, date(2026, 9, 14)) == (
        tmp_path / "Daily_Logs" / "2026" / "09" / "2026-09-14.md"
    )


def test_iter_recent_window_and_order(tmp_path):
    base = tmp_path / "vault" / "Daily_Logs"
    for rel in (
        "2026/09/2026-09-14.md",
        "2026/09/2026-09-01.md",
        "2026/06/2026-06-01.md",  # outside the 90-day window
        "2026-08-20.md",  # legacy flat shape still counted
    ):
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x", encoding="utf-8")
    (base / "notes.txt").write_text("not a log", encoding="utf-8")
    got = [
        p.relative_to(base).as_posix()
        for p in iter_recent_daily_logs(tmp_path / "vault", today=date(2026, 9, 14))
    ]
    assert got == [
        "2026/09/2026-09-14.md",
        "2026/09/2026-09-01.md",
        "2026-08-20.md",
    ]


def test_iter_recent_empty_root(tmp_path):
    assert list(iter_recent_daily_logs(tmp_path / "nope")) == []
