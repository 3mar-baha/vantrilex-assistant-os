"""Sprint-4 §4.4c: release v1.0.0 — version/CHANGELOG consistency, the complete
v1.0 scope lock (zero live-call code, no memory-layer deps), and a release script
that refuses ungross states and never writes git history without --tag."""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest
from loguru import logger

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import make_release  # noqa: E402


def _captured_errors(caplog_sink: list) -> str:
    return "\n".join(str(record.record["message"]) for record in caplog_sink)


def test_version_matches_changelog():
    """AC1 — src.__version__ is the newest CHANGELOG heading carrying an ISO date."""
    version = make_release.current_version()
    release = make_release.changelog_release(version)
    assert release is not None, f"CHANGELOG has no '## [{version}] — <date>' heading"
    date, _section = release
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", date), f"release date must be ISO: {date}"


def test_no_live_call_stack_in_artifacts_and_source():
    """AC2 — scope lock, complete exclusion set: pytgcalls/telethon/pyrogram absent
    from the deploy artifacts AND every runtime import; mem0/firestore likewise
    (the settled v1.0 exclusion set, locked)."""
    forbidden = re.compile(r"pytgcalls|telethon|pyrogram|mem0|firestore", re.IGNORECASE)
    for name in ("Dockerfile", "requirements.txt"):
        assert not forbidden.search((REPO / name).read_text(encoding="utf-8")), (
            f"excluded stack leaked into {name}"
        )
    for tree in ("src", "bridge", "common"):
        for path in (REPO / tree).rglob("*.py"):
            module = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(module):
                if isinstance(node, ast.Import):
                    imported = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    imported = [node.module or ""]
                else:
                    continue
                for name in imported:
                    assert not forbidden.search(name), f"{path}: import {name}"


def test_v100_documents_scope_deferrals():
    """AC3 — the [1.0.0] CHANGELOG section carries a Deferred-to-v1.1 block naming
    the PyTgCalls engine and the Mem0/Firestore memory evaluation."""
    _date, section = make_release.changelog_release(make_release.current_version())
    assert re.search(r"#+\s*Deferred", section), "no deferral section in the [1.0.0] notes"
    assert re.search(r"pytgcalls", section, re.IGNORECASE)
    assert re.search(r"mem0|firestore", section, re.IGNORECASE)


def test_release_script_refuses_version_mismatch(monkeypatch):
    """AC4 — src.__version__ disagreeing with the newest CHANGELOG heading exits 1
    naming BOTH values."""
    records: list = []
    handler_id = logger.add(records.append, level="ERROR")
    monkeypatch.setattr(make_release, "current_version", lambda: "9.9.9")
    try:
        with pytest.raises(SystemExit) as excinfo:
            make_release.verify_consistency()
    finally:
        logger.remove(handler_id)
    assert excinfo.value.code == 1
    blob = _captured_errors(records)
    assert "9.9.9" in blob and make_release.newest_changelog_version() in blob


def test_release_script_refuses_dirty_tree(monkeypatch):
    """AC5 — a non-empty `git status --porcelain` refuses the release, echoing it."""
    fake = mock.Mock(returncode=0, stdout=" M src/some_module.py\n?? scratch.txt\n", stderr="")
    monkeypatch.setattr(make_release.subprocess, "run", lambda *args, **kwargs: fake)
    with pytest.raises(SystemExit) as excinfo:
        make_release.verify_clean_tree()
    assert excinfo.value.code == 1


def test_release_script_refuses_red_gate(monkeypatch):
    """AC6 — a red quality gate refuses the release (subprocess returncode 1)."""
    fake = mock.Mock(returncode=1, stdout="lint failed", stderr="ruff: 2 errors")
    monkeypatch.setattr(make_release.subprocess, "run", lambda *args, **kwargs: fake)
    with pytest.raises(SystemExit) as excinfo:
        make_release.verify_gate()
    assert excinfo.value.code == 1


def test_tag_only_with_explicit_flag(monkeypatch, capsys):
    """AC7 — no git writes on a dry run; --tag issues EXACTLY one annotated tag
    command; an existing-tag failure surfaces unswallowed; --force does not exist."""
    calls: list[list[str]] = []

    def fake_run(cmd, **_kwargs):
        calls.append(list(cmd))
        return mock.Mock(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(make_release.subprocess, "run", fake_run)
    monkeypatch.setattr(make_release, "verify_consistency", lambda: None)
    monkeypatch.setattr(make_release, "verify_clean_tree", lambda: None)
    monkeypatch.setattr(make_release, "verify_gate", lambda: None)

    version = make_release.current_version()
    assert make_release.main([]) == 0
    assert not any("tag" in call for call in calls), "dry run wrote to git"
    assert f"gh release create v{version}" in capsys.readouterr().out

    assert make_release.main(["--tag"]) == 0
    tag_calls = [call for call in calls if "tag" in call]
    assert len(tag_calls) == 1
    assert tag_calls[0][:4] == ["git", "tag", "-a", f"v{version}"]

    calls.clear()
    failing = mock.Mock(returncode=1, stdout="", stderr="fatal: tag 'v1.0.0' already exists")

    def failing_run(cmd, **_kwargs):
        calls.append(list(cmd))
        return failing

    monkeypatch.setattr(make_release.subprocess, "run", failing_run)
    records: list = []
    handler_id = logger.add(records.append, level="ERROR")
    try:
        assert make_release.main(["--tag"]) == 1
    finally:
        logger.remove(handler_id)
    assert "already exists" in _captured_errors(records), "tag error was swallowed"

    with pytest.raises(SystemExit):  # argparse rejects unknown flags — no --force by design
        make_release.main(["--force"])
