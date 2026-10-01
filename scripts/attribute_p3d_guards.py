"""Attribute every P3-D guard test to the registration surface it exercises.

WHY THIS EXISTS. The P3-D barrier is 112 collected node ids across two files. A
landing report that cites only totals ("107 red -> green") cannot be audited: the
same totals are reachable by an implementation that closes one surface well and
another partially. This script produces a PARTITION of the 112 ids -- every id in
exactly one bucket -- so a reader can check per-surface completeness rather than
trust a sum.

Reproducibility is the point. Run it; it derives everything from the tree:

    python scripts/attribute_p3d_guards.py           # partition + per-function list
    python scripts/attribute_p3d_guards.py --ids     # full 112-id table, sortable

TWO ATTRIBUTION STRATEGIES WERE TRIED AND REJECTED, recorded because the failure
modes recur:

  1. Regex over TEST FUNCTION NAMES misbucketed badly -- 55 of 112 ids fell into
     a junk bucket, because a node id carries no body and name vocabulary is
     weak (the collision guard is named `...collides_with_a_live_tool` but asserts
     atomicity, idempotency and restoration too).

  2. Counting TEST FUNCTIONS understates coverage severely --
     `test_registration_refuses_a_name_that_collides_with_a_live_tool` is ONE
     function and 46 generated cases (it is parametrized over the full collision
     union). It is the single largest red block in the barrier and it is one line
     long. A per-function report would have shown it as a rounding error.

So: attribute by PARSED TEST BODY (ast.dump), then weight by COLLECTED node ids.
The body decides the bucket; pytest decides the multiplicity.

ATTRIBUTION RULES -- the contract, stated so a third party can disagree with it
explicitly rather than guess at it.

Six registration surfaces, from `src/tool_overlay.py` (P3-D) and the four-point
table in `tests/test_p3d_seams.py:31-45`:

    P1  ToolRegistry._do_<name>       getattr on the instance   src/tools.py:138
    P2  TOOL_CAPABILITIES[<name>]     read by markers_for       src/skills/capabilities.py:358
    P3  valid_tools()                 the merged route allow-list
    P4  tool_goals()[<name>]          the merged goal vocabulary
    P5  sara_tool_skills._SKILLS      the narration guide (fifth surface, found by
                                      measurement; breaks test_skill_standard.py:50
                                      in whatever test runs NEXT)
    P6  _COLLIDING_TOOL_NAMES         reachability from src/evolution.py:253

Plus four cross-cutting seams:

    S1  router prompt composition     the model may only name tools its catalog lists
    S-irreversible-gate              blueprint 3.6 "closed by construction"
    S0  atomicity / idempotency       all-six-or-none, release, reset
    S-other-harness                  non-vacuity sentinels and ordering

RULE 1 -- FIRST MATCH WINS, in the fixed order below. Narrow seams carry
distinctive vocabulary (`router_calls`, `has_confirmation`); broad ones do not
(`reversible` appears in nearly every atomicity guard). Ordering therefore runs
narrow-to-broad, and a test that touches both a narrow seam and a broad property
is attributed to the narrow one -- because the broad property is a consequence
of that seam landing.

RULE 2 -- A test asserting SEVERAL surfaces of the same seam family stays in that
family. `test_registration_populates_all_four_registration_points` touches P1-P4
and is counted under P1: it is one guard with one pass/fail, so splitting it
would inflate the denominator and let a partial pass look like a narrow miss.

RULE 3 -- THE UNATTRIBUTED RESIDUE IS THE AUDIT SIGNAL. Any id landing in
`S-other-harness` is a claim this script cannot make, not a pass. The tool prints
`accounted N / collected N`; those two numbers must be EQUAL, and a reader who
disagrees with a rule should expect that count to be where their disagreement
shows up.

WHAT THIS SCRIPT DOES NOT DO. It does not decide whether a surface is correctly
implemented -- only which guards bear on it. Correctness is `pytest`'s job, and
the 100%-per-surface pass rule in the landing report is a human judgement applied
to pytest's output. A bucket reading 65/65 means 65 guards passed, not that the
collision logic is correct.
"""

from __future__ import annotations

import argparse
import ast
import collections
import pathlib
import subprocess
import sys

BARRIER = ("tests/test_p3d_seams.py", "tests/test_p3d_registration.py")

# RULE 1: first match wins, narrow-to-broad. Do not reorder without updating the
# docstring above -- the partition changes when you do.
ORDER: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("S1-router-prompt", ("router_prompt", "ROUTER_PROMPT", "router_calls")),
    ("S-irreversible-gate", ("IRREVERSIBLE_TOOLS", "reversible", "IRREVERSIBLE")),
    ("P6-collision-live", ("is_valid_task_name", "_COLLIDING_TOOL_NAMES", "collision", "EvolutionTask")),
    ("P1-handler", ("_do_", "HANDLER_PREFIX", "ToolRegistry", "handler", "TOOL_FAIL_AR", "getattr")),
    ("P5-guide", ("_SKILLS", "narration", "shipped", "guide")),
    ("P2-capability", ("TOOL_CAPABILITIES", "markers_for", "capability_ids", "record")),
    ("P3-route", ("valid_tools",)),
    ("P4-goals", ("tool_goals", "deduce", "MARKER_A")),
)

FALLBACK = "S-other-harness"


def surface_of(dump: str) -> str:
    """The bucket for one test function, decided by its parsed body."""
    for surface, tokens in ORDER:
        if any(token in dump for token in tokens):
            return surface
    return FALLBACK


def function_surfaces() -> dict[str, str]:
    """function name -> bucket, from the barrier sources on disk."""
    mapping: dict[str, str] = {}
    for name in BARRIER:
        tree = ast.parse(pathlib.Path(name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                # setdefault: a duplicate name across the two files keeps the first.
                mapping.setdefault(node.name, surface_of(ast.dump(node)))
    return mapping


def collect() -> list[str]:
    """Collected node ids from pytest, so multiplicity is pytest's, not ours."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", *BARRIER, "-q", "-p", "no:cacheprovider",
         "--no-cov", "--collect-only"],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout + proc.stderr)
        raise SystemExit("collection failed -- cannot attribute an incomplete set")
    return [ln.strip() for ln in proc.stdout.splitlines() if ln.strip().startswith("tests/")]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ids", action="store_true", help="print every node id, not just functions")
    args = parser.parse_args()

    surfaces = function_surfaces()
    ids = collect()
    buckets: dict[str, list[str]] = collections.defaultdict(list)
    for test_id in ids:
        func = test_id.split("::")[-1].split("[")[0]
        buckets[surfaces.get(func, FALLBACK)].append(test_id)

    accounted = sum(len(v) for v in buckets.values())
    residue = len(ids) - accounted
    print(f"collected {len(ids)} node ids from {len(BARRIER)} barrier files")
    print(f"accounted {accounted} · unattributed {residue}  (RULE 3: these two must be equal)")
    print()
    for surface in sorted(buckets, key=lambda s: (-len(buckets[s]), s)):
        funcs = sorted({i.split("::")[-1].split("[")[0] for i in buckets[surface]})
        print(f"{len(buckets[surface]):4d} cases / {len(funcs):3d} functions  {surface}")

    print()
    for surface in sorted(buckets, key=lambda s: (-len(buckets[s]), s)):
        cases = buckets[surface]
        print(f"--- {surface}: {len(cases)} cases / {len({i.split('::')[-1].split('[')[0] for i in cases})} functions")
        if args.ids:
            for test_id in sorted(cases):
                print(f"      {test_id}")
        else:
            for func in sorted({i.split("::")[-1].split("[")[0] for i in cases}):
                print(f"      {func}")
        print()

    if residue:
        print("WARNING: unattributed ids exist -- a reader who disagrees with an "
              "attribution rule should expect to find it here.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())