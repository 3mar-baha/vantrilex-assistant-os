"""Sprint-3 §3.1 AC1-AC6 + AC9: vault primitives + GitHub Contents API client.

Contract: docs/specs/sprint-3.md — para path routing/sanitization, frontmatter
writer/splitter, zettel wikilinks, create/update roundtrip with sha semantics,
token redaction, oversize pre-flight refusal, error modes (nothing swallowed).
"""

import importlib.util
import traceback
from datetime import date
from pathlib import Path

import httpx
import pytest
from helpers_vault import FakeGitHub
from loguru import logger

from src.vault import (
    Note,
    VaultClient,
    VaultConflictError,
    daily_log_path,
    para_path,
    redact_secret,
    split_frontmatter,
    write_frontmatter,
    zettel_link,
)

TOKEN = "your-github-test-pat-abcdef0123456789"


def _client(gh: FakeGitHub, token: str = TOKEN) -> VaultClient:
    session = httpx.AsyncClient(transport=gh.transport, base_url="https://api.github.com")
    return VaultClient("owner/vault-repo", token, session=session)


async def test_note_create_update_roundtrip():
    """AC1: create-then-update on the mocked backend — sha semantics, created flag,
    one 409 retried via GET->PUT, persistent 409 raises VaultConflictError."""
    gh = FakeGitHub()
    client = _client(gh)

    first = await client.upsert("04_Archives/Audit/x.md", "مرحبا", message="create")
    assert first.created is True and first.commit_sha
    assert gh.objects["04_Archives/Audit/x.md"][1] == "مرحبا"

    second = await client.upsert("04_Archives/Audit/x.md", "تحديث", message="update")
    assert second.created is False
    assert gh.objects["04_Archives/Audit/x.md"][1] == "تحديث"
    assert await client.read("04_Archives/Audit/x.md") == "تحديث"

    note = Note(
        path="Contacts/Colleagues/أحمد.md",
        frontmatter={"name": "أحمد", "category": "Colleagues"},
        body="# أحمد\n",
    )
    await client.upsert_note(note, message="dossier")
    stored = gh.objects[note.path][1]
    assert stored.startswith("---\n") and "category: Colleagues" in stored and "أحمد" in stored

    gh.put_conflicts[note.path] = 1  # one conflict -> GET->PUT retry succeeds
    retried = await client.upsert(note.path, "b after conflict", message="retry")
    assert retried.created is False and gh.objects[note.path][1] == "b after conflict"

    gh.put_conflicts[note.path] = 99  # conflict every time -> loud error
    with pytest.raises(VaultConflictError):
        await client.upsert(note.path, "x", message="conflict")


async def test_concurrent_appends_lose_no_sections():
    """Pass-1 (audit C-9): two append_section calls racing on the SAME note
    both land — the client lock serializes the read-modify-write, and a 409
    re-merge re-appends onto the LATEST remote (never a stale re-PUT that
    would drop the other writer's lines)."""
    import asyncio

    gh = FakeGitHub()
    client = _client(gh)
    await client.append_section(
        "Daily_Logs/2026-09-04.md", "دردشة 10:00", ["**المالك:** أول"], commit_prefix="sara"
    )
    await asyncio.gather(
        client.append_section(
            "Daily_Logs/2026-09-04.md", "دردشة 11:00", ["**المالك:** ثاني"], commit_prefix="sara"
        ),
        client.append_section(
            "Daily_Logs/2026-09-04.md", "دردشة 12:00", ["**المالك:** ثالث"], commit_prefix="sara"
        ),
    )
    body = gh.objects["Daily_Logs/2026-09-04.md"][1]
    assert "أول" in body and "ثاني" in body and "ثالث" in body  # NOTHING lost


async def test_conflict_remerge_keeps_racing_writer():
    """Pass-1: on a forced 409 the re-merge re-appends onto the LATEST remote
    content — a racing writer's section survives, ours re-lands on top."""
    gh = FakeGitHub()
    client = _client(gh)
    await client.append_section("Daily_Logs/2026-09-04.md", "أساس", ["أ"], commit_prefix="sara")
    # one conflict: the first PUT after the read bumps into a foreign commit;
    # the re-merge must read THAT content (with the foreign section) first.
    gh.put_conflicts["Daily_Logs/2026-09-04.md"] = 1
    await client.append_section(
        "Daily_Logs/2026-09-04.md", "دردشة 13:00", ["**المالك:** بعد تعارض"], commit_prefix="sara"
    )
    body = gh.objects["Daily_Logs/2026-09-04.md"][1]
    assert "أساس" in body and "بعد تعارض" in body


def test_frontmatter_writer_and_splitter():
    """AC2: roundtrip is byte-identical on the body, Arabic intact, insertion
    order kept; only leading fences count as frontmatter; malformed YAML raises."""
    meta = {"name": "سارة", "category": "Colleagues", "tags": ["عائلة", "work"], "tracking": False}
    body = "سطر أول\nسطر ثانٍ\n"
    text = write_frontmatter(meta, body)
    assert text.startswith("---\n")
    parsed, back_body = split_frontmatter(text)
    assert back_body == body
    assert parsed == meta
    assert list(parsed) == list(meta)

    body_only = "بلا مقدمة\n---\nليست مقدمة\n"
    assert split_frontmatter(body_only) == ({}, body_only)

    with pytest.raises(ValueError):
        split_frontmatter("---\n{invalid yaml\n---\nbody")


def test_zettelkasten_link_builder():
    """AC3: embed/alias/block render Obsidian wikilink syntax."""
    assert zettel_link("Obsidian") == "[[Obsidian]]"
    assert zettel_link("Obsidian", alias="التطبيق", block="abc", embed=True) == (
        "![[Obsidian|التطبيق#^abc]]"
    )
    assert zettel_link("Obsidian", embed=True) == "![[Obsidian]]"
    assert zettel_link("Obsidian", alias="بديل") == "[[Obsidian|بديل]]"


@pytest.mark.parametrize(
    ("category", "title", "expected"),
    [
        ("projects", "ملاحظة: اجتماع/الأسبوع؟", "01_Projects/ملاحظة اجتماع الأسبوع.md"),
        ("areas", "Q3: backlog", "02_Areas/Q3 backlog.md"),
        ("resources", "Papers/2026", "03_Resources/Papers 2026.md"),
        ("archives", "Conversations", "04_Archives/Conversations.md"),
        ("contacts", "أحمد", "Contacts/أحمد.md"),
        ("memos", "voice note", "Voice_Memos/voice note.md"),
    ],
)
def test_para_path_routing_and_sanitization(category, title, expected):
    """AC4: category routing + deterministic sanitizer (separators to spaces,
    forbidden chars stripped, Arabic preserved verbatim)."""
    assert para_path(category, title) == expected


def test_para_path_custom_extension():
    assert para_path("projects", "plan", ext=".txt") == "01_Projects/plan.txt"


@pytest.mark.parametrize("bad_title", ["..", ".", "", "   ", ":", "؟؟؟", "???"])
def test_para_path_refuses_traversal_and_empty(bad_title):
    with pytest.raises(ValueError):
        para_path("projects", bad_title)


def test_para_path_unknown_category_refused():
    with pytest.raises(ValueError):
        para_path("junk", "note")


async def test_no_token_in_logs_or_errors():
    """AC5: token never appears in exception text, log records, or outgoing URLs."""
    gh = FakeGitHub()
    gh.fail_get_status["Contacts/_index.md"] = 401  # auth error -> loud, no retry
    client = _client(gh, token=TOKEN)

    records: list[str] = []
    handler_id = logger.add(records.append, level="TRACE")
    try:
        with pytest.raises(httpx.HTTPStatusError) as error:
            await client.read("Contacts/_index.md")
    finally:
        logger.remove(handler_id)

    assert len(gh.requests) == 1  # propagated immediately, zero retries
    assert TOKEN not in str(error.value)
    assert TOKEN not in "".join(traceback.format_exception(error.value))
    assert TOKEN not in "\n".join(records)
    assert all(TOKEN not in str(r.url) for r in gh.requests)
    assert gh.requests[0].headers["Authorization"] == f"Bearer {TOKEN}"

    redacted = redact_secret(f"leak {TOKEN} end")
    assert TOKEN not in redacted and "leak" in redacted


async def test_read_missing_file_raises_file_not_found():
    gh = FakeGitHub()
    with pytest.raises(FileNotFoundError):
        await _client(gh).read("Daily_Logs/2020-01-01.md")


async def test_read_malformed_frontmatter_names_path():
    gh = FakeGitHub()
    gh.seed("Studies/x.md", "---\n{bad yaml\n---\nbody")
    with pytest.raises(ValueError, match="Studies/x.md"):
        await _client(gh).read("Studies/x.md")


async def test_oversize_payload_refused():
    """AC6: >1,000,000 bytes refused pre-flight — zero API calls."""
    gh = FakeGitHub()
    with pytest.raises(ValueError):
        await _client(gh).upsert("Daily_Logs/2026-08-31.md", "x" * 1_000_001, message="big")
    assert gh.requests == []


def test_daily_log_path_dated_and_guard_importable():
    """AC9: dated daily-log path; the guard test module imports without credentials."""
    assert daily_log_path(date(2026, 8, 31)) == "Daily_Logs/2026-08-31.md"
    spec = importlib.util.spec_from_file_location(
        "vault_dirs_guard", Path(__file__).parent / "test_vault_dirs.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert "Contacts/" in module.MANDATORY_DIRS
