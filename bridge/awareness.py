"""Ambient attention sampling (Leap 3, Phase-3) — daemon side, Windows only.

Privacy posture (owner directive): record process_name + sanitized coarse
category ONLY. Raw window titles (URLs, chat names, banking identifiers) are
never read into a stored field — the title handle is used solely to resolve
the owning process, then dropped. stdlib ctypes + psutil (already a bridge
dep); every read degrades to None, never raises.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
from typing import Any, Final

try:
    import psutil
except ImportError:  # pragma: no cover -- bridge runtime always ships psutil
    psutil = None  # type: ignore[assignment]

# process.exe (lowercased) -> coarse attention category. Unknown processes
# resolve to "Other" — the map is data, extend without code changes.
CATEGORY_MAP: Final[dict[str, str]] = {
    "code.exe": "IDE / Coding",
    "devenv.exe": "IDE / Coding",
    "pycharm64.exe": "IDE / Coding",
    "idea64.exe": "IDE / Coding",
    "sublime_text.exe": "IDE / Coding",
    "notepad++.exe": "Editor / Notes",
    "notepad.exe": "Editor / Notes",
    "obsidian.exe": "Notes / Vault",
    "chrome.exe": "Browser / General",
    "msedge.exe": "Browser / General",
    "firefox.exe": "Browser / General",
    "telegram.exe": "Chat / Telegram",
    "whatsapp.exe": "Chat / General",
    "discord.exe": "Chat / General",
    "spotify.exe": "Media / Music",
    "vlc.exe": "Media / Video",
    "excel.exe": "Office / Sheets",
    "winword.exe": "Office / Docs",
    "powerpnt.exe": "Office / Slides",
    "game.exe": "Gaming / High Focus",
    "cs2.exe": "Gaming / High Focus",
    "valorant.exe": "Gaming / High Focus",
    "eldenring.exe": "Gaming / High Focus",
}

FALLBACK_CATEGORY: Final[str] = "Other"


def categorize(process_name: str | None) -> str:
    """Sanitized coarse category — the only context label that ever persists."""
    if not process_name:
        return FALLBACK_CATEGORY
    return CATEGORY_MAP.get(process_name.strip().lower(), FALLBACK_CATEGORY)


@dataclass
class AttentionSample:
    fg_process: str | None = None
    category: str = FALLBACK_CATEGORY
    idle_s: float | None = None


class _LastInputInfo(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]


def _default_fg_process() -> str | None:
    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    if psutil is None or not pid.value:
        return None
    try:
        return psutil.Process(pid.value).name()
    except Exception:  # noqa: BLE001 — exited/denied PIDs degrade to None
        return None


def _default_idle_s() -> float | None:
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        info = _LastInputInfo()
        info.cbSize = ctypes.sizeof(_LastInputInfo)
        if not user32.GetLastInputInfo(ctypes.byref(info)):
            return None
        elapsed_ms = kernel32.GetTickCount() - info.dwTime
        return max(0.0, elapsed_ms / 1000.0)
    except Exception:  # noqa: BLE001 — non-Windows / denied API degrades
        return None


def sample_attention(
    fg_impl: Any | None = None,
    idle_impl: Any | None = None,
) -> AttentionSample:
    """One ambient sample. Injectable impls keep hermetic tests off win32."""
    try:
        proc = (fg_impl or _default_fg_process)()
    except Exception:  # noqa: BLE001
        proc = None
    try:
        idle = (idle_impl or _default_idle_s)()
    except Exception:  # noqa: BLE001
        idle = None
    return AttentionSample(fg_process=proc, category=categorize(proc), idle_s=idle)
