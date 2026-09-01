"""Start Menu app indexer (v1.0.2): discovers installed applications from the two
Windows Start Menu shortcut roots and merges them into ``config/whitelist.json`` so
the owner never hand-writes executable paths.

Safety contract (CLAUDE.md rule 4 preserved): only Start-Menu-installed desktop
shortcuts enter the whitelist — anything resolving under the Windows directory
(System32 included) is dropped; existing entries and ``restricted_actions`` are
never touched; merging is idempotent; the whitelist Guard still re-reads the file
on every check and power actions still always require confirmation.

Run: ``python -m src.app_indexer [--dry-run]`` (merge into config/whitelist.json).
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import subprocess
import sys
from pathlib import Path

from loguru import logger

WHITELIST_PATH = Path("config/whitelist.json")
_POWERSHELL_BATCH = 80

RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (
        (
            "visual studio",
            "vscode",
            "pycharm",
            "intellij",
            "clion",
            "rider",
            "android studio",
            "sublime",
            "postman",
            "docker",
            "github",
            "git ",
            "python",
            "node",
            "terminal",
            "code",
        ),
        "Coding",
    ),
    (
        (
            "game",
            "steam",
            "epic games",
            "riot",
            "battle.net",
            "origin",
            "ubisoft",
            "gog ",
            "minecraft",
            "roblox",
            "strike",
            "fortnite",
            "valorant",
            "itch",
        ),
        "Gaming",
    ),
    (
        (
            "obsidian",
            "notion",
            "anki",
            "zotero",
            "mendeley",
            "xmind",
            "calibre",
            "word",
            "excel",
            "powerpoint",
            "onenote",
            "quizlet",
            "pdf",
        ),
        "Study",
    ),
)


def categorize(name: str) -> str:
    folded = f" {name.casefold()} "
    for keywords, category in RULES:
        if any(keyword in folded for keyword in keywords):
            return category
    return "Productivity"


def default_shortcut_dirs() -> list[Path]:
    appdata = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    roots = [
        Path(r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs"),
        appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    ]
    return [root for root in roots if root.is_dir()]


def discover(shortcut_dirs: list[Path]) -> list[str]:
    """Human-readable names from shortcut FILENAMES (the .lnk stem), deduped,
    deterministic order. Only ``*.lnk`` files are read; file contents never parsed."""
    seen: set[str] = set()
    names: list[str] = []
    for root in shortcut_dirs:
        for shortcut in sorted(root.rglob("*.lnk")):
            name = shortcut.stem.strip()
            if name and name.casefold() not in seen:
                seen.add(name.casefold())
                names.append(name)
    return names


def is_system_path(target: str) -> bool:
    parts = Path(target).parts
    return len(parts) >= 2 and Path(target).drive.lower() == "c:" and parts[1].lower() == "windows"


def filter_system(resolved: dict[str, str]) -> dict[str, str]:
    """Drop every resolution that lands inside C:\\Windows (System32 included)."""
    return {
        path: target for path, target in resolved.items() if target and not is_system_path(target)
    }


def build_entries(names: list[str], resolved: dict[str, str]) -> list[dict]:
    """Whitelist entries for shortcuts whose target resolved; one entry per unique
    target (a name whose target matches an already-added app is skipped)."""
    entries: list[dict] = []
    seen_targets: set[str] = set()
    for name in names:
        target = next(
            (t for path, t in resolved.items() if Path(path).stem.casefold() == name.casefold()), ""
        )
        if not target or target.casefold() in seen_targets:
            continue
        seen_targets.add(target.casefold())
        entries.append(
            {"name": name, "executable": target, "auto_approve": True, "category": categorize(name)}
        )
    return entries


def _ps_script(paths: list[str]) -> str:
    literals = ", ".join("'" + path.replace("'", "''") + "'" for path in paths)
    return (
        "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
        "$sh = New-Object -ComObject WScript.Shell; "
        f"$paths = @({literals}); "
        "foreach ($p in $paths) { "
        "try { $t = $sh.CreateShortcut($p).TargetPath } catch { $t = '' }; "
        "if ($null -eq $t) { $t = '' }; "
        "Write-Output $t }"
    )


def resolve_targets_sync(shortcut_paths: list[Path]) -> dict[str, str]:
    """Resolve .lnk targets via Windows PowerShell + WScript.Shell COM — one
    EncodedCommand process per batch (no shell, no quoting hazards); failures
    resolve to '' preserving input order."""
    resolved: dict[str, str] = {}
    for start in range(0, len(shortcut_paths), _POWERSHELL_BATCH):
        batch = [str(path) for path in shortcut_paths[start : start + _POWERSHELL_BATCH]]
        encoded = base64.b64encode(_ps_script(batch).encode("utf-16-le")).decode("ascii")
        result = subprocess_run(["powershell", "-NoProfile", "-EncodedCommand", encoded])
        lines = result.splitlines()
        if len(lines) != len(batch):
            logger.warning(
                "shortcut resolution returned {got} lines for {want} shortcuts",
                got=len(lines),
                want=len(batch),
            )
        for path, target in zip(batch, lines):
            resolved[path] = target.strip()
    return resolved


def subprocess_run(argv: list[str]) -> str:
    return subprocess.run(
        argv, capture_output=True, text=True, encoding="utf-8", timeout=120, check=False
    ).stdout


async def resolve_targets(shortcut_paths: list[Path]) -> dict[str, str]:
    return await asyncio.to_thread(resolve_targets_sync, shortcut_paths)


def merge_whitelist(whitelist_path: Path, apps: list[dict]) -> list[dict]:
    """Merge discovered apps into the whitelist: existing entries and
    ``restricted_actions`` preserved verbatim, casefold dedupe on name+executable,
    idempotent. Returns the full merged allowed_apps list."""
    try:
        data = json.loads(whitelist_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    allowed = list(data.get("allowed_apps", []))
    known = {
        (str(entry.get("name", "")).casefold(), str(entry.get("executable", "")).casefold())
        for entry in allowed
    }
    for app in apps:
        key = (str(app["name"]).casefold(), str(app["executable"]).casefold())
        if key[0] in {k[0] for k in known} or key in known:
            continue
        allowed.append(app)
        known.add(key)
    data["allowed_apps"] = allowed
    data.setdefault("restricted_actions", [])
    whitelist_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return allowed


async def index_start_menu(
    whitelist_path: Path = WHITELIST_PATH,
    dirs: list[Path] | None = None,
    resolver=resolve_targets,
    dry_run: bool = False,
) -> dict:
    shortcut_dirs = dirs if dirs is not None else default_shortcut_dirs()
    names = discover(shortcut_dirs)
    shortcut_paths = [
        shortcut for root in shortcut_dirs for shortcut in sorted(root.rglob("*.lnk"))
    ]
    resolved = filter_system(await resolver(shortcut_paths))
    skipped_system = len(shortcut_paths) - len(resolved)
    apps = build_entries(names, resolved)
    if dry_run:
        return {
            "discovered": len(names),
            "added": len(apps),
            "skipped_system": skipped_system,
            "dry_run": True,
        }
    merged = merge_whitelist(whitelist_path, apps)
    logger.info(
        "app indexer: {discovered} discovered, {added} added, {skipped} system-skipped, "
        "{total} total whitelisted",
        discovered=len(names),
        added=len(apps),
        skipped=skipped_system,
        total=len(merged),
    )
    return {
        "discovered": len(names),
        "added": len(apps),
        "skipped_system": skipped_system,
        "total": len(merged),
    }


def main() -> None:
    dry_run = "--dry-run" in sys.argv
    report = asyncio.run(index_start_menu(dry_run=dry_run))
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
