"""H05 — Bridge chaos (safe subset): a live daemon is NEVER disturbed.

If the daemon answers, skip — chaos against a live owner system is forbidden.
If it is down, the honest-offline contract is verified instead.
"""

import pytest

from src.tools import ToolRegistry


def _daemon_up() -> bool:
    import socket

    for port in (8000, 8443):
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1.0):
                return True
        except OSError:
            continue
    return False


async def test_bridge_down_means_honest_offline():
    if _daemon_up():
        pytest.skip("bridge daemon live — chaos forbidden on a live system")
    out = await ToolRegistry().call("telemetry", "")
    assert out and "مو متصل" in out
