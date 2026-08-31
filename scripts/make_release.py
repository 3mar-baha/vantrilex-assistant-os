"""Release tooling (sprint-4 4.4c): verify version/CHANGELOG consistency, a clean
tree and a green quality gate — then optionally create the annotated tag. The
script STOPS at the tag; publishing the GitHub Release stays an owner step
(the exact `gh release create` command is printed).

If the tag already exists, do NOT fight it — bump to the next patch version
(e.g. 1.0.1) in ONE commit and re-run. There is deliberately NO --force flag:
its absence IS the safety feature.

Usage: python scripts/make_release.py [--tag]
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from loguru import logger

from src import __version__  # single source of truth

REPO = Path(__file__).resolve().parents[1]
CHANGELOG = REPO / "CHANGELOG.md"
_RELEASE_HEADING = re.compile(r"^## \[(\d+\.\d+\.\d+)\] — (\d{4}-\d{2}-\d{2})", re.MULTILINE)


def current_version() -> str:
    return __version__


def newest_changelog_version() -> str | None:
    match = _RELEASE_HEADING.search(CHANGELOG.read_text(encoding="utf-8"))
    return match.group(1) if match else None


def changelog_release(version: str) -> tuple[str, str] | None:
    """(date, section text) for the `## [version] — date` heading, or None."""
    text = CHANGELOG.read_text(encoding="utf-8")
    match = re.search(
        rf"^## \[{re.escape(version)}\] — (\d{{4}}-\d{{2}}-\d{{2}})", text, re.MULTILINE
    )
    if match is None:
        return None
    start = match.start()
    following = text.find("\n## [", match.end())
    section = text[start:] if following == -1 else text[start:following]
    return match.group(1), section


def verify_consistency() -> None:
    version = current_version()
    newest = newest_changelog_version()
    if version != newest or changelog_release(version) is None:
        logger.error(
            "version/CHANGELOG mismatch: src.__version__={version} but newest CHANGELOG "
            "release heading is {newest} — reconcile before tagging",
            version=version,
            newest=newest,
        )
        raise SystemExit(1)


def verify_clean_tree() -> None:
    status = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, check=False, cwd=REPO
    )
    if status.returncode != 0 or status.stdout.strip():
        logger.error(
            "working tree not clean — commit or stash everything before tagging:\n{out}{err}",
            out=status.stdout,
            err=status.stderr,
        )
        raise SystemExit(1)


def verify_gate() -> None:
    gate = subprocess.run(["make", "gate"], capture_output=True, text=True, check=False, cwd=REPO)
    if gate.returncode != 0:
        logger.error(
            "quality gate RED — refusing to tag:\n{out}{err}",
            out=gate.stdout[-2000:],
            err=gate.stderr[-2000:],
        )
        raise SystemExit(1)


def _tag(version: str) -> int:
    tag_name = f"v{version}"
    tag = subprocess.run(
        ["git", "tag", "-a", tag_name, "-m", f"Vantrilex Assistant OS {tag_name} — Sara"],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO,
    )
    if tag.returncode != 0:
        logger.error(
            "git tag failed — if v{version} already exists, bump to the next patch "
            "(e.g. 1.0.1) in one commit instead of forcing:\n{err}",
            version=version,
            err=tag.stderr,
        )
        return 1
    logger.info("annotated tag {tag} created on the validated HEAD", tag=tag_name)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify and tag the release (no force flags exist, by design)."
    )
    parser.add_argument(
        "--tag", action="store_true", help="create the annotated tag after all verifications"
    )
    args = parser.parse_args(argv)

    verify_consistency()
    verify_clean_tree()
    verify_gate()

    version = current_version()
    date, _section = changelog_release(version)
    logger.info("release {version} ({date}) — all verifications green", version=version, date=date)
    print(
        f"owner step: gh release create v{version} --verify-tag "
        f'--title "Vantrilex Assistant OS v{version}" '
        f"--notes-file <(sed -n '/^## \\[{version}\\]/,$p' CHANGELOG.md)"
    )
    if args.tag:
        return _tag(version)
    logger.info("dry run green — re-run with --tag to create the annotated tag")
    return 0


if __name__ == "__main__":
    sys.exit(main())
