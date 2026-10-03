"""P3-C/P3-D registration overlay — the merge layer AND the entry point that writes it.

Registering a tool needs SIX registration points across five modules, and every
one of them fails SILENTLY — a tool that simply does not work. Four of the six
are a WRITE and land in four modules — ``landed`` carries exactly four labels,
``capability``, ``registry``, ``overlay``, ``guide`` — while points 3 and 4 share
one dict and point 6 is a union this module FEEDS rather than a line it writes:

    1. ``ToolRegistry._do_<name>``       getattr  src/tools.py:287
    2. ``TOOL_CAPABILITIES[<name>]``    dict     src/skills/capabilities.py:436
    3. ``_VALID_TOOLS``                  overlay  merged by ``valid_tools()``
    4. ``_TOOL_GOALS[<name>]``          overlay  merged by ``tool_goals()``
    5. ``sara_tool_skills._SKILLS``     tuple    the per-tool narration guide
    6. the collision surface            unioned INSIDE
                                              ``evolution.is_valid_task_name``

Points 3, 4 and 6 are the trap P3-C built the merge layer for. ``_VALID_TOOLS``
and ``_TOOL_GOALS`` are ``Final`` literals no runtime path can rewrite, so the
merge lives here and the base keeps its name, its type and its contents —
fourteen test modules import ``_VALID_TOOLS`` from ``src.dispatcher`` by name and
four import ``_TOOL_GOALS`` from ``src.cognition``; ``Final`` is the very
property this module works AROUND rather than removes. A router verdict naming a
name outside (3) was rewritten to ``"none"`` with no exception raised, and
``deduce`` iterates (4), so a tool registered only in (2) is a tool Sara can
never *select*. "The feature just doesn't work" is the entire failure signal.

Point 5 is not in the four-point table at all and was found by MEASUREMENT: a
capability record with no guide turns the green guard
``tests/suite/tier1_resilience/test_skill_standard.py:50`` red in whatever test
runs NEXT, not in the one that registered the tool.

``register_tool`` lands at ALL SIX or at NONE, and those are separate claims.
Landing means every surface above is written; NONE means a refusal moves nothing,
and a point that cannot be written rolls back every surface already written. A
half-registration is strictly worse than no registration: a tool in the overlay
with no capability record parses, deduces, and then answers ``TOOL_FAIL_AR``,
while a capability record with no handler turns a passing guard red in whichever
test runs next. The RISKIEST write therefore goes FIRST — the capability
registry (2) is the one surface a caller can have made unwritable, so
discovering that before anything else is written leaves nothing to unwind.

HANDLER BINDING, and the failure it prevents. ``ToolRegistry.call`` does
``getattr(self, f"_do_{tool}")`` — on an INSTANCE. A plain function stored as a
class attribute comes back as a BOUND method, so the registry's
``await handler(arg)`` passes ``self`` as the argument, the call raises
``TypeError``, and the blanket ``except`` turns it into ``TOOL_FAIL_AR``: a tool
that is registered and does nothing, with no exception anywhere along the way.
``staticmethod(handler)`` is therefore not a style choice, it is the only correct
binding. Registration BINDS the handler and never CALLS it — a synthesizer whose
import side effects run at registration time is a synthesizer running code on the
hot path.

THE IRREVERSIBLE TIER, closed by construction. ``IRREVERSIBLE_TOOLS`` is a
``Final`` frozenset built at import, so a catalog entry carrying
``reversible=False`` that is NOT in the deny-list is invisible to every
confirmation gate downstream. Blueprint §3.6 claims the tier is "never reachable
by synthesis — closed by construction"; that claim is enforced here twice. Refusal
R4 refuses ``reversible=False`` outright, and a POST-CONDITION re-checks the whole
live registry after the capability record is written, rolling the registration
back if any non-deny-listed key carries the irreversible flag. The first half
keeps the tier closed for this entry point; the second half is what makes the
claim structural rather than a promise about one function's argument list.

R3 IS NOT ONE OF THE TWO HALVES, and this paragraph must not read as if it were.
The ``name in IRREVERSIBLE_TOOLS`` refusal is UNOBSERVABLE at this boundary: the
deny-list is DERIVED from ``TOOL_CAPABILITIES``, which is one of R2's two halves,
so R2's union refuses every deny-listed name before R3 can be reached. It is kept
as a stated law rather than deleted, so a future reordering that weakened R2
could not silently reopen the tier. The law ACTUALLY ENFORCED is therefore R4
plus the registry-wide post-condition — the ``unlisted`` sweep in
``register_tool``'s ``try`` block, placed immediately after the capability write
and its ``landed.append("capability")`` and BEFORE the handler binding, and
routed to ``_rollback`` by ``except _IrreversibleTierWouldOpen``. Those two
locations are named structurally on purpose: a bare line number here would be
the next stale citation in this file, and this commit exists because there were
three.

SHIPS EMPTY, still. No tool is registered at import time, and NOTHING in this
repository calls ``register_tool`` — Sara still does not autonomously synthesize
or register tools. What ships is the all-or-nothing entry point and the guards
that hold it honest. A registration's footprint is process-global state, which is
why ``reset_overlay`` now releases every registration: it is the suite's only
cleanup primitive, and a reset that empties the overlay while leaving a capability
record behind turns every test that follows into a false failure whose cause is
invisible.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Any, Final

from loguru import logger

__all__ = [
    "OVERLAY",
    "register_tool",
    "reset_overlay",
    "router_catalog_lines",
    "tool_goals",
    "unregister_tool",
    "valid_tools",
]

#: Runtime-mutable registration overlay: tool name -> its goal markers.
#:
#: EMPTY at import, and neither ``Final`` nor ``MappingProxyType`` — mutability is
#: the entire purpose of the seam. Both accessors read it on every call and
#: neither memoises, so a mutation is visible to the next reader immediately.
OVERLAY: dict[str, tuple[str, ...]] = {}

#: The names THIS module registered — the record of what it owns. A set, not a
#: name->payload map: a release deletes every surface BY NAME, so a second field
#: would be a speculative layer, and the only question either caller asks is "did
#: *I* put this here?". Written to before the surfaces, read by the idempotency
#: check and by the release, and never by the merge accessors — a caller that
#: writes a key into `OVERLAY` by hand gets a routable-but-unrunnable tool, and
#: the difference between the two states is exactly what this set records.
_REGISTERED: set[str] = set()

#: Every refusal message carries this prefix: a refusal that does not say which
#: name is unusable is a log line nobody can act on.
_REFUSAL_PREFIX: Final[str] = "register_tool refused"

#: The capability record's goal key, named once so the router catalog and the
#: record cannot drift on a spelling.
_GOALS_KEY: Final[str] = "goals"

#: `needs` values, and the honest narration each one owes the owner when its
#: backend is absent. The per-tool guide repeats the value in its own words,
#: because a guide is read by the narration lane on its own and never alongside
#: this table.
_NEEDS_HONEST_LINE: Final[dict[str, str]] = {
    "bridge": "الجسر مو متصل",
    "google": "ما في وصول لحساب جوجل",
    "network": "ما في اتصال بالنت",
    "vault": "ما في وصول للخزينة",
    "local": "ما في وصول محلي للجهاز",
    "none": "ما في متطلبات",
}

#: The goal prose rides into a SYSTEM PROMPT, so it is flattened to one line and
#: capped: a synthesized goal carrying a newline would forge a catalog
#: instruction of its own, and an unbounded one would let a single registration
#: swamp the catalog.
_MAX_GOAL_CHARS: Final[int] = 160


def valid_tools() -> tuple[str, ...]:
    """`_VALID_TOOLS` merged with the overlay's keys; base order preserved.

    Returns a ``tuple`` because that is what every importing call site already
    does to ``_VALID_TOOLS`` — ``in``, iteration, ``set()``, ``len()`` and
    slicing all have to keep working unchanged for the fourteen test modules that
    read the base.
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


def router_catalog_lines() -> tuple[str, ...]:
    """One router-catalog line per tool the overlay makes routable.

    A router model may only name a tool its system catalog lists, so a tool the
    prompt does not mention is UNEMITTABLE however well `valid_tools()` accepts
    it. Built from the live overlay on every call and one line per tool, so
    releasing ONE tool removes exactly its own line: a composition that is
    memoised or baked into an import-time literal is the same snapshot defect as
    the collision surface, one layer up.

    The caller APPENDS these to the static literal rather than splicing them in.
    The base catalog's text is hand-maintained and pinned by other guards
    (`tests/test_router_fused_p31.py`, `tests/suite/tier1_resilience/
    test_contextual_routing.py`); surgery on a `Final` literal is how seam 1
    would reopen.
    """
    from src.skills.capabilities import TOOL_CAPABILITIES  # deferred: import-leaf

    return tuple(
        f"  {name}={_one_line(TOOL_CAPABILITIES.get(name, {}).get(_GOALS_KEY, ''))} "
        'مع التفاصيل في "arg"،\n'
        for name in OVERLAY
    )


def _one_line(text: str) -> str:
    """Goal prose flattened to ONE bounded line for a system prompt."""
    return " ".join(str(text).split())[:_MAX_GOAL_CHARS]


def _narration_guide(name: str, goals: str, needs: str) -> str:
    """The per-tool guide registration point 5 ships with every registered tool.

    `tests/suite/tier1_resilience/test_skill_standard.py:50` requires EVERY
    `TOOL_CAPABILITIES` key to ship a guide, so a record written without one turns
    that green guard red. The body is assembled from the record the caller already
    passed — never from prose invented here — so a guide cannot claim a behaviour
    the registration does not have.
    """
    honest = _NEEDS_HONEST_LINE.get(needs, f"«{needs}» مو متعرّف عليه — اسأل المالك")
    return (
        f"# مهارة {name} (أداة مسجّلة وقت التشغيل)\n"
        "\n"
        f"**متى تنفّذي هالمهارة؟** كل مرة يطلب منك المالك {_one_line(goals)}.\n"
        "\n"
        "## الاستخدام\n"
        f"- الأداة `{name}` مسجّلة وقت التشغيل: سماها في `tool` وحط طلبه كاملاً في "
        '"arg".\n'
        f"- المتطلب: {honest} — قلها بالزبط ولا تخترع نتيجة.\n"
        "- الأدارة reversible، فما في تأكيد لازم؛ نفّذي بس اللي طلبه المالك.\n"
        "\n"
        "## الفشل الصادق\n"
        f"- رجعت الأداة «فشلت» أو ما رجعت: قول «ما قدرت أنفّذ `{name}`» بالزبط، "
        "ولا تعيد المحاولة بصوت غيرك.\n"
        "- التشك إن `{name}` مو الأداة الصح: اسأل توضيح بدل ما تخمّن.\n"
    )


def _live_tool_names() -> set[str]:
    """The union the collision refusal consults, read live.

    The union is load-bearing and NOT symmetric: ``TOOL_CAPABILITIES`` is a
    strict subset of the routed set, so a refusal reading only the capabilities
    half would let every routed-but-uncatalogued name through. Phase 0 catalogued
    the last three (46 routed, 45 catalogued), so exactly ``none`` is left in the
    gap — and ``none`` is the one that must STAY there, being the dispatcher's
    no-tool-selected sentinel rather than a name with a handler. Read from the
    live registries on every call, so a registration made a moment ago is a
    collision for the next one.
    """
    from src.skills.capabilities import TOOL_CAPABILITIES  # deferred: import-leaf

    return set(TOOL_CAPABILITIES) | set(valid_tools())


class _IrreversibleTierWouldOpen(Exception):
    """The post-condition tripped: the catalog would hold an irreversible tool the
    deny-list does not name.

    A private exception type rather than a `ValueError` plus a message-prefix test, so
    the refusal the caller finally sees is a plain `ValueError` naming the tool and the
    point, while the routing decision between "my own refusal" and "an unreachable point"
    does not depend on string comparison. Carries the offending names, because the
    operator's question is WHICH tools opened the tier, not that one did.
    """

    def __init__(self, tools: list[str]) -> None:
        super().__init__(f"irreversible tools outside the deny-list: {tools}")
        self.tools = tools


def _rollback(name: str, landed: tuple[str, ...]) -> None:
    """Undo, in reverse order, exactly the surfaces a refused registration wrote.

    Driven by ``landed`` — the labels of the writes that actually SUCCEEDED — so
    a rollback can never delete a surface the failing write never reached, which
    is how a rollback turns into a second, quieter defect.
    """
    from src.skills import sara_tool_skills
    from src.skills.capabilities import TOOL_CAPABILITIES
    from src.tools import ToolRegistry

    if "guide" in landed:
        sara_tool_skills._SKILLS = tuple(
            entry for entry in sara_tool_skills._SKILLS if entry[0] != f"{name}.md"
        )
    if "overlay" in landed:
        OVERLAY.pop(name, None)
    if "registry" in landed:
        delattr(ToolRegistry, f"_do_{name}")
    if "capability" in landed:
        TOOL_CAPABILITIES.pop(name, None)


def register_tool(
    name: str,
    markers: tuple[str, ...],
    handler: Callable[[str], Coroutine[Any, Any, str]],
    *,
    goals: str,
    needs: str,
    reversible: bool,
    chains_with: tuple[str, ...],
) -> None:
    """Register a runtime tool at ALL SIX registration points, or at NONE.

    ``handler`` is an ``async (str) -> str`` — the shape ``ToolRegistry.call``
    awaits. It is BOUND here and never CALLED: registration is not execution.

    Refusals, all ``ValueError``, all naming the tool, in this order — the order
    is load-bearing:

    1. a name THIS MODULE already registered is a NO-OP (idempotency). Consulted
       FIRST on purpose: a naive collision check sees its own registration and
       refuses, making "registering twice" an error instead of an idempotent
       operation, and making every cleanup path a hazard. The first registration
       stands — a second call with a different handler is not an update.
    2. R1 — a name that is not ``NAME_RE``-shaped. The REGEX half only: the
       collision half cannot apply to a name that does not exist yet.
    3. R2 — a name colliding with any live tool: the UNION of the capability
       registry and the routed set, not one half.
    4. R3 — a name in ``IRREVERSIBLE_TOOLS`` (Leader decision 6, zero
       exceptions). UNREACHABLE at this boundary by construction: the deny-list
       is DERIVED from ``TOOL_CAPABILITIES``, one of R2's two halves, so R2
       refuses all seven deny-listed names first. It is kept as an explicit law
       so a future reordering that weakened R2 cannot silently reopen the
       irreversible tier; the enforceable form of the same rule is R4 plus the
       registry-wide post-condition.
    5. R4 — ``reversible=False``.
    """
    from src.evolution import NAME_RE
    from src.skills import sara_tool_skills
    from src.skills.capabilities import IRREVERSIBLE_TOOLS, TOOL_CAPABILITIES
    from src.tools import ToolRegistry

    # (1) Idempotency, recognised BEFORE any refusal.
    if name in _REGISTERED:
        return

    # (2) R1 — shape only. `NAME_RE` is read LIVE off `src.evolution`; the regex
    # half is P3-A's and P3-D does not widen it.
    if NAME_RE.fullmatch(name) is None:
        raise ValueError(
            f"{_REFUSAL_PREFIX} {name!r}: the name is not a legal tool name. "
            f"src.evolution.NAME_RE is {NAME_RE.pattern!r} — lowercase snake_case, 3 to 40 "
            "characters, no spaces, no dashes, no leading digit or underscore."
        )

    # (3) R2 — the UNION, read live.
    if name in _live_tool_names():
        raise ValueError(
            f"{_REFUSAL_PREFIX} {name!r}: the name collides with a live tool. This is the "
            "collision half of evolution.is_valid_task_name, and taking a live name would be "
            "a silent takeover of that tool's behaviour — the dispatcher routes on the name."
        )

    # (4) R3 — Leader decision 6, zero exceptions. Unreachable while R2 reads the
    # full union (see the docstring); kept so the law is stated, not implied.
    if name in IRREVERSIBLE_TOOLS:
        raise ValueError(
            f"{_REFUSAL_PREFIX} {name!r}: the name is in IRREVERSIBLE_TOOLS. The "
            "irreversible tier is never registerable — zero exceptions."
        )

    # (5) R4 — `IRREVERSIBLE_TOOLS` is a `Final` frozenset built at import, so a
    # `reversible=False` tool would enter the catalog and NOT the deny-list, and
    # every confirmation gate downstream would miss it.
    if reversible is not True:
        raise ValueError(
            f"{_REFUSAL_PREFIX} {name!r}: reversible=False. Blueprint §3.6 closes the "
            "irreversible tier by construction — it is never reachable by synthesis, and a "
            "registration cannot join IRREVERSIBLE_TOOLS (a Final import-time set), so it "
            "must not create one."
        )

    guide = _narration_guide(name, goals, needs)
    landed: list[str] = []

    # Registration point 2 FIRST — the riskiest write. The capability registry is
    # a plain dict and the only surface a caller can have made unwritable, so
    # discovering that here leaves NOTHING to unwind.
    try:
        TOOL_CAPABILITIES[name] = {
            _GOALS_KEY: goals,
            "markers": tuple(markers),
            "needs": needs,
            "reversible": True,
            "chains_with": tuple(chains_with),
        }
        landed.append("capability")
        # The POST-CONDITION: the structural half of "closed by construction".
        # Evaluated over the WHOLE live registry rather than over this call's
        # arguments, so a future writer that skips R4 still cannot open the tier.
        unlisted = sorted(
            tool
            for tool, cap in TOOL_CAPABILITIES.items()
            if cap.get("reversible") is False and tool not in IRREVERSIBLE_TOOLS
        )
        if unlisted:
            raise _IrreversibleTierWouldOpen(unlisted)
        # (1) The registry binding. `staticmethod` is load-bearing: a plain class
        # attribute makes `getattr(instance, "_do_<name>")` return a BOUND method,
        # the extra `self` raises TypeError, and the registry's blanket `except`
        # turns it into TOOL_FAIL_AR — a registered tool that does nothing.
        setattr(ToolRegistry, f"_do_{name}", staticmethod(handler))
        landed.append("registry")
        # (3) and (4) the overlay — the two `Final` bases are merged, never moved.
        OVERLAY[name] = tuple(markers)
        landed.append("overlay")
        # (5) the narration guide.
        sara_tool_skills._SKILLS = (*sara_tool_skills._SKILLS, (f"{name}.md", guide))
        landed.append("guide")
    except _IrreversibleTierWouldOpen as refusal:
        _rollback(name, tuple(landed))
        raise ValueError(
            f"{_REFUSAL_PREFIX} {name!r}: the capability registry (registration point 2, "
            f"TOOL_CAPABILITIES) would leave the irreversible tier OPEN — {refusal.tools} "
            "declare reversible=False without being in IRREVERSIBLE_TOOLS, so no "
            f"confirmation gate can see them. The record for {name!r} was rolled back and no "
            "other registration point was written."
        ) from refusal
    except Exception as error:  # a point we cannot reach is a refusal, not a crash
        _rollback(name, tuple(landed))
        raise ValueError(
            f"{_REFUSAL_PREFIX} {name!r}: a registration point could not be written, so every "
            f"surface written so far ({', '.join(landed) or 'none'}) was rolled back and no "
            f"registration point was kept. Cause: {error!r}"
        ) from error

    _REGISTERED.add(name)
    logger.info("registered runtime tool {!r} at all six registration points", name)


def unregister_tool(name: str) -> None:
    """Release ONE registration, exactly, and leave every other surface alone.

    Inert on a name this module never registered: cleanup code, a fixture and an
    error path all reach it, and raising on an unknown name would make it fail
    exactly when it is needed — and would delete a SHIPPED tool's handler, since
    a shipped name is not in the registry of what we wrote.
    """
    if name not in _REGISTERED:
        return
    _REGISTERED.discard(name)
    _rollback(name, ("guide", "overlay", "registry", "capability"))


def reset_overlay() -> None:
    """Release EVERY registration, then empty the overlay in place.

    P3-C's reset emptied one dict. P3-D widened the footprint from one surface to
    six, and this function is the suite's ONLY cleanup primitive — the autouse
    hygiene fixture of every registration guard calls it. A reset that empties the
    overlay and leaves a capability record, a handler or a guide behind turns
    every test that follows — including the ~2,380 that were green before P3-D —
    into a false failure whose cause is invisible.

    Every registration is released through the SAME rollback the refusal path
    uses, so a surface added later cannot be half-unwound here. ``clear()`` rather
    than rebinding to ``{}``: the overlay is process-global state, and in-place
    clearing keeps every existing reference to it valid.
    """
    for name in tuple(_REGISTERED):
        unregister_tool(name)
    OVERLAY.clear()
