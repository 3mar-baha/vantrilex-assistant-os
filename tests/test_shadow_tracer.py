"""Live shadow tracer console: domain classification + rotation-safe tail.

Seam: scripts/live_shadow_tracer.classify_record / follow_events (public API).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

_TRACER_PATH = Path(__file__).resolve().parent.parent / "scripts" / "live_shadow_tracer.py"


def _load_tracer():
    spec = importlib.util.spec_from_file_location("live_shadow_tracer", _TRACER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def tracer():
    return _load_tracer()


def _record(name: str, function: str, message: str) -> dict:
    return {"record": {"name": name, "function": function, "message": message}}


@pytest.mark.parametrize(
    ("name", "function", "message", "expected"),
    [
        ("src.dispatcher", "dispatch", "router verdict: tool=gmail_search", "router"),
        ("src.associative", "recall", "RAG top-3 injected (600 chars)", "memory"),
        ("src.gateway", "chat", "TTFT 0.7s, PaidModelBlockedError armed", "generation"),
        ("src.pc_actions", "launch", "tool=launch confirmation_id=abc123", "tools"),
        ("src.fish_voice", "synthesize", "fish opus transcode 48kHz", "audio"),
        ("src.bot", "handle_voice", "voice note inbound, transcription ready", "ingest"),
        ("src.situational", "posture", "posture=FOCUS turns_since_refresh=7", "posture"),
        ("src.turn_counter", "bump_turn_counter", "turn 42 tallied", "posture"),
        ("src.voice_biometric_auth", "verify", "owner biometric match", "ingest"),
        ("src.bridge_server", "session", "bridge session online", "tools"),
        ("src.memory_ledger", "persist", "write-back digest upsert", "memory"),
    ],
)
def test_classify_domains(tracer, name: str, function: str, message: str, expected: str) -> None:
    assert tracer.classify_record(_record(name, function, message)) == expected


def test_classify_unknown_and_malformed_never_raise(tracer) -> None:
    assert tracer.classify_record(_record("src.obscure", "mystery", "something new")) == "system"
    assert tracer.classify_record({}) == "system"
    assert tracer.classify_record({"record": None}) == "system"


def test_follow_events_reads_appends_and_survives_rotation(tracer, tmp_path: Path) -> None:
    log = tmp_path / "shadow.jsonl"
    log.write_text(
        json.dumps(_record("src.dispatcher", "dispatch", "first")) + "\n", encoding="utf-8"
    )
    gen = tracer.follow_events(log, poll_s=0.0)
    assert next(gen)["record"]["message"] == "first"
    with log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(_record("src.gateway", "chat", "second")) + "\n")
    assert next(gen)["record"]["message"] == "second"
    log.write_text(json.dumps(_record("src.bot", "ping", "rotated")) + "\n", encoding="utf-8")
    assert next(gen)["record"]["message"] == "rotated"
    gen.close()
