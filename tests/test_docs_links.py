"""Decision 5 — no relative markdown link in the documentation may dangle.

MEASURED DEFECT (Directive 3, counted by script, not taken from the brief).
Twelve tracked files under `docs/reports/` and `docs/specs/` — plus two at the
`docs/` root — are deleted in the working tree and unstaged. The deletion breaks
**17** relative links across **4** documents:

    docs/00-MAP-OF-ARCHITECTURE.md          9 links
    docs/00-MAP-OF-TESTING-AND-AUDITS.md    4 links
    docs/10-CHECKPOINT.md                   3 links
    docs/16-WORKFLOWS.md                    1 link

REFUTED PREMISE, recorded rather than quietly dropped: the brief scoped the
count to "9 broken relative links in docs/00-MAP-OF-ARCHITECTURE.md". That is
exactly right for that one file and an undercount for the tree — three further
documents point at the same 12 missing files, for 17 in total. The guard covers
the whole tree, so the number the guard reports is the number the fix needs.

WIKILINKS ARE OUT OF SCOPE, deliberately. `[[Some Note]]` is Obsidian syntax
that resolves inside the local `vault/` mirror, which is not committed
(`docs/00-MAP-OF-ARCHITECTURE.md:54-57`). A guard that flagged wikilinks would
fail on every vault-only note and would be muted within a day.

MEASURED, so the exclusion is not overstated: it is TWO independent layers, not
one. `WIKILINK_RE` strips `[[...]]` spans before extraction, AND `LINK_RE` would
decline them anyway because it requires `]` immediately followed by `(` while a
wikilink closes with `]]` (verified against both the plain and the adversarial
`[[Note](path)]]` spelling). The tests assert the OUTCOME — no wikilink target
ever reaches the checker — which holds while either layer stands. Both layers
are there so neither regex is load-bearing on its own.

Hermetic: filesystem reads only. No socket, no HTTP, no clock, no subprocess —
so unlike `git ls-files` the walk cannot be broken by a missing git, and it
resolves links against what is actually on disk, which is what a reader needs.
(`git status` cross-check at HEAD: all 12 targets are tracked deletions, and no
broken target is untracked — i.e. restoring the files is the whole fix.)

KNOWN LIMITATION, stated rather than hidden: fenced code blocks are not skipped,
so a document that *demonstrates* markdown link syntax would false-positive.
Measured at HEAD: 233 links checked, 17 broken, every one of them real, so no
exemption is needed today. Widening the checker later is a one-line change here.
"""

from __future__ import annotations

import re
import urllib.parse
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DOCS = REPO / "docs"
README = REPO / "README.md"

# Obsidian wikilinks: vault-only, never a filesystem path.
WIKILINK_RE = re.compile(r"\[\[[^\]]*\]\]")

# Inline markdown links: [text](target) and [text](<target with spaces> "Title").
LINK_RE = re.compile(r"\[[^\]]*\]\(\s*<?([^)<>\s]+)>?(?:\s+(?:\"[^\"]*\"|'[^']*'))?\s*\)")

# Targets that are not filesystem paths at all.
NON_RELATIVE = ("http://", "https://", "mailto:", "tel:", "//", "#")


def _doc_files(root: Path) -> list[Path]:
    readme = root / "README.md"
    return sorted((root / "docs").rglob("*.md")) + ([readme] if readme.exists() else [])


def _relative_targets(text: str) -> list[str]:
    """Every relative link target in `text`, with wikilinks removed first."""
    without_wikilinks = WIKILINK_RE.sub("", text)
    targets: list[str] = []
    for raw in LINK_RE.findall(without_wikilinks):
        if raw.startswith(NON_RELATIVE):
            continue
        path = urllib.parse.unquote(raw.split("#", 1)[0]).strip()
        if path:
            targets.append(path)
    return targets


def _broken_links(root: Path) -> list[tuple[str, str]]:
    """(source, target) for every relative link that does not resolve on disk."""
    broken: list[tuple[str, str]] = []
    for md in _doc_files(root):
        for target in _relative_targets(md.read_text(encoding="utf-8")):
            if not (md.parent / target).exists():
                broken.append((md.relative_to(root).as_posix(), target))
    return broken


def _report(broken: list[tuple[str, str]]) -> str:
    lines = [f"{len(broken)} broken relative link(s):"]
    lines += [f"  {source} -> {target}" for source, target in broken]
    targets = sorted({target for _, target in broken})
    lines.append(f"  {len(targets)} distinct missing file(s): {targets}")
    return "\n".join(lines)


# --- the guard ------------------------------------------------------------------


def test_every_relative_doc_link_resolves() -> None:
    """RED: 17 links across 4 documents point at 12 files deleted from the tree."""
    broken = _broken_links(REPO)
    assert not broken, _report(broken)


def test_the_walk_actually_finds_links_to_check() -> None:
    """A link guard that finds no links passes for the wrong reason.

    Stated as its own test so a future refactor that breaks the extractor fails
    here, loudly, instead of turning `test_every_relative_doc_link_resolves` into
    a vacuous green (Directive 4: does it exist, can it fire, is it correct).
    """
    files = _doc_files(REPO)
    targets = [t for md in files for t in _relative_targets(md.read_text(encoding="utf-8"))]
    assert len(files) >= 20, f"doc walk found only {len(files)} files under docs/"
    assert len(targets) >= 100, (
        f"doc walk extracted only {len(targets)} relative links — the extractor "
        "is not seeing the documents and every other guard here is vacuous"
    )


# --- the exclusions, proven -----------------------------------------------------


def test_wikilinks_are_excluded_entirely(tmp_path) -> None:
    """A `[[…]]` wikilink resolves in the local `vault/` mirror, never on disk, so
    the checker must not see one — not even when it names a file that does not
    exist. Only the real relative link may be reported."""
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "note.md").write_text(
        "[[Omar_Master_Digest]] and [[Daily_Logs/2026-09-30]] and [[Nowhere At All]]\n"
        "[present](./sibling.md)\n"
        "[missing](./gone.md)\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "sibling.md").write_text("sibling\n", encoding="utf-8")
    assert _broken_links(tmp_path) == [("docs/note.md", "./gone.md")]


def test_wikilink_style_spans_never_reach_the_extractor() -> None:
    """Proves the exclusion at the extractor level, not only through the walk: no
    target returned by `_relative_targets` may contain a wikilink marker."""
    text = "[[Budget]] [a](./a.md) [[Ops/Runbook]] [b](../b.md) [[x]](c.md)"
    targets = _relative_targets(text)
    assert targets == ["./a.md", "../b.md"], f"wikilinks leaked into the target list: {targets}"
    assert all("[[" not in target for target in targets)


@pytest.mark.parametrize(
    "target",
    [
        "https://github.com/diegosouzapw/OmniRoute",
        "http://localhost:20128/v1",
        "mailto:owner@example.com",
        "tel:+9627900000000",
        "#a-section-anchor",
    ],
)
def test_external_and_anchor_targets_are_not_filesystem_paths(target: str) -> None:
    """An external URL or a same-page anchor is not a dangling file. Without this
    the guard would fire on every outbound link in the docs."""
    assert _relative_targets(f"[x]({target})") == [], f"{target} was treated as a relative path"
