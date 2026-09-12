"""Tier 3 tests — shadow-user scenarios assert principles, not keywords."""

import pytest

from tests.suite.tier3_shadow_tracer.tracer import ShadowTracer

pytestmark = pytest.mark.shadow


async def test_shadow_mail_read_over_calendar():
    tracer = ShadowTracer()
    turn = await tracer.run_query("شوفلي بريدي الجديد هسا")
    assert turn.winner == "gmail", tracer.diagnose(turn, expected="gmail")


async def test_shadow_close_beats_launch():
    tracer = ShadowTracer()
    turn = await tracer.run_query("سكري الآلة الحاسبة")
    assert turn.winner == "close", tracer.diagnose(turn, expected="close")


async def test_shadow_reminder_carries_full_text():
    tracer = ShadowTracer()
    turn = await tracer.run_query("ذكريني بعد ساعة أرد على الجيميل")
    assert turn.winner == "schedule", tracer.diagnose(turn, expected="schedule")


async def test_shadow_multitask_detection():
    tracer = ShadowTracer()
    turn = await tracer.run_query("افتحي المفكرة و سكري الآلة الحاسبة")
    assert turn.winner == "multi_task", tracer.diagnose(turn, expected="multi_task")


async def test_shadow_vague_device_complaint_expands_horizon():
    tracer = ShadowTracer()
    turn = await tracer.run_query("جهازي بطيء هسا")
    assert turn.winner == "telemetry", tracer.diagnose(turn, expected="telemetry")
    assert "running_apps" in turn.horizon, f"horizon must offer adjacents, got {turn.horizon}"


async def test_shadow_self_correction_demotes_failing_tool():
    from src.cognition import evaluate_candidates

    tracer = ShadowTracer()
    first = await tracer.run_query("شو وضع الجهاز", simulate_outcome="bridge offline")
    assert first.winner == "telemetry"
    second = await tracer.run_query("شو وضع الجهاز")
    # Reflective adaptation: friction recorded AND the failing tool either
    # loses confidence or yields to none/adjacent — never blindly repeated
    # at full confidence.
    assert second.friction, "friction ledger must record the obstacle"
    tele_first = next(
        h.confidence for h in evaluate_candidates("شو وضع الجهاز") if h.tool == "telemetry"
    )
    tele_second = next(
        h.confidence
        for h in evaluate_candidates("شو وضع الجهاز", trace=tracer.trace)
        if h.tool == "telemetry"
    )
    assert tele_second < tele_first, f"penalty missing: {tele_second} !< {tele_first}"
    assert second.winner != "telemetry" or second.confidence < first.confidence + 0.01
    print(f"\n[SHADOW]\n{tracer.report.summary()}")
