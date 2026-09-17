"""live_harness shared seams: credential-gated, skip-soft, diary-pristine.

Nothing here runs in CI green-path: every harness skips unless its backend is
provably live. Harnesses never read .env — required secrets arrive only via
explicitly exported environment variables (documented per module).
"""

import time

import pytest

pytestmark = pytest.mark.live_harness

MIN_PACING_S = 1.5
_last_call: list[float] = [0.0]


def pace() -> None:
    """Telegram pacing: ≥1.5s between live calls (FloodWait discipline)."""
    wait = MIN_PACING_S - (time.monotonic() - _last_call[0])
    if wait > 0:
        time.sleep(wait)
    _last_call[0] = time.monotonic()


def require_env(name: str) -> str:
    """Explicitly exported secret or skip — .env is never read here."""
    import os

    value = (os.environ.get(name) or "").strip()
    if not value:
        pytest.skip(f"{name} not exported — harness needs a live backend")
    return value


def require_gateway(base_url: str = "http://localhost:20128/v1") -> None:
    import httpx

    try:
        response = httpx.get(f"{base_url.rstrip('/')}/models", timeout=10.0)
    except Exception as exc:  # noqa: BLE001 — fail-soft probe
        pytest.skip(f"gateway unreachable: {exc}")
    if response.status_code != 200:
        pytest.skip(f"gateway HTTP {response.status_code}")
