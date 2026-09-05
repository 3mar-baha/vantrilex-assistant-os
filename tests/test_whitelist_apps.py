"""Live-6 (owner 2026-09-05 7:25am): «شو في تطبيقات عندك في القائمة» -> «ما
عندي قائمة تطبيقات معتمدة هسا» — the whitelist HOLDS 136 entries Sara reads
on every launch/close; the owner's direct question had NO tool to answer it.

Contract — the `whitelist_apps` tool:
- Reads the REAL whitelist (config/whitelist.json), narrates the app names
  (count + list, capped, honest overflow counter)
- Mirrors the list into the vault at 02_Areas/PC/Apps_Whitelist.md (ADR-21
  home for PC state) — the owner asked Sara to keep her authorized apps in
  Obsidian memory
- Net routing: «شو في تطبيقات بالقائمة/شو البرامج المسموحة/وين القائمة»
  reach it — and never steal running_apps' live-list question
"""

from __future__ import annotations

import json


def _wl(tmp_path, entries):
    path = tmp_path / "whitelist.json"
    path.write_text(json.dumps({"allowed_apps": entries}), encoding="utf-8")
    return path


async def test_whitelist_apps_tool_narrates_real_list(tmp_path):
    """The count + the names, capped, honest overflow — the direct answer to
    «شو في تطبيقات عندك في القائمة»."""
    from src.tools import ToolRegistry

    entries = [
        {"name": f"app{i}", "executable": f"x{i}.exe", "auto_approve": True} for i in range(30)
    ]
    entries.insert(0, {"name": "Google Chrome", "executable": "chrome.exe", "auto_approve": True})
    registry = ToolRegistry()
    registry.bind_whitelist_path(_wl(tmp_path, entries))
    out = await registry.call("whitelist_apps", "")
    assert "31" in out  # the real count
    assert "Google Chrome" in out
    assert "و" in out and "غير" in out  # the honest overflow counter


async def test_whitelist_apps_mirrors_to_vault(tmp_path):
    """The list lands in 02_Areas/PC/Apps_Whitelist.md — Sara's authorized
    apps live in Obsidian memory (the owner's explicit morning request)."""
    from src.tools import ToolRegistry

    mirrored: dict = {}

    class _Vault:
        async def upsert(self, path, content, *, message="", merge=None):
            mirrored["path"] = path
            mirrored["content"] = content

    entries = [{"name": "Google Chrome", "executable": "chrome.exe", "auto_approve": True}]
    registry = ToolRegistry(vault=_Vault())
    registry.bind_whitelist_path(_wl(tmp_path, entries))
    await registry.call("whitelist_apps", "")
    assert mirrored["path"] == "02_Areas/PC/Apps_Whitelist.md"
    assert "Google Chrome" in mirrored["content"]
    assert "chrome.exe" in mirrored["content"]


async def test_whitelist_apps_missing_file_honest():
    """A missing/corrupt whitelist -> the honest line (never a crash, never a
    fabricated list)."""
    from pathlib import Path

    from src.tools import ToolRegistry

    registry = ToolRegistry()
    registry.bind_whitelist_path(Path("Z:/nonexistent/whitelist.json"))
    out = await registry.call("whitelist_apps", "")
    assert "ما" in out  # honest


def test_net_routes_whitelist_question():
    """«شو في تطبيقات بالقائمة/شو البرامج المسموحة» -> whitelist_apps — and
    the LIVE running question keeps running_apps («شو التطبيقات المفتوحة»)."""
    from src.dispatcher import _VALID_TOOLS, _keyword_net

    assert "whitelist_apps" in _VALID_TOOLS
    for phrase in (
        "شو في تطبيقات عندك في القائمة",
        "شو البرامج المسموحة",
        "وين قائمة التطبيقات",
        "شو البرامج اللي عندك صلاحية عليها",
    ):
        assert _keyword_net(phrase)[0] == "whitelist_apps", phrase
    # the live list stays separate
    assert _keyword_net("شو التطبيقات المفتوحة")[0] == "running_apps"
    assert _keyword_net("افحصي التطبيقات التي كانت تعمل")[0] == "running_apps"
