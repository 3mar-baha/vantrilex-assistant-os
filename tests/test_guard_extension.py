"""$0.00 guard: the `gemini/` prefix and the daily-call backstop.

RED-first: written and run against the pre-change tree, where `gemini/` was
blocked and no daily ceiling existed. Both halves failed there.

The prefix half is the owner's 2026-10-03 decision: the Gemini key lives on
OmniRoute with no billing account attached, so dispatch cannot silently bill —
quota exhaustion returns 429, never a charge. The list stays STATIC: a
config-driven "has a key" list would weaken the invariant structurally, because
holding a key is not the same claim as being free.
"""

from __future__ import annotations

import pytest

from src.gateway import (
    _DAILY_CALLS,
    FREE_TIER_DAILY_CALL_CEILING,
    FREE_TIER_PREFIXES,
    PaidModelBlockedError,
    _claim_daily_budget,
    assert_zero_paid_model,
)


@pytest.fixture(autouse=True)
def _reset_budget():
    """Per-test budget slate, so one test's spend cannot decide another's."""
    _DAILY_CALLS.clear()
    import src.gateway as g

    g._DAILY_DAY = "1970-01-01"  # forces the first claim to open a fresh day
    yield
    _DAILY_CALLS.clear()


# --- the prefix allow-list -------------------------------------------------------


@pytest.mark.parametrize(
    "model",
    [
        "gemini/gemini-3.8-flash",
        "gemini/gemini-2.5-pro",
        "gemini/gemma-4-31b-it",
    ],
)
def test_gateway_held_gemini_prefix_is_free_by_construction(model):
    """The owner's key sits on OmniRoute with no billing attached."""
    assert_zero_paid_model(model)  # must not raise


def test_gemini_prefix_is_in_the_static_allow_list():
    assert "gemini/" in FREE_TIER_PREFIXES
    assert "groq/" in FREE_TIER_PREFIXES


@pytest.mark.parametrize(
    "model",
    [
        "openai/gpt-4o",
        "anthropic/claude-opus-4-5",
        "openrouter/google/gemini-3.8-flash",  # PAID route to the same model
        "gemini/gemini-3.8-flash:paid",
    ],
)
def test_paid_routes_to_gemini_remain_blocked(model):
    """Allowing the prefix must NOT open the paid OpenRouter route to it."""
    with pytest.raises(PaidModelBlockedError):
        assert_zero_paid_model(model)


def test_the_allow_list_is_not_config_driven():
    """A config-driven list replaces 'free by construction' with 'configured'."""
    assert isinstance(FREE_TIER_PREFIXES, tuple)
    assert all(isinstance(p, str) and p.endswith("/") for p in FREE_TIER_PREFIXES)


# --- the daily-call backstop -----------------------------------------------------


def test_calls_under_the_ceiling_are_allowed():
    for _ in range(5):
        _claim_daily_budget("gemini/gemini-3.8-flash")
    assert _DAILY_CALLS["gemini"] == 5


def test_the_ceiling_refuses_before_the_wire_and_fails_safely():
    """Exhaust the provider, then prove the next call is REFUSED, not sent."""
    for _ in range(FREE_TIER_DAILY_CALL_CEILING):
        _claim_daily_budget("gemini/gemini-3.8-flash")
    with pytest.raises(PaidModelBlockedError) as caught:
        _claim_daily_budget("gemini/gemini-3.8-flash")
    msg = str(caught.value)
    assert "gemini" in msg
    assert str(FREE_TIER_DAILY_CALL_CEILING) in msg
    assert "before the wire" in msg, "the refusal must say it happens pre-network"


def test_the_ceiling_is_per_provider_not_global():
    """Spending Gemini's budget must not block Groq."""
    for _ in range(FREE_TIER_DAILY_CALL_CEILING):
        _claim_daily_budget("gemini/gemini-3.8-flash")
    with pytest.raises(PaidModelBlockedError):
        _claim_daily_budget("gemini/gemini-3.8-flash")
    _claim_daily_budget("groq/openai/gpt-oss-120b")  # must NOT raise
    assert _DAILY_CALLS["groq"] == 1


def test_the_ceiling_raises_the_same_type_the_cascade_already_handles():
    """So a ceiling refusal falls through to the next chain entry, not the turn."""
    from src.gateway import GatewayError

    assert issubclass(PaidModelBlockedError, GatewayError)


def test_the_ceiling_is_conservative_against_the_providers_own_limit():
    """A guard that fires only after the provider's limit is not a guard."""
    assert 0 < FREE_TIER_DAILY_CALL_CEILING <= 1000
