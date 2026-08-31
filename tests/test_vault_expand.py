"""Sprint-3 §3.2 (M5): dynamic vault taxonomy expansion.

Contract: docs/specs/sprint-3.md §3.2 — AC1-AC10 map 1:1 onto the test names below
(no new test design). VaultClient rides the shared FakeGitHub double
(tests/helpers_vault.py); only the HTTP edge is faked.
"""

from __future__ import annotations

from datetime import datetime

import httpx
import pytest
import yaml
from helpers_vault import FakeGitHub
from loguru import logger

from src.vault import VaultClient, split_frontmatter
from src.vault_expand import PARA_BACKBONE, BackboneImmutableError, VaultExpander

TOKEN = "your-github-test-pat-abcdef0123456789"
DOMAIN = "دراسة"
DIRS = ["محاضرات", "ملخصات/شهر-أول"]
TAGS = ["#جامعة", "#امتحانات"]
ROOT = f"01_Projects/{DOMAIN}"
DIR_PATHS = [ROOT, f"{ROOT}/محاضرات", f"{ROOT}/ملخصات", f"{ROOT}/ملخصات/شهر-أول"]


def _expander(gh: FakeGitHub) -> VaultExpander:
    session = httpx.AsyncClient(transport=gh.transport, base_url="https://api.github.com")
    return VaultExpander(VaultClient("owner/vault-repo", TOKEN, session=session))


async def test_new_domain_creates_dir_and_tags():
    """AC1 — new domain creates its dirs, index notes, and _tags.yaml."""
    gh = FakeGitHub()
    result = await _expander(gh).expand(DOMAIN, dirs=DIRS, tags=TAGS)
    assert set(result.created_dirs) == set(DIR_PATHS)
    assert f"{ROOT}/_tags.yaml" in result.created_files
    assert {f"{d}/_index.md" for d in DIR_PATHS} <= set(result.created_files)
    doc = yaml.safe_load(gh.objects[f"{ROOT}/_tags.yaml"][1])
    assert doc["tags"] == TAGS and doc["domain"] == DOMAIN


async def test_structure_change_is_git_commit():
    """AC2 — the whole expansion lands as exactly ONE vault commit, prefixed."""
    gh = FakeGitHub()
    before = len(gh.commits)
    result = await _expander(gh).expand(DOMAIN, dirs=DIRS, tags=TAGS)
    new = gh.commits[before:]
    assert len(new) == 1
    assert new[0]["message"] == f"sara: expand vault — {DOMAIN}"
    assert result.commit_sha == new[0]["sha"]


async def test_para_backbone_immutable():
    """AC3 — a domain touching a backbone path is refused with zero API calls."""
    assert PARA_BACKBONE == frozenset(
        {
            "01_Projects/",
            "02_Areas/",
            "03_Resources/",
            "04_Archives/",
            "Contacts/",
            "Call_Transcripts/",
            "Studies/",
            "Voice_Memos/",
            "Daily_Logs/",
        }
    )
    gh = FakeGitHub()
    for bad in ("Contacts", "01_Projects", "Daily_Logs"):
        with pytest.raises(BackboneImmutableError):
            await _expander(gh).expand(bad, dirs=["x"], tags=["t"])
    assert gh.requests == []


async def test_expansion_idempotent():
    """AC4 — re-expanding an existing domain: zero writes, empty delta."""
    gh = FakeGitHub()
    exp = _expander(gh)
    await exp.expand(DOMAIN, dirs=DIRS, tags=TAGS)
    puts_before, commits_before = len(gh.puts), len(gh.commits)
    again = await exp.expand(DOMAIN, dirs=DIRS, tags=TAGS)
    assert again.created_dirs == [] and again.created_files == []
    assert again.commit_sha == ""
    assert len(gh.puts) == puts_before and len(gh.commits) == commits_before


async def test_invalid_expansion_refused():
    """AC5 — empty domain / empty dirs+tags / residual separators: pre-flight refusal."""
    gh = FakeGitHub()
    exp = _expander(gh)
    with pytest.raises(ValueError):
        await exp.expand("", dirs=["a"], tags=["t"])
    with pytest.raises(ValueError):
        await exp.expand("   ", dirs=["a"], tags=["t"])
    with pytest.raises(ValueError):
        await exp.expand(DOMAIN, dirs=[], tags=[])
    with pytest.raises(ValueError):
        await exp.expand(DOMAIN, dirs=["a//b"], tags=["t"])
    with pytest.raises(ValueError):
        await exp.expand(DOMAIN, dirs=["/lead"], tags=["t"])
    with pytest.raises(ValueError):
        await exp.expand(DOMAIN, dirs=[".."], tags=["t"])
    assert gh.requests == []


async def test_tag_ontology_yaml_roundtrip():
    """AC6 — _tags.yaml safe_loads back to the same tag list, Arabic intact."""
    gh = FakeGitHub()
    await _expander(gh).expand(DOMAIN, dirs=[], tags=TAGS)
    doc = yaml.safe_load(gh.objects[f"{ROOT}/_tags.yaml"][1])
    assert doc["tags"] == TAGS
    assert doc["domain"] == DOMAIN
    created = doc["created"]
    if isinstance(created, str):  # YAML may parse the ISO stamp back into datetime
        created = datetime.fromisoformat(created)
    assert created.tzinfo is not None and created.utcoffset().total_seconds() == 0


async def test_index_notes_link_domain_root():
    """AC7 — index notes cross-link with zettel wikilinks to the domain root."""
    gh = FakeGitHub()
    await _expander(gh).expand(DOMAIN, dirs=DIRS, tags=TAGS)
    for d in DIR_PATHS:
        meta, body = split_frontmatter(gh.objects[f"{d}/_index.md"][1])
        assert meta["type"] == "vault-index"
        assert f"[[{DOMAIN}]]" in body


async def test_state_derives_from_vault():
    """AC8 — a fresh expander over the same backend derives state from vault alone."""
    gh = FakeGitHub()
    first = await _expander(gh).expand(DOMAIN, dirs=DIRS, tags=TAGS)
    again = await _expander(gh).expand(DOMAIN, dirs=DIRS, tags=TAGS)
    assert again.created_dirs == [] and again.created_files == []
    vault_dirs = {
        p.rsplit("/", 1)[0] for p in gh.objects if p.endswith("/_index.md") and p.startswith(ROOT)
    }
    assert vault_dirs == set(first.created_dirs)
    vault_files = {p for p in gh.objects if p.startswith(ROOT)}
    assert vault_files <= set(first.created_files)


async def test_failure_then_retry_completes():
    """AC9 — mid-expansion backend failure propagates; retry completes the delta."""
    gh = FakeGitHub()
    gh.break_data_api = True
    with pytest.raises(httpx.HTTPStatusError):
        await _expander(gh).expand(DOMAIN, dirs=DIRS, tags=TAGS)
    gh.break_data_api = False
    result = await _expander(gh).expand(DOMAIN, dirs=DIRS, tags=TAGS)
    assert result.created_dirs
    expands = [c for c in gh.commits if c["message"] == f"sara: expand vault — {DOMAIN}"]
    assert len(expands) == 1
    for d in DIR_PATHS:
        assert f"{d}/_index.md" in gh.objects


async def test_expansion_logs_redacted():
    """AC10 — the vault token never reaches logs or exceptions on any path."""
    gh = FakeGitHub()
    records: list = []
    hid = logger.add(records.append, level="TRACE")
    exp = _expander(gh)
    try:
        gh.break_data_api = True
        with pytest.raises(httpx.HTTPStatusError) as failed:
            await exp.expand(DOMAIN, dirs=DIRS, tags=TAGS)
        gh.break_data_api = False
        await exp.expand(DOMAIN, dirs=DIRS, tags=TAGS)
    finally:
        logger.remove(hid)
    assert TOKEN not in str(failed.value)
    assert TOKEN not in "\n".join(str(r) for r in records)
    assert all(TOKEN not in str(r.url) for r in gh.requests)
