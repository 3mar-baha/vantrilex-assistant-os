"""H03 — Quota simulator: an invalid model fails fast live, burning nothing."""

import pytest

from src.gateway import GatewayError, OmniRouteClient, Tier
from tests.live_harness.conftest import require_gateway


async def test_invalid_model_fails_fast_live():
    require_gateway()
    client = OmniRouteClient(
        "http://localhost:20128/v1",
        "harness",
        chains={Tier.FAST: ["no-such-model:free"]},
    )
    async with client:
        with pytest.raises(GatewayError):
            await client.chat([{"role": "user", "content": "hi"}], tier=Tier.FAST)
