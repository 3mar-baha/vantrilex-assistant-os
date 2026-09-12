"""Tier 3 — coach scenarios: initiative, brevity, ambiguity, modality."""

import pytest

from tests.suite.tier3_shadow_tracer.coach import CoachAgent

pytestmark = pytest.mark.shadow


async def test_coach_defers_when_user_busy():
    coach = CoachAgent()
    v = await coach.scenario(
        "busy-owner", "initiative", "مشغول هسا", expected="defer", context={"value": "low"}
    )
    assert v.passed, v.fix


async def test_coach_engages_on_critical_value():
    coach = CoachAgent()
    v = await coach.scenario(
        "critical-mail",
        "initiative",
        "شوفلي بريدي الجديد",
        expected="engage",
        context={"value": "critical", "user_busy": True},
    )
    assert v.passed, v.fix


async def test_coach_short_for_fast_pace():
    coach = CoachAgent()
    v = await coach.scenario("quick-ask", "brevity", "شو الطقس", expected="short")
    assert v.passed, v.fix


async def test_coach_detailed_on_explicit_depth():
    coach = CoachAgent()
    v = await coach.scenario("explain", "brevity", "اشرحلي هالموضوع بالتفصيل", expected="detailed")
    assert v.passed, v.fix


async def test_coach_clarifies_irreversible_without_target():
    coach = CoachAgent()
    v = await coach.scenario("vague-close", "ambiguity", "سكري", expected="clarify")
    assert v.passed, v.fix


async def test_coach_executes_clear_irreversible():
    coach = CoachAgent()
    v = await coach.scenario("clear-close", "ambiguity", "سكري الآلة الحاسبة", expected="execute")
    assert v.passed, v.fix


async def test_coach_modality_demand_and_text():
    coach = CoachAgent()
    v1 = await coach.scenario("demand", "modality", "ابعثي رسالة صوتية", expected="voice")
    v2 = await coach.scenario("text", "modality", "رد نصي مش صوتي", expected="text")
    assert v1.passed, v1.fix
    assert v2.passed, v2.fix


async def test_coach_report_accumulates():
    coach = CoachAgent()
    await coach.scenario("a", "brevity", "مرحبا", expected="short")
    await coach.scenario("b", "modality", "رد نصي", expected="text")
    assert coach.report.passed == 2
