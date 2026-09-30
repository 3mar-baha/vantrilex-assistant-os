"""Decision 3 — `scripts/check_tiered_coverage.py` is a permanent `make gate` barrier.

MEASURED DEFECT (Directive 3, re-derived from the tree). `Makefile:40` reads
`gate: lint test security docs-guard` — coverage is NOT in it. Meanwhile
`docs/11-TESTING.md:37-42` lists `scripts/check_tiered_coverage.py` as the third
step of the gate checklist. The document and the executable gate disagree: the
22-core-modules-at-98% and global-90% thresholds are enforced by a script nobody
runs unless they read the doc.

Two guards, and the second is the one that matters:

  1. SHAPE — the `gate` target's prerequisites name a coverage target. Cheap,
     states the decision directly, and reads as the commit's intent.

  2. AGREEMENT (anti-drift) — the two sides are re-derived from the tree on every
     run and compared: every `scripts/*.py` the docs claim under the `make gate`
     heading must appear in the transitive recipe closure of the `gate` target.
     This is the guard that stops the recurrence, because it does not hardcode
     the answer — it re-reads `Makefile` and `docs/11-TESTING.md` and asks
     whether they still tell the same story. Fix the document, never the checker
     (Directive 6); conversely, a Makefile that drops a documented step fails
     here instead of silently regressing.

The closure walk also means an EMPTY coverage target does not satisfy either
guard: a prerequisite with no recipe invokes no script, so the documented path
stays unreachable.

`make` is never executed — parsing is pure text (`tests/test_quality_gate.py:65`
established the regex style for the same line).

NON-DUPLICATION: `tests/test_quality_gate.py::test_makefile_gate_order` pins the
EXACT prerequisite list `["lint", "test", "security", "docs-guard"]`. That test
is not duplicated here and it WILL fail once the coverage target is added — the
implementer owns that one-line update. This file only asserts a coverage
prerequisite EXISTS, which stays true under either list.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MAKEFILE = REPO / "Makefile"
GATE_DOC = REPO / "docs" / "11-TESTING.md"

SCRIPT_RE = re.compile(r"scripts/[\w./-]+\.py")
# A target is a line that starts in column 0 with `name:` and no `=` (that is a
# Make variable assignment). Recipes are indented.
TARGET_RE = re.compile(r"^([A-Za-z][\w.-]*):\s*(.*)$")
VARIABLE_RE = re.compile(r"^\s*[A-Za-z_][\w.]*\s*=(?!=)")
# A prerequisite name that says "this target enforces coverage".
COVERAGE_RE = re.compile(r"cover")

GATE = "gate"


def _targets() -> dict[str, tuple[list[str], list[str]]]:
    """Every declared target -> (prerequisites, recipe lines), in file order."""
    found: dict[str, tuple[list[str], list[str]]] = {}
    current: str | None = None
    for line in MAKEFILE.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#") or VARIABLE_RE.match(line):
            continue
        if line[0] in " \t":
            if current is not None:
                found[current][1].append(line)
            continue
        head = TARGET_RE.match(line)
        if head is None:
            current = None
            continue
        current = head.group(1)
        found[current] = (head.group(2).split(), [])
    return found


def _gate_closure(targets: dict[str, tuple[list[str], list[str]]]) -> list[str]:
    """Every recipe line reachable from `gate`, following prerequisites."""
    collected: list[str] = []
    seen: set[str] = set()
    pending = [GATE]
    while pending:
        name = pending.pop()
        if name in seen or name not in targets:
            continue
        seen.add(name)
        prereqs, recipe = targets[name]
        collected.extend(recipe)
        pending.extend(prereqs)
    return collected


def _documented_gate_scripts() -> set[str]:
    """Scripts the docs claim run under `make gate` — the `make gate` section only."""
    text = GATE_DOC.read_text(encoding="utf-8")
    lines = text.splitlines()
    start = next(
        (index for index, line in enumerate(lines) if line.startswith("#") and "make gate" in line),
        None,
    )
    assert start is not None, "docs/11-TESTING.md has no 'make gate' heading to re-derive from"
    body: list[str] = []
    for line in lines[start + 1 :]:
        if line.startswith("## "):
            break
        body.append(line)
    return set(SCRIPT_RE.findall("\n".join(body)))


def test_gate_target_declares_a_coverage_prerequisite() -> None:
    """RED: `gate: lint test security docs-guard` names no coverage target.

    The tiers (22 safety/cost/gender cores >=98% branch, global >=90%) are only
    enforced if a target that runs `check_tiered_coverage.py` is a prerequisite
    of the gate.
    """
    targets = _targets()
    assert GATE in targets, f"{MAKEFILE.name} has no `{GATE}:` target"
    prereqs = targets[GATE][0]
    assert any(COVERAGE_RE.search(name) for name in prereqs), (
        f"the `{GATE}` target must require a coverage target; its prerequisites are {prereqs}"
    )


def test_make_gate_invocations_match_the_documented_gate() -> None:
    """RED: the docs promise `scripts/check_tiered_coverage.py`; the Makefile
    never invokes it.

    The anti-drift guard: both sides are re-derived from the tree, so this fails
    again the day someone adds a gate step to the docs and forgets the Makefile
    (today's defect), or removes a step from the Makefile and forgets the docs.
    """
    documented = _documented_gate_scripts()
    assert documented, (
        "no scripts found under the 'make gate' heading in docs/11-TESTING.md — "
        "the re-derivation found nothing to compare, which means the check has "
        "stopped seeing the document"
    )
    invoked = set(SCRIPT_RE.findall("\n".join(_gate_closure(_targets()))))
    missing = sorted(documented - invoked)
    assert not missing, (
        f"docs/11-TESTING.md says `make gate` runs {missing} but the `{GATE}` "
        f"target's recipe closure only runs {sorted(invoked)}. The gate the owner "
        "runs is not the gate the docs describe."
    )
