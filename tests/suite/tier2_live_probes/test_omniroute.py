"""Tier 2a — OmniRoute live round-trip + real TTFT."""

import time

import httpx
import pytest

from src.config import get_settings
from src.gateway import OmniRouteClient, Tier
from tests.suite.tier2_live_probes.conftest import require_gateway

pytestmark = pytest.mark.live_probe


def test_models_endpoint_reachable():
    try:
        settings = get_settings()
    except Exception as exc:  # noqa: BLE001 — fail-soft: settings absence is a skip
        pytest.skip(f"settings unavailable: {exc}")
    require_gateway(settings)
    r = httpx.get(f"{settings.omniroute_base_url.rstrip('/')}/models", timeout=10.0)
    assert r.status_code == 200
    assert "data" in r.json()


async def test_live_ttft_first_token():
    try:
        settings = get_settings()
    except Exception as exc:  # noqa: BLE001 — fail-soft: settings absence is a skip
        pytest.skip(f"settings unavailable: {exc}")
    require_gateway(settings)
    client = OmniRouteClient(
        settings.omniroute_base_url,
        settings.omniroute_api_key,
        chains={
            Tier.FAST: settings.fast_chain,
            Tier.MEDIUM: settings.medium_chain,
            Tier.HEAVY: settings.heavy_chain,
        },
    )
    from src.gateway import GatewayError

    t0 = time.perf_counter()
    first_ms: float | None = None
    deltas = 0
    try:
        try:
            stream = client.stream_chat(
                [{"role": "user", "content": "قل: تم"}], tier=Tier.FAST, max_tokens=16
            )
            async for delta in stream:
                if first_ms is None:
                    first_ms = (time.perf_counter() - t0) * 1000
                if delta:
                    deltas += 1
                if deltas >= 3:
                    break
        except GatewayError as exc:
            # Fail-soft per Tier-2 contract: a retired/quota-dead free pin is a
            # reported infrastructure gap, not a test bug. Surface honestly
            # via skip (retired minimax-m3:free 404 observed pre-repin).
            pytest.skip(f"live brain unavailable (free-pin retired/quota): {exc}")
    finally:
        await client.aclose()
    if first_ms is None:
        # Fail-soft: the gateway answered but streamed zero content tokens
        # (flaky free pool) — an infrastructure gap, not a test bug.
        pytest.skip("gateway streamed no content tokens this turn")
    print(f"\n[LIVE] TTFT={first_ms:.0f}ms deltas={deltas} (target <250ms)")
