"""Item D (plan §1) — shadow-tracer HUD markers (Decision 10) + per-tool counters (Decision 8).

`scripts/live_shadow_tracer.py` is the whole of Terminal 2 today. Five of Decision 10's
six HUD markers already classify (plan §3): TTFT and model tier and `$0.00` cost land
in the `generation` group, tool latency in `tools`, Fish audio tags in `audio`. The
sixth — invariant checks — has no classifier group, so an invariant line is filed as
`system`, which is the gap item D closes. The test asserts all six so the sixth is
genuinely red rather than quietly absent.

Decision 8's per-tool counters read the same record stream the classifier already
consumes, so no new instrumentation is needed in `src/`: a tool call is a record
carrying the tracer's own established `tool '<name>'` marker (the keyword the `tools`
group already keys on, and the shape `src/tools.py:143` emits).

No wall-clock read is exercised here and no network is touched: the four vitals
sources are stubbed to `--` before `vitals_table()` is called, so the suite is
deterministic and adds nothing to the live-pool class.
"""

from __future__ import annotations

import importlib.util
import io
from pathlib import Path

import pytest
from rich.console import Console

TRACER_PATH = Path(__file__).resolve().parents[1] / "scripts" / "live_shadow_tracer.py"

# Decision 10's six HUD markers, each as (label, logger name, function, message,
# expected domain). The synthetic messages use the same spellings the live stream
# emits, so classification is exercised on realistic blobs.
HUD_MARKERS = [
    (
        "ttft",
        "src.gateway",
        "_stream",
        "TTFT 0.7s first-token ok",
        "generation",
    ),
    (
        "tool-latency",
        "src.tools",
        "call",
        "tool 'gmail' answered in 812ms",
        "tools",
    ),
    (
        "model-tier",
        "src.gateway",
        "chat",
        "tier=FAST gateway model=groq/openai/gpt-oss-120b",
        "generation",
    ),
    (
        "zero-cost",
        "src.gateway",
        "chat",
        "paidmodel guard: cost $0.00 for 1234 tokens",
        "generation",
    ),
    (
        "fish-audio",
        "src.fish_voice",
        "synthesize",
        "fish s2.1-pro-free opus tag [cheerful]",
        "audio",
    ),
    (
        "invariant",
        "src.security_gate",
        "check",
        "invariant check: ar-JO immersion PASS",
        "invariants",
    ),
]

# A real invariant report names the cost invariant, so the blob collides with the
# `generation` keywords. Rules are first-match-wins (`:56`), so the invariant group
# must be ordered ahead of `generation` or every invariant line is filed as a
# generation line and the HUD silently loses its sixth marker.
COST_COLLIDING_INVARIANT = "invariant: $0.00 cost PASS, zero unconfirmed cmd PASS"

TOOL_STREAM = [
    "src.tools|call|tool 'gmail' answered in 812ms",
    "src.tools|call|tool 'gmail' retried after a stall",
    "src.tools|call|tool 'calendar' listed 3 events",
    "src.gateway|chat|TTFT 0.7s first-token ok",  # a gateway call, but not a tool call
    "src.pc_actions|launch|confirmation_id pending",  # tools domain, no tool name
]


def _load_tracer():
    spec = importlib.util.spec_from_file_location("live_shadow_tracer_markers", TRACER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def tracer():
    return _load_tracer()


def _record(name: str, function: str, message: str) -> dict:
    return {"record": {"name": name, "function": function, "message": message}}


def _stream(blobs: list[str]) -> list[dict]:
    records = []
    for blob in blobs:
        name, function, message = blob.split("|", 2)
        records.append(_record(name, function, message))
    return records


def _render(table) -> str:
    stream = io.StringIO()
    Console(file=stream, width=200, no_color=True).print(table)
    return stream.getvalue()


# --- Decision 10: all six HUD markers classify ------------------------------------


@pytest.mark.parametrize(
    ("label", "name", "function", "message", "expected"),
    HUD_MARKERS,
    ids=[marker[0] for marker in HUD_MARKERS],
)
def test_hud_marker_classifies(
    tracer, label: str, name: str, function: str, message: str, expected: str
) -> None:
    """Every marker Decision 10 lists must land in a domain, not in `system`.

    Red: the `invariant` case, which today classifies as `system` because no
    classifier group names it. Green: a `("invariants", ("invariant", ...))` entry in
    `DOMAIN_RULES` that the other five do not disturb.
    """
    assert tracer.classify_record(_record(name, function, message)) == expected, (
        f"HUD marker {label!r} classified wrong for {message!r}"
    )


def test_invariant_marker_wins_over_the_cost_keyword(tracer) -> None:
    """A cost-colliding invariant line must still read as an invariant line.

    Red: `generation` claims it via `cost` / `$0`. Green: the invariant group is
    ordered before `generation`, which is the only lever first-match-wins offers.
    """
    assert (
        tracer.classify_record(
            _record("src.security_gate", "verify_invariants", COST_COLLIDING_INVARIANT)
        )
        == "invariants"
    )


def test_invariant_domain_has_a_hud_color(tracer) -> None:
    """`render_event` indexes `DOMAIN_COLORS[domain]` (`:232`) — a new group without a
    color is a KeyError on the owner's screen, not a missing row."""
    assert "invariants" in tracer.DOMAIN_COLORS, (
        f"DOMAIN_COLORS has no invariants entry; it has {sorted(tracer.DOMAIN_COLORS)}"
    )


# --- Decision 8: per-tool gateway-call counters ------------------------------------


def test_tool_call_counters_count_gateway_calls_per_tool(tracer) -> None:
    """Count what the record stream already carries: calls per named tool.

    Red: the function does not exist. Green: a `tool_call_counters(records)` that
    keys on the tracer's own `tool '<name>'` marker, so gmail is 2 and calendar is 1
    and a bare gateway record or an unnamed tools record contributes nothing.
    """
    assert tracer.tool_call_counters(_stream(TOOL_STREAM)) == {"gmail": 2, "calendar": 1}


def test_no_tool_records_is_an_empty_counter_map(tracer) -> None:
    """A turn that called no tool is `{}`, never `None` and never a defaultdict.

    Red: the function does not exist. Green: an empty record list yields `{}` so the
    HUD can print the row without a `TypeError` on `len(None)`.
    """
    assert tracer.tool_call_counters(_stream([])) == {}


def test_vitals_table_surfaces_the_per_tool_counter(tracer, monkeypatch) -> None:
    """Decision 8 puts the counters in the tracer's HUD, not only in a helper.

    Red: the helper does not exist / the vitals table ignores it. Green: the vitals
    table renders one row per tool with its count.
    """
    for probe in ("core_health", "bridge_sessions", "gateway_models", "turn_count"):
        monkeypatch.setattr(tracer, probe, lambda: "--")  # no socket, no HTTP, no disk
    monkeypatch.setattr(tracer, "tool_call_counters", lambda *a, **k: {"gmail": 2})
    lines = [line for line in _render(tracer.vitals_table()).splitlines() if "gmail" in line]
    assert lines, "the vitals table shows no per-tool counter row"
    assert any("2" in line for line in lines), f"the gmail row carries no count: {lines}"
