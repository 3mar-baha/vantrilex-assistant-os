"""H04 — TTFT monitor: first delta arrival timed; hang bound enforced."""

import time

from src.gateway import OmniRouteClient, Tier
from tests.live_harness.conftest import require_gateway
from tests.test_dispatcher import CHAINS


async def test_live_first_token_arrives():
    """Hang detection (<10 s), not a perf gate — the TTFT number is reported."""
    require_gateway()
    client = OmniRouteClient("http://localhost:20128/v1", "harness", chains=CHAINS)
    async with client:
        started = time.perf_counter()
        first_ms: float | None = None
        async for _ in client.stream_chat(
            [{"role": "user", "content": "قول تمام"}], tier=Tier.FAST, max_tokens=16
        ):
            if first_ms is None:
                first_ms = (time.perf_counter() - started) * 1000.0
            break
    assert first_ms is not None, "stream produced zero deltas"
    assert first_ms < 10_000, f"first token took {first_ms:.0f} ms (hang?)"
    print(f"\n[LIVE-TTFT] {first_ms:.0f} ms")
