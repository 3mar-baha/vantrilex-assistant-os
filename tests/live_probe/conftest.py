"""Live-probe shared seams: skip-soft when infra is offline (gate stays green)."""

import pytest

pytestmark = pytest.mark.live_probe


def require_gateway(settings) -> None:
    import httpx

    try:
        r = httpx.get(f"{settings.omniroute_base_url.rstrip('/')}/models", timeout=5.0)
        if r.status_code != 200:
            pytest.skip(f"gateway HTTP {r.status_code} — probe needs a live OmniRoute")
    except Exception as exc:  # noqa: BLE001 — fail-soft probe: any outage is a skip
        pytest.skip(f"gateway unreachable: {exc}")
