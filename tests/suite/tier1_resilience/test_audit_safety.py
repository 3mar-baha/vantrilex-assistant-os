"""Tier 1 — audit-harness safety contracts (zero-exclusion + no live side effects).

Hermetic: no network, no voice, no registry execution — only the harness's
static policy tables and report builder.
"""

import re

from src.skills.capabilities import IRREVERSIBLE_TOOLS, TOOL_CAPABILITIES
from tests.suite.tier3_shadow_tracer.audit_harness import (
    EXPECTED_SARA_VOICE,
    LIVE_TOOLS,
    PROMPTS,
    TESTER_VOICE,
    build_report,
    normalize_ar,
    word_f1,
)


def test_matrix_covers_every_capability_zero_exclusions():
    """The audit matrix == TOOL_CAPABILITIES exactly: no tool omitted, none extra."""
    assert set(PROMPTS) == set(TOOL_CAPABILITIES), (
        f"missing={set(TOOL_CAPABILITIES) - set(PROMPTS)} "
        f"extra={set(PROMPTS) - set(TOOL_CAPABILITIES)}"
    )


def test_no_irreversible_tool_runs_live():
    """Proof of the safety policy: irreversible tools can never be LIVE_EXEC."""
    assert not (IRREVERSIBLE_TOOLS & LIVE_TOOLS), (
        f"irreversible tools marked LIVE: {IRREVERSIBLE_TOOLS & LIVE_TOOLS}"
    )


def test_live_tools_are_read_only_by_construction():
    """LIVE tier admits only tools whose audit path performs reads (or a
    self-cleaning sandbox). Anything that changes owner state stays out."""
    side_effecting = {
        "launch",
        "close",
        "volume",
        "media",
        "file_fetch",
        "screenshot",
        "screen_ocr",
        "telemetry",
        "running_apps",
        "app_sessions",
        "gmail",
        "calendar",
        "tasks",
        "drive",
        "contacts",
        "fitness",
        "create_event",
        "create_task",
        "schedule",
        "list_reminders",
        "cancel_reminder",
        "brief",
        "multi_task",
        "youtube",
        "places",
        "deep_search",
    }
    assert not (side_effecting & LIVE_TOOLS)


def test_voice_ids_well_formed_and_distinct():
    hex32 = re.compile(r"^[0-9a-f]{32}$")
    assert hex32.match(TESTER_VOICE)
    assert hex32.match(EXPECTED_SARA_VOICE)
    assert TESTER_VOICE != EXPECTED_SARA_VOICE


def test_report_builder_renders_matrix():
    rec = {
        "tool": "weather",
        "prompt": "x",
        "tester_tts": {"status": "OK", "ms": 1.0, "bytes": 10},
        "asr": {"status": "OK", "ms": 1.0, "fidelity": 0.9, "heard": "x"},
        "tracer": {
            "winner": "weather",
            "confidence": 0.8,
            "rationale": "r",
            "alternatives": [],
            "friction": [],
            "diagnosis": "OK",
            "match": True,
            "ms": 1.0,
        },
        "router": {"status": "OK", "tool": "weather", "ms": 1.0, "match": True},
        "exec": {"tier": "LIVE", "status": "OK", "ms": 1.0, "detail": "sunny"},
        "sara_text": {"status": "OK", "text": "y"},
        "sara_tts": {"status": "OK", "ogg_ok": True, "bytes": 5, "ms": 1.0},
    }
    md = build_report(
        [rec],
        {"tester": {"voice_ok": True}, "sara": {"voice_ok": True}},
        {
            "date": "d",
            "commit": "c",
            "daemons": "x",
            "fish_dedicated": True,
            "endpoint": "e",
            "whisper": "w",
            "llm_chain": "test",
        },
    )
    assert "| weather |" in md and "zero exclusions" in md


def test_fidelity_metric_sane():
    assert word_f1("كيف الطقس بعمان", "كيف الطقس بعمان") == 1.0
    assert word_f1("أهلا", "وداعا") == 0.0
    assert normalize_ar("أهلاً") == normalize_ar("اهلا")
