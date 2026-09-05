"""Pass-1 app-session telemetry (v2.0 directive §3-د/3): minute-level foreground-app
tracking + category roll-up (Games/Programming/Study/Productivity) + boot/shutdown
session log. The tracker is PURE given a clock and a foreground value — the real
psutil probe lives at the bottom and is injected; the daemon ticks it every 60 s.
State persists as JSON so a daemon restart keeps the day's minutes."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

from loguru import logger
from pydantic import BaseModel

# the directive's four buckets + the honest fifth for uncategorized apps.
# Audit finding (2026-09-05): the real whitelist spells its categories
# Gaming/Coding (owner usage), not the directive's Games/Programming — both
# spellings now map so a Gaming app is never misreported as Productivity.
CATEGORIES = ("Games", "Programming", "Study", "Productivity", "Unknown")
_CATEGORY_ALIASES = {
    "games": "Games",
    "gaming": "Games",
    "programming": "Programming",
    "coding": "Programming",
    "study": "Study",
    "productivity": "Productivity",
}

_TICK_S = 60  # one sample = one foreground minute (the directive's unit)


class UnknownForeground(Exception):
    """The foreground probe could not read a title (locked screen / access denied)."""


class _AppStat(BaseModel):
    name: str
    minutes: int = 0
    sessions: int = 0
    first_seen: str | None = None
    last_seen: str | None = None


def categorize(name: str, whitelist_categories: dict[str, str]) -> str:
    """Map an app to one of the directive's buckets using its whitelist
    category (case-insensitive name match, Gaming/Coding aliases honored);
    anything unrecognized stays honest as Unknown — NEVER misbucketed to
    Productivity."""
    if whitelist_categories:
        for wl_name, category in whitelist_categories.items():
            if wl_name.casefold() == name.casefold():
                return _CATEGORY_ALIASES.get(category.strip().casefold(), "Unknown")
    return "Unknown"


class AppSessionTracker:
    """Accumulates foreground minutes per app. tick(app) is called once per minute
    with the foreground app name (None = locked/idle gap)."""

    def __init__(
        self,
        interval_s: Callable[[], float],
        *,
        probe: Callable[[], str] | None = None,
        store_path: Path | str | None = None,
    ) -> None:
        self._interval_s = interval_s  # wall source (kept for API symmetry)
        self._probe = probe
        self._store_path = Path(store_path) if store_path else None
        self._day: str | None = None
        self._apps: dict[str, _AppStat] = {}
        self._open_app: str | None = None  # app in an open session
        self._cat_minutes: dict[str, int] = {c: 0 for c in CATEGORIES}
        self._boot_log: list[dict[str, str | None]] = []

    # -- ticking -----------------------------------------------------------

    def tick(self, app: str | None, *, now: datetime, category: str | None = None) -> None:
        """One foreground sample = one minute on that app's row (or a gap)."""
        if app is None:
            self._open_app = None  # session interrupted (lock/idle)
            return
        self._rollover_day(now)
        stat = self._apps.get(app)
        if stat is None:
            stat = _AppStat(name=app, first_seen=now.isoformat())
            self._apps[app] = stat
        if self._open_app != app:
            stat.sessions += 1
            self._open_app = app
        stat.minutes += 1
        stat.last_seen = now.isoformat()
        if category in self._cat_minutes:
            self._cat_minutes[category] = self._cat_minutes.get(category, 0) + 1

    # -- boot/shutdown session log (§3-د/4) ---------------------------------

    def mark_boot(self, *, now: datetime) -> None:
        self._rollover_day(now)
        self._boot_log.append({"boot_at": now.isoformat(), "shutdown_at": None})

    def mark_shutdown(self, *, now: datetime) -> None:
        if self._boot_log and self._boot_log[-1]["shutdown_at"] is None:
            self._boot_log[-1]["shutdown_at"] = now.isoformat()

    # -- report / persistence ------------------------------------------------

    def report(self, *, now: datetime) -> dict[str, Any]:
        """Wire-ready dict: per-app minutes + sessions, category totals, grand
        total, boot log — numbers the narration must quote verbatim."""
        total = sum(stat.minutes for stat in self._apps.values())
        return {
            "apps": [s.model_dump() for s in self._apps.values()],
            "categories": dict(self._cat_minutes),
            "total_minutes": total,
            "screen_hours": round(total / 60, 1),
            "boot_log": list(self._boot_log),
        }

    def save(self, *, now: datetime) -> None:
        """Persist today's state as JSON (atomicity via the caller's single writer)."""
        if self._store_path is None:
            return
        payload = {
            "day": self._day or now.strftime("%Y-%m-%d"),
            "apps": self._apps,
            "cat_minutes": self._cat_minutes,
            "boot_log": self._boot_log,
        }
        data = {
            "day": payload["day"],
            "apps": {k: v.model_dump() for k, v in self._apps.items()},
            "cat_minutes": self._cat_minutes,
            "boot_log": self._boot_log,
        }
        try:
            self._store_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        except OSError:
            logger.warning("app-session state save failed (best-effort)")

    def load(self, *, now: datetime) -> None:
        """Restore today's state after a daemon restart; stale days drop."""
        if self._store_path is None or not self._store_path.exists():
            return
        try:
            data = json.loads(self._store_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("app-session state corrupt — starting fresh")
            return
        if data.get("day") != now.strftime("%Y-%m-%d"):
            return  # yesterday's file: a new day starts at zero
        self._day = data["day"]
        self._apps = {k: _AppStat(**v) for k, v in data.get("apps", {}).items()}
        self._cat_minutes = {c: int(data.get("cat_minutes", {}).get(c, 0)) for c in CATEGORIES}
        self._boot_log = list(data.get("boot_log", []))

    def _rollover_day(self, now: datetime) -> None:
        today = now.strftime("%Y-%m-%d")
        if self._day is None:
            self._day = today
        elif self._day != today:
            logger.info("app-session day rollover {old} -> {new}", old=self._day, new=today)
            self._day = today
            self._apps = {}
            self._cat_minutes = {c: 0 for c in CATEGORIES}
            self._boot_log = []


# -- the real foreground probe (daemon only) ---------------------------------


def windows_foreground_app() -> str | None:
    """Best-effort foreground app name via ctypes user32 (no new dependency —
    keeps the $0.00 and wheel-free constraints). Raises UnknownForeground when
    the title cannot be read; None means locked/idle."""
    import ctypes

    try:
        user32 = ctypes.windll.user32  # type: ignore[attr-defined]
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return None
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return None
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value.strip()
        return title or None
    except Exception as exc:
        raise UnknownForeground(str(exc)) from exc


def whitelist_categories(whitelist_path: Path | str) -> dict[str, str]:
    """Read {app name -> category} from the whitelist for bucketing."""
    try:
        data = json.loads(Path(whitelist_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {
        str(entry.get("name", "")): str(entry.get("category", "") or "")
        for entry in data.get("allowed_apps", [])
        if entry.get("name")
    }


# STT-2 (owner 2026-09-04 7:07pm): system/noise process prefixes stay OUT of
# the running-apps report — the owner asks what HE has open, not what Windows
# has open. Real apps never carry these image prefixes.
_SYSTEM_IMAGE_PREFIXES: Final[tuple[str, ...]] = (
    "svchost",
    "csrss",
    "wininit",
    "winlogon",
    "services",
    "lsass",
    "smss",
    "dwm",
    "fontdrvhost",
    "sihost",
    "taskhostw",
    "runtimebroker",
    "applicationframehost",
    "system",
    "system idle",
    "idle",
    "registry",
    "memcompression",
    "searchindexer",
    "audiodg",
    "conhost",
    "dllhost",
    "backgroundtaskhost",
    "spoolsv",
    "wudfhost",
    "wermgr",
    "wmiprvse",
)


def _running_processes() -> list[tuple[str, str | None]]:
    """The REAL running user-facing processes: (image, window title) via
    psutil — the test seam (tests monkeypatch this single function)."""
    import psutil

    out: list[tuple[str, str | None]] = []
    for proc in psutil.process_iter(attrs=["name"]):
        name = proc.info.get("name") or ""
        if name:
            out.append((name, None))
    return out


def _whitelist_exe_map(whitelist_path: Path | str | None) -> dict[str, str]:
    """Gap-ج: exe-basename -> the owner's display name, from the whitelist
    (chrome.exe -> «Atheer Sovereign», calc.exe -> calculator). Empty when the
    whitelist is missing — the raw image is the honest fallback."""
    if whitelist_path is None:
        return {}
    try:
        data = json.loads(Path(whitelist_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    mapping: dict[str, str] = {}
    for entry in data.get("allowed_apps", []):
        exe = str(entry.get("executable") or "").rsplit("\\", 1)[-1].casefold()
        name = str(entry.get("name") or "").strip()
        if exe and name:
            mapping.setdefault(exe, name)
    return mapping


# Gap-ج (owner 2026-09-05): the OWNER-facing section vs the Windows background.
# Owner apps = whitelisted exes + anything that is clearly a user-launched app
# (not in the system-noise table and not a service image). Nothing is FILTERED
# — the background processes stay, in their own labeled section.
_BACKGROUND_HINTS: Final[tuple[str, ...]] = (
    *("service", "broker", "host", "daemon", "agent", "helper", "guard", "shim"),
    "msedgewebview2",
    "runtimebroker",
    "useroobe",
    "vmms",
    "wmiregistrationservice",
    "presentationfontcache",
    "nvdisplay",
    "nvcontainer",
    "msmpeng",
    "mpdefendercore",
    "jhi_service",
    "lsaiso",
    "planetvpnservice",
    "asuscertservice",
    "shellhost",
    "oneapp.igcc",
    "googleplaygamesservices",
    "xboxpcappft",
)


def _is_background(image: str, known_exe_names: set[str]) -> bool:
    """A process is background when it is NOT a whitelisted exe and its image
    carries a service/broker/AV hint. Whitelisted apps are NEVER background."""
    folded = image.casefold()
    base = folded.removesuffix(".exe")
    if folded in known_exe_names:
        return False
    return any(hint in base for hint in _BACKGROUND_HINTS)


def running_apps_report(whitelist_path: Path | str | None = None) -> dict:
    """Gap-ج (owner's WIDER spec 2026-09-05): EVERY app BY NAME —
    - whitelisted exes report by their DISPLAY name (chrome.exe -> «Atheer
      Sovereign»); non-whitelisted apps keep the raw image (nothing filtered)
    - two honest sections: owner_apps first, background (services/AV/helpers)
      in its own labeled list — every process named, nothing hidden
    - deduped by casefolded image; system-noise prefixes still out
    Wire-ready dict (apps kept for legacy readers)."""
    exe_map = _whitelist_exe_map(whitelist_path)
    known = set(exe_map)
    seen: set[str] = set()  # casefolded images already reported
    owner_apps: list[dict] = []
    background: list[dict] = []
    for image, _title in _running_processes():
        folded = image.casefold()
        if any(folded.startswith(prefix) for prefix in _SYSTEM_IMAGE_PREFIXES):
            continue
        if folded in seen:
            continue
        seen.add(folded)
        if folded in exe_map:
            owner_apps.append({"name": exe_map[folded], "whitelisted": True})
        elif _is_background(image, known):
            background.append({"name": image, "whitelisted": False})
        else:
            owner_apps.append({"name": image, "whitelisted": False})
    return {
        "apps": owner_apps + background,  # legacy flat union (nothing lost)
        "owner_apps": owner_apps,
        "background": background,
    }


def today_store_path(base_dir: Path | str, *, now: datetime | None = None) -> Path:
    """One JSON file per local day under the daemon's state dir."""
    stamp = (now or datetime.now(UTC)).strftime("%Y-%m-%d")
    return Path(base_dir) / f"app_sessions_{stamp}.json"
