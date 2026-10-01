"""P3-D guards: the three seams P3-C named UNREACHABLE, plus the registration seam.

P3-C shipped a merge layer (`src/tool_overlay.py`) that keeps points 3 and 4 of the
four-point registration table editable at runtime, and stated the remaining
unreachability AT THE CALL SITE (Directive 4). This file is the RED barrier for
closing it. The three seams, each MEASURED on 2026-10-01 against the live tree:

SEAM 1 — `src/dispatcher.py:868`. A router verdict naming an overlay tool now
SURVIVES parsing (P3-C moved the allow-list to `valid_tools()`), but the router can
never EMIT one: `_ROUTER_PROMPT_AR` is a `Final` string literal, and a model may
only name tools its catalog lists. MEASURED: the system prompt handed to the gateway
is byte-identical to that literal whether the overlay holds one tool or forty, and
the overlay name is ABSENT from it. The tool is parsed-but-unnameable — the same
silent loss as the original `"none"` rewrite, one layer up.

SEAM 2 — `src/cognition.py:418`. `deduce` iterates the merged `tool_goals()`, so an
overlay tool is *selectable* (MEASURED: one unique marker scores 0.30, above the
0.12 no-trust floor at `src/cognition.py:550`). But `_goal_markers`
(`src/cognition.py:400`) unions `markers_for(tool)` on top of the inline family, and
`markers_for` reads `TOOL_CAPABILITIES` — MEASURED: `()` for an unregistered name, so
the tool gets no capability schema, no narration guide, and no `_do_<name>` binding.
MEASURED: `ToolRegistry.call(<overlay tool>)` returns `TOOL_FAIL_AR`. "Selectable" is
not "runnable", and the two are different properties of one registration.

SEAM 3 — `src/evolution.py:253`. `_COLLIDING_TOOL_NAMES` is an IMPORT-TIME `Final`
frozenset, so a name registered after import is not yet a collision surface.
MEASURED: `is_valid_task_name("p3d_gold_rate")` is `True` before the registration and
is STILL `True` after it — a task may be proposed for a tool that already exists, and
`EvolutionTask.__post_init__` accepts it too.

WHAT "REACHABLE" MEANS, pinned once per registration point. "Registered" is not one
property, so each is asserted on its own live surface, re-read off the module
attribute rather than from any binding captured at import:

    1. ToolRegistry._do_<name>    getattr on the instance    src/tools.py:138
    2. TOOL_CAPABILITIES[<name>]  read by markers_for        src/skills/capabilities.py:358
    3. valid_tools()              the merged route allow-list
    4. tool_goals()[<name>]       the merged goal vocabulary

A FIFTH surface, found by measurement rather than assumed: writing
`TOOL_CAPABILITIES[<name>]` with no matching narration guide turns the existing green
guard `tests/suite/tier1_resilience/test_skill_standard.py:50` RED, because it
requires every `TOOL_CAPABILITIES` key to ship a guide. A registration that breaks a
passing guard is not a registration. Pinned by
`test_registration_keeps_every_capability_covered_by_a_narration_guide`.

ONE MORE `Final` SNAPSHOT, the same class of bug as seam 3 and not in the brief:
`IRREVERSIBLE_TOOLS` (`src/skills/capabilities.py:353`) is a `Final` frozenset built
at import. A dynamically bound tool that declared itself irreversible would enter
`TOOL_CAPABILITIES` and NOT the deny-list, so every confirmation gate downstream
would miss it. Blueprint §3.6 closes this by construction — "SOVERNIUM | Irreversible
tier ... | Never reachable by synthesis — closed by construction" — which today is a
sentence in a document and nothing else. Pinned by
`test_registration_never_makes_a_tool_irreversible` and
`test_registration_leaves_the_irreversible_deny_list_untouched`.

THE SPECIFIED API, and the one place this file had to choose a shape. The blueprint
fixes the four POINTS; it does not fix a signature. This file specifies the smallest
signature that populates all four plus the narration guide, and routes every
registration through the single adapter `_register()` below, so a change of parameter
names is a one-line edit in one place:

    register_tool(name, markers, handler, *, goals, needs, reversible, chains_with)
    unregister_tool(name)

`handler` is an `async (str) -> str` — the shape `ToolRegistry.call` awaits
(`src/tools.py:143`). The refusal contract, the four-point atomicity requirement and
the idempotency requirement are specified in `tests/test_p3d_registration.py`.

MEASUREMENT NOTE (recorded, not asserted — every assertion below re-derives from the
live tree, per Directive 6): on 2026-10-01 `_ROUTER_PROMPT_AR` measured 4440
characters, sha256 `1475677bc56af8f20bf31c641874cdd1c46e407cb7ceb41e0cdaca934baeac62`,
naming 46 routed tools; `len(TOOL_CAPABILITIES)` is 42, `len(_TOOL_GOALS)` is 37 and
`IRREVERSIBLE_TOOLS` holds 6 names.

No socket, no HTTP, no wall clock, no subprocess. The gateway is the repo's own
`FakeGateway` double; the tool registry is built with every dependency `None`.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from src import evolution
from src.cognition import _TOOL_GOALS, _goal_markers, deduce
from src.dispatcher import _VALID_TOOLS, FrontDoorDispatcher, _parse_router
from src.skills import sara_tool_skills
from src.skills.capabilities import IRREVERSIBLE_TOOLS, TOOL_CAPABILITIES, markers_for
from src.tools import TOOL_FAIL_AR, ToolRegistry
from tests.conftest import FakeGateway, StreamProgram

# --- the registration seam, resolved loudly, never skipped -----------------------


def _seam(symbol: str) -> Any:
    """Resolve a P3-D producer on `src.tool_overlay`; a missing one FAILS.

    A module-level `from src.tool_overlay import register_tool` would abort collection
    with a bare ImportError and no guard would ever be seen failing (Directive 2: a
    guard is real once you have seen it fail). Same reasoning as `_seam()` in
    `tests/test_evolution_task.py:181`.
    """
    import src.tool_overlay as overlay

    try:
        return getattr(overlay, symbol)
    except AttributeError:
        pytest.fail(
            f"src.tool_overlay.{symbol} does not exist yet — P3-D is RED. Registering a "
            "tool needs an all-or-nothing entry point on the merge layer; without it the "
            "three seams below have no producer to close (missing producer: "
            f"src.tool_overlay.{symbol})."
        )


# --- sentinels and probes --------------------------------------------------------

#: Two names guaranteed absent from every registry today: a `NAME_RE` shape match
#: and no collision with `TOOL_CAPABILITIES`, `_VALID_TOOLS` or `_TOOL_GOALS`.
#: `test_the_sentinels_are_provably_free` re-derives that instead of asserting it.
TOOL_A = "p3d_gold_rate"
TOOL_B = "p3d_brew_jar"

#: Goal markers with a real utterance shape, each ABSENT from every static goal family
#: (re-derived by `test_the_probe_markers_are_out_of_vocabulary_today`), so a deduction
#: that reaches the sentinel cannot be a coincidental substring hit on another tool.
MARKER_A = "زعتر"
MARKER_B = "كفّة"

#: The exact text the bound handler must return. Asserting an exact reply INCLUDING the
#: echoed argument — not merely "not the failure string" — is load-bearing: MEASURED,
#: storing an async function as a PLAIN class attribute makes
#: `getattr(instance, "_do_<name>")` return a BOUND METHOD, so `ToolRegistry.call`'s
#: `await handler(arg)` passes `self` as the argument, raises `TypeError`, and the
#: blanket `except` swallows it into `TOOL_FAIL_AR`. "Not the failure string" would sit
#: green on top of a tool that never ran.
HANDLER_PREFIX = "سجّلت الأداة"
GOAL_A = "قراءة سعر الذهب"
GOAL_B = "تحضير القهوة"

#: `needs` must be one of these or `tests/suite/tier1_resilience/
#: test_skill_standard.py:30` goes red on the registered tool.
NEEDS_ENUM = ("bridge", "google", "network", "vault", "local", "none")

#: The framing clauses the neighbouring guard in
#: `tests/suite/tier1_resilience/test_contextual_routing.py:41-42` relies on. Re-asserted
#: here because seam 1 rewrites HOW that prompt is built, and a composer that dropped a
#: clause would be a silent regression the byte-identity test would not notice.
FRAMING_PHRASES = ("القصد الظرفي", "rag_domains", "لا تكتب أي شيء خارج الـ JSON")

#: Module-level so the handler below can append without a closure per test. Cleared by
#: the hygiene fixture, never asserted across tests.
_HANDLER_CALLS: list[str] = []


async def _handler(arg: str) -> str:
    _HANDLER_CALLS.append(arg)
    return f"{HANDLER_PREFIX}:{arg}"


def _register(
    name: str,
    *,
    markers: tuple[str, ...],
    goals: str,
    handler: Any = _handler,
    needs: str = "local",
    reversible: bool = True,
    chains_with: tuple[str, ...] = (),
) -> None:
    """THE SINGLE ADAPTATION POINT for the registration API this file specifies.

    Every argument is passed by name, so any parameter ORDER is accepted; a different
    parameter NAME is a one-line edit here and nowhere else, and a mismatch surfaces as
    a `TypeError` naming the call rather than as a silently skipped guard.
    """
    _seam("register_tool")(
        name=name,
        markers=markers,
        handler=handler,
        goals=goals,
        needs=needs,
        reversible=reversible,
        chains_with=chains_with,
    )


def _register_a(**overrides: Any) -> None:
    _register(TOOL_A, markers=(MARKER_A,), goals=GOAL_A, **overrides)


def _register_b(**overrides: Any) -> None:
    _register(TOOL_B, markers=(MARKER_B,), goals=GOAL_B, **overrides)


def _unregister(name: str) -> None:
    _seam("unregister_tool")(name=name)


def _bound_handler(name: str) -> Any:
    """Registration point 1, read the way `ToolRegistry.call` reads it."""
    return getattr(ToolRegistry(), f"_do_{name}", None)


def _router_prompt() -> str:
    """The BASE prompt, read live off the module rather than captured at import."""
    import src.dispatcher as disp

    return disp._ROUTER_PROMPT_AR


async def _router_prompt_sent(settings: Any) -> str:
    """The system prompt actually handed to the gateway on a routed turn.

    Reads the message the dispatcher built, not the module constant: the seam is the
    CALL SITE at :868, and a module constant can be correct while the call site still
    sends something else. `FakeGateway` is the repo's own double — no socket, no HTTP.
    """
    gw = FakeGateway(
        router_replies=[
            json.dumps(
                {"route": "tier2", "tool": "none", "arg": "", "ack": "لحظة"},
                ensure_ascii=False,
            )
        ],
        stream_programs=[StreamProgram(deltas=("أهلين",)), StreamProgram(deltas=("تمام",))],
    )
    disp = FrontDoorDispatcher(gw, settings)
    _drained = [delta async for delta in disp.handle("مساء الخير")]
    assert gw.router_calls, "the router was never called — the prompt is not observable"
    return gw.router_calls[0][0]["content"]


# --- order-independence, structural, independent of the seam existing -----------


@pytest.fixture(autouse=True)
def _registration_hygiene():
    """Snapshot every surface a registration can move, restore in a `finally`.

    The overlay is process-global state and P3-D widens that to six more
    process-global surfaces. A test that registers and then FAILS before it can
    unregister would poison every later test — and the rest of the suite — with a
    half-bound tool. The snapshot is taken before the test body, so it is correct
    whether or not the seam exists, and the restore does not go through
    `unregister_tool` (a missing `unregister_tool` must not also mean a leaked
    capability record).
    """
    import src.dispatcher as disp
    import src.skills.capabilities as caps
    import src.tool_overlay as overlay

    before = {
        "overlay": dict(overlay.OVERLAY),
        "caps": dict(TOOL_CAPABILITIES),
        "cap_ids": {k: id(v) for k, v in TOOL_CAPABILITIES.items()},
        "guides": sara_tool_skills._SKILLS,
        "handlers": frozenset(k for k in vars(ToolRegistry) if k.startswith("_do_")),
        "irreversible": caps.IRREVERSIBLE_TOOLS,
        "colliding": evolution._COLLIDING_TOOL_NAMES,
        "prompt": disp._ROUTER_PROMPT_AR,
    }
    _HANDLER_CALLS.clear()
    try:
        yield
    finally:
        _HANDLER_CALLS.clear()
        # Unwind THROUGH THE API first, when it exists. Deleting the surfaces by hand
        # would leave the implementation's own bookkeeping (its registry of what it
        # registered) out of sync, and the next test's identical registration would be
        # treated as an idempotent no-op against a handler this fixture just removed —
        # a green failure that reads as a product bug. The manual restore below remains
        # the backstop for the RED state, where no such API exists to unwind through.
        if hasattr(overlay, "reset_overlay"):
            overlay.reset_overlay()
        for name in set(TOOL_CAPABILITIES) - set(before["caps"]):
            del TOOL_CAPABILITIES[name]
        for name, record in before["caps"].items():
            TOOL_CAPABILITIES[name] = record
        for attr in set(vars(ToolRegistry)) - before["handlers"]:
            if attr.startswith("_do_"):
                delattr(ToolRegistry, attr)
        sara_tool_skills._SKILLS = before["guides"]
        caps.IRREVERSIBLE_TOOLS = before["irreversible"]
        evolution._COLLIDING_TOOL_NAMES = before["colliding"]
        disp._ROUTER_PROMPT_AR = before["prompt"]
        overlay.OVERLAY.clear()
        overlay.OVERLAY.update(before["overlay"])
        del before["cap_ids"]


# ==================================================================================
# 0. non-vacuity — the harness fires, and the sentinels are what this file claims
# ==================================================================================


def test_the_sentinels_are_provably_free() -> None:
    """A sentinel that collides with a live tool would make every guard below a lie."""
    occupied = set(TOOL_CAPABILITIES) | set(_VALID_TOOLS) | set(_TOOL_GOALS)
    for name in (TOOL_A, TOOL_B):
        assert evolution.NAME_RE.fullmatch(name) is not None, f"{name!r} is not a legal name"
        assert name not in occupied, f"{name!r} collides with a live registry"
        assert evolution.is_valid_task_name(name) is True


def test_the_probe_markers_are_out_of_vocabulary_today() -> None:
    """The markers must reach NO static tool, or a deduction could pass for the wrong
    reason — the winner would be a coincidental substring, not the registered one."""
    for marker in (MARKER_A, MARKER_B):
        hyp = deduce(marker)
        assert hyp.tool == "none", f"{marker!r} already deduces to {hyp.tool!r} today"


def test_the_control_registration_actually_landed() -> None:
    """Directive 2/4: can the harness fire at all. Every other test in this file
    assumes a registration happened; with the seam missing they all fail with the same
    message and none of them is evidence about the SEAMS. This one separates "the
    registration did not happen" from "the seam is still open"."""
    _register_a()
    assert TOOL_A in _seam("valid_tools")()
    assert TOOL_A in _seam("tool_goals")()


# ==================================================================================
# SEAM 1 — the router can never EMIT an overlay tool (src/dispatcher.py:868)
# ==================================================================================


async def test_router_prompt_sent_to_the_gateway_names_a_registered_overlay_tool(
    make_settings,
) -> None:
    """THE SEAM 1 GUARD. RED today: the name is absent from the prompt the gateway
    receives, so a router model has no catalog entry naming it. "The name is a substring
    of the prompt" is the honest formulation of "the router can emit it": a catalog
    that does not contain the literal name cannot produce it, and the verdict would be
    UNREACHABLE no matter that `deduce` can select the tool and `ToolRegistry.call` can
    serve it."""
    _register_a()
    prompt = await _router_prompt_sent(make_settings())
    assert TOOL_A in prompt, (
        f"{TOOL_A!r} is registered but absent from the router system prompt — the router "
        "can never emit it, so the tool is unreachable from the router lane. Missing "
        "producer: a prompt line naming the overlay tool (src/dispatcher.py:35, consumed "
        "at :868)."
    )


async def test_router_prompt_with_an_empty_overlay_is_the_static_base_byte_for_byte(
    make_settings,
) -> None:
    """The zero-regression half of seam 1. Whatever composition the fix introduces, an
    empty overlay must send exactly today's prompt. The base is read LIVE off the module
    each run, so this is a byte-identity claim rather than a frozen hash."""
    assert _seam("valid_tools")() == tuple(_VALID_TOOLS), "precondition: the overlay is empty"
    prompt = await _router_prompt_sent(make_settings())
    assert prompt == _router_prompt(), (
        "an empty overlay must send the base prompt unchanged — a fix that rewrites the "
        "static literal changes the catalog for every turn, registered or not"
    )


async def test_the_base_prompt_still_names_every_base_routed_tool(make_settings) -> None:
    """Re-derivation, so the byte-identity test above cannot pass on a hollow base.
    Byte-identity against the module's own literal holds even for a literal that has
    lost a tool; this pins the CONTENT instead."""
    prompt = await _router_prompt_sent(make_settings())
    missing = [tool for tool in _VALID_TOOLS if tool not in prompt]
    assert not missing, f"tools invisible to the router: {missing}"
    for phrase in FRAMING_PHRASES:
        assert phrase in _router_prompt(), f"the base router prompt lost its framing: {phrase!r}"
        assert phrase in prompt


async def test_unregistering_removes_the_tool_from_the_router_prompt(make_settings) -> None:
    """The anti-leak half. A prompt that BAKES overlay names into a static literal at
    import time is the same import-time-snapshot bug as seam 3, one layer up: the name
    would outlive its registration and the router would keep advertising a tool that no
    longer exists. The prompt must be a live view, so the differential pair
    (absent -> present -> absent) is observable."""
    _register_a()
    assert TOOL_A in await _router_prompt_sent(make_settings())
    _unregister(TOOL_A)
    assert TOOL_A not in await _router_prompt_sent(make_settings()), (
        "the router prompt still advertises an unregistered tool — the composition is "
        "memoised or baked rather than read live"
    )


async def test_two_registered_tools_are_both_named_and_release_one_by_one(make_settings) -> None:
    """Composition is per-tool, not all-or-nothing: registering B must not hide A, and
    releasing A must not remove B."""
    _register_a()
    _register_b()
    prompt = await _router_prompt_sent(make_settings())
    assert TOOL_A in prompt
    assert TOOL_B in prompt
    _unregister(TOOL_A)
    prompt = await _router_prompt_sent(make_settings())
    assert TOOL_B in prompt, "releasing one tool removed another from the catalog"
    assert TOOL_A not in prompt


async def test_a_registered_tool_is_emittable_end_to_end(make_settings) -> None:
    """Seam 1 is the conjunction of two facts: the router's catalog names the tool AND
    the verdict survives parsing. P3-C pinned the second; this file adds the first.
    Asserting the pair makes "emittable" one greppable claim instead of a reader's
    inference."""
    _register_a()
    assert TOOL_A in await _router_prompt_sent(make_settings()), "the catalog does not name it"
    raw = json.dumps(
        {"route": "tier2", "tool": TOOL_A, "ack": "لحظة", "voice_reply": False},
        ensure_ascii=False,
    )
    verdict = _parse_router(raw)
    assert verdict is not None
    assert verdict[2] == TOOL_A, "the verdict lost the registered tool on parsing"


# ==================================================================================
# SEAM 2 — "selectable" is not "runnable" (src/cognition.py:418)
# ==================================================================================


def test_registration_point_1_binds_a_do_handler() -> None:
    """Point 1. `ToolRegistry.call` does `getattr(self, f"_do_{tool}")`
    (`src/tools.py:138`); with no binding, every call logs "unknown tool" and returns
    `TOOL_FAIL_AR`."""
    _register_a()
    assert _bound_handler(TOOL_A) is not None, (
        f"no _do_{TOOL_A} binding path — ToolRegistry.call cannot getattr a handler, so "
        "the tool is selected and never executed"
    )


async def test_registration_point_1_is_reachable_through_tool_registry_call() -> None:
    """Point 1, behaviourally. The assertion is the handler's EXACT reply including the
    echoed argument — see the `HANDLER_PREFIX` note for why a weaker assertion is
    satisfiable by a tool that never runs."""
    _register_a()
    result = await ToolRegistry().call(TOOL_A, "(arg-echo)")
    assert result == f"{HANDLER_PREFIX}:(arg-echo)", (
        f"ToolRegistry.call did not reach the bound handler (got {result!r}). A handler "
        "stored as a plain class attribute becomes a bound method, the extra `self` "
        "raises TypeError, and the blanket except turns it into a generic failure — the "
        "tool is registered and does nothing"
    )


async def test_registration_binds_the_handler_without_calling_it() -> None:
    """Registration BINDS; it never invokes. A synthesizer whose import side effects run
    at registration time is a synthesizer running code on the hot path, and the §3.4
    subprocess gate exists precisely so a module-level `raise` cannot take the bot down
    during load."""
    _register_a()
    assert _HANDLER_CALLS == [], f"the handler ran at registration time: {_HANDLER_CALLS}"


def test_registration_point_2_lands_in_the_capability_registry() -> None:
    """Point 2. `markers_for` (`src/skills/capabilities.py:358`) is a bare
    `TOOL_CAPABILITIES.get(tool, {})`, so this dict is the only thing that can resolve
    an overlay tool's capability family. Live re-read of the module attribute."""
    _register_a()
    assert TOOL_A in TOOL_CAPABILITIES, (
        f"{TOOL_A!r} is not in TOOL_CAPABILITIES — markers_for returns () for it, so the "
        "tool has no schema, no narration guide and no chains (src/cognition.py:400)"
    )


def test_registration_point_2_marker_family_is_fully_resolvable() -> None:
    """Point 2, at the CONSUMER, because the dict entry alone is not the claim. Not
    "the name is in the dict" — the point of `_goal_markers` is that it UNIONS the
    capability markers on top of the inline family, so a record carrying no markers
    resolves to the inline family alone. Asserts both halves: the registered markers
    reached the capability registry, and the capability markers reach the scorer."""
    _register_a()
    capability_markers = markers_for(TOOL_A)
    assert capability_markers, (
        f"markers_for({TOOL_A!r}) is empty — the tool resolves to its inline goal family "
        "only, which is the unreachability stated at src/cognition.py:422-429"
    )
    assert {MARKER_A} <= set(capability_markers), (
        "the registered markers never reached the capability registry — the two goal "
        "sources have drifted and no single reader sees the union"
    )
    resolved = _goal_markers(TOOL_A, _seam("tool_goals")()[TOOL_A])
    assert set(capability_markers) <= set(resolved), (
        "the capability markers do not reach the scorer — _goal_markers is not reading "
        "the surface the registration wrote"
    )


def test_registration_point_3_lands_in_the_route_allow_list() -> None:
    """Point 3. Without it the verdict is rewritten to `"none"` at
    `src/dispatcher.py:740` and `parse_thought` returns `None` at
    `src/decision_loop.py:221` — both silent, neither logged as a defect."""
    _register_a()
    merged = _seam("valid_tools")()
    assert TOOL_A in merged
    assert set(_VALID_TOOLS) <= set(merged), "the base route list lost tools"


def test_registration_point_4_lands_in_the_goal_vocabulary() -> None:
    """Point 4. `deduce` iterates `tool_goals()` (`src/cognition.py:430`); a tool with
    no entry there can never be proposed, whatever the other three points say."""
    _register_a()
    goals = _seam("tool_goals")()
    assert TOOL_A in goals
    assert MARKER_A in goals[TOOL_A]


def test_a_registered_tool_is_selectable_by_deduce() -> None:
    """Selectability — the property P3-C already delivered, re-asserted so seam 2's
    stronger claim is anchored to something that was already true. Without it the
    'the registered tool is reachable' family could be satisfied by a registration that
    never joined the goal map at all."""
    _register_a()
    hyp = deduce(MARKER_A)
    assert hyp.tool == TOOL_A, f"{MARKER_A!r} -> {hyp.tool}@{hyp.confidence:.2f}"


def test_registration_does_not_mutate_the_static_base_registries() -> None:
    """P3-C's invariant must survive P3-D. Ten test modules import `_VALID_TOOLS` and
    `_TOOL_GOALS` by name and read the BASE; if a registration grew either of them,
    those modules would change meaning mid-suite."""
    _register_a()
    _register_b()
    for name in (TOOL_A, TOOL_B):
        assert name not in _VALID_TOOLS
        assert name not in _TOOL_GOALS
    assert len(_VALID_TOOLS) == len(set(_VALID_TOOLS)), "duplicate tool name in the base"


def test_registration_keeps_the_capability_record_complete() -> None:
    """The record shape `tests/suite/tier1_resilience/test_skill_standard.py:27-32`
    validates for every `TOOL_CAPABILITIES` key. A partial record turns a passing guard
    red — and that guard reads the LIVE dict, so it fails in whatever test runs next,
    not in this one. Asserted here, where the cause is."""
    _register_a()
    record = TOOL_CAPABILITIES[TOOL_A]
    assert record.get("goals"), f"{TOOL_A} has no goals"
    assert record.get("markers"), f"{TOOL_A} has no markers"
    assert record.get("needs") in NEEDS_ENUM, f"{TOOL_A} needs={record.get('needs')!r}"
    assert isinstance(record.get("reversible"), bool), f"{TOOL_A} reversible is not a bool"
    assert isinstance(record.get("chains_with"), tuple), f"{TOOL_A} chains_with is not a tuple"


def test_registration_keeps_every_capability_covered_by_a_narration_guide() -> None:
    """THE FIFTH SURFACE, found by measurement. Writing `TOOL_CAPABILITIES[<name>]`
    with no guide makes the existing green guard `tests/suite/tier1_resilience/
    test_skill_standard.py:50` RED, because it requires every capability key to ship
    one. A registration that turns a passing test red is not a registration; this is a
    fifth registration point the four-point table does not name, and it is load-bearing
    for the narration lane."""
    _register_a()
    shipped = {name.removesuffix(".md") for name, _ in sara_tool_skills._SKILLS}
    missing = [tool for tool in TOOL_CAPABILITIES if tool not in shipped]
    assert not missing, (
        f"tools without a narration guide: {missing} — registering a capability with no "
        "guide turns test_skill_standard.py::test_sara_tool_guides_cover_capabilities red "
        "in whatever test runs next"
    )
    assert TOOL_A in shipped, f"no narration guide shipped for {TOOL_A!r}"


def test_registration_never_makes_a_tool_irreversible() -> None:
    """Blueprint §3.6, SOVERNIUM row: "Irreversible tier ... Never reachable by
    synthesis — closed by construction". Today that sentence is enforced by nothing.
    `IRREVERSIBLE_TOOLS` is a `Final` frozenset built at import, so a dynamically bound
    tool declaring `reversible=False` would enter `TOOL_CAPABILITIES` and NOT the
    deny-list, and the confirmation gate would never see it. Refusing is the only way to
    keep the claim true."""
    with pytest.raises(ValueError):
        _register_a(reversible=False)
    assert TOOL_A not in TOOL_CAPABILITIES, (
        "a refused irreversible registration still wrote the capability record — a "
        "half-registration is worse than a refusal"
    )


def test_registration_leaves_the_irreversible_deny_list_untouched() -> None:
    """The snapshot is `Final`: nothing can add to it at runtime, so a reversible
    registration is the only kind that can be safe, and the deny-list must come out of a
    registration unchanged."""
    before = set(IRREVERSIBLE_TOOLS)
    _register_a()
    assert set(IRREVERSIBLE_TOOLS) == before, (
        "registration moved the irreversible deny-list — a downstream gate would read a "
        "different set than the one this test snapshotted"
    )
    assert TOOL_A not in IRREVERSIBLE_TOOLS


async def test_a_handler_that_raises_is_contained_by_the_registry() -> None:
    """Blueprint §4: "`ToolRegistry.call` catches every exception". A dynamic handler is
    a new source of exceptions, and containment must come from the same `except` that
    covers the hand-written handlers — not from the handler author."""

    async def exploding(arg: str) -> str:
        raise RuntimeError("synthesized tool blew up")

    _register_a(handler=exploding)
    result = await ToolRegistry().call(TOOL_A, "x")
    assert result == TOOL_FAIL_AR, (
        f"a raising dynamic handler escaped ToolRegistry.call and returned {result!r} — "
        "containment is the registry's job, not the synthesized tool's"
    )


# ==================================================================================
# SEAM 3 — the collision surface is an import-time snapshot (src/evolution.py:253)
# ==================================================================================


def test_a_registered_name_is_no_longer_a_valid_task_name() -> None:
    """THE SEAM 3 GUARD. RED today. `_COLLIDING_TOOL_NAMES` is a `Final` frozenset built
    at import, so `is_valid_task_name` cannot see a tool registered afterwards. A task
    named after a tool that already exists is a duplicate proposal for a capability Sara
    has; the collision rule exists precisely to refuse that, and it is the structural
    backstop for the paraphrase blind spot in the forced safety tier (documented at
    `tests/test_evolution_task.py:26-32`)."""
    assert evolution.is_valid_task_name(TOOL_A) is True, "precondition: the name is free"
    _register_a()
    assert evolution.is_valid_task_name(TOOL_A) is False, (
        f"{TOOL_A!r} is a registered tool and is still a valid TASK name — a task may be "
        "proposed for a capability that already exists, which is the silent collision "
        "is_valid_task_name exists to refuse (src/evolution.py:253: the collision set is "
        "an import-time snapshot)"
    )


def test_unregistering_makes_the_name_a_valid_task_name_again() -> None:
    """The opposite direction. A one-way latch is not a guard, it is a leak: after an
    unregistration the name is free again and the backlog must be able to name it."""
    _register_a()
    assert evolution.is_valid_task_name(TOOL_A) is False
    _unregister(TOOL_A)
    assert evolution.is_valid_task_name(TOOL_A) is True, (
        f"{TOOL_A!r} is unregistered and is still refused as a task name — the collision "
        "surface never shrank, so the set is leaking names"
    )


def test_the_constructor_refuses_a_task_named_after_a_registered_tool() -> None:
    """A predicate nobody calls is a hollow guard. `EvolutionTask.__post_init__`
    (`src/evolution.py:322`) is where a task is actually built, so the live surface has
    to reach it too — otherwise the backlog keeps accepting duplicates and the seam is
    closed only for the direct predicate call."""
    _register_a()
    with pytest.raises(ValueError):
        evolution.EvolutionTask(
            name=TOOL_A,
            intent="«سعر الذهب»",
            schema={"params": {}, "returns": "str"},
            safety_tier="safe",
            acceptance_criteria=["returns the Amman price line"],
            evidence=["«شو سعر الذهب»"],
            occurrences=3,
            created_day="2026-10-01",
            kind="tool",
        )


def test_the_collision_surface_is_live_for_every_registration_not_just_the_first() -> None:
    """One hard-coded entry proves nothing about liveness. Register three names in
    sequence; each must be refused as a task name, and each must be free again on
    release. A cache, a memo, or a snapshot rebuilt once would fail on the second."""
    names = (TOOL_A, TOOL_B, "p3d_third_tool")
    for name in names:
        _register(name, markers=(f"بروفة-{name}",), goals=f"هدف تجريبي {name}")
    for name in names:
        assert evolution.is_valid_task_name(name) is False, f"{name!r} escaped the live set"
    for name in names:
        _unregister(name)
    for name in names:
        assert evolution.is_valid_task_name(name) is True, f"{name!r} stayed reserved"


def test_a_live_collision_surface_keeps_both_halves_of_the_union() -> None:
    """The union is load-bearing and NOT symmetric: `TOOL_CAPABILITIES` is a strict
    subset of the routed set, so a guard that "went live" by replacing the snapshot with
    the overlay alone would drop every routed-but-uncatalogued name. The asymmetry is
    re-derived here, not asserted — `tests/test_tool_overlay.py:532` owns the set."""
    _register_a()
    assert evolution.is_valid_task_name(TOOL_A) is False, "precondition: the overlay is live"
    for name in set(TOOL_CAPABILITIES) | set(_VALID_TOOLS):
        assert evolution.is_valid_task_name(name) is False, (
            f"{name!r} is a live tool and became a valid task name — going live dropped "
            "part of the collision union"
        )
    assert set(_VALID_TOOLS) - set(TOOL_CAPABILITIES), (
        "the asymmetry this guard leans on no longer exists; the union is no longer "
        "tested against a guard that reads only one of its halves"
    )


def test_the_shape_half_of_the_name_rule_is_unchanged_by_a_registration() -> None:
    """Only the collision half is a live surface. The regex half is `NAME_RE` and must
    stay exactly as `tests/test_evolution_task.py:217-238` pins it, or P3-D would
    quietly widen what a task may be called."""
    _register_a()
    for bad in ("Gold-Rate", "ab", "1tool", "a" + "b" * 40):
        assert evolution.is_valid_task_name(bad) is False, f"{bad!r} became acceptable"
    assert evolution.NAME_RE.pattern == r"^[a-z][a-z0-9_]{2,39}$"
