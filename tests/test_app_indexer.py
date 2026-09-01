"""v1.0.2: Start Menu app indexer — clean name extraction, category mapping, safe
whitelist merging (existing entries + restricted_actions preserved, System32 binaries
never enter), and the guarded end-to-end merge that the whitelist Guard accepts.

Pure functions run anywhere; the real PowerShell shortcut resolution test is
win32-only (CI runs ubuntu)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import app_indexer


def _lnk(directory: Path, name: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    shortcut = directory / f"{name}.lnk"
    shortcut.write_bytes(b"")  # discovery reads FILENAMES only; resolution is injected
    return shortcut


def _both_roots(tmp_path: Path) -> tuple[Path, Path]:
    system = tmp_path / "ProgramData" / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    user = tmp_path / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    return system, user


def test_categorize_known_apps():
    assert app_indexer.categorize("Visual Studio Code") == "Coding"
    assert app_indexer.categorize("PyCharm Community Edition") == "Coding"
    assert app_indexer.categorize("Blood Strike") == "Gaming"
    assert app_indexer.categorize("Steam") == "Gaming"
    assert app_indexer.categorize("Obsidian") == "Study"
    assert app_indexer.categorize("Anki") == "Study"
    assert app_indexer.categorize("Google Chrome") == "Productivity"
    assert app_indexer.categorize("Some Unknown Tool") == "Productivity"


def test_discovers_shortcut_names_recursively_and_ignores_other_files(tmp_path):
    system, user = _both_roots(tmp_path)
    _lnk(system, "Obsidian")
    _lnk(system / "Games", "Blood Strike")
    _lnk(user, "Visual Studio Code")
    (system / "readme.txt").write_text("not a shortcut", encoding="utf-8")

    names = app_indexer.discover([system, user])
    assert names == ["Blood Strike", "Obsidian", "Visual Studio Code"]


def test_discover_dedupes_same_shortcut_in_both_roots(tmp_path):
    system, user = _both_roots(tmp_path)
    _lnk(system, "Google Chrome")
    _lnk(user, "Google Chrome")

    assert app_indexer.discover([system, user]) == ["Google Chrome"]


@pytest.mark.skipif(sys.platform != "win32", reason="PowerShell + COM are Windows-only")
def test_resolve_targets_reads_real_shortcuts(tmp_path):
    shortcut = tmp_path / "Tiny Target App.lnk"
    target = tmp_path / "TinyTarget.exe"
    target.write_bytes(b"")
    script = (
        "$sh = New-Object -ComObject WScript.Shell; "
        f"$s = $sh.CreateShortcut('{shortcut}'); "
        f"$s.TargetPath = '{target}'; $s.Save()"
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", script], check=True, timeout=30, capture_output=True
    )

    resolved = app_indexer.resolve_targets_sync([shortcut])
    assert resolved[str(shortcut)] == str(target)


def test_system_binaries_are_dropped_from_resolution(tmp_path):
    shortcut = tmp_path / "Evil Shortcut.lnk"
    resolved = {str(shortcut): r"C:\Windows\System32\cmd.exe"}

    targets = app_indexer.filter_system(resolved)

    assert targets == {}
    assert app_indexer.is_system_path(r"C:\Windows\System32\cmd.exe")
    assert not app_indexer.is_system_path(r"C:\Users\omarb\AppData\Local\Obsidian\Obsidian.exe")


def _write_whitelist(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "allowed_apps": [
                    {"name": "calculator", "executable": "calc.exe", "auto_approve": True},
                ],
                "restricted_actions": [{"action": "shutdown", "requires_confirmation": True}],
            }
        ),
        encoding="utf-8",
    )


def _discovered_entries(tmp_path: Path) -> list[dict]:
    system, _ = _both_roots(tmp_path)
    names = app_indexer.discover([system])
    resolved = app_indexer.filter_system(
        {name: f"C:\\Users\\omarb\\Apps\\{name.replace(' ', '')}\\{name.replace(' ', '')}.exe"
         for name in names}
    )
    return app_indexer.build_entries(names, resolved)


def test_merge_preserves_existing_entries_and_restricted_actions(tmp_path):
    system, _ = _both_roots(tmp_path)
    _lnk(system, "Obsidian")
    whitelist = tmp_path / "whitelist.json"
    _write_whitelist(whitelist)

    merged = app_indexer.merge_whitelist(whitelist, _discovered_entries(tmp_path))

    assert {"name": "calculator", "executable": "calc.exe", "auto_approve": True} in merged
    data = json.loads(whitelist.read_text(encoding="utf-8"))
    assert data["restricted_actions"] == [{"action": "shutdown", "requires_confirmation": True}]
    assert any(entry["name"] == "Obsidian" and entry["category"] == "Study" for entry in merged)


def test_merge_is_idempotent_and_casefold_dedupe(tmp_path):
    system, _ = _both_roots(tmp_path)
    _lnk(system, "Obsidian")
    whitelist = tmp_path / "whitelist.json"
    _write_whitelist(whitelist)

    entries = _discovered_entries(tmp_path)
    first = app_indexer.merge_whitelist(whitelist, entries)
    second = app_indexer.merge_whitelist(whitelist, entries)

    assert len(first) == len(second) == 2  # calculator + Obsidian, never duplicated
    assert sum(1 for entry in second if entry["name"].casefold() == "obsidian") == 1


async def test_index_start_menu_end_to_end_guard_accepted(tmp_path, monkeypatch):
    system, _ = _both_roots(tmp_path)
    _lnk(system, "Obsidian")
    _lnk(system / "Games", "Blood Strike")
    whitelist = tmp_path / "whitelist.json"
    _write_whitelist(whitelist)

    async def fake_resolver(paths: list[Path]) -> dict[str, str]:
        return {
            str(p): f"C:\\Users\\omarb\\Apps\\{p.stem.replace(' ', '')}.exe" for p in paths
        }

    report = await app_indexer.index_start_menu(
        whitelist, dirs=[system], resolver=fake_resolver
    )

    assert report["discovered"] == 2
    assert report["added"] == 2
    data = json.loads(whitelist.read_text(encoding="utf-8"))

    from bridge.guard import Guard

    guard = Guard(whitelist)
    verdict = guard.check_app("obsidian")
    assert verdict.allowed_without_confirmation is True
    assert verdict.executable == "C:\\Users\\omarb\\Apps\\Obsidian.exe"
    assert all("system32" not in str(entry["executable"]).lower() for entry in data["allowed_apps"])


async def test_index_start_menu_dry_run_writes_nothing(tmp_path, monkeypatch):
    system, _ = _both_roots(tmp_path)
    _lnk(system, "Obsidian")
    whitelist = tmp_path / "whitelist.json"
    _write_whitelist(whitelist)
    before = whitelist.read_text(encoding="utf-8")

    async def fake_resolver(paths: list[Path]) -> dict[str, str]:
        return {str(p): f"C:\\apps\\{p.stem}.exe" for p in paths}

    report = await app_indexer.index_start_menu(
        whitelist, dirs=[system], resolver=fake_resolver, dry_run=True
    )

    assert report["added"] == 1
    assert whitelist.read_text(encoding="utf-8") == before
