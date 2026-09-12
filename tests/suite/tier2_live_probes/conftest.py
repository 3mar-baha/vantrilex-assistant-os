"""Tier 2 shared: fail-soft skips keep the gate green when infra is offline."""

import pytest

pytestmark = pytest.mark.live_probe


def require_gateway(settings) -> None:
    import httpx

    try:
        r = httpx.get(f"{settings.omniroute_base_url.rstrip('/')}/models", timeout=5.0)
        if r.status_code != 200:
            pytest.skip(f"gateway HTTP {r.status_code}")
    except Exception as exc:  # noqa: BLE001 — fail-soft probe: any outage is a skip
        pytest.skip(f"gateway unreachable: {exc}")
