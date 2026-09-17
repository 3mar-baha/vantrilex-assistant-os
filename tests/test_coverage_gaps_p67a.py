"""P6 batch 7a — bridge/app_sessions.py pure-logic matrix: categorize aliases,
tick sessions, boot log, save/load round-trip + stale/corrupt guards, whitelist
maps, background split, foreground probe both branches, real psutil seam.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from bridge.app_sessions import (
    CATEGORIES,
    AppSessionTracker,
    UnknownForeground,
    _is_background,
    _running_processes,
    _whitelist_exe_map,
    categorize,
    running_apps_report,
    today_store_path,
    whitelist_categories,
    windows_foreground_app,
)

_NOW = datetime(2026, 9, 17, 9, 0, tzinfo=UTC)


def _tracker(tmp_path: Path | None = None) -> AppSessionTracker:
    store = None if tmp_path is None else tmp_path / "sessions.json"
    return AppSessionTracker(lambda: 60.0, store_path=store)


def test_categorize_exact_alias_and_unknown():
    assert categorize("Atheer", {"Atheer": "Gaming"}) == "Games"
    assert categorize("VSCode", {"vscode": "Coding"}) == "Programming"
    assert categorize("Chrome", {"chrome": "Productivity"}) == "Productivity"
    assert categorize("Mystery", {"Other": "Gaming"}) == "Unknown"
    assert categorize("Anything", {}) == "Unknown"


def test_tick_sessions_and_category_minutes():
    tracker = _tracker()
    tracker.tick("A", now=_NOW, category="Games")
    tracker.tick("A", now=_NOW, category="Games")
    tracker.tick("B", now=_NOW, category="Nope")
    tracker.tick(None, now=_NOW)
    rep = tracker.report(now=_NOW)
    by_name = {row["name"]: row for row in rep["apps"]}
    assert by_name["A"]["sessions"] == 1 and by_name["A"]["minutes"] == 2
    assert by_name["B"]["sessions"] == 1
    assert rep["categories"]["Games"] == 2
    assert rep["total_minutes"] == 3
    assert rep["screen_hours"] == round(3 / 60, 1)
    # interrupted session: returning to A opens a NEW session
    tracker.tick("A", now=_NOW)
    assert tracker.report(now=_NOW)["apps"][0]["sessions"] == 2


def test_boot_shutdown_log_edges():
    tracker = _tracker()
    tracker.mark_shutdown(now=_NOW)  # no boot yet: honest no-op
    assert tracker.report(now=_NOW)["boot_log"] == []
    tracker.mark_boot(now=_NOW)
    tracker.mark_shutdown(now=_NOW)
    log = tracker.report(now=_NOW)["boot_log"]
    assert log[0]["boot_at"] is not None and log[0]["shutdown_at"] is not None


def test_save_load_round_trip_and_stale_day(tmp_path):
    tracker = _tracker(tmp_path)
    tracker.tick("A", now=_NOW, category="Study")
    tracker.mark_boot(now=_NOW)
    tracker.save(now=_NOW)
    fresh = _tracker(tmp_path)
    fresh.load(now=_NOW)
    rep = fresh.report(now=_NOW)
    assert rep["total_minutes"] == 1
    assert rep["categories"]["Study"] == 1
    assert len(rep["boot_log"]) == 1
    # yesterday's file drops: the new day honestly starts at zero
    other = datetime(2026, 9, 18, 9, 0, tzinfo=UTC)
    fresh2 = _tracker(tmp_path)
    fresh2.load(now=other)
    assert fresh2.report(now=other)["total_minutes"] == 0


def test_save_without_store_and_load_corrupt(tmp_path):
    tracker = _tracker()
    tracker.save(now=_NOW)  # no store: silent no-op
    bad = tmp_path / "sessions.json"
    bad.write_text("{not json", encoding="utf-8")
    tracker2 = AppSessionTracker(lambda: 60.0, store_path=bad)
    tracker2.load(now=_NOW)  # corrupt: start fresh, no crash
    assert tracker2.report(now=_NOW)["total_minutes"] == 0
    missing = AppSessionTracker(lambda: 60.0, store_path=tmp_path / "absent.json")
    missing.load(now=_NOW)
    assert missing.report(now=_NOW)["total_minutes"] == 0


def test_whitelist_categories_edges(tmp_path):
    assert whitelist_categories(tmp_path / "absent.json") == {}
    bad = tmp_path / "bad.json"
    bad.write_text("[broken", encoding="utf-8")
    assert whitelist_categories(bad) == {}
    good = tmp_path / "wl.json"
    good.write_text(
        json.dumps(
            {"allowed_apps": [{"name": "Atheer", "category": "Gaming"}, {"category": "Coding"}]}
        ),
        encoding="utf-8",
    )
    assert whitelist_categories(good) == {"Atheer": "Gaming"}


def test_whitelist_exe_map_edges(tmp_path):
    assert _whitelist_exe_map(None) == {}
    assert _whitelist_exe_map(tmp_path / "absent.json") == {}
    good = tmp_path / "wl.json"
    good.write_text(
        json.dumps(
            {
                "allowed_apps": [
                    {"name": "Atheer Sovereign", "executable": "C:\\X\\chrome.exe"},
                    {"name": "", "executable": "nope.exe"},
                ]
            }
        ),
        encoding="utf-8",
    )
    assert _whitelist_exe_map(good) == {"chrome.exe": "Atheer Sovereign"}


def test_is_background_split():
    assert _is_background("chrome.exe", {"chrome.exe"}) is False  # whitelisted never bg
    assert _is_background("SomeHelper.exe", set()) is True
    assert _is_background("notepad.exe", set()) is False


def test_running_apps_report_sections(monkeypatch, tmp_path):
    procs = [
        ("svchost.exe", None),  # system noise: out
        ("chrome.exe", None),
        ("CHROME.EXE", None),  # dup: single row
        ("SomeHelper.exe", None),  # background section
        ("notepad.exe", None),  # owner section, raw name
    ]
    monkeypatch.setattr("bridge.app_sessions._running_processes", lambda: procs)
    wl = tmp_path / "wl.json"
    wl.write_text(
        json.dumps({"allowed_apps": [{"name": "Atheer Sovereign", "executable": "chrome.exe"}]}),
        encoding="utf-8",
    )
    rep = running_apps_report(wl)
    assert {"name": "Atheer Sovereign", "whitelisted": True} in rep["owner_apps"]
    assert {"name": "notepad.exe", "whitelisted": False} in rep["owner_apps"]
    assert {"name": "SomeHelper.exe", "whitelisted": False} in rep["background"]
    assert all("svchost" not in row["name"] for row in rep["apps"])
    assert len([r for r in rep["owner_apps"] if "Atheer" in r["name"]]) == 1
    # no whitelist: raw images, nothing hidden
    raw = running_apps_report(None)
    assert any(r["name"] == "chrome.exe" for r in raw["owner_apps"])


def test_today_store_path_stamp():
    path = today_store_path("/tmp", now=_NOW)
    assert path.name == "app_sessions_2026-09-17.json"
    assert isinstance(today_store_path("/tmp"), Path)


def test_foreground_probe_live_and_failure(monkeypatch):
    seen = windows_foreground_app()  # real read-only OS call: str title or None
    assert seen is None or isinstance(seen, str)
    import ctypes

    class _Boom:
        def __getattr__(self, _name):
            raise OSError("denied")

    monkeypatch.setattr(ctypes, "windll", _Boom(), raising=False)
    with pytest.raises(UnknownForeground):
        windows_foreground_app()


def test_running_processes_live():
    rows = _running_processes()  # real psutil seam: honest live inventory
    assert isinstance(rows, list) and all(isinstance(name, str) for name, _ in rows)


def test_categories_shape():
    assert set(CATEGORIES) == {"Games", "Programming", "Study", "Productivity", "Unknown"}


def test_save_oserror_is_best_effort(tmp_path, monkeypatch):
    from pathlib import Path as _Path

    tracker = _tracker(tmp_path)
    tracker.tick("A", now=_NOW)

    def _boom(self, *args, **kwargs):
        raise OSError("read-only vault")

    monkeypatch.setattr(_Path, "write_text", _boom)
    tracker.save(now=_NOW)  # logs loudly, never raises


def test_tick_across_midnight_rolls_the_day():
    tracker = _tracker()
    day1 = datetime(2026, 9, 16, 23, 59, tzinfo=UTC)
    day2 = datetime(2026, 9, 17, 0, 1, tzinfo=UTC)
    tracker.tick("A", now=day1, category="Games")
    tracker.tick("B", now=day2, category="Study")
    rep = tracker.report(now=day2)
    assert rep["total_minutes"] == 1  # yesterday's minutes reset at rollover
    assert [row["name"] for row in rep["apps"]] == ["B"]
    assert rep["categories"]["Games"] == 0


def test_foreground_probe_none_branches(monkeypatch):
    import ctypes

    class _User32:
        def __init__(self, hwnd, length):
            self._hwnd = hwnd
            self._length = length

        def GetForegroundWindow(self):
            return self._hwnd

        def GetWindowTextLengthW(self, _hwnd):
            return self._length

        def GetWindowTextW(self, _hwnd, _buf, _n):
            pass  # empty title: locked/idle honest None

    class _Windll:
        def __init__(self, user32):
            self.user32 = user32

    monkeypatch.setattr(ctypes, "windll", _Windll(_User32(0, 0)), raising=False)
    assert windows_foreground_app() is None  # no foreground window
    monkeypatch.setattr(ctypes, "windll", _Windll(_User32(1234, 0)), raising=False)
    assert windows_foreground_app() is None  # window without readable title
    monkeypatch.setattr(ctypes, "windll", _Windll(_User32(1234, 9)), raising=False)
    assert windows_foreground_app() is None  # empty title buffer
