"""Live shadow tracer console: domain classification + rotation-safe tail.

Seam: scripts/live_shadow_tracer.classify_record / follow_events (public API).
"""

from __future__ import annotations

import importlib.util
import io
import json
from pathlib import Path

import pytest
from rich.console import Console

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


def _loguru_record(name: str, function: str, message: str) -> dict:
    """Faithful serialized-loguru shape: time/level are dicts, not strings."""
    return {
        "text": message,
        "record": {
            "name": name,
            "function": function,
            "message": message,
            "level": {"name": "WARNING", "no": 30},
            "time": {"repr": "2026-09-18T14:53:32.092+0300", "timestamp": 1789732412.0},
        },
    }


def test_render_event_unwraps_loguru_time_dict(tracer) -> None:
    """Live incident 2026-09-18: timestamps rendered as `{'repr': '2026-09-1`."""
    stream = io.StringIO()
    tracer.render_event(
        Console(file=stream, width=200),
        _loguru_record("src.gateway", "_stream", "gateway model unavailable"),
    )
    text = stream.getvalue()
    assert "2026-09-18T14:53:32" in text
    assert "{'repr'" not in text


def test_classify_openrouter_slug_is_generation_not_router(tracer) -> None:
    """Live incident: `openrouter/…` model slug collided with the `router` keyword."""
    assert (
        tracer.classify_record(
            _record(
                "src.gateway",
                "_stream",
                "gateway empty reply | model=openrouter/nvidia/nemotron-3-ultra-550b-a55b:free",
            )
        )
        == "generation"
    )


def test_classify_quota_403_text_is_tools_not_generation(tracer) -> None:
    """Live incident: Google's `Cost` wording in the 403 body stole the record."""
    assert (
        tracer.classify_record(
            _record(
                "src.tools",
                "call",
                "tool 'gmail' failed: Google API HTTP 403: Quota exceeded for quota metric 'Total Query Cost'",
            )
        )
        == "tools"
    )


def test_classify_exhaustion_is_generation(tracer) -> None:
    assert (
        tracer.classify_record(
            _record("src.bot", "_stream_answer", "brain stream failed: all models exhausted")
        )
        == "generation"
    )


def test_wait_for_log_notifies_once_then_blocks(tracer, tmp_path: Path) -> None:
    """Live incident: the tracer spammed `Waiting for shadow log …` every 2 s."""
    stream = io.StringIO()
    missing = tmp_path / "absent.jsonl"
    with pytest.raises(TimeoutError):
        tracer.wait_for_log(Console(file=stream, width=200), missing, poll_s=0.0, timeout_s=0.05)
    assert stream.getvalue().count("Waiting for shadow log") == 1
