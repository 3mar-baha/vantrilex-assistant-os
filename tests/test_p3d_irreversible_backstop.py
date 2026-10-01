"""P3-D guard: the irreversible tier is CLOSED BY CONSTRUCTION, not by a sentence.

Blueprint §3.6's SOVERNIUM row says the irreversible tier is "never reachable by
synthesis — closed by construction". P3-D builds the synthesis entry point
(`register_tool`), and this file guards the second half of that claim: closing
the tier is an ENFORCED post-condition of the registration path, not a comment.

`IRREVERSIBLE_TOOLS` (`src/skills/capabilities.py`) is a `Final` frozenset built
at import from `_CAPABILITIES`. Nothing can add to it at runtime, so a catalog
entry carrying `reversible=False` that is NOT in the deny-list is invisible to
every confirmation gate downstream: the tool would be routed, catalogued and
narration-ready, and the gate that asks the owner before an irreversible action
would never fire for it.

`register_tool` therefore does BOTH halves:

  (a) refuses ``reversible=False`` outright (refusal R4), and
  (b) re-checks the whole-registry invariant ``IRREVERSIBLE_TOOLS ⊇
      {k : TOOL_CAPABILITIES[k]["reversible"] is False}`` AFTER writing the
      capability record, and rolls the whole registration back if it fails.

(b) is what makes (a) structural: a future writer that skips R4 still cannot open
the tier, because the post-condition is evaluated over the LIVE registry rather
than over the arguments of one call.

No socket, no HTTP, no wall clock, no subprocess. Every surface is read off a live
module attribute.
"""

from __future__ import annotations

import pytest

from src import evolution
from src.skills import sara_tool_skills
from src.skills.capabilities import IRREVERSIBLE_TOOLS, TOOL_CAPABILITIES

#: A name absent from every live registry, and a goal marker absent from every
#: static goal family, so a landing registration is provably additive.
TOOL_A = "p3d_backstop_probe"
MARKER_A = "زعتر"
GOAL_A = "قراءة سعر الذهب"


def _seam(symbol: str):
    """Resolve a P3-D producer on `src.tool_overlay`; a missing one FAILS.

    A module-level import of `register_tool` would abort collection with a bare
    ImportError, and a guard that never reports a failure is not a guard
    (Directive 2). Same reasoning as `_seam()` in `tests/test_p3d_seams.py:98`.
    """
    import src.tool_overlay as overlay

    try:
        return getattr(overlay, symbol)
    except AttributeError:
        pytest.fail(
            f"src.tool_overlay.{symbol} does not exist yet — P3-D is RED. Closing the "
            "irreversible tier by construction needs the registration entry point (missing "
            f"producer: src.tool_overlay.{symbol})."
        )


def _overlay():
    import src.tool_overlay as overlay

    return overlay


#: A tool the catalog does NOT deny-list, carrying the irreversible flag. This is
#: the exact shape R4 exists to keep out; it is injected here only so the
#: post-condition can be observed refusing it.
UNDENIED_IRREVERSIBLE = "p3d_undenied"

#: Every surface a registration can move, read LIVE off the module attributes.
SURFACES = (
    "valid_tools",
    "tool_goals",
    "TOOL_CAPABILITIES",
    "guide_names",
    "registry_handlers",
    "collision_set",
    "name_is_valid",
)


async def _handler(arg: str) -> str:
    return f"{arg}"


def _register(name: str = TOOL_A, **overrides: object) -> None:
    _seam("register_tool")(
        name=name,
        markers=(MARKER_A,),
        handler=_handler,
        goals=GOAL_A,
        needs="local",
        reversible=True,
        chains_with=(),
        **overrides,  # type: ignore[arg-type]
    )


def _state() -> dict[str, object]:
    from src.tools import ToolRegistry

    return {
        "valid_tools": set(_seam("valid_tools")()),
        "tool_goals": dict(_seam("tool_goals")()),
        "TOOL_CAPABILITIES": dict(TOOL_CAPABILITIES),
        "guide_names": tuple(filename for filename, _ in sara_tool_skills._SKILLS),
        "registry_handlers": frozenset(k for k in vars(ToolRegistry) if k.startswith("_do_")),
        "collision_set": set(evolution._COLLIDING_TOOL_NAMES),
        "name_is_valid": evolution.is_valid_task_name(TOOL_A),
    }


@pytest.fixture(autouse=True)
def _backstop_hygiene():
    """Undo every write this file makes, in a `finally`, through the public API
    first and by hand second — a guard that leaks poisons the rest of the suite
    with a half-bound tool rather than failing."""
    try:
        yield
    finally:
        _seam("reset_overlay")()
        for name in (TOOL_A, UNDENIED_IRREVERSIBLE):
            TOOL_CAPABILITIES.pop(name, None)
        from src.tools import ToolRegistry

        for attr in tuple(k for k in vars(ToolRegistry) if k.startswith("_do_")):
            if attr in (f"_do_{TOOL_A}", f"_do_{UNDENIED_IRREVERSIBLE}"):
                delattr(ToolRegistry, attr)
        sara_tool_skills._SKILLS = tuple(
            (f, body)
            for f, body in sara_tool_skills._SKILLS
            if f not in (f"{TOOL_A}.md", f"{UNDENIED_IRREVERSIBLE}.md")
        )
        _overlay().OVERLAY.clear()


def test_the_invariant_holds_across_the_live_registry_today() -> None:
    """The post-condition is not decorative: it must be TRUE of the shipped
    registry, or it would refuse every registration for a pre-existing gap."""
    gaps = sorted(
        tool
        for tool, cap in TOOL_CAPABILITIES.items()
        if cap.get("reversible") is False and tool not in IRREVERSIBLE_TOOLS
    )
    assert not gaps, f"irreversible tools outside the deny-list: {gaps}"
    assert IRREVERSIBLE_TOOLS <= set(TOOL_CAPABILITIES), (
        "the deny-list names a tool the catalog does not carry — the inclusion every "
        "structural backstop in this file leans on no longer holds"
    )


def test_an_undenied_irreversible_entry_makes_the_registration_refuse_and_roll_back(
    monkeypatch,
) -> None:
    """THE BACKSTOP GUARD. An irreversible entry that the deny-list does not
    cover is the exact shape R4 refuses to create. Injected directly into the
    live catalog, it must still stop the NEXT registration and leave nothing
    behind — a registration that landed on top of an open tier would add a
    second tool to the same blind spot.

    The `finally` in the hygiene fixture removes the injected entry afterwards;
    the assertion here is that `register_tool` itself moved no surface while
    refusing."""
    TOOL_CAPABILITIES[UNDENIED_IRREVERSIBLE] = {
        "goals": GOAL_A,
        "markers": (MARKER_A,),
        "needs": "local",
        "reversible": False,
        "chains_with": (),
    }
    before = _state()
    with pytest.raises(ValueError) as caught:
        _register()
    message = str(caught.value)
    assert TOOL_A in message, f"the refusal does not name the tool it refused: {message!r}"
    assert UNDENIED_IRREVERSIBLE in message, (
        f"the refusal does not name the irreversible tool that opened the tier: {message!r} "
        "— an operator cannot act on a refusal that does not say what failed"
    )
    after = _state()
    moved = {key for key in SURFACES if before[key] != after[key]}
    assert not moved, (
        f"a registration refused by the post-condition still moved {sorted(moved)} — the "
        "capability record was written and must be rolled back"
    )
    assert TOOL_A not in TOOL_CAPABILITIES
    assert TOOL_A not in _seam("valid_tools")()


def test_the_post_condition_reports_a_gap_in_the_deny_list_direction() -> None:
    """A deny-list naming a tool the catalog does not carry is the mirror defect:
    the gate would ask about a tool nobody can route. The post-condition checks
    the one direction the registration path can actually create (a catalog entry
    the deny-list misses), and this guard says so out loud so the asymmetry is a
    recorded decision rather than an oversight."""
    assert IRREVERSIBLE_TOOLS <= set(TOOL_CAPABILITIES)
    assert not (IRREVERSIBLE_TOOLS - set(TOOL_CAPABILITIES)), (
        "the deny-list holds a name the catalog does not — nothing in the registration "
        "path can create that, so it is a base-registry defect, not a P3-D one"
    )
