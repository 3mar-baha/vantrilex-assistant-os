"""Gap-ج (owner 2026-09-05, WIDER spec): «اريد ان يعرض اسم كل تطبيق» — the
running-apps report shows EVERY app BY NAME. The owner explicitly REJECTED
filtering non-whitelisted apps out: every app shows, each by name.

What changes (bridges the probe findings):
1. WHITELIST DISPLAY NAMES: an exe in the whitelist reports by its display
   name (chrome.exe -> «Atheer Sovereign», calc.exe -> calculator) — the raw
   image is the fallback, never the preference.
2. HONEST TWO-SECTION SURFACE: the owner's real apps first, then the
   background/OS processes under their OWN labeled section — every process
   still named, nothing hidden, but «Atheer Sovereign» no longer drowns
   between vmms and jhi_service.
3. The core report carries (name, whitelisted) per app; the tool narrates
   every name.

Contract stays: read-only, deduped, no confirmation gate.
"""

from __future__ import annotations

import json


def _wl_file(tmp_path, entries):

    path = tmp_path / "whitelist.json"
    path.write_text(json.dumps({"allowed_apps": entries}), encoding="utf-8")
    return path


# -- display-name resolution ----------------------------------------------------


def test_report_prefers_whitelist_display_names(tmp_path, monkeypatch):
    """A whitelisted exe reports by its DISPLAY name; a non-whitelisted exe
    keeps its raw image — BOTH show (the owner's wider spec: no filtering)."""
    from bridge.app_sessions import running_apps_report

    wl_path = _wl_file(
        tmp_path,
        [
            {"name": "Atheer Sovereign", "executable": "C:\\x\\chrome.exe"},
            {"name": "calculator", "executable": "calc.exe", "auto_approve": True},
        ],
    )
    monkeypatch.setattr(
        "bridge.app_sessions._running_processes",
        lambda: [("chrome.exe", None), ("Perplexity.exe", None), ("calc.exe", None)],
    )
    monkeypatch.setattr(
        "bridge.app_sessions._whitelist_exe_map",
        lambda path: {"chrome.exe": "Atheer Sovereign", "calc.exe": "calculator"},
    )
    report = running_apps_report(whitelist_path=wl_path)
    apps = {a["name"]: a for a in report["apps"]}
    assert "Atheer Sovereign" in apps  # display name won
    assert "calculator" in apps
    assert "Perplexity.exe" in apps  # non-whitelisted STILL SHOWS by raw name
    # every app carries its whitelist truth
    assert apps["Atheer Sovereign"]["whitelisted"] is True
    assert apps["Perplexity.exe"]["whitelisted"] is False


def test_sections_owner_apps_first_background_labeled(tmp_path, monkeypatch):
    """The honest two-section surface: the owner's REAL apps (whitelisted
    exes) first, the OS/background processes in their own labeled section —
    every process named, nothing filtered."""
    from bridge.app_sessions import running_apps_report

    monkeypatch.setattr(
        "bridge.app_sessions._running_processes",
        lambda: [
            ("vmms.exe", None),  # background service
            ("chrome.exe", None),  # owner app (whitelisted)
            ("SomeGame.exe", None),  # non-whitelisted owner app — STILL SHOWS
            ("MsMpEng.exe", None),  # background
        ],
    )
    monkeypatch.setattr(
        "bridge.app_sessions._whitelist_exe_map", lambda path: {"chrome.exe": "Atheer Sovereign"}
    )
    report = running_apps_report(whitelist_path=_wl_file(tmp_path, []))
    owner_names = [a["name"] for a in report["owner_apps"]]
    background = [a["name"] for a in report["background"]]
    assert "Atheer Sovereign" in owner_names
    assert "SomeGame.exe" in owner_names  # non-whitelisted in the owner section
    assert "vmms.exe" in background and "MsMpEng.exe" in background
    # the union is every process — nothing hidden
    assert len(owner_names) + len(background) == 4


# -- the tool narrates every name --------------------------------------------


async def test_tool_narrates_both_sections():
    """The running_apps tool: owner apps listed by name, the background
    section labeled but complete — the owner sees EVERY app by name."""
    from src.tools import ToolRegistry

    class _Bridge:
        async def send_cmd(self, cmd, args, *, timeout_s=20.0):
            assert cmd == "exec.list_apps"
            return {
                "owner_apps": [{"name": "Atheer Sovereign", "whitelisted": True}],
                "background": [{"name": "vmms.exe", "whitelisted": False}],
                "apps": [{"name": "Atheer Sovereign"}, {"name": "vmms.exe"}],
            }

    out = await ToolRegistry(bridge=_Bridge()).call("running_apps", "")
    assert "Atheer Sovereign" in out
    assert "vmms.exe" in out  # background STILL NAMED
    assert "خلفية" in out or "برامج النظام" in out  # the section is labeled


async def test_tool_accepts_legacy_apps_only_payload():
    """Wire compatibility: an old daemon payload (apps only) still narrates —
    the tool degrades to the flat list, never breaks."""
    from src.tools import ToolRegistry

    class _Bridge:
        async def send_cmd(self, cmd, args, *, timeout_s=20.0):
            return {"apps": [{"name": "Chrome"}]}

    out = await ToolRegistry(bridge=_Bridge()).call("running_apps", "")
    assert "Chrome" in out and "خلفية" not in out


# -- daemon serves the new shape ------------------------------------------------


async def test_daemon_branch_returns_new_report(tmp_path, monkeypatch):
    """exec.list_apps through the daemon's _execute carries both sections."""

    from bridge.daemon import BridgeDaemon
    from bridge.executor import Executor
    from bridge.guard import Guard
    from common.protocol import new_envelope

    wl = tmp_path / "whitelist.json"
    wl.write_text(json.dumps({"allowed_apps": [], "restricted_actions": []}), encoding="utf-8")
    daemon = BridgeDaemon("ws://127.0.0.1:1", "t", Executor(Guard(str(wl))))
    monkeypatch.setattr("bridge.app_sessions._running_processes", lambda: [("SomeGame.exe", None)])
    frame = new_envelope(type="cmd", cmd="exec.list_apps", args={})
    status, payload = await daemon._execute(frame)
    assert status == "ok"
    assert payload["owner_apps"] == [{"name": "SomeGame.exe", "whitelisted": False}]
    assert payload["background"] == []
