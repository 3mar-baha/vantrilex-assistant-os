"""P6 batch 7c — src/vault.py uncovered edges: para_path bad extension,
iter_recent non-date stems, scaffolding dot-dir skip + OSError skips, digest
absent-seed + write-failure guards, non-owned aclose, read-on-directory,
list_dir matrix, rate-limit once-retry + malformed header, studies migration
early return.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from src.vault import (
    VaultClient,
    ensure_master_digest,
    ensure_resources_scaffolding,
    iter_recent_daily_logs,
    para_path,
)

TOKEN = "your-github-test-pat-abcdef0123456789"


class _Resp:
    def __init__(self, status=200, payload=None, headers=None):
        self.status_code = status
        self._payload = payload
        self.headers = headers or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")


class _Session:
    """Queue-per-path fake: each GET pops the next queued response."""

    def __init__(self):
        self.queues: dict[str, list[_Resp]] = {}
        self.closed = False

    def queue(self, path_suffix, *responses):
        self.queues.setdefault(path_suffix, []).extend(responses)

    async def get(self, url, *, params=None, headers=None):
        for suffix, pending in self.queues.items():
            if url.endswith(suffix) and pending:
                return pending.pop(0)
        return _Resp(status=404, payload={"message": "not found"})

    async def aclose(self):
        self.closed = True


def _client(session):
    return VaultClient("owner/vault-repo", TOKEN, session=session)


def test_para_path_rejects_extension_without_dot():
    with pytest.raises(ValueError):
        para_path("projects", "plan", ext="txt")


def test_iter_recent_skips_non_date_stems(tmp_path):
    logs = tmp_path / "Daily_Logs"
    logs.mkdir()
    (logs / "notes.md").write_text("not a log", encoding="utf-8")
    (logs / "2026-09-14.md").write_text("ledger", encoding="utf-8")
    found = list(iter_recent_daily_logs(tmp_path, today=date(2026, 9, 15)))
    assert [p.name for p in found] == ["2026-09-14.md"]
    assert all("notes" not in p.name for p in found)


def test_scaffolding_skips_dot_dirs(tmp_path):
    src = tmp_path / "src"
    (src / ".hidden").mkdir(parents=True)
    (src / ".hidden" / "x.md").write_text("secret", encoding="utf-8")
    (src / "a.md").write_text("pub", encoding="utf-8")
    assert ensure_resources_scaffolding(tmp_path / "vault", source=src) == ["a.md"]


def test_scaffolding_write_oserror_skips_loudly(tmp_path, monkeypatch):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.md").write_text("pub", encoding="utf-8")

    def _boom(self, data):
        raise OSError("read-only vault")

    monkeypatch.setattr(Path, "write_bytes", _boom)
    assert ensure_resources_scaffolding(tmp_path / "vault", source=src) == []


def test_scaffolding_diverged_reread_oserror_skips(tmp_path, monkeypatch):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.md").write_text("seed", encoding="utf-8")
    root = tmp_path / "vault"
    assert ensure_resources_scaffolding(root, source=src) == ["a.md"]
    (root / "04_Resources" / "a.md").write_text("sara-authored", encoding="utf-8")

    real_read = Path.read_bytes

    def _flaky(self):
        if self.name == "a.md" and "04_Resources" in self.parts:
            raise OSError("locked")
        return real_read(self)

    monkeypatch.setattr(Path, "read_bytes", _flaky)
    assert ensure_resources_scaffolding(root, source=src) == []


def test_digest_absent_seed_is_empty(tmp_path):
    assert ensure_master_digest(tmp_path / "vault", source=tmp_path / "empty-src") == []


def test_digest_write_failure_is_empty_never_raises(tmp_path):
    src = tmp_path / "src"
    seed_dir = src / "Personal_Context"
    seed_dir.mkdir(parents=True)
    (seed_dir / "Omar_Core_Digest.md").write_text("seed", encoding="utf-8")
    blocker = tmp_path / "blocker"
    blocker.write_text("a file, not a dir", encoding="utf-8")
    assert ensure_master_digest(blocker, source=src) == []


async def test_aclose_never_closes_caller_session():
    session = _Session()
    client = _client(session)
    await client.aclose()
    assert session.closed is False


async def test_read_on_directory_raises_type_error():
    session = _Session()
    session.queue("notes/x.md", _Resp(200, [{"name": "x.md"}]))
    with pytest.raises(TypeError):
        await _client(session).read("notes/x.md")


async def test_list_dir_matrix():
    session = _Session()
    session.queue("missing", _Resp(404, {}))
    session.queue(
        "flat",
        _Resp(
            200,
            [
                {"type": "file", "name": "a.md"},
                {"type": "file", "name": "img.png"},
                {"type": "dir", "name": "sub"},
            ],
        ),
    )
    session.queue(
        "deep",
        _Resp(
            200,
            [
                {"type": "file", "name": "top.md"},
                {"type": "dir", "name": "sub"},
                {"type": "dir", "name": ".git"},
            ],
        ),
    )
    session.queue("deep/sub", _Resp(200, [{"type": "file", "name": "nested.md"}]))
    session.queue("deep/.git", _Resp(200, [{"type": "file", "name": "evil.md"}]))
    session.queue("note", _Resp(200, {"content": "eA=="}))
    client = _client(session)
    assert await client.list_dir("missing") == []
    assert await client.list_dir("flat") == ["flat/a.md"]
    assert await client.list_dir("deep", recursive=True) == ["deep/top.md", "deep/sub/nested.md"]
    with pytest.raises(TypeError):
        await client.list_dir("note")


async def test_rate_limit_honored_once_then_surfaces():
    session = _Session()
    session.queue("notes/x.md", _Resp(429, {}, {"Retry-After": "0"}), _Resp(404, {}))
    with pytest.raises(FileNotFoundError):
        await _client(session).read("notes/x.md")


async def test_malformed_retry_after_falls_back_without_crashing_or_sleeping_garbage(
    monkeypatch,
):
    """N5 CHANGED THIS GUARD'S LAW, and the old law was wrong.

    It used to read: «a 429 whose ``Retry-After`` cannot be parsed SURFACES as an
    error». That was true only because the old reader gave up whenever
    ``float(retry_after)`` raised — and giving up on a 429 was one of the three
    defects N5 exists to remove, because a 429 is GitHub's unambiguous «slow down»
    and is now ALWAYS retried once. So the 429 no longer surfaces; the RETRIED
    response does.

    What survives, and is now asserted more tightly than before: a malformed hint
    buys neither a parse crash nor a garbage wait. The read waits the short declared
    fallback, makes exactly two requests, and reports what the second one said.
    """
    from src.vault import RATE_LIMIT_FALLBACK_BACKOFF_S

    waits: list[float] = []

    async def _sleep(seconds):
        waits.append(seconds)

    monkeypatch.setattr("asyncio.sleep", _sleep)
    session = _Session()
    session.queue("notes/x.md", _Resp(429, {}, {"Retry-After": "soon"}), _Resp(404, {}))
    with pytest.raises(FileNotFoundError):
        await _client(session).read("notes/x.md")
    assert len(session.queues["notes/x.md"]) == 0, "both responses were consumed"
    assert waits == [RATE_LIMIT_FALLBACK_BACKOFF_S], (
        f"a malformed hint must wait the declared fallback, never a parsed-from-garbage "
        f"duration; waited {waits}"
    )


async def test_migrate_studies_non_list_returns_quietly():
    session = _Session()
    session.queue("02_Areas/Studies/", _Resp(200, {"content": "not-a-list"}))
    assert await _client(session)._migrate_studies() is None
