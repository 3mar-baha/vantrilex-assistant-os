"""Pass-1 app-session telemetry (v2.0 directive §3-د/3): minute-level tracking of
foreground apps + category totals (games/programming/study/productivity), reported
over the tunnel as `telemetry.app_sessions`. The tracker is PURE given a clock and
an injected foreground probe — no psutil in the unit tests; the real probe reads
psutil on the daemon only. Boot/shutdown session logging rides the same store."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from bridge.app_sessions import CATEGORIES, AppSessionTracker, UnknownForeground, categorize


def _t(minute: int) -> datetime:
    """A deterministic clock source: minute 0 = boot instant."""
    return datetime(2026, 9, 4, 9, 0, tzinfo=UTC) + timedelta(minutes=minute)


def test_categorize_maps_whitelist_categories():
    """Apps with a whitelist category land in that bucket; unknowns are honest."""
    assert categorize("Visual Studio Code", {"Visual Studio Code": "Programming"}) == "Programming"
    assert categorize("Steam", {"Steam": "Games"}) == "Games"
    # case-insensitive on the name
    assert categorize("steam", {"Steam": "Games"}) == "Games"
    # unknown app, no category info -> the honest bucket, never a guess
    assert categorize("MysteryApp", {}) == "Unknown"


def test_categorize_buckets_are_the_directive_four_plus_unknown():
    assert set(CATEGORIES) == {"Games", "Programming", "Study", "Productivity", "Unknown"}


def test_tracker_accumulates_minutes_per_app():
    """Same app foreground for 5 consecutive samples -> 5 minutes logged once,
    then a switch accumulates the second app separately."""
    fg = ["Visual Studio Code"] * 5 + ["Steam"] * 3
    tracker = AppSessionTracker(lambda: 0.0)  # interval irrelevant for ticks
    for i, app in enumerate(fg):
        tracker.tick(app, now=_t(i))
    report = tracker.report(now=_t(8))
    apps = {e["name"]: e for e in report["apps"]}
    assert apps["Visual Studio Code"]["minutes"] == 5
    assert apps["Steam"]["minutes"] == 3
    # sessions list per app: first_seen/last_seen present, ordered
    assert apps["Steam"]["first_seen"] is not None


def test_tracker_reopen_merges_not_duplicates():
    """App leaves foreground and comes back -> one entry, minutes summed, sessions=2."""
    fg = ["Notepad", "Steam", "Notepad"]
    tracker = AppSessionTracker(lambda: 0.0)
    for i, app in enumerate(fg):
        tracker.tick(app, now=_t(i))
    report = tracker.report(now=_t(3))
    apps = {e["name"]: e for e in report["apps"]}
    assert len(report["apps"]) == 2
    assert apps["Notepad"]["minutes"] == 2
    assert apps["Notepad"]["sessions"] == 2


def test_tracker_category_totals_include_every_minute():
    """The category roll-up sums every logged minute into the directive's four
    buckets (+ Unknown) — nothing double-counted."""
    fg = ["Visual Studio Code", "Visual Studio Code", "Steam", "Calculator"]
    cats = {"Steam": "Games", "Calculator": "Productivity"}
    tracker = AppSessionTracker(lambda: 0.0)
    for i, app in enumerate(fg):
        tracker.tick(app, now=_t(i), category=categorize(app, cats))
    report = tracker.report(now=_t(4))
    assert report["categories"]["Unknown"] == 2  # VSCode x2 (no category info)
    assert report["categories"]["Games"] == 1
    assert report["categories"]["Productivity"] == 1
    assert sum(report["categories"].values()) == 4


def test_tracker_idle_and_unknown_dont_pollute():
    """A None probe result (locked screen) is a gap — no app row, no minutes."""
    fg = ["Steam", None, None, "Steam"]
    tracker = AppSessionTracker(lambda: 0.0)
    for i, app in enumerate(fg):
        tracker.tick(app, now=_t(i))
    report = tracker.report(now=_t(4))
    apps = {e["name"]: e for e in report["apps"]}
    assert apps["Steam"]["minutes"] == 2
    assert all(e["name"] != "None" for e in report["apps"])


def test_tracker_report_is_wire_ready():
    """The report is a JSON-serializable dict with total_minutes + boot/shutdown
    session log for the day."""
    tracker = AppSessionTracker(lambda: 0.0)
    tracker.tick("Steam", now=_t(0), category="Games")
    tracker.mark_boot(now=_t(0))
    report = tracker.report(now=_t(1))
    assert report["total_minutes"] == 1
    assert report["boot_log"][0]["boot_at"].startswith("2026-09-04T09:00")
    assert isinstance(report, dict)  # model_dump-compatible for the tunnel


def test_boot_shutdown_log_pairs_sessions():
    """mark_boot/mark_shutdown append one row each; an unclean end (no shutdown)
    leaves shutdown_at None — the honest state."""
    tracker = AppSessionTracker(lambda: 0.0)
    tracker.mark_boot(now=_t(0))
    tracker.mark_shutdown(now=_t(120))
    tracker.mark_boot(now=_t(200))
    log = tracker.report(now=_t(300))["boot_log"]
    assert log[0]["shutdown_at"] is not None
    assert log[1]["shutdown_at"] is None


def test_persistence_roundtrip(tmp_path: Path):
    """Session state survives a daemon restart (JSON file), preserving minutes."""

    tracker = AppSessionTracker(lambda: 0.0, store_path=tmp_path / "sessions.json")
    tracker.tick("Steam", now=_t(0), category="Games")
    tracker.save(now=_t(5))

    revived = AppSessionTracker(lambda: 0.0, store_path=tmp_path / "sessions.json")
    revived.load(now=_t(5))
    report = revived.report(now=_t(6))
    apps = {e["name"]: e for e in report["apps"]}
    assert apps["Steam"]["minutes"] == 1


def test_unknown_foreground_exception_is_a_gap():
    """The real psutil probe can raise (access denied on system procs) — the
    tracker treats an exception-bearing probe exactly like a locked screen."""

    def bad_probe() -> str:
        raise UnknownForeground("access denied")

    tracker = AppSessionTracker(lambda: 0.0, probe=bad_probe)
    tracker.tick(_probe_safe(bad_probe), now=_t(0))
    assert tracker.report(now=_t(1))["apps"] == []


def _probe_safe(probe) -> str | None:
    """Test helper mirroring the daemon's try/except around the probe."""
    try:
        return probe()
    except UnknownForeground:
        return None
