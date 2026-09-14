"""Tier 1 — OpenClaw Phase-4 bench scenarios A–E (mock doubles, zero live UI).

Each test runs one scenario from scenarios.py (shared with the
scripts/benchmark_openclaw.py runner — single source, two harnesses) and
asserts its contract. Doubles only: MockDesktop/MockUIA/MockWebPage/fake
fetchers. No Win32, no browser, no network.
"""

import pytest

from tests.suite.openclaw_bench.scenarios import ALL_SCENARIOS


@pytest.mark.parametrize("scenario", ALL_SCENARIOS, ids=lambda fn: fn.__name__)
async def test_bench_scenario(scenario):
    result = await scenario()
    assert result.passed, f"{result.name}: {result.detail}"
    assert result.latency_ms >= 0
    assert result.safety_violations == 0, f"{result.name}: violations counted"


async def test_bench_matrix_complete():
    """The battery covers every mandated scenario family exactly once."""
    names = sorted(fn.__name__ for fn in ALL_SCENARIOS)
    assert names == sorted(
        [
            "run_a1_silent_inspect",
            "run_a2_passive_fetch",
            "run_b1_web_fill_and_click",
            "run_b2_web_scroll",
            "run_c1_hotkey_preferred_over_click",
            "run_c2_run_dialog_flow",
            "run_d1_commit_parks_without_confirmation",
            "run_d2_forbidden_never_executes",
            "run_e1_popup_recovery",
            "run_e2_focus_loss_degrades",
            "run_e3_missing_element_graceful",
            "run_e4_stale_web_handle_recovers",
        ]
    )
