"""Tier 2a — OmniRoute live connectivity + real TTFT.

Target TTFT <250ms is the architectural aspiration; free pools routinely
exceed it, so the probe REPORTS the number honestly and passes on
reachability + first-token delivery (the matrix flags the TTFT gap).
"""

import time

import httpx
import pytest

from src.config import get_settings
from src.gateway import OmniRouteClient, Tier
from tests.live_probe.conftest import require_gateway

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
    """Stream one tiny FAST turn; record time-to-first-token honestly."""
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
    t0 = time.perf_counter()
    first_ms: float | None = None
    deltas = 0
    try:
        # 2026-09-14: 64-token budget (not 16) — the groq fallback is a
        # reasoning model and starves on 16 tokens (blank turn); 64 stays a
        # tiny turn while letting the fallback actually serve.
        async for delta in client.stream_chat(
            [{"role": "user", "content": "قل: تم"}], tier=Tier.FAST, max_tokens=64
        ):
            if first_ms is None:
                first_ms = (time.perf_counter() - t0) * 1000
            if delta:
                deltas += 1
            if deltas >= 3:
                break
    finally:
        await client.aclose()
    assert first_ms is not None, "no first token arrived — gateway silent"
    print(f"\n[LIVE] TTFT={first_ms:.0f}ms deltas={deltas} (target <250ms)")
