r"""A-3 — the point where tool and arg meet: the shape table and the merge rule.

`entity_from_phrase` exists to answer ONE question — "given this tool, is its
argument an entity or a phrase?" — and this file pins the answer where it is
decided, plus the two places a wrong answer would become a wrong tool call.

  T1  the SHAPE TABLE (`ARG_ENTITY_TOOLS`) — a tool absent from it is IDENTITY
      by construction, not by accident. This is the over-trim guard's structural
      premise (`tests/test_a3_over_trim_guard.py`) stated at its source.
  T2  the MERGE RULE (`src/dispatcher.py:985-995`) — the branch that refines an
      arg must reconcile both producers instead of overwriting one with the
      other.
  T3  `normalize_tool_arg` COVERAGE — the known, DEFERRED limitation, measured.

THE DEFERRED CHOKE POINT, STATED HONESTLY. `normalize_tool_arg`
(`src/decision_loop.py:65-68`) is applied at exactly ONE of the three
`tools.call` sites — the dispatcher heal path (`src/dispatcher.py:1072-1077`),
which guards the call at :1101. The ReAct loop
(`src/decision_loop.py:472`) and the agent manager
(`src/agent_manager.py:272`) bypass it entirely. Relocating the hygiene pass to
`ToolRegistry.call` (`src/tools.py:277`, the ONE dispatch choke point, which
already carries the irreversible gate and the action log) would cover all three
— that is the approved plan's A-3c, and it is NOT this node: `src/tools.py`,
`src/decision_loop.py` and `src/agent_manager.py` are outside this node's file
ownership. `test_normalize_tool_arg_covers_one_of_three_call_sites` below pins
that measurement so the day someone does A-3c, this file turns RED and the
docstring has to be rewritten rather than the measurement quietly changing.

IMPORTS ARE LAZY, ON PURPOSE — see the module docstring of
`tests/test_a3_argument_hygiene.py`.

WHAT THIS FILE DOES NOT CLAIM
-----------------------------
- It does NOT claim `normalize_tool_arg` is the identity function. It strips
  whitespace and dictated quotes and folds Arabic-Indic digits
  (`src/decision_loop.py:65-68`), all three pinned by
  `tests/test_scratchpad_healing.py:12-17`. §A-corrections-2 Item 1 withdrew that
  claim.
- It does NOT claim the merge rule can pick a BETTER arg on its own. It cannot,
  and it must not try: the reconciliation is shape-scoped normalization applied
  to both sides, which is decidable. "Which arg is better" is not.
- It does NOT touch A-10 or A-13, and it does NOT change any file other than
  `src/dispatcher.py` and `src/cognition.py`.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Final

from src import cognition, dispatcher

ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------
# T1 — the shape table
# --------------------------------------------------------------------------


def test_shape_table_is_a_declared_frozenset():
    """A mutable dict here would make the whole shape discipline a suggestion."""
    assert isinstance(cognition.ARG_ENTITY_TOOLS, frozenset)
    assert cognition.ARG_ENTITY_TOOLS, "at least one tool has an entity arg"


def test_entity_extractor_is_reachable_from_both_producers():
    """One extractor, two producers. A second, divergent implementation in the
    dispatcher is how the two stopped agreeing in the first place — at `b5f3953`
    `_extract_arg` returned `'في عمان'` while `_keyword_net` returned
    `'عمّان'`, and the merge rule resolved the disagreement by picking wrong."""
    assert dispatcher.entity_from_phrase is cognition.entity_from_phrase


def test_entity_extractor_takes_no_tool_argument():
    """Shape selection happens at the CALL SITE, not inside the extractor.
    A tool-aware extractor is a tool-aware extractor with a branch that some
    future tool will fall through, and the over-trim hazard returns with it."""
    params = list(inspect.signature(cognition.entity_from_phrase).parameters)
    assert params == ["span"], params


# --------------------------------------------------------------------------
# T2 — the merge rule
# --------------------------------------------------------------------------


def _same_tool_branch() -> str:
    """The body of the same-tool refinement branch, read from the SOURCE rather
    than from a re-implementation — a guard that copies the code it guards
    cannot see the code changing."""
    source = inspect.getsource(dispatcher)
    return source.split("elif net_tool == tool:", 1)[1].split("if verdict_hit is None:", 1)[0]


def test_refinement_branch_normalizes_both_sides():
    """`src/dispatcher.py:985-995`. At `b5f3953` the body was
    `if net_arg != arg: arg = net_arg` — one-sided, unconditional. The resolved
    entity must now be computed for BOTH the incoming arg and the net's arg, so
    that a shadda-only difference can no longer make the worse side win."""
    assert "entity_from_phrase" in _same_tool_branch(), (
        "the same-tool refinement branch must reconcile both args through the "
        "entity extractor (src/dispatcher.py:985-995)"
    )


def test_refinement_branch_does_not_write_a_bare_net_arg():
    """The overwrite itself must be gone. Assigning `arg = net_arg` inside that
    branch is the exact line that let a filler-laden city beat a clean one."""
    assert "arg = net_arg" not in _same_tool_branch(), (
        "src/dispatcher.py:995 assigned the net's arg unconditionally; the "
        "refinement must reconcile, not overwrite"
    )


# --------------------------------------------------------------------------
# T3 — the deferred choke point, measured (GREEN by design)
# --------------------------------------------------------------------------


def _tools_call_sites() -> list[tuple[str, int]]:
    """Every `<tool registry>.call(` in src, as (file, line).

    The receiver is matched by NAME (`tools`, `self._tools`) rather than by
    "any `.call(`" — `src/google_cloud_suite.py` has an unrelated
    `Adapter.call` and a name-blind scan counts it, which would make this
    measurement lie in the one direction that hides a real bypass.
    """
    found: list[tuple[str, int]] = []
    for path in sorted((ROOT / "src").rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):  # pragma: no cover — fails elsewhere
            continue
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "call"
            ):
                continue
            receiver = node.func.value
            if isinstance(receiver, ast.Name):
                name = receiver.id
            elif isinstance(receiver, ast.Attribute):
                name = receiver.attr
            else:
                continue
            if name in ("tools", "_tools"):
                found.append((path.relative_to(ROOT).as_posix(), node.lineno))
    return found


#: The dispatch surfaces a tool call can leave from. Three files, four sites —
#: the dispatcher heals at two of them (`src/dispatcher.py:1101` first attempt,
#: :1115 the healed retry), both inside `_tool_lane`.
_DISPATCH_SURFACES: Final = frozenset(
    {"src/dispatcher.py", "src/decision_loop.py", "src/agent_manager.py"}
)


def test_normalize_tool_arg_covers_one_of_three_surfaces():
    """MEASURED, NOT CLAIMED-FIXED. `normalize_tool_arg` is a no-op on
    conversational filler by construction — it removes quotes, whitespace and
    Arabic-Indic digits and nothing else (`src/decision_loop.py:65-68`) — and
    it is reached only from `src/dispatcher.py:1072-1077`, inside `_tool_lane`.
    The ReAct loop (`src/decision_loop.py:472`) and the agent manager
    (`src/agent_manager.py:272`) bypass it entirely, so two of the three
    dispatch surfaces deliver an uncleaned arg today.

    This test pins the MEASUREMENT, not a defect: when A-3c relocates the pass
    to `ToolRegistry.call` this goes RED on purpose, and whoever does that must
    rewrite this docstring rather than let the number move silently.
    """
    sites = _tools_call_sites()
    assert {path for path, _ in sites} == _DISPATCH_SURFACES, f"surfaces moved: {sites}"

    behind_the_heal = {path for path, _ in sites if path == "src/dispatcher.py"}
    bypassing = {path for path, _ in sites} - behind_the_heal
    assert len(bypassing) == 2, (
        "expected exactly two dispatch surfaces that bypass "
        f"normalize_tool_arg today; they are now {sorted(bypassing)}"
    )

