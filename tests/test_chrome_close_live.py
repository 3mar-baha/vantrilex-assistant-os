"""Live finding 2026-09-05 7:25am: «سكري الكروم» refused — Sara said «chrome
مش موجود بالقائمة المعتمدة». Root cause (TWO holes compounding):

1. The guard matched only the FULL executable path
   (C:\\...\\Application\\chrome.exe) — an exe BASENAME («chrome», «chrome.exe»)
   never matched, so any process-image name arriving from running-apps reports
   or short owner speech falls through to "not whitelisted".
2. resolve_app_alias passed short latin names («chrome») through unchanged.

Contract: the guard matches name OR full path OR exe BASENAME (case-insensitive);
resolve_app_alias maps the colloquial/short latin names to the whitelist entry.
"""

from __future__ import annotations

import json
from pathlib import Path

CHROME_ENTRY = {
    "name": "Google Chrome",
    "executable": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    "auto_approve": True,
}


def _guard(tmp_path: Path, entries=None):
    from bridge.guard import Guard

    wl = tmp_path / "whitelist.json"
    wl.write_text(
        json.dumps(
            {
                "allowed_apps": [CHROME_ENTRY] if entries is None else entries,
                "restricted_actions": [],
            }
        ),
        encoding="utf-8",
    )
    return Guard(str(wl))


def test_guard_basename_real(tmp_path):
    from bridge.guard import Guard

    wl = tmp_path / "whitelist.json"
    wl.write_text(
        json.dumps({"allowed_apps": [CHROME_ENTRY], "restricted_actions": []}),
        encoding="utf-8",
    )
    guard = Guard(str(wl))
    for candidate in ("chrome", "chrome.exe", "Chrome.EXE"):
        verdict = guard.check_app(candidate)
        assert verdict.allowed_without_confirmation is True, candidate
    # the full name and full path keep matching
    assert guard.check_app("Google Chrome").allowed_without_confirmation is True
    verdict = guard.check_app(CHROME_ENTRY["executable"])
    assert verdict.allowed_without_confirmation is True
    # an unrelated exe still fails closed honestly
    assert guard.check_app("definitely-not.exe").reason == "not whitelisted"


def test_alias_maps_short_latin_to_whitelist():
    """«الكروم»/«كروم»/«chrome» all land on the SAME whitelist entry the
    owner whitelisted (Google Chrome) — speech, image names, and brand all
    reach the same verdict."""
    from src.pc_actions import resolve_app_alias

    assert resolve_app_alias("الكروم") == "Google Chrome"
    assert resolve_app_alias("كروم") == "Google Chrome"
    assert resolve_app_alias("chrome") == "Google Chrome"
    assert resolve_app_alias("Chrome.exe") == "Google Chrome"
    # unknown names pass through unchanged (the honest fallback)
    assert resolve_app_alias("ززز غير موجود") == "ززز غير موجود"


async def test_close_by_colloquial_name_roundtrip(tmp_path):
    """The live phrase end-to-end: «سكري الكروم» -> close tool -> coordinator
    -> guard resolves -> the daemon receives the REAL executable's image for
    taskkill (not the refused line)."""
    from bridge.guard import Guard
    from src.pc_actions import PCActionCoordinator

    wl = tmp_path / "whitelist.json"
    wl.write_text(
        json.dumps({"allowed_apps": [CHROME_ENTRY], "restricted_actions": []}),
        encoding="utf-8",
    )
    guard = Guard(str(wl))

    sent: list[tuple] = []

    class _Bridge:
        async def send_cmd(self, cmd, args, *, timeout_s=20.0):
            sent.append((cmd, args))
            return {
                "status": "ok",
                "detail": "✅ سكّرت chrome.exe (نسخة 1)",
                "audit_code": "PC-TEST",
                "killed_processes": 1,
            }

    class _Vault:
        """The ledger seam: in-memory append (the real one files to the vault)."""

        def __init__(self):
            self.lines: list[str] = []

        async def read(self, path):
            return "\n".join(self.lines) + ("\n" if self.lines else "")

        async def upsert(self, path, content, message=""):
            self.lines = content.splitlines()

    class _Notifier:
        def __init__(self):
            self.lines: list[str] = []

        async def notify(self, line):
            self.lines.append(line)

    coordinator = PCActionCoordinator(_Bridge(), vault=_Vault(), notifier=_Notifier(), guard=guard)
    # direct call with the raw spoken name (the net delivers «الكروم»)
    status = await coordinator.request_close("الكروم", origin="owner_chat")
    # the refusal line NEVER fired; the kill command went to the wire
    assert status.value == "executed"
    assert sent and sent[0][0] == "exec.close"
