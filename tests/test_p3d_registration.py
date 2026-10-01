"""P3-D guards: `register_tool` / `unregister_tool` — the all-or-nothing registration API.

P3-C built the merge layer and shipped it EMPTY, and enumerated the trap in the module
docstring: registering a tool needs FOUR edits, two of which are `Final` literals that
no runtime path can rewrite. The failure both of those edits produce is SILENT — a tool
that simply does not work. So the API this file specifies has exactly one job beyond
making a tool runnable, and it is the job the four-point table exists to force:

    A registration either lands at ALL FOUR POINTS or at NONE OF THEM.

Half a registration is strictly worse than no registration. A tool in the overlay with
no capability record parses, deduces, and then answers `TOOL_FAIL_AR`; a capability
record with no handler turns a green guard red in whichever test runs next. Neither
raises at the point of the mistake, and the operator's signal is "the feature just
doesn't work". Pinned by
`test_a_refused_registration_leaves_no_registration_point_half_populated`, run once per
specified refusal reason.

THE SPECIFIED API — the smallest signature that satisfies the four points plus the
narration guide that `tests/suite/tier1_resilience/test_skill_standard.py:50` demands
(see `tests/test_p3d_seams.py` for why the guide is a fifth surface):

    register_tool(name, markers, handler, *, goals, needs, reversible, chains_with)
    unregister_tool(name)

    - name:      str, `NAME_RE`-shaped, and not held by any live tool
    - markers:   the goal vocabulary, written to BOTH the goal overlay and the
                 capability record so the two sources cannot drift
    - handler:   `async (str) -> str`, the shape `ToolRegistry.call` awaits
    - goals/needs/reversible/chains_with: the capability record fields, the same five
                 `test_skill_standard.py:27-32` validates for every shipped tool
    - raises ValueError on any refusal; never half-registers

    Refusals, all three specified by the brief plus one derived from blueprint §3.6:
      R1  a name that is not `is_valid_task_name`-SHAPED (the regex half only — the
          collision half cannot apply to a name that does not exist yet)
      R2  a name colliding with an existing tool
      R3  a name in `IRREVERSIBLE_TOOLS` — "never registerable, zero exceptions"
      R4  `reversible=False` — blueprint §3.6: the irreversible tier is "never
          reachable by synthesis — closed by construction"

    IDEMPOTENCY, stated because it is a design decision and not an obvious one:
    registering an ALREADY-REGISTERED name is a NO-OP, not a collision refusal. A
    naive collision check runs first and refuses the second call, which would make
    "registering twice" an error rather than an idempotent operation; the registry
    must therefore recognise its own registrations before it consults the collision
    surface. The first registration stands — a second call with different arguments
    does not overwrite it. Pinned by `test_registering_the_same_name_twice_is_a_no_op`.

    A NOTE ON R3, recorded because it is a finding and not a test: at this boundary R3
    is UNOBSERVABLE. `IRREVERSIBLE_TOOLS ⊆ TOOL_CAPABILITIES ⊆ valid_tools()`
    (`tests/test_evolution_task.py:292` already proves the first inclusion), so the
    collision check of R2 refuses all six names before any irreversibility check could
    run. `test_registration_refuses_every_irreversible_tool_name` still asserts the
    refusal — the guard documents the law and would catch a future reordering that
    weakened R2 — but the mutation run shows an implementation that omits the R3 check
    entirely is caught only by R4, not by R3. The law that is actually enforceable at
    this boundary is R4.

No socket, no HTTP, no wall clock, no subprocess, no file I/O. Every surface is read
off a live module attribute; nothing is cached between snapshots.
"""

from __future__ import annotations

from typing import Any

import pytest

from src import evolution
from src.cognition import _TOOL_GOALS
from src.dispatcher import _VALID_TOOLS
from src.skills import sara_tool_skills
from src.skills.capabilities import IRREVERSIBLE_TOOLS, TOOL_CAPABILITIES
from src.tools import ToolRegistry

TOOL_A = "p3d_gold_rate"
TOOL_B = "p3d_brew_jar"
MARKER_A = "زعتر"
MARKER_B = "كفّة"
HANDLER_PREFIX = "سجّلت الأداة"
GOAL_A = "قراءة سعر الذهب"
GOAL_B = "تحضير القهوة"


def _seam(symbol: str) -> Any:
    """Resolve a P3-D producer on `src.tool_overlay`; a missing one FAILS.

    Never skips: a skip would let an unbuilt phase report green, which is the exact
    failure mode §5.1 Directive 4 is written against.
    """
    import src.tool_overlay as overlay

    try:
        return getattr(overlay, symbol)
    except AttributeError:
        pytest.fail(
            f"src.tool_overlay.{symbol} does not exist yet — P3-D is RED. Registration "
            "needs an all-or-nothing entry point on the merge layer (missing producer: "
            f"src.tool_overlay.{symbol})."
        )


def _register(
    name: str,
    *,
    markers: tuple[str, ...],
    goals: str,
    handler: Any = None,
    needs: str = "local",
    reversible: bool = True,
    chains_with: tuple[str, ...] = (),
) -> None:
    """The one adaptation point for the specified signature. Keyword-only, so any
    parameter ORDER is accepted; a name mismatch raises `TypeError` here, naming the
    call, rather than silently skipping a guard."""
    if handler is None:
        handler = _handler(name)
    _seam("register_tool")(
        name=name,
        markers=markers,
        handler=handler,
        goals=goals,
        needs=needs,
        reversible=reversible,
        chains_with=chains_with,
    )


def _handler(name: str) -> Any:
    async def _run(arg: str) -> str:
        return f"{HANDLER_PREFIX}:{name}:{arg}"

    return _run


def _unregister(name: str) -> None:
    _seam("unregister_tool")(name=name)


def _register_a(**overrides: Any) -> None:
    _register(TOOL_A, markers=(MARKER_A,), goals=GOAL_A, **overrides)


def _register_b(**overrides: Any) -> None:
    _register(TOOL_B, markers=(MARKER_B,), goals=GOAL_B, **overrides)


# --- the live state, re-read every time -----------------------------------------


def _live_state() -> dict[str, Any]:
    """Every surface a registration can move, read LIVE off the module attributes.

    Nothing here is a value captured earlier: an implementation that restores by
    rebinding `dispatcher._VALID_TOOLS` back to an equal tuple, or by rebuilding a base
    capability record instead of putting the original object back, would satisfy a
    comparison against a cached value. `cap_ids` carries object IDENTITY for that
    reason — a rebuilt record is equal but not the same object, and "restored exactly"
    is the claim.
    """
    import src.dispatcher as disp
    import src.evolution as evo
    import src.skills.capabilities as caps
    import src.tool_overlay as overlay

    return {
        "OVERLAY": dict(overlay.OVERLAY),
        "valid_tools": set(overlay.valid_tools()),
        "tool_goals": dict(overlay.tool_goals()),
        "TOOL_CAPABILITIES": dict(TOOL_CAPABILITIES),
        "capability_ids": {k: id(v) for k, v in TOOL_CAPABILITIES.items()},
        "IRREVERSIBLE_TOOLS": set(caps.IRREVERSIBLE_TOOLS),
        "guide_names": tuple(filename for filename, _ in sara_tool_skills._SKILLS),
        "registry_handlers": frozenset(k for k in vars(ToolRegistry) if k.startswith("_do_")),
        "static_valid_tools": tuple(disp._VALID_TOOLS),
        "static_tool_goals": dict(_TOOL_GOALS),
        "collision_set": set(evo._COLLIDING_TOOL_NAMES),
        "name_is_valid": evolution.is_valid_task_name(TOOL_A),
    }


def _moved(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    """Per-key difference, so a failed restore NAMES the surface that moved."""
    return {key: (before[key], after[key]) for key in before if before[key] != after[key]}


@pytest.fixture(autouse=True)
def _registration_hygiene():
    """Restore every surface in a `finally`, independently of the seam existing.

    A registration that leaks would break the 2379-test suite rather than this file, so
    the guarantee has to be structural. The restore does not go through
    `unregister_tool`: a missing or broken `unregister_tool` must not also mean a
    leaked capability record in the rest of the suite.
    """
    import src.evolution as evo
    import src.skills.capabilities as caps
    import src.tool_overlay as overlay

    before = _live_state()
    try:
        yield
    finally:
        # Unwind THROUGH THE API first, when it exists. Hand-deleting the surfaces would
        # leave the implementation's own bookkeeping out of sync, and the next test's
        # identical registration would be refused as an idempotent repeat of something
        # this fixture already removed — a green failure that reads as a product bug.
        # The manual restore below stays as the backstop for the RED state, where there
        # is no such API to unwind through.
        if hasattr(overlay, "reset_overlay"):
            overlay.reset_overlay()
        for name in set(TOOL_CAPABILITIES) - set(before["TOOL_CAPABILITIES"]):
            del TOOL_CAPABILITIES[name]
        for name, record in before["TOOL_CAPABILITIES"].items():
            TOOL_CAPABILITIES[name] = record
        for attr in set(vars(ToolRegistry)) - before["registry_handlers"]:
            if attr.startswith("_do_"):
                delattr(ToolRegistry, attr)
        sara_tool_skills._SKILLS = tuple(
            (f, c) for f, c in sara_tool_skills._SKILLS if f not in set(before["guide_names"])
        ) + tuple((f, c) for f, c in sara_tool_skills._SKILLS if f in set(before["guide_names"]))
        caps.IRREVERSIBLE_TOOLS = frozenset(before["IRREVERSIBLE_TOOLS"])
        evo._COLLIDING_TOOL_NAMES = frozenset(before["collision_set"])
        overlay.OVERLAY.clear()
        overlay.OVERLAY.update(before["OVERLAY"])


# ==================================================================================
# 0. non-vacuity
# ==================================================================================


def test_the_control_registration_moved_every_registration_point() -> None:
    """Directive 2/4: can the harness fire at all. Without this control every
    "restores exactly" assertion below is satisfiable by a `register_tool` that does
    nothing at all — the strongest form of a vacuous green."""
    before = _live_state()
    _register_a()
    after = _live_state()
    for label, moved in (
        ("registry handler", after["registry_handlers"] - before["registry_handlers"]),
        ("capability record", set(after["TOOL_CAPABILITIES"]) - set(before["TOOL_CAPABILITIES"])),
        ("route allow-list", after["valid_tools"] - before["valid_tools"]),
        ("goal vocabulary", set(after["tool_goals"]) - set(before["tool_goals"])),
    ):
        assert moved, f"the {label} did not move — the registration is not landing"
    assert after["name_is_valid"] is False, "the collision surface is not live"


# ==================================================================================
# 1. all four points, or none
# ==================================================================================


def test_registration_populates_all_four_registration_points() -> None:
    """The headline claim, asserted as one sentence so it is greppable. Each point is
    then asserted on its own in the four tests below, so a failure NAMES the point."""
    _register_a()
    assert TOOL_A in _seam("valid_tools")()
    assert TOOL_A in _seam("tool_goals")()
    assert TOOL_A in TOOL_CAPABILITIES
    assert getattr(ToolRegistry(), f"_do_{TOOL_A}", None) is not None


def test_registration_point_1_the_registry_can_getattr_a_handler() -> None:
    _register_a()
    assert getattr(ToolRegistry(), f"_do_{TOOL_A}", None) is not None, (
        f"registration point 1 (ToolRegistry._do_{TOOL_A}) is empty — ToolRegistry.call "
        "getattrs the handler at src/tools.py:138 and gets None"
    )


def test_registration_point_2_the_capability_registry_carries_the_record() -> None:
    _register_a()
    assert TOOL_A in TOOL_CAPABILITIES, (
        f"registration point 2 (TOOL_CAPABILITIES[{TOOL_A!r}]) is empty — markers_for "
        "returns () and the tool has no schema, guide or chains"
    )


def test_registration_point_3_the_route_allow_list_carries_the_name() -> None:
    _register_a()
    assert TOOL_A in _seam("valid_tools")(), (
        "registration point 3 (valid_tools()) is missing the name — a router verdict "
        'naming it is rewritten to "none" at src/dispatcher.py:740'
    )


def test_registration_point_4_the_goal_vocabulary_carries_the_markers() -> None:
    _register_a()
    goals = _seam("tool_goals")()
    assert TOOL_A in goals and MARKER_A in goals[TOOL_A], (
        "registration point 4 (tool_goals()) is missing the name or its markers — deduce "
        "iterates this map and can never propose a tool that is not in it"
    )


# ==================================================================================
# 2. the four-point trap: never half-register
# ==================================================================================

#: One entry per specified refusal reason, so the atomicity guard runs against each and
#: a name that moves reports which reason leaked. The reasons themselves are specified
#: in the module docstring (R1..R4) and each has its own test below.
REFUSAL_REASONS = (
    pytest.param("R1_bad_shape", "Gold-Rate", id="R1-bad-shape"),
    pytest.param("R2_collision", "gmail", id="R2-collision"),
    pytest.param("R3_irreversible", "close", id="R3-irreversible"),
    pytest.param("R4_irreversible_tier", TOOL_A, id="R4-reversible-false"),
)


@pytest.mark.parametrize("reason,name", REFUSAL_REASONS)
def test_a_refused_registration_leaves_no_registration_point_half_populated(
    reason: str, name: str
) -> None:
    """THE FOUR-POINT TRAP. A refused registration must move NOTHING. This is the whole
    reason the API has to be all-or-nothing: a partial write is a tool that parses,
    deduces and then fails at execution, with no exception anywhere along the way.

    Run once per refusal reason, so a name that moves reports the reason that leaked
    rather than a bare set difference."""
    before = _live_state()
    kwargs: dict[str, Any] = {}
    if reason == "R4_irreversible_tier":
        kwargs["reversible"] = False
    with pytest.raises(ValueError):
        _register(name, markers=(MARKER_A,), goals=GOAL_A, **kwargs)
    leaked = _moved(before, _live_state())
    assert not leaked, (
        f"a registration refused for {reason} still moved {sorted(leaked)} — a "
        "half-registration is worse than no registration: the tool is routed and "
        "selectable but answers nothing"
    )


def test_a_refusal_leaves_the_collision_surface_untouched_too() -> None:
    """The seventh surface, and the easiest to half-write: a registration that records
    the name in the collision union and then fails leaves the name reserved forever,
    because nothing will ever release it."""
    before = evolution.is_valid_task_name(TOOL_A)
    with pytest.raises(ValueError):
        _register_a(reversible=False)
    assert evolution.is_valid_task_name(TOOL_A) == before, (
        f"{TOOL_A!r} is now reserved by a registration that never completed — a leaked "
        "collision entry is unreleasable"
    )


class _RefusingCapabilities(dict):
    """`TOOL_CAPABILITIES` that refuses one key, to simulate a point that cannot be
    reached. A `dict` subclass, not a mock: `register_tool` legitimately reads this
    mapping (membership, `.get`) and only the WRITE of the named key must fail."""

    def __init__(self, real: dict, refused: str) -> None:
        super().__init__(real)
        self._refused = refused

    def __setitem__(self, key: str, value: Any) -> None:
        if key == self._refused:
            raise RuntimeError(f"capability registry is read-only for {key!r}")
        super().__setitem__(key, value)


def test_registration_refuses_and_names_the_point_it_cannot_reach(monkeypatch) -> None:
    """The other half of "all four or none": when a point genuinely cannot be reached,
    `register_tool` must REFUSE and NAME it. Silent partial progress with an unreadable
    cause is the failure this whole refactor exists to eliminate, so the refusal has to
    be legible — an operator who cannot tell which of the four points failed has the
    original problem with a new message.

    The failure is injected at registration point 2, the one surface the tree documents
    as runtime-mutable (`src/skills/capabilities.py:350`, "dict, mutable at runtime").
    Every module that holds a live binding to the registry is repointed at the refusing
    copy, so the injection lands whether the implementation imports the dict inside the
    function or holds it at module scope — a one-shot monkeypatch on one module would
    silently miss the other and the test would pass for the wrong reason."""
    import src.cognition as cog
    import src.evolution as evo
    import src.skills.capabilities as caps
    import src.tool_overlay as overlay

    refusing = _RefusingCapabilities(dict(TOOL_CAPABILITIES), TOOL_A)
    for module in (caps, overlay, evo, cog):
        if hasattr(module, "TOOL_CAPABILITIES"):
            monkeypatch.setattr(module, "TOOL_CAPABILITIES", refusing)

    before = _live_state()
    with pytest.raises(Exception) as caught:  # the exception TYPE is the implementer's
        _register_a()
    message = str(caught.value)
    assert TOOL_A in message, (
        f"the refusal does not name the tool it refused: {message!r} — an operator cannot "
        "act on a refusal that does not say what failed"
    )
    assert "capabilit" in message.lower() or "capabilit" in message, (
        f"the refusal does not name the registration point it could not reach: {message!r}"
    )
    leaked = _moved(before, _live_state())
    leaked.pop("TOOL_CAPABILITIES", None)  # the injected dict, not a leak
    leaked.pop("capability_ids", None)
    assert not leaked, (
        f"a registration that could not reach a point still moved {sorted(leaked)} — the "
        "write order must put the riskiest point first, or unwind what it already wrote"
    )


# ==================================================================================
# 3. the three specified refusals (+ the one derived from blueprint §3.6)
# ==================================================================================

#: Names the regex half of `is_valid_task_name` refuses. The list is the shape space,
#: not a sample: every entry fails `NAME_RE.fullmatch` today, and a registration that
#: accepts one of them has widened what a tool may be called.
BAD_SHAPES = [
    pytest.param("", id="empty"),
    pytest.param("ab", id="too-short"),
    pytest.param("Gmail", id="uppercase"),
    pytest.param("Gold-Rate", id="hyphen"),
    pytest.param("gold rate", id="space"),
    pytest.param("1tool", id="leading-digit"),
    pytest.param("_tool", id="underscore-leading"),
    pytest.param("a" * 41, id="41-chars"),
    pytest.param("أداة", id="arabic"),
]

#: Every name held by a live tool, derived — 46 routed plus the capability half. A
#: registration that takes one of these is a silent takeover of a shipped tool's
#: behaviour, which is what `is_valid_task_name`'s collision half exists to refuse.
LIVE_TOOL_NAMES = sorted(set(TOOL_CAPABILITIES) | set(_VALID_TOOLS))


@pytest.mark.parametrize("name", BAD_SHAPES)
def test_registration_refuses_a_name_that_is_not_task_name_shaped(name: str) -> None:
    """R1. The shape half of `NAME_RE` — the collision half cannot apply to a name that
    does not exist yet, so the gate here is the regex and nothing else."""
    assert evolution.NAME_RE.fullmatch(name) is None, "precondition: the name has the right shape"
    with pytest.raises(ValueError):
        _register(name, markers=(MARKER_A,), goals=GOAL_A)
    assert name not in TOOL_CAPABILITIES
    assert name not in _seam("valid_tools")()


@pytest.mark.parametrize("name", LIVE_TOOL_NAMES)
def test_registration_refuses_a_name_that_collides_with_a_live_tool(name: str) -> None:
    """R2. Parametrized over every live tool name, not a sample, so a hole names itself
    the way `tests/test_tool_overlay.py:125` does. The whole union is covered —
    reading only one of its two halves would let every routed-but-uncatalogued name
    through, which is the asymmetry `tests/test_evolution_task.py:274` already pins."""
    assert evolution.is_valid_task_name(name) is False, "precondition: the name collides"
    before = _live_state()
    with pytest.raises(ValueError):
        _register(name, markers=(MARKER_A,), goals=GOAL_A)
    # Nothing may move. Deliberately NOT `name in TOOL_CAPABILITIES`: four routed names
    # are absent from that registry by design (`analytics`, `cloud_backup`, `none`,
    # `quota_safety`), so requiring the membership would fail a correct refusal — and
    # for those four it would be the ONLY thing being checked, which is too thin a
    # guard for the routed-but-uncatalogued half of the union.
    assert not _moved(before, _live_state()), (
        f"a registration refused for colliding with {name!r} still moved "
        f"{sorted(_moved(before, _live_state()))}"
    )


@pytest.mark.parametrize("name", sorted(IRREVERSIBLE_TOOLS))
def test_registration_refuses_every_irreversible_tool_name(name: str) -> None:
    """R3 — Leader decision 6, zero exceptions. See the module docstring: at this
    boundary the refusal is already implied by R2 (the deny-list is a subset of both
    live registries), so this guard documents the law and would catch a future
    reordering that weakened the collision check. The enforceable form of the same law
    is `test_registration_refuses_to_create_an_irreversible_tool`."""
    assert name in IRREVERSIBLE_TOOLS
    assert name in set(TOOL_CAPABILITIES) and name in set(_VALID_TOOLS), (
        "the deny-list is no longer a subset of both live registries — the structural "
        "backstop this refusal leans on no longer holds"
    )
    with pytest.raises(ValueError):
        _register(name, markers=(MARKER_A,), goals=GOAL_A)


def test_registration_refuses_to_create_an_irreversible_tool() -> None:
    """R4 — the enforceable form of R3, derived from blueprint §3.6: "SOVERNIUM |
    Irreversible tier ... | Never reachable by synthesis — closed by construction".
    `IRREVERSIBLE_TOOLS` is a `Final` frozenset built at import, so a dynamically bound
    tool declaring `reversible=False` would enter `TOOL_CAPABILITIES` and NOT the
    deny-list — the confirmation gate would never see it. Refusing is the only way to
    keep the sentence true."""
    before = set(IRREVERSIBLE_TOOLS)
    with pytest.raises(ValueError):
        _register_a(reversible=False)
    assert TOOL_A not in TOOL_CAPABILITIES, "a refused registration still wrote a record"
    assert set(IRREVERSIBLE_TOOLS) == before


def test_the_refusal_message_names_the_tool_it_refused() -> None:
    """A refusal that does not say which name is unusable is a log line nobody can act
    on. Asserted on the refusal whose cause is NOT the name, so the message has to
    carry it deliberately rather than by echoing the call site."""
    with pytest.raises(ValueError) as caught:
        _register_a(reversible=False)
    assert TOOL_A in str(caught.value), f"the refusal message omits the name: {caught.value}"


# ==================================================================================
# 4. unregister restores the pre-registration state EXACTLY
# ==================================================================================


def test_unregister_restores_every_live_surface_exactly() -> None:
    """The headline restore claim. Every surface is re-read off the module AFTER the
    release — never compared against a value captured before the registration, which
    would let an implementation that "restores" by rebinding a module global to an equal
    value pass. `capability_ids` compares object IDENTITY, so a base capability record
    that was rebuilt rather than put back is caught too."""
    before = _live_state()
    _register_a()
    assert _moved(before, _live_state()), "precondition: the registration changed nothing"
    _unregister(TOOL_A)
    leaked = _moved(before, _live_state())
    assert not leaked, f"unregister left residue in {sorted(leaked)}: {leaked}"


def test_unregister_releases_only_the_named_tool() -> None:
    """Two registrations, one release: the survivor must be untouched on all four
    points. An `unregister` that cleared the overlay wholesale would satisfy every other
    test in this file and silently unregister the wrong tool."""
    _register_a()
    _register_b()
    _unregister(TOOL_A)
    assert TOOL_B in _seam("valid_tools")()
    assert TOOL_B in _seam("tool_goals")()
    assert TOOL_B in TOOL_CAPABILITIES
    assert getattr(ToolRegistry(), f"_do_{TOOL_B}", None) is not None
    assert TOOL_A not in _seam("valid_tools")()
    assert TOOL_A not in TOOL_CAPABILITIES
    assert getattr(ToolRegistry(), f"_do_{TOOL_A}", None) is None


def test_unregister_does_not_disturb_a_registration_it_never_made() -> None:
    """Releasing an unknown name must be inert, not destructive. This is also the
    second half of the idempotency requirement."""
    before = _live_state()
    _unregister("p3d_never_registered")
    assert not _moved(before, _live_state()), "releasing an unknown name disturbed the tree"


# ==================================================================================
# 5. idempotency
# ==================================================================================


def test_registering_the_same_name_twice_is_a_no_op() -> None:
    """The first registration stands and the second call changes nothing — including
    the handler, which is NOT overwritten. A naive implementation consults the collision
    surface first, sees its own registration there, and refuses; that is an error, not
    an idempotent operation, so the registry must recognise its own registrations
    before it consults the collision union."""
    _register_a()
    after_first = _live_state()
    _register_a()
    assert not _moved(after_first, _live_state()), "a second identical registration mutated state"

    async def replacement(arg: str) -> str:
        return "overwritten"

    _register_a(handler=replacement)
    assert not _moved(after_first, _live_state()), (
        "a second registration overwrote the first — idempotency means the second call "
        "is a no-op, not an update"
    )


def test_unregistering_twice_is_a_no_op() -> None:
    """The second release must not raise and must not touch anything. A release that
    raised on an unknown name would make cleanup code — a fixture, an error path — fail
    exactly when it is needed."""
    before = _live_state()
    _register_a()
    _unregister(TOOL_A)
    after_first = _live_state()
    assert not _moved(before, after_first), "precondition: the first release was not exact"
    _unregister(TOOL_A)
    assert not _moved(after_first, _live_state()), "a second release mutated state"


# ==================================================================================
# 6. reset_overlay still empties EVERYTHING, so test order cannot leak
# ==================================================================================


def test_reset_overlay_empties_a_registration_completely() -> None:
    """`reset_overlay` is the suite's only cleanup primitive, and P3-D widened what it
    has to clear from one dict to six surfaces. A reset that empties the overlay and
    leaves the capability record behind turns every test that follows — including the
    2379 that were green before P3-D — into a false failure whose cause is invisible.

    This is the leak the brief names, so it gets its own test rather than a `finally`."""
    before = _live_state()
    _register_a()
    _seam("reset_overlay")()
    leaked = _moved(before, _live_state())
    assert not leaked, f"reset_overlay left residue in {sorted(leaked)}: {leaked}"


def test_reset_overlay_empties_two_registrations_at_once() -> None:
    """One reset, both tools gone. A reset that released only the most recent
    registration would look exact for a single-tool test and leak under a second."""
    before = _live_state()
    _register_a()
    _register_b()
    _seam("reset_overlay")()
    assert not _moved(before, _live_state())


def test_the_overlay_starts_empty_despite_a_registration_in_the_previous_test() -> None:
    """Order-independence, exercised rather than promised. The autouse fixture resets
    before every test, so a leaked registration from ANY earlier test in this file —
    or in the file that runs before it — is invisible here. If the fixture ever stops
    resetting, this is the test that notices."""
    import src.tool_overlay as overlay

    assert overlay.OVERLAY == {}, f"the overlay leaked into this test: {overlay.OVERLAY}"
    assert TOOL_A not in TOOL_CAPABILITIES
    assert TOOL_B not in TOOL_CAPABILITIES
    assert getattr(ToolRegistry(), f"_do_{TOOL_A}", None) is None
    assert evolution.is_valid_task_name(TOOL_A) is True
