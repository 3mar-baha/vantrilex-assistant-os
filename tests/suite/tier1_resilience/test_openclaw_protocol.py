"""Tier 1 — OpenClaw Phase-2 wire-protocol contracts. Hermetic.

The tunnel boundary (core <-> PC daemon) speaks ONLY these Pydantic
schemas: a closed OpKind enum (no string-exec exists to smuggle), element
handles, single ops, DAGs, and transcripts. Both sides import the same
shapes — bridge owns the canonical definitions, src re-exports them, so
the wire can never drift between the two ends.
"""

import json

import pytest
from pydantic import ValidationError

from bridge.openclaw.protocol import (
    ActionDAG,
    ActionTranscript,
    ElementHandle,
    Op,
    OpKind,
)


def test_opkind_is_closed_no_string_exec():
    """The sandcastle invariant at the type level: there is no generic
    run/shell/exec member — an action the enum cannot name cannot travel."""
    names = {m.value for m in OpKind}
    assert names == {
        "focus",
        "click",
        "double_click",
        "right_click",
        "type_text",
        "hotkey",
        "scroll",
        "navigate",
        "extract",
        "screenshot",
        "inspect_tree",
    }
    for banned in ("run_command", "shell", "exec", "run", "command", "powershell", "cmd"):
        assert banned not in names


def test_unknown_op_rejected():
    with pytest.raises(ValidationError):
        Op(op="run_command", target=None, value="calc.exe")


def test_op_defaults_safe():
    op = Op(op=OpKind.SCREENSHOT)
    assert op.target is None and op.value is None
    assert op.reversibility == "reversible"  # the claim; the breaker recomputes
    assert op.verify is None


def test_element_handle_shape():
    el = ElementHandle(id="e12", role="button", name="حفظ", bbox=(10, 20, 120, 60))
    assert el.hotkey is None and el.source == "uia"
    web = ElementHandle(id="w3", role="link", name="next", source="dom")
    assert web.bbox is None


def test_dag_and_transcript_round_trip_over_the_wire():
    """JSON serialization survives the WSS boundary byte-identical in shape:
    dump on one side, validate on the other."""
    dag = ActionDAG(
        goal="افتحي المفكرة",
        ops=[Op(op=OpKind.HOTKEY, value="Win+R"), Op(op=OpKind.TYPE_TEXT, value="notepad")],
        weight=2,
        plan_id="plan-1",
    )
    wire = dag.model_dump_json()
    back = ActionDAG.model_validate_json(wire)
    assert back == dag
    assert json.loads(wire)["ops"][0]["op"] == "hotkey"

    transcript = ActionTranscript(
        plan_id="plan-1",
        success=True,
        observations=[{"op": "hotkey", "ok": True, "evidence": "run dialog focused"}],
        audit_codes=["PC-1"],
    )
    assert ActionTranscript.model_validate_json(transcript.model_dump_json()) == transcript


def test_src_reexports_identical_shapes():
    """One vocabulary, two importers: the core side IS the bridge side."""
    from src.openclaw import protocol as core_protocol

    assert core_protocol.Op is Op
    assert core_protocol.OpKind is OpKind
    assert core_protocol.ActionDAG is ActionDAG
    assert core_protocol.ActionTranscript is ActionTranscript
    assert core_protocol.ElementHandle is ElementHandle
