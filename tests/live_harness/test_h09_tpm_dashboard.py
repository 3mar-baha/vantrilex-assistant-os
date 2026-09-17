"""H09 — TPM dashboard: live catalog size + quarantine registries readable."""

import httpx

from tests.live_harness.conftest import require_gateway


async def test_catalog_and_quarantine_visible():
    require_gateway()
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get("http://localhost:20128/v1/models")
    assert response.status_code == 200
    body = response.json()
    models = body.get("data", body) if isinstance(body, dict) else body
    assert isinstance(models, list) and len(models) > 0
    from src.gateway import _429_STREAK, _MODEL_COOLDOWNS

    print(
        f"\n[LIVE-TPM] models={len(models)} cooldowns={len(_MODEL_COOLDOWNS)} streaks={len(_429_STREAK)}"
    )
