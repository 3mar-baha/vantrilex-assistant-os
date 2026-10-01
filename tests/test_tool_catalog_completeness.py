"""QW-7 — the capability catalog must cover every ROUTED tool, and the deny-list
must cover every routed tool that changes external state.

This is the guard that makes the irreversible tier's soundness a property of the
tree rather than a promise about one function's argument list.

THE LEAK THIS PINS. `IRREVERSIBLE_TOOLS` is DERIVED from `TOOL_CAPABILITIES`
(`src/skills/capabilities.py`: ``frozenset(t for t, c in TOOL_CAPABILITIES.items()
if not c["reversible"])``). So an uncatalogued tool is not merely "absent from
the deny-list" — it is STRUCTURALLY INCAPABLE of being in it. Every
confirmation gate downstream (`src/decision_loop.py:428`, and F-1's irreversible
gate) reads that set, so a routed tool with a live `_do_<name>` handler and no
capability record executes its external effect with nobody asked.

MEASURED at the commit this guard was written against: 46 routed names, 42
catalogued, four routed-but-uncatalogued — `analytics`, `cloud_backup`, `none`,
`quota_safety`. THREE of the four had live handlers. `cloud_backup` uploads a
Fernet-sealed vault snapshot to Google Cloud Storage, an external state change
the owner cannot un-do, and it was invisible to a deny-list that never had to
consider it.

`none` is the fourth and is NOT a tool: it is the dispatcher's rewrite target for
"no tool selected" and for an unknown router verdict (`src/dispatcher.py:763-765`).
It has no handler. Cataloguing it would be a lie that also drags a narration guide
and an audit prompt into existence for a non-tool, so it gets an explicit
`INTERNAL_ONLY_TOOLS` marker instead — machine-visible, so THIS guard can assert
the routed set is accounted for rather than assume it.

THE TWO INVARIANTS, STATED.

  I1  every name in `valid_tools()` is either a `TOOL_CAPABILITIES` key or in
      `INTERNAL_ONLY_TOOLS` — nothing routed escapes the accounting.
  I2  `IRREVERSIBLE_TOOLS ⊇ {every routed tool whose handler changes external
      state}`.

I2 is stated against an explicit, hand-audited table (`EXTERNAL_STATE_WRITERS`)
with each handler's call site cited, NOT against a set derived from the catalog
itself: a check derived from the dict it audits cannot detect the dict being
wrong. `reversible: True` on a row of that table is the exact mutation F-1's
gate would wave through, and it is what guard `..._external_state_writer_is_deny_listed`
turns red.

Read-only-but-routed is deliberately NOT in the table and must not be: `analytics`
and `quota_safety` both perform reads (`sqlite_life_analytics` over local SQLite;
`free_tier_usage_percent` over the Service Usage API), and deny-listing a read
would make the confirmation gate fire on questions. Their reversibility decisions
and the evidence behind them are recorded in the catalog itself, at
`src/skills/capabilities.py`.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.skills.capabilities import IRREVERSIBLE_TOOLS, TOOL_CAPABILITIES, markers_for
from src.tools import ToolRegistry

ROOT = Path(__file__).resolve().parents[1]


def _internal_only_tools() -> frozenset[str]:
    """Resolve `INTERNAL_ONLY_TOOLS` off the catalog, LAZILY and by name.

    A module-level `from src.skills.capabilities import INTERNAL_ONLY_TOOLS`
    aborts collection with a bare `ImportError` while the marker is unbuilt, and
    then no guard in this file is ever SEEN failing — the failure Directive 2 is
    written against, and the same reason `tests/test_p3d_seams.py:98` and
    `tests/test_evolution_task.py:181` resolve their seams through a helper
    rather than an import. Resolved on every call and never memoised: it is live
    process state, and a snapshot would not see a marker written after import.
    """
    from src.skills import capabilities

    try:
        marker = capabilities.INTERNAL_ONLY_TOOLS
    except AttributeError:
        pytest.fail(
            "src/skills/capabilities.py has no INTERNAL_ONLY_TOOLS — the routed name "
            "`none` is unaccounted for (missing producer: INTERNAL_ONLY_TOOLS). It is the "
            "dispatcher's no-tool-selected sentinel and must NOT receive a capability "
            "record, so this marker is the only honest way to close the completeness "
            "invariant. Do not add a capability record for it to make this go green."
        )
    return frozenset(marker)


def _routed() -> set[str]:
    """Every routed name, read live so a runtime registration is audited too."""
    from src.tool_overlay import valid_tools

    return set(valid_tools())


def _executable() -> set[str]:
    """Routed names with a callable `ToolRegistry._do_<name>`.

    Read off the class, never off `_VALID_TOOLS`: routability and executability
    are different properties, and the whole leak is a name that has one while the
    other is never checked. `ToolRegistry.call` does
    `getattr(self, f"_do_{tool}")`, so a name with a handler is a name whose code
    runs.
    """
    return {
        name[len("_do_") :]
        for name in vars(ToolRegistry)
        if name.startswith("_do_") and callable(getattr(ToolRegistry, name, None))
    }


#: Routed tools whose handler performs an EXTERNAL state change — the upload, the
#: app kill, the click that may commit. Hand-audited against the source, with the
#: call site cited per row, because this table is what the deny-list is checked
#: against and a table derived from the catalog would be circular.
EXTERNAL_STATE_WRITERS = frozenset(
    {
        "cloud_backup",  # _do_cloud_backup -> client.cloud_backup -> objects.insert (upload)
        "close",  # kills a process on the owner's machine
        "cancel_reminder",  # deletes a stored reminder
        "create_event",  # writes the owner's calendar
        "create_task",  # writes the owner's task list
        "openclaw_browse",  # clicks may commit; the breaker gates per op
        "openclaw_desktop",  # actuation may commit; the breaker gates per op
    }
)

#: Names the catalog must never carry an executable claim for. `none` is the
#: dispatcher's no-tool-selected sentinel: a router verdict naming a tool
#: `valid_tools()` rejects is rewritten to it (`src/dispatcher.py:763-765`). It is
#: a routing SENTINEL, and giving it a capability record would assert a handler
#: that does not exist and pull a narration guide and an audit prompt into
#: existence for a non-tool.
EXPECTED_INTERNAL_ONLY = frozenset({"none"})


# --- I1: the routed set is fully accounted for --------------------------------------


def test_every_routed_tool_is_either_catalogued_or_explicitly_internal_only() -> None:
    """I1, the leak as an assertion. A routed name outside both sets is a tool the
    deny-list cannot see."""
    unaccounted = sorted(_routed() - set(TOOL_CAPABILITIES) - _internal_only_tools())
    assert not unaccounted, (
        f"routed tools that are neither catalogued nor marked internal-only: {unaccounted}. "
        f"A routed name with no capability record cannot enter IRREVERSIBLE_TOOLS (that set "
        f"is derived from TOOL_CAPABILITIES), so no confirmation gate can see it. Catalog "
        f"it, or - if it is not a tool - name it in INTERNAL_ONLY_TOOLS with the reason."
    )


def test_the_accounting_holds_for_the_EXECUTABLE_routed_names_specifically() -> None:
    """I1 restated on the subset that can actually run. Routability alone is a weak
    claim; this is the one that names code which executes."""
    executable = _executable() & _routed()
    assert executable, "precondition: routed names carry live handlers"
    invisible = sorted(executable - set(TOOL_CAPABILITIES))
    assert not invisible, (
        f"routed tools with a live handler and NO capability record: {invisible}. Each "
        f"executes, and each is structurally absent from IRREVERSIBLE_TOOLS — an external "
        f"effect nobody was asked about."
    )


def test_the_internal_only_marker_matches_what_the_dispatcher_rewrites_to() -> None:
    """Re-derived against the dispatcher's own rewrite target, so the marker cannot
    rot into a list of names the dispatcher no longer produces."""
    actual = _internal_only_tools()
    assert actual == EXPECTED_INTERNAL_ONLY, (
        f"INTERNAL_ONLY_TOOLS is {sorted(actual)}; the dispatcher's no-tool-selected "
        f"sentinel is {sorted(EXPECTED_INTERNAL_ONLY)} (src/dispatcher.py rewrites an "
        f"unknown verdict to it). If the dispatcher moved, move this marker with it in the "
        f"same commit — never delete it to make the completeness guard pass."
    )


def test_an_internal_only_name_claims_no_handler_and_no_capability() -> None:
    """The marker's meaning is "this is not a tool". All three halves are pinned, so
    the escape hatch cannot become a place to hide an executable tool."""
    for name in sorted(_internal_only_tools()):
        assert name not in TOOL_CAPABILITIES, (
            f"{name!r} is marked internal-only AND catalogued — it is either a tool (drop "
            f"the marker) or a sentinel (drop the capability record). Both cannot hold."
        )
        assert not hasattr(ToolRegistry, f"_do_{name}"), (
            f"{name!r} is marked internal-only but ToolRegistry._do_{name} exists. An "
            f"executable tool cannot claim to be a routing sentinel — that is exactly the "
            f"escape hatch this marker must not become."
        )
        assert name in _routed(), (
            f"{name!r} is marked internal-only but is not routed, so the marker is dead "
            f"weight — remove it, so the set names only what it governs."
        )


# --- I2: the deny-list covers every external-state writer ---------------------------


def test_the_external_state_writer_table_is_not_empty() -> None:
    """Directive 2: a guard over an empty table asserts nothing, and an empty table
    is the state that let this leak ship."""
    assert EXTERNAL_STATE_WRITERS, "the external-state-writer table is empty"


def test_every_external_state_writer_is_deny_listed() -> None:
    """I2 — the load-bearing one. This is the assertion F-1's entry gate leans on:
    nothing whose handler changes external state escapes confirmation."""
    unguarded = sorted(EXTERNAL_STATE_WRITERS - set(IRREVERSIBLE_TOOLS))
    assert not unguarded, (
        f"routed tools whose handlers change external state but which are NOT in "
        f"IRREVERSIBLE_TOOLS: {unguarded}. Each executes its effect unconfirmed, because the "
        f"confirmation gates read a set these names are not in. Either the reversibility "
        f"decision in the catalog is wrong or this table is — resolve it; do not delete the "
        f"name from the table."
    )


def test_every_external_state_writer_is_catalogued_and_routed() -> None:
    """The table's own precondition. A row naming an uncatalogued tool makes guard
    `..._external_state_writer_is_deny_listed` weaker than it reads."""
    uncatalogued = sorted(EXTERNAL_STATE_WRITERS - set(TOOL_CAPABILITIES))
    assert not uncatalogued, (
        f"EXTERNAL_STATE_WRITERS names tools with no capability record: {uncatalogued}. Every "
        f"row must be a catalogued tool, or the completeness invariant it guards is being "
        f"asserted over a fiction."
    )
    unrouted = sorted(EXTERNAL_STATE_WRITERS - _routed())
    assert not unrouted, f"EXTERNAL_STATE_WRITERS names unrouted tools: {unrouted}"


def test_the_deny_list_equals_the_catalogued_irreversible_set() -> None:
    """The derivation, restated at the call site so its failure mode is NAMED.
    `IRREVERSIBLE_TOOLS` is a `Final` frozenset built at import from
    `TOOL_CAPABILITIES`, so it is correct only while catalog and flag agree. A
    record carrying `reversible: False` that the deny-list does not name is
    invisible to every gate downstream; the missing producer for this class of bug
    is a capability record written outside the catalog's own discipline.
    """
    expected = {t for t, cap in TOOL_CAPABILITIES.items() if cap.get("reversible") is False}
    assert set(IRREVERSIBLE_TOOLS) == expected, (
        f"IRREVERSIBLE_TOOLS does not match the catalog: deny-list-only="
        f"{sorted(set(IRREVERSIBLE_TOOLS) - expected)}, catalog-only="
        f"{sorted(expected - set(IRREVERSIBLE_TOOLS))}"
    )


def test_no_deny_listed_tool_is_routed_as_a_live_read() -> None:
    """The audit harness's own law, re-checked here so this file stands alone: an
    irreversible tool must not sit in the LIVE tier, because LIVE fires real
    backends (`tests/suite/tier3_shadow_tracer/audit_harness.py`)."""
    from tests.suite.tier3_shadow_tracer.audit_harness import LIVE_TOOLS

    clash = sorted(set(IRREVERSIBLE_TOOLS) & set(LIVE_TOOLS))
    assert not clash, f"irreversible tools marked LIVE_EXEC: {clash}"


# --- the record shape the completeness claim depends on -----------------------------


@pytest.mark.parametrize("tool", sorted(TOOL_CAPABILITIES))
def test_every_catalogued_tool_carries_real_markers_and_a_guide(tool: str) -> None:
    """A catalog entry that cannot be scored is a catalog entry that never reaches
    its goal: `markers_for` feeds `_goal_markers` (`src/cognition.py:393`), so empty
    markers leave the tool invisible to deduction even when it is catalogued. The
    guide is the other half — `register_tool` counts it as a registration point, so a
    record without one is a half-registration."""
    assert markers_for(tool), f"{tool} has no markers, so deduction can never score it"
    from src.skills.sara_tool_skills import _SKILLS

    shipped = {name.removesuffix(".md") for name, _ in _SKILLS}
    assert tool in shipped, (
        f"{tool} is catalogued but ships no narration guide in sara_tool_skills._SKILLS. A "
        f"record without a guide is a half-registration: the narration lane has nothing to "
        f"read for a tool the router can already select."
    )


def test_the_catalogued_record_fields_are_exactly_the_shape_the_gates_read() -> None:
    """The keys and the `needs` enum, asserted once against the live dict rather than
    per tool. A renamed key would turn every `cap["..."]` read into an import-time
    `KeyError` far from the gate that needed it."""
    allowed_needs = {"bridge", "google", "network", "vault", "local", "none"}
    for tool, cap in TOOL_CAPABILITIES.items():
        assert set(cap) == {"goals", "markers", "needs", "reversible", "chains_with"}, (
            f"{tool} record keys are {sorted(cap)}; the gates read exactly this set"
        )
        assert cap["needs"] in allowed_needs, f"{tool} declares needs={cap['needs']!r}"
        assert isinstance(cap["markers"], tuple) and cap["markers"], tool
        assert isinstance(cap["chains_with"], tuple), tool
        assert isinstance(cap["reversible"], bool), tool


def test_the_catalog_stays_an_import_leaf() -> None:
    """`src/skills/capabilities.py` documents itself as "Zero src imports —
    `src/cognition.py` merges these markers into its scoring". That is why a tier1
    guard can import it without dragging the dispatcher in behind it. Checked
    structurally, because a silent import would turn this file into a second
    coupling point between the catalog and the dispatcher."""
    path = ROOT / "src" / "skills" / "capabilities.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            offenders = [a.name for a in node.names if a.name.split(".")[0] == "src"]
            assert not offenders, f"{path.name} imports {offenders}"
        if isinstance(node, ast.ImportFrom) and (node.module or "").split(".")[0] == "src":
            raise AssertionError(f"{path.name} imports from {node.module!r}")
