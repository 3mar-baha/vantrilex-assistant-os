"""Tier 1 — $0.00 hard guardrails: paid-model circuit breaker + Fish key separation.

Hermetic: no network, no secrets (dummy keys only). The zero-paid invariant is
verified at two seams — the pure predicate and the client's network edge.
"""

import httpx
import pytest

from src.gateway import (
    GatewayError,
    OmniRouteClient,
    PaidModelBlockedError,
    Tier,
    assert_zero_paid_model,
)

FAST = "google/gemma-4-31b-it:free"
MEDIUM = "openrouter/nex-agi/nex-n2.5-mini:free"
HEAVY = "openrouter/nex-agi/nex-n2.5-pro:free"
ESCALATED = "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"
FB = "groq/openai/gpt-oss-120b"


@pytest.mark.parametrize("model", [FAST, MEDIUM, HEAVY, ESCALATED])
def test_free_suffix_models_pass(model):
    assert_zero_paid_model(model)  # must not raise


@pytest.mark.parametrize("model", ["groq/openai/gpt-oss-120b", "groq/llama-3.3-70b-versatile"])
def test_groq_free_tier_models_pass(model):
    assert_zero_paid_model(model)  # Groq lane is free-tier by construction


@pytest.mark.parametrize(
    "model",
    [
        "openai/gpt-4o",
        "anthropic/claude-opus-4-5",
        "openrouter/nvidia/nemotron-3-ultra-550b-a55b",  # escalation minus :free
        "google/gemma-4-31b-it",  # FAST pin minus :free
        "groq",  # prefix alone is not a model
        "",
        "   ",
    ],
)
def test_non_free_models_blocked(model):
    with pytest.raises(PaidModelBlockedError):
        assert_zero_paid_model(model)


def test_blocked_error_stays_gateway_compatible():
    """Callers catching GatewayError keep working; the breaker is loud, not silent."""
    assert issubclass(PaidModelBlockedError, GatewayError)


async def test_paid_model_never_reaches_network():
    """The breaker fires inside _attempt, before any request is built or sent."""
    seen: list[httpx.Request] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"choices": []})

    client = OmniRouteClient(
        "http://gw.test/v1",
        "test-key",
        chains={Tier.FAST: ["openai/gpt-4o"]},
        transport=httpx.MockTransport(_handler),
    )
    try:
        with pytest.raises(PaidModelBlockedError):
            await client.chat([{"role": "user", "content": "hi"}], tier=Tier.FAST)
    finally:
        await client.aclose()
    assert seen == [], f"paid model hit the wire: {seen}"


async def test_free_model_still_serves():
    """The breaker must not break the legitimate free path (regression lock)."""
    seen: list[str] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.path)
        body = 'data: {"choices": [{"delta": {"content": "تمام"}}]}\n\ndata: [DONE]\n\n'
        return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

    client = OmniRouteClient(
        "http://gw.test/v1",
        "test-key",
        chains={Tier.FAST: [FAST]},
        transport=httpx.MockTransport(_handler),
    )
    try:
        reply = await client.chat([{"role": "user", "content": "hi"}], tier=Tier.FAST)
    finally:
        await client.aclose()
    assert reply == "تمام"
    assert seen == ["/v1/chat/completions"]


def test_fish_dedicated_key_preferred_over_openrouter(make_settings):
    """Credential separation: FISH_AUDIO_API_KEY wins; OPENROUTER_API_KEY is fallback."""
    assert (
        make_settings(fish_audio_api_key="dedicated-fish-key").fish_audio_key
        == "dedicated-fish-key"
    )
    assert make_settings().fish_audio_key == "your-openrouter-key"  # fallback: shared pool key


async def test_fish_endpoint_configurable(make_settings):
    """Both speech surfaces addressable; OpenRouter speech stays the default."""
    from src.fish_voice import FISH_SPEECH_URL, FishVoice

    assert make_settings().fish_audio_endpoint == FISH_SPEECH_URL
    custom = "https://api.fish.audio/v1/tts"
    s = make_settings(fish_audio_endpoint=custom)
    assert s.fish_audio_endpoint == custom
    fish = FishVoice.from_settings(s)
    try:
        assert fish.endpoint == custom
        assert fish._api_key == "your-openrouter-key"  # no dedicated key in mirror
    finally:
        await fish.aclose()
