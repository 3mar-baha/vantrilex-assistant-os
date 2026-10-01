"""P3-C guards: the registration overlay refactor must ship EMPTY and lose nothing.

Today a synthesized tool is unrunnable. Registering one needs four edits, and two
of them are `Final` literals that are NOT runtime-mutable:

    1. ToolRegistry.call -> getattr(self, f"_do_{tool}")   src/tools.py:138
    2. TOOL_CAPABILITIES[<name>]   src/skills/capabilities.py:350  (mutable dict)
    3. _VALID_TOOLS                src/dispatcher.py:123   (Final tuple)
    4. _TOOL_GOALS[<name>]         src/cognition.py:30     (Final dict)

A tool registered only in (2) can never be SELECTED, because `deduce` iterates
(4). A name outside (3) is silently rewritten to `"none"` at `src/dispatcher.py:730`
with no exception raised. Neither failure raises, so neither is a crash you can
smell from CI — they are a tool that silently does nothing.

P3-C makes (3) and (4) read through a merge layer owned by a new shared module
(`src/tool_overlay.py`; `src.dispatcher` already imports `src.cognition`, and
cognition does not import dispatcher, so a third module is the only placement
with no import cycle). P3-D enables an actual tool. This phase proves the
refactor is regression-free with the overlay EMPTY.

Contract this file pins (the implementer builds to it):

    OVERLAY: dict[str, tuple[str, ...]]   # name -> goal markers, mutable
    def valid_tools() -> tuple[str, ...]  # _VALID_TOOLS merged with OVERLAY keys
    def tool_goals() -> dict[str, tuple[str, ...]]  # _TOOL_GOALS merged with OVERLAY
    def reset_overlay() -> None

`_VALID_TOOLS` and `_TOOL_GOALS` KEEP THEIR NAMES AND TYPES and remain the
STATIC BASE — test modules import them by name, so renaming breaks all of them.
Only the production consumers move to the accessors; these guards read the base
directly, which is correct precisely BECAUSE the overlay is empty. P3-D updates
them.

Every count in the header table above is re-derived from the live registries at
collection time. No number here is hardcoded (Directive 6).
"""

from __future__ import annotations

import json
import sys
import textwrap

import pytest

from src.cognition import _TOOL_GOALS
from src.dispatcher import _VALID_TOOLS

# --- Derived ground truth (Directive 6: re-derived from the tree, never asserted) ---

#: 46 names today. It splices `*VALID_OPENCLAW_TOOLS` at src/dispatcher.py:168.
EXPECTED_VALID_TOOL_COUNT = 46
#: 37 goal keys today; values are tuples of str.
EXPECTED_GOAL_KEY_COUNT = 37

#: A name guaranteed absent from every registry, so adding it to the overlay is
#: provably additive and provably not a rename of something real.
SENTINEL = "p3c_synthetic_probe"
SENTINEL_MARKER = "p3c_probe_marker"
SENTINEL_GOALS = "فحص الاستعلام التجريبي"


async def _sentinel_handler(arg: str) -> str:
    """The `async (str) -> str` shape `ToolRegistry.call` awaits. Never invoked by
    the guards below — registration binds a handler, it does not call it."""
    return f"sentinel:{arg}"


def _overlay():
    """Import the P3-C overlay module, or fail naming the missing producer.

    Directive 4: unreachability is stated at the call site naming what is
    missing, not in a report. A module-level `import src.tool_overlay` would
    abort collection with a bare ImportError and the individual guards would
    never be seen failing (Directive 2). A pytest FIXTURE was tried first and
    rejected: a fixture that fails reports as ERROR, which reads as "broken test
    file" rather than "guard not satisfied". Calling this at the top of each test
    body keeps every guard a FAILED with its own message.
    """
    try:
        import src.tool_overlay as mod
    except ModuleNotFoundError as exc:  # pragma: no cover -- the RED path, gone post-P3-C
        pytest.fail(
            "src/tool_overlay.py does not exist yet — P3-C is RED. The merge layer "
            "must expose OVERLAY, valid_tools(), tool_goals(), reset_overlay() "
            f"(missing producer: {exc.name})."
        )
    return mod


@pytest.fixture(autouse=True)
def _overlay_hygiene():
    """Order-independence, structurally.

    The overlay is process-global state, so a test that mutates it can leak into
    whatever runs next. Resetting before AND after every test makes the guarantee
    a property of the fixture rather than a promise in a docstring. Tolerates the
    RED state so it does not mask the per-test failure message.
    """
    try:
        import src.tool_overlay as mod
    except ModuleNotFoundError:
        yield
        return
    mod.reset_overlay()
    yield
    mod.reset_overlay()


# --------------------------------------------------------------------------------------
# 0. the base registries still hold their derived shape
# --------------------------------------------------------------------------------------


def test_valid_tools_has_the_derived_count():
    assert len(_VALID_TOOLS) == EXPECTED_VALID_TOOL_COUNT
    assert len(set(_VALID_TOOLS)) == EXPECTED_VALID_TOOL_COUNT, "duplicate tool name"


def test_tool_goals_has_the_derived_count_and_value_shape():
    assert len(_TOOL_GOALS) == EXPECTED_GOAL_KEY_COUNT
    assert all(isinstance(v, tuple) for v in _TOOL_GOALS.values())
    assert all(isinstance(m, str) for v in _TOOL_GOALS.values() for m in v)


# --------------------------------------------------------------------------------------
# 1. THE ZERO-REGRESSION GUARD — the most important test in this set
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("tool", _VALID_TOOLS)
def test_every_static_tool_survives_the_merge(tool):
    """Parametrized, not one aggregate assert, so a dropped name NAMES ITSELF.

    An aggregate `assert merged == base` that fails reports a set difference and
    leaves you to diff it by hand; this reports the exact tool that vanished.
    """
    ov = _overlay()
    assert tool in _VALID_TOOLS
    assert tool in ov.valid_tools(), f"{tool!r} lost by the merge"


def test_merged_valid_tools_invents_nothing():
    ov = _overlay()
    invented = set(ov.valid_tools()) - set(_VALID_TOOLS)
    assert not invented, f"merge invented tools not in the static base: {sorted(invented)}"


def test_merged_valid_tools_loses_nothing():
    ov = _overlay()
    lost = set(_VALID_TOOLS) - set(ov.valid_tools())
    assert not lost, f"merge dropped static tools: {sorted(lost)}"


def test_merged_valid_tools_equals_static_set_exactly():
    """The equality, stated as one claim so the headline guard is greppable."""
    ov = _overlay()
    assert set(ov.valid_tools()) == set(_VALID_TOOLS)


# --------------------------------------------------------------------------------------
# 2. _TOOL_GOALS parity
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("tool", sorted(_TOOL_GOALS))
def test_every_static_goal_entry_survives_the_merge(tool):
    ov = _overlay()
    merged = ov.tool_goals()
    assert tool in merged, f"{tool!r} goal entry lost by the merge"
    assert merged[tool] == _TOOL_GOALS[tool], f"{tool!r} goal markers altered"
    assert isinstance(merged[tool], tuple)


def test_merged_tool_goals_invents_no_key():
    ov = _overlay()
    invented = set(ov.tool_goals()) - set(_TOOL_GOALS)
    assert not invented, f"merge invented goal keys: {sorted(invented)}"


def test_merged_tool_goals_loses_no_key():
    ov = _overlay()
    lost = set(_TOOL_GOALS) - set(ov.tool_goals())
    assert not lost, f"merge dropped goal keys: {sorted(lost)}"


def test_merged_tool_goals_equals_static_mapping_exactly():
    ov = _overlay()
    assert dict(ov.tool_goals()) == dict(_TOOL_GOALS)


# --------------------------------------------------------------------------------------
# 3. the overlay ships EMPTY
# --------------------------------------------------------------------------------------


def test_overlay_ships_empty():
    """P3-C ships the seam, not a tool. An entry here is a P3-D change smuggled in."""
    ov = _overlay()
    assert ov.OVERLAY == {}, f"P3-C must ship an empty overlay, found {ov.OVERLAY}"


def test_merged_views_are_identical_to_base_at_import():
    ov = _overlay()
    assert set(ov.valid_tools()) == set(_VALID_TOOLS)
    assert dict(ov.tool_goals()) == dict(_TOOL_GOALS)


def test_reset_overlay_on_a_clean_overlay_is_a_no_op():
    ov = _overlay()
    ov.reset_overlay()
    assert ov.OVERLAY == {}
    assert set(ov.valid_tools()) == set(_VALID_TOOLS)


def test_reset_overlay_empties_a_mutated_overlay():
    """Proves reset actually resets, not merely that nothing was there."""
    ov = _overlay()
    ov.OVERLAY[SENTINEL] = (SENTINEL_MARKER,)
    assert SENTINEL in ov.valid_tools(), "precondition: mutation landed"
    ov.reset_overlay()
    assert ov.OVERLAY == {}
    assert SENTINEL not in ov.valid_tools()


def test_mutation_then_reset_leaves_merged_equal_to_base():
    """Order-independence, exercised: a dirty neighbour cannot poison a later read."""
    ov = _overlay()
    ov.OVERLAY[SENTINEL] = (SENTINEL_MARKER,)
    ov.reset_overlay()
    assert set(ov.valid_tools()) == set(_VALID_TOOLS)
    assert dict(ov.tool_goals()) == dict(_TOOL_GOALS)


# --------------------------------------------------------------------------------------
# 4. merge semantics, proven on a throwaway overlay — never on production state
# --------------------------------------------------------------------------------------


def test_overlay_tool_joins_the_merge_without_touching_the_base():
    """The only test allowed to mutate the overlay. Restoration is proven HERE, in
    the same test, not delegated to a fixture — a finally-restore that silently
    no-ops would leave every later test green and wrong."""
    ov = _overlay()
    assert SENTINEL not in _VALID_TOOLS, "sentinel collides with a real tool"
    base_before = _VALID_TOOLS

    ov.OVERLAY[SENTINEL] = (SENTINEL_MARKER,)
    try:
        assert SENTINEL in ov.valid_tools(), "overlay tool must join the merge"
        assert SENTINEL not in _VALID_TOOLS, "merge leaked into the static base"
        assert _VALID_TOOLS == base_before
        assert dict(ov.tool_goals())[SENTINEL] == (SENTINEL_MARKER,)
        # Re-read the LIVE module attributes, not this file's import-time binding:
        # an implementation that "merges" by rebinding `dispatcher._VALID_TOOLS`
        # to a larger tuple leaves the local binding intact and would otherwise
        # sneak past the three asserts above.
        import src.cognition as cog
        import src.dispatcher as disp

        assert SENTINEL not in disp._VALID_TOOLS, "base constant was rebound, not merged"
        assert disp._VALID_TOOLS == base_before
        assert SENTINEL not in cog._TOOL_GOALS, "goal base was mutated, not merged"
    finally:
        ov.reset_overlay()

    assert ov.OVERLAY == {}, "the test failed to restore the overlay"
    assert SENTINEL not in ov.valid_tools()
    assert set(ov.valid_tools()) == set(_VALID_TOOLS)
    assert dict(ov.tool_goals()) == dict(_TOOL_GOALS)


def test_overlay_goals_union_with_static_goals_rather_than_shadowing_them():
    """REQUIRED SEMANTICS: a colliding overlay key must UNION its markers with the
    static ones, not replace them.

    Union is the contract for two reasons already present in the tree:
    `_goal_markers` (src/cognition.py:399) unions the inline goal family with the
    capability registry via `dict.fromkeys`, so "merge two goal sources" already has
    a house convention; and replacement would silently SHRINK a tool's detection
    vocabulary on an accidental key collision — a silent degradation of exactly the
    kind this refactor exists to eliminate. A plain `dict(base) | overlay` is
    therefore NOT an acceptable implementation.
    """
    ov = _overlay()
    probe = min(_TOOL_GOALS)
    original = _TOOL_GOALS[probe]
    ov.OVERLAY[probe] = ("only_a_probe_marker",)
    try:
        merged = ov.tool_goals()[probe]
        assert set(original) <= set(merged), "static markers dropped on collision"
        assert "only_a_probe_marker" in merged
    finally:
        ov.reset_overlay()
    assert dict(ov.tool_goals()) == dict(_TOOL_GOALS)


def test_overlay_mutation_does_not_alias_the_base_object():
    """A merged view must be a copy. Aliasing would let a caller mutate the base
    through what looks like a read-only accessor."""
    ov = _overlay()
    ov.OVERLAY[SENTINEL] = (SENTINEL_MARKER,)
    try:
        ov.valid_tools()  # build the merged view
        assert SENTINEL not in _VALID_TOOLS
        assert len(_VALID_TOOLS) == EXPECTED_VALID_TOOL_COUNT
    finally:
        ov.reset_overlay()


# --------------------------------------------------------------------------------------
# 5. type compatibility — the test modules that import the base depend on exactly
#    `in`, iteration and set() over it, so the accessor must support all three.
# --------------------------------------------------------------------------------------


def test_accessor_supports_membership():
    ov = _overlay()
    for tool in _VALID_TOOLS:
        assert tool in ov.valid_tools()


def test_accessor_supports_iteration():
    ov = _overlay()
    assert list(ov.valid_tools()) == list(_VALID_TOOLS)
    assert list(iter(ov.tool_goals())) == list(_TOOL_GOALS)


def test_accessor_supports_set_construction():
    ov = _overlay()
    assert set(ov.valid_tools()) == set(_VALID_TOOLS)
    assert set(ov.tool_goals()) == set(_TOOL_GOALS)


def test_accessor_supports_len_and_indexing():
    ov = _overlay()
    merged = ov.valid_tools()
    assert len(merged) == len(_VALID_TOOLS)
    assert merged[0] == _VALID_TOOLS[0]
    assert isinstance(ov.tool_goals(), dict)


def test_accessor_keeps_the_base_tuple_type():
    """`return set(...)` is NOT a drop-in for the importing test modules: they rely
    on ordering and on tuple semantics. The accessor must return a tuple."""
    ov = _overlay()
    assert isinstance(ov.valid_tools(), tuple)


def test_accessor_preserves_static_order():
    """Base order is load-bearing for prompt-adjacent readers; the overlay appends.

    Repaired 2026-09-30. The first version read `valid_tools()` against an EMPTY
    overlay, so `merged[:len(_VALID_TOOLS)] == _VALID_TOOLS` held whether the
    implementation appended or PREPENDED — the guard could not observe the
    property its name claimed. Proof it was blind: injecting a prepending
    `return (*extra, *_VALID_TOOLS)` left it green.

    The overlay now carries a sentinel before the read, so the tail is observable
    and a prepend fails the suffix assertion instead of passing silently.
    """
    ov = _overlay()
    ov.OVERLAY[SENTINEL] = (SENTINEL_MARKER,)
    merged = ov.valid_tools()
    assert len(merged) == len(_VALID_TOOLS) + 1, "the overlay entry was dropped, not merged"
    assert merged[: len(_VALID_TOOLS)] == _VALID_TOOLS, "the static base was reordered"
    assert merged[len(_VALID_TOOLS) :] == (SENTINEL,), "the overlay did not append after the base"
    assert set(merged) == set(_VALID_TOOLS) | {SENTINEL}


def test_accessor_results_are_not_cached_across_calls():
    """A memoised merge would keep serving a stale view after a mutation."""
    ov = _overlay()
    ov.OVERLAY[SENTINEL] = (SENTINEL_MARKER,)
    try:
        first = ov.valid_tools()
        ov.OVERLAY["p3c_second_probe"] = (SENTINEL_MARKER,)
        second = ov.valid_tools()
        assert "p3c_second_probe" not in first
        assert "p3c_second_probe" in second
    finally:
        ov.reset_overlay()


# --------------------------------------------------------------------------------------
# 6. THE TRAP — measured, not assumed
# --------------------------------------------------------------------------------------


def test_parallel_scouts_registration_literal_expectation_is_fixture_scoped(tmp_path):
    """tests/test_parallel_scouts.py:218/:220 asserts an exact symbol set, so it
    LOOKS like a P3-C landmine. MEASURED: it is not.

    That test builds a synthetic repo under `tmp_path` via `_tree()` and calls
    `lps.find_registration_literals(root)` on it. Every call site in the file
    passes a temp fixture — none reads the live `src/`. This test reproduces the
    same assertion against the same fixture shape to prove it stays green no matter
    what P3-C does to the real tree.
    """
    import scripts.launch_parallel_scouts as lps

    fixture = {
        "src/dispatcher.py": '''
            """Tool routing table."""

            from __future__ import annotations

            from typing import Final

            _VALID_TOOLS: Final = ("none", "gmail", "launch")
            _FRESH_MARKERS: Final[tuple[str, ...]] = ("هسا", "الحين")
            ''',
        "src/cognition.py": '''
            """Goal lexicon per tool."""

            from __future__ import annotations

            from typing import Final

            _TOOL_GOALS: Final[dict[str, tuple[str, ...]]] = {
                "gmail": ("mail", "inbox"),
                "launch": ("open",),
            }
            _FRESH_MARKERS: Final[tuple[str, ...]] = ("هسا", "الحين")
            ''',
    }
    root = tmp_path / "synthetic_repo"
    for rel, body in fixture.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(textwrap.dedent(body), encoding="utf-8")

    found = lps.find_registration_literals(root)
    symbols = {f.symbol for f in found}
    hot = {f.symbol for f in found if "hot spot" in f.detail}
    assert symbols == {"_VALID_TOOLS", "_TOOL_GOALS", "_FRESH_MARKERS"}
    assert hot == {"_VALID_TOOLS", "_TOOL_GOALS"}


def test_live_registration_symbol_sets_are_decoupled_from_the_fixture_expectation():
    """The live tree's Final-container sets are LARGER than the fixture's, which is
    the proof that the parallel-scouts expectation does not read the live tree.
    Any P3-C change to the live tree therefore cannot move it."""
    import scripts.launch_parallel_scouts as lps

    found = lps.find_registration_literals(lps.REPO)
    live_dispatcher = {f.symbol for f in found if f.path == "src/dispatcher.py"}
    live_cognition = {f.symbol for f in found if f.path == "src/cognition.py"}
    live_hot = {f.symbol for f in found if "hot spot" in f.detail}

    assert "_VALID_TOOLS" in live_dispatcher
    assert "_TOOL_GOALS" in live_cognition
    assert {"_VALID_TOOLS", "_TOOL_GOALS"} <= live_hot
    # Decoupled: the live sets are strictly larger than the fixture's 3 / 2.
    assert live_dispatcher != {"_VALID_TOOLS", "_TOOL_GOALS", "_FRESH_MARKERS"}
    assert len(live_hot) > 2


def test_both_overlay_targets_are_still_detected_as_hot_spots():
    """If the refactor moves these literals, this detector is the pre-existing
    signal that would need re-pointing. Encode it so P3-C cannot lose the thread."""
    import scripts.launch_parallel_scouts as lps

    hot = {f.symbol for f in lps.find_registration_literals(lps.REPO) if "hot spot" in f.detail}
    assert "_VALID_TOOLS" in hot
    assert "_TOOL_GOALS" in hot


def test_both_overlay_target_modules_import_without_a_cycle():
    """The placement premise: a third module is importable from BOTH consumers
    because dispatcher imports cognition and cognition does not import dispatcher."""
    import src.cognition as cog
    import src.dispatcher as disp

    assert hasattr(disp, "_VALID_TOOLS")
    assert hasattr(cog, "_TOOL_GOALS")
    assert "src.cognition" not in sys.modules.get("src.dispatcher").__dict__.values()


# --------------------------------------------------------------------------------------
# 7. two latent constraints that will bite P3-D, not P3-C
# --------------------------------------------------------------------------------------


def test_router_prompt_constraint_holds_and_now_tracks_the_overlay():
    """INVERTED 2026-10-01 (P3-D). The old claim was: the router prompt is BLIND to
    the overlay, so a registered tool "can never be emitted, because the router may
    only name tools its catalog lists". That was the DEFECT, not the law — and its
    own assertion said so ("if this now passes, the prompt was extended and this
    doc-test is stale"). The static literal is still blind, deliberately; the
    COMPOSED prompt is not.

    Why the literal stays blind, and why that is not a hole: `_ROUTER_PROMPT_AR` is
    a `Final` hand-maintained catalog whose text other guards pin, so the overlay is
    APPENDED at the call site by `router_prompt()` instead of spliced into it. The
    law is therefore about the prompt the gateway actually receives — which is what
    `tests/test_p3d_seams.py` asserts on `gw.router_calls`. Composing at the call
    site is also what keeps that byte-identity guard NON-VACUOUS: it compares the
    base literal the module still holds against what is sent, so an implementation
    that rebinds the module attribute would satisfy the comparison against itself.

    Three claims, in order: the base still names every static tool; a registered
    tool is named; and releasing it removes exactly that one name.
    """
    from src.dispatcher import _ROUTER_PROMPT_AR, router_prompt

    ov = _overlay()
    missing = [t for t in _VALID_TOOLS if t not in _ROUTER_PROMPT_AR]
    assert not missing, f"tools invisible to the router: {missing}"

    assert ov.OVERLAY == {}, "precondition: the overlay is empty"
    assert router_prompt() == _ROUTER_PROMPT_AR, (
        "an empty overlay must compose to the static base byte for byte — a fix that "
        "rewrites the base changes the catalog for every turn, registered or not"
    )

    ov.register_tool(
        SENTINEL,
        (SENTINEL_MARKER,),
        _sentinel_handler,
        goals="فحص الاستعلام التجريبي",
        needs="none",
        reversible=True,
        chains_with=(),
    )
    try:
        assert SENTINEL in router_prompt(), (
            f"{SENTINEL!r} is registered and absent from the composed router prompt — the "
            "router may only name a tool its catalog lists, so an unnameable tool is "
            "UNREACHABLE from the router lane however well the allow-list accepts it"
        )
        missing_after = [t for t in ov.valid_tools() if t not in router_prompt()]
        assert not missing_after, f"routable but unnameable by the router: {missing_after}"
    finally:
        ov.reset_overlay()

    assert SENTINEL not in router_prompt(), (
        "the composed prompt still advertises a released tool — the composition is "
        "memoised or baked rather than read live"
    )
    assert router_prompt() == _ROUTER_PROMPT_AR


def test_capability_constraint_holds_for_every_registered_tool():
    """INVERTED 2026-10-01 (P3-D). The old claim was: the capability guard is blind
    to the overlay, "so an overlay tool skips the capability schema entirely". Same
    inversion, same reason: blindness was the defect and the guard said so itself.

    What is NOT inverted is the hazard the old test documented. A name written
    straight into `OVERLAY` — bypassing `register_tool` — is still routable and
    still selectable with no capability record, no handler and no narration guide.
    That is a real half-registration, and the honest post-P3-D law is that
    `register_tool` is what closes it: the low-level seam is reachable, and the
    public entry point is the thing that keeps the five other surfaces in step.
    """
    from src.skills.capabilities import TOOL_CAPABILITIES

    ov = _overlay()
    missing = [t for t in _TOOL_GOALS if t not in TOOL_CAPABILITIES]
    assert not missing, f"tools without capabilities: {missing}"

    ov.OVERLAY[SENTINEL] = (SENTINEL_MARKER,)
    try:
        still_missing = [t for t in ov.tool_goals() if t not in TOOL_CAPABILITIES]
        assert still_missing == [SENTINEL], (
            "a raw OVERLAY write is expected to leave a tool with no capability record "
            "— that bypass is the hazard `register_tool` exists to close, and if this "
            "now passes the low-level seam changed shape"
        )
    finally:
        ov.reset_overlay()

    ov.register_tool(
        SENTINEL,
        (SENTINEL_MARKER,),
        _sentinel_handler,
        goals="فحص الاستعلام التجريبي",
        needs="none",
        reversible=True,
        chains_with=(),
    )
    try:
        still_missing = [t for t in ov.tool_goals() if t not in TOOL_CAPABILITIES]
        assert not still_missing, f"registered tools without capabilities: {still_missing}"
        record = TOOL_CAPABILITIES[SENTINEL]
        assert record["markers"] == (SENTINEL_MARKER,), record
        assert record["reversible"] is True, record
    finally:
        ov.reset_overlay()

    assert SENTINEL not in TOOL_CAPABILITIES, "reset_overlay left the capability record"


def test_capability_registry_is_a_strict_subset_of_valid_tools():
    """Documents the asymmetry both existing guards lean on: fewer capabilities than
    routed names, with the difference non-empty. `cap - valid` is empty.

    GUARD REWRITTEN 2026-10-01 (Phase 0, QW-7), loudly. This test previously
    asserted the routed-but-uncatalogued set was exactly
    `{analytics, cloud_backup, none, quota_safety}`. Read its name against its
    assertion: the NAME states the law — the capability registry is a STRICT
    subset of the routed set — while the assertion pinned one week's measurement
    of the gap. It therefore encoded a snapshot as if it were a law, and
    enforcing it made the defect it documented permanent: three of those four had
    live `_do_<name>` handlers, and because `IRREVERSIBLE_TOOLS` is DERIVED from
    `TOOL_CAPABILITIES`, none of them could reach the deny-list at all —
    `cloud_backup`'s vault-snapshot upload executed unconfirmed. Directive 5 calls
    this a test that pins a bug, and the repair is to delete the pin, not the fix.

    What survives is the law itself, and it is now DERIVED rather than asserted:
    the gap must be exactly `INTERNAL_ONLY_TOOLS` — the routed names that are
    explicitly not tools. `none` is that name today, so the asymmetry the
    neighbouring guards lean on is intact (it is non-empty, and
    `tests/test_evolution_task.py:264` and `tests/test_p3d_seams.py:693` both
    require a non-empty gap and still pass). The four-name literal is gone
    because a fifth uncatalogued tool must now fail
    `tests/test_tool_catalog_completeness.py` rather than be absorbed here.
    """
    from src.skills.capabilities import INTERNAL_ONLY_TOOLS, TOOL_CAPABILITIES

    assert set(TOOL_CAPABILITIES) <= set(_VALID_TOOLS)
    assert set(_VALID_TOOLS) - set(TOOL_CAPABILITIES) == set(INTERNAL_ONLY_TOOLS)
    assert INTERNAL_ONLY_TOOLS, (
        "the gap must stay non-empty — it is what proves a guard reading only "
        "TOOL_CAPABILITIES would let a routed name through"
    )


# --------------------------------------------------------------------------------------
# 8. the refactor must be able to FIRE — Directive 4: does it exist, can it fire
# --------------------------------------------------------------------------------------


def test_router_verdict_no_longer_silently_rewrites_an_overlay_tool():
    """src/dispatcher.py:730 rewrites an unknown name to "none" with NO exception.
    That silent rewrite is the defect P3-C exists to remove, so the guard lives on
    the real seam: a router verdict naming an overlay tool must survive parsing."""
    from src.dispatcher import _parse_router

    ov = _overlay()
    ov.OVERLAY[SENTINEL] = (SENTINEL_MARKER,)
    try:
        raw = json.dumps({"route": "tier2", "tool": SENTINEL, "ack": "تمام"}, ensure_ascii=False)
        verdict = _parse_router(raw)
        assert verdict is not None
        assert verdict[2] == SENTINEL, "overlay tool was silently rewritten"
    finally:
        ov.reset_overlay()


def test_router_verdict_still_rewrites_a_genuinely_unknown_tool():
    """The control. If this passed trivially, the test above would prove nothing."""
    from src.dispatcher import _parse_router

    raw = json.dumps(
        {"route": "tier2", "tool": "p3c_never_registered", "ack": "تمام"}, ensure_ascii=False
    )
    verdict = _parse_router(raw)
    assert verdict is not None
    assert verdict[2] == "none"


def test_decision_loop_no_longer_rejects_an_overlay_tool():
    """src/decision_loop.py:217 rejects a thought tool outside `_VALID_TOOLS`
    (returns None, silently). Same defect, second surface."""
    from src.decision_loop import parse_thought

    ov = _overlay()
    ov.OVERLAY[SENTINEL] = (SENTINEL_MARKER,)
    try:
        raw = json.dumps(
            {"action": {"tool": SENTINEL, "arg": "x"}, "final": True}, ensure_ascii=False
        )
        parsed = parse_thought(raw)
        assert parsed is not None, "overlay tool rejected by the decision loop"
        assert parsed["action"]["tool"] == SENTINEL
    finally:
        ov.reset_overlay()


def test_decision_loop_still_rejects_a_genuinely_unknown_tool():
    """The control, same reason as above."""
    from src.decision_loop import parse_thought

    raw = json.dumps(
        {"action": {"tool": "p3c_never_registered", "arg": "x"}, "final": True},
        ensure_ascii=False,
    )
    assert parse_thought(raw) is None


def test_deduction_can_select_an_overlay_tool():
    """`deduce` iterates `_TOOL_GOALS` (src/cognition.py:416). A tool in the overlay
    only, with real goal markers, must become selectable — otherwise registration
    point (2) alone still yields an unrunnable tool. Measured: one unique marker
    scores 0.30, above the 0.12 no-trust floor at src/cognition.py:536."""
    from src.cognition import deduce

    ov = _overlay()
    probe = "بروفه"  # one unique marker, absent from every static goal family
    ov.OVERLAY["p3c_deducible"] = (probe,)
    try:
        hyp = deduce(probe)
        assert hyp.tool == "p3c_deducible", f"got {hyp.tool!r} — overlay tool not selectable"
    finally:
        ov.reset_overlay()


def test_overlay_tool_stays_out_of_the_static_registries_after_reset():
    """Belt-and-braces: after reset, the static registries hold their derived shape
    and neither sentinel leaked in."""
    assert len(_VALID_TOOLS) == EXPECTED_VALID_TOOL_COUNT
    assert len(_TOOL_GOALS) == EXPECTED_GOAL_KEY_COUNT
    assert SENTINEL not in _VALID_TOOLS
    assert SENTINEL not in _TOOL_GOALS
