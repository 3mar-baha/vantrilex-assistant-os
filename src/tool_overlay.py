"""P3-C registration overlay — the merge layer that makes registration editable.

Registering a tool today takes FOUR edits, and two of them are `Final` literals
that no runtime path can rewrite:

    1. ``ToolRegistry._do_<name>``       getattr  src/tools.py:138
    2. ``TOOL_CAPABILITIES[<name>]``    dict     src/skills/capabilities.py:350
    3. ``_VALID_TOOLS``                  Final    src/dispatcher.py:123
    4. ``_TOOL_GOALS[<name>]``          Final    src/cognition.py:30

Points 3 and 4 are the trap, and both fail SILENTLY. A router verdict naming a
name outside (3) was rewritten to ``"none"`` with no exception raised
(``src/dispatcher.py:730``), and ``deduce`` iterates (4) — so a tool registered
only in (2) is a tool Sara can never *select*. "The feature just doesn't work"
is the entire failure signal.

This module is the seam. It holds the runtime-mutable ``OVERLAY`` and exposes
``valid_tools()`` / ``tool_goals()``, which merge that overlay onto the static
base. ``_VALID_TOOLS`` and ``_TOOL_GOALS`` KEEP their names, their types and
their contents: ten test modules import them by name, and ``Final`` is the very
property this refactor works AROUND rather than removes. They stay the static
base; only the production consumers move to the accessors.

Placement: a THIRD module, not either of the two. ``src.dispatcher`` already
imports ``src.cognition`` (:21) and cognition does not import dispatcher, so
neither existing module can host the overlay without an import cycle. The base
registries are therefore imported INSIDE the accessors — a module-level import of
``src.dispatcher`` from here would close the cycle the moment dispatcher
imports this file back.

Merge semantics — the one decision that is easy to get wrong:

* ``valid_tools()`` APPENDS overlay keys after the base, preserving base order.
  Base order is load-bearing for prompt-adjacent readers.
* ``tool_goals()`` UNIONS, never replaces. On a colliding key the overlay's
  markers are merged with the static ones via ``dict.fromkeys`` — the house
  convention already established by ``_goal_markers`` (``src/cognition.py:399``).
  A plain ``dict(base) | overlay`` is the reflexive implementation and it is
  WRONG: on an accidental key collision it would silently SHRINK a tool's
  detection vocabulary, degrading a working tool without raising anything.
  Pinned by ``tests/test_tool_overlay.py::
  test_overlay_goals_union_with_static_goals_rather_than_shadowing_them``.

SHIPS EMPTY. This phase registers nothing; P3-D enables an actual tool. An entry
in ``OVERLAY`` at this stage is a P3-D change smuggled into a refactor commit.
"""

from __future__ import annotations

__all__ = ["OVERLAY", "reset_overlay", "tool_goals", "valid_tools"]

#: Runtime-mutable registration overlay: tool name -> its goal markers.
#:
#: EMPTY at P3-C. Not ``Final`` and not ``MappingProxyType`` — mutability is the
#: entire purpose of the seam. Both accessors read it on every call and neither
#: memoises, so a mutation is visible to the next reader immediately.
OVERLAY: dict[str, tuple[str, ...]] = {}


def valid_tools() -> tuple[str, ...]:
    """`_VALID_TOOLS` merged with the overlay's keys; base order preserved.

    Returns a ``tuple`` because that is what every importing call site already
    does to ``_VALID_TOOLS`` — ``in``, iteration, ``set()``, ``len()`` and
    slicing all have to keep working unchanged for the ten test modules that read
    the base.
    """
    from src.dispatcher import _VALID_TOOLS  # deferred: dispatcher imports this module

    extra = tuple(name for name in OVERLAY if name not in _VALID_TOOLS)
    if not extra:
        return _VALID_TOOLS
    return (*_VALID_TOOLS, *extra)


def tool_goals() -> dict[str, tuple[str, ...]]:
    """`_TOOL_GOALS` merged with the overlay, UNIONING markers on a collision.

    A fresh ``dict`` every call: the returned mapping is a VIEW, and handing back
    the base dict itself would let a caller mutate the static registry through
    what reads as a read-only accessor. With an empty overlay the values are the
    base's own tuples, untouched — identity, not just equality.
    """
    from src.cognition import _TOOL_GOALS  # deferred: keeps this module import-leaf

    merged = dict(_TOOL_GOALS)
    for name, markers in OVERLAY.items():
        base = merged.get(name)
        # Union, not replace — see the module docstring. No collision means the
        # base tuple is kept verbatim, so a merge can never alter a static entry.
        merged[name] = tuple(dict.fromkeys((*base, *markers))) if base else tuple(markers)
    return merged


def reset_overlay() -> None:
    """Empty the overlay in place.

    ``clear()`` rather than rebinding to ``{}``: the overlay is process-global
    state, and in-place clearing keeps every existing reference to it valid. The
    process-global shape is a real hazard — a test that mutates ``OVERLAY`` leaks
    into whatever runs next — which is why the guards in
    ``tests/test_tool_overlay.py`` reset before AND after each test.
    """
    OVERLAY.clear()
