"""QW-3 — `src/vault.py`'s module docstring must describe the retry loop it ships.

`CLAUDE.md` §5.1 Directive 6: every claim a document makes is re-derived from
the tree, and "unverifiable" is an error rather than a warning. A module
docstring is a document, and it is the one a maintainer reads before touching
error handling — so a false claim about how conflicts resolve is not cosmetic.

THE DEFECT THIS PINS. The shipped docstring read::

    409 after one GET->PUT retry raises VaultConflictError

and `VaultClient._upsert_locked` ships::

    for attempt in (1, 2, 3):  # C-9: full re-merge, never a stale re-PUT

Three attempts, not one. And each attempt is a FULL re-merge — re-read the
sha, re-run the caller's ``merge(path, content)`` callback, re-PUT — which is
the opposite of the single GET->PUT retry the docstring describes. The
comment on that very line states it correctly; the docstring two hundred lines
above states it wrongly.

WHY THE COUNT ALONE IS NOT ENOUGH. A guard that only compared "3" against
"three" would pass a docstring claiming "three stale re-PUTs", which is a
different and wrong law: re-running a caller's merge callback three times and
blindly re-PUTting three times are not interchangeable, and a merge callback
with a side effect behaves differently under each. So this guard checks both
halves — the attempt count AND that the docstring says re-merge rather than
stale re-PUT — and the second half is derived from the code too: the loop body
calls ``merge`` on each attempt, which is what makes it a re-merge.

THE GUARD IS AN AST READ, NOT A GREP. The retry count is taken from the loop's
own tuple literal, so the check cannot be satisfied by rewording the docstring
and cannot drift when the loop is refactored — if the loop changes, this test
says so and the docstring is what has to follow.

Scope note: this file pins the CLAIM. It does not touch the retry logic, and
`tests/` already covers the behaviour itself; the hazard a false docstring
creates is a reader's misreasoning about a merge callback they own, and that
is what this closes.
"""

from __future__ import annotations

import ast
from pathlib import Path

VAULT_PATH = Path(__file__).resolve().parents[1] / "src" / "vault.py"

#: The loop TARGET name of the `for ... in <int tuple>` that carries the 409
#: re-merge attempts (`for attempt in (1, 2, 3)`). Its inline comment names the
#: C-9 fix, so the loop is locatable by structure and not only by line number,
#: which any refactor would move.
_LOOP_TARGET_NAME = "attempt"


def _module() -> ast.Module:
    return ast.parse(VAULT_PATH.read_text(encoding="utf-8"))


def _module_docstring() -> str:
    doc = ast.get_docstring(_module())
    assert doc is not None, f"{VAULT_PATH.name} has no module docstring to check"
    return doc


def _conflict_retry_loop() -> ast.For:
    """The 409 re-merge loop, found by structure rather than by line number.

    A `for` whose target is `_LOOP_TARGET_NAME` and whose iterable is a tuple of
    integer literals. Raises if it is gone, because a silently-absent loop would
    make every assertion below vacuously true — a guard that passes because its
    subject disappeared is not a guard (Directive 2).
    """
    for node in ast.walk(_module()):
        if not isinstance(node, ast.For) or not isinstance(node.iter, ast.Tuple):
            continue
        if not (isinstance(node.target, ast.Name) and node.target.id == _LOOP_TARGET_NAME):
            continue
        if all(
            isinstance(elt, ast.Constant) and isinstance(elt.value, int) for elt in node.iter.elts
        ):
            return node
    raise AssertionError(
        f"{VAULT_PATH.name}: no `for {_LOOP_TARGET_NAME} in (<ints>)` loop was found — the "
        f"409 conflict re-merge loop was renamed, restructured or removed, and the module "
        f"docstring's retry claim now has no code to check against."
    )


def _attempt_count() -> int:
    return len(_conflict_retry_loop().iter.elts)  # type: ignore[attr-defined]


def _loop_calls_merge() -> bool:
    """True when the loop re-runs the caller's merge on each attempt.

    This is what makes the loop a full re-merge rather than a stale re-PUT, so
    it is read from the code rather than asserted about the docstring's prose.
    ``await merge(path, content)`` puts the call under an `ast.Await`, so the
    walk has to see through it — matching only top-level calls would miss the
    real one and report "no merge", which is the same defect in reverse.
    """
    for node in ast.walk(_conflict_retry_loop()):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id == "merge":
            return True
        if isinstance(node.func, ast.Attribute) and node.func.attr == "merge":
            return True
    return False


def test_the_retry_loop_the_code_ships_is_found_so_no_check_below_is_vacuous() -> None:
    """Directive 2: a guard that cannot fire is hollow, and a helper that
    silently returns nothing makes every assertion using it pass for the wrong
    reason. The loop's existence and shape are pinned on their own."""
    loop = _conflict_retry_loop()
    assert isinstance(loop.iter, ast.Tuple)
    assert _attempt_count() >= 1
    assert _loop_calls_merge() is True, (
        "the conflict retry loop no longer calls the caller's merge callback — if it now "
        "performs a stale re-PUT instead of a re-merge, that changes the hazard this guard "
        "describes and the module docstring must be rewritten, not re-counted"
    )


def test_the_module_docstring_states_the_retry_count_the_loop_actually_performs() -> None:
    """The pin. The docstring's 409 claim must carry the number the loop runs."""
    doc = _module_docstring()
    attempts = _attempt_count()
    words = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}
    stated = words.get(attempts)
    assert stated is not None, (
        f"the conflict loop now performs {attempts} attempts and this guard has no word for "
        f"that number — extend `words` here AND correct the module docstring in the same "
        f"commit, so the claim is never silently dropped"
    )
    lowered = doc.lower()
    assert stated in lowered, (
        f"{VAULT_PATH.name} docstring does not state that a 409 is retried {stated} time(s). "
        f"The loop performs {attempts} attempts. Fix the docstring to match the code — the "
        f"code is the authority (Directive 6).\n--- docstring ---\n{doc}\n--------------"
    )


def test_the_module_docstring_does_not_describe_a_single_retry() -> None:
    """The negative control, stated so the pin above cannot be passed by luck.

    "one GET->PUT retry" is the exact phrase the stale docstring shipped. If a
    future edit reintroduces a single-retry description, this names it even if
    the word "one" appears somewhere unrelated in the docstring.
    """
    doc = _module_docstring().lower()
    stale = "one get->put retry"
    assert stale not in doc, (
        f"{VAULT_PATH.name} docstring still describes '409 after {stale}'. The shipped loop "
        f"performs a full re-merge {_attempt_count()} times, never a single stale GET->PUT."
    )


def test_the_module_docstring_says_re_merge_not_stale_re_put() -> None:
    """The second half of the claim, which a count-only check cannot reach.

    The loop re-reads the sha and re-runs the caller's merge on every attempt,
    so the docstring has to say re-merge. A docstring claiming three attempts
    of a *stale* re-PUT would satisfy the count check while describing a
    different — and wrong — failure mode.
    """
    assert _loop_calls_merge() is True, "precondition: the loop re-runs merge"
    doc = _module_docstring().lower()
    assert "re-merge" in doc or "remerge" in doc or "re-merging" in doc, (
        f"{VAULT_PATH.name} docstring never says the 409 path RE-MERGES. The loop re-reads the "
        f"sha and re-runs the caller's merge callback on each of its "
        f"{_attempt_count()} attempts — which is why a merge callback must assume it can be "
        f"invoked repeatedly."
    )
