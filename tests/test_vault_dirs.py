"""Sprint-3 §3.1 AC7/AC8/AC10/AC11: first-boot mandatory-tree guard (M6).

Empty repo -> all mandatory dirs + contacts taxonomy + profile files exist after
one bootstrap call; re-run makes ZERO writes; legacy 02_Areas/Studies/ migrates
to top-level Studies/ as ONE structural commit. This file must stay importable
without credentials (pure constants + mocked transport) — it runs in make gate.
"""

from pathlib import Path

import httpx
import pytest

from helpers_vault import FakeGitHub
from src.vault import CONTACTS_SUBDIRS, MANDATORY_DIRS, MANDATORY_FILES, VaultClient, split_frontmatter


def _client(gh: FakeGitHub) -> VaultClient:
    session = httpx.AsyncClient(transport=gh.transport, base_url="https://api.github.com")
    return VaultClient("owner/vault-repo", "your-github-test-pat-abcdef0123456789", session=session)


async def test_first_boot_creates_mandatory_tree_idempotent():
    """AC7: empty repo -> every mandatory dir gets an index note + both profile
    files (frontmatter + purpose line); second run makes zero writes."""
    gh = FakeGitHub()
    client = _client(gh)

    results = await client.ensure_mandatory_dirs()
    written = {r.path for r in results}
    expected = {f"{d}_index.md" for d in (*MANDATORY_DIRS, *CONTACTS_SUBDIRS)} | set(MANDATORY_FILES)
    assert written == expected
    for path in written:
        meta, body = split_frontmatter(gh.objects[path][1])
        assert meta, f"{path} lacks frontmatter"
        assert body.strip(), f"{path} lacks a purpose line"

    puts_after_first = len(gh.puts)
    assert await client.ensure_mandatory_dirs() == []
    assert len(gh.puts) == puts_after_first  # idempotent: zero writes on re-run


async def test_studies_dir_migrated_to_top_level():
    """AC8: legacy 02_Areas/Studies/ with notes -> ONE migration commit moving
    them to top-level Studies/; absent legacy -> no migration commit."""
    gh = FakeGitHub()
    gh.seed("02_Areas/Studies/Calc.md", "---\ntitle: حساب\n---\nمقدمة في الحساب\n")
    gh.seed("02_Areas/Studies/Physics.md", "physics body\n")
    await _client(gh).ensure_mandatory_dirs()

    migrations = [c for c in gh.commits if c["message"] == "sara: migrate Studies to top-level"]
    assert len(migrations) == 1
    assert "Studies/Calc.md" in gh.objects and "الحساب" in gh.objects["Studies/Calc.md"][1]
    assert "Studies/Physics.md" in gh.objects
    assert "02_Areas/Studies/Calc.md" not in gh.objects
    assert "02_Areas/Studies/Physics.md" not in gh.objects

    gh2 = FakeGitHub()  # absent legacy -> no migration commit
    await _client(gh2).ensure_mandatory_dirs()
    assert not [c for c in gh2.commits if c["message"].startswith("sara: migrate")]


async def test_contacts_taxonomy_created():
    """AC11 (2026-08-29 addendum): first boot also creates all five Contacts/
    subdirs — the social-graph taxonomy — idempotently."""
    gh = FakeGitHub()
    results = await _client(gh).ensure_mandatory_dirs()
    written = {r.path for r in results}
    for sub in CONTACTS_SUBDIRS:
        assert f"{sub}_index.md" in written
        assert f"{sub}_index.md" in gh.objects


def test_vault_dirs_in_default_gate():
    """AC10: the guard runs inside make gate — testpaths covers tests/ and this
    file lives there, so a missing-dir regression fails CI before any writer."""
    pyproject = (Path(__file__).parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    assert 'testpaths = ["tests"]' in pyproject
    assert (Path(__file__).parent / "test_vault_dirs.py").exists()
