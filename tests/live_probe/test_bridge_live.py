"""Tier 2c (legacy rig) — WebSocket bridge connectivity + authentication.

Spins a real BridgeServer on loopback, completes a Hello handshake with the
real protocol framing, and proves a bad token is rejected. Also probes the
configured BRIDGE_SERVER_URL briefly (fail-soft: offline is reported, not fatal).
"""

import pytest

pytestmark = pytest.mark.live_probe


async def test_bridge_hello_auth_roundtrip():
    from common.protocol import Hello, decode_frame, new_envelope
    from src.bridge_server import BridgeServer

    server = BridgeServer("live-probe-token", silence_timeout_s=5.0)
    port = await server.start("127.0.0.1", 0)
    try:
        import websockets

        async with websockets.connect(f"ws://127.0.0.1:{port}/bridge") as ws:
            await ws.send(Hello(token="live-probe-token", hostname="probe").model_dump_json())
            raw = await ws.recv()
            msg = decode_frame(raw)
            assert (
                getattr(msg, "ok", True) is not False or getattr(msg, "payload", None) is not None
            )
            assert server.online()
            await ws.send(new_envelope(type="heartbeat").model_dump_json())
    finally:
        await server.close()


async def test_bridge_bad_token_rejected():
    from common.protocol import Hello
    from src.bridge_server import BridgeServer

    server = BridgeServer("correct-token", silence_timeout_s=5.0)
    port = await server.start("127.0.0.1", 0)
    try:
        import websockets

        async with websockets.connect(f"ws://127.0.0.1:{port}/bridge") as ws:
            await ws.send(Hello(token="wrong-token", hostname="probe").model_dump_json())
            try:
                raw = await ws.recv()
                assert raw is not None  # server answered (likely an auth error frame)
            except Exception:  # noqa: BLE001, S110 — server dropping the socket is also a valid rejection
                pass
            assert not server.online(), "bad token must never authenticate"
    finally:
        await server.close()


async def test_configured_bridge_endpoint_probe():
    """Fail-soft: report whether the configured bridge endpoint is reachable."""
    try:
        from src.config import get_settings

        settings = get_settings()
    except Exception as exc:  # noqa: BLE001 — settings absence is a skip
        pytest.skip(f"settings unavailable: {exc}")
    import asyncio

    import websockets

    url = settings.bridge_server_url
    try:
        async with asyncio.timeout(4):
            async with websockets.connect(url):
                pass
        print(f"\n[LIVE] bridge {url} reachable")
    except Exception as exc:  # noqa: BLE001 — offline is reported, not fatal
        pytest.skip(f"configured bridge offline ({url}): {type(exc).__name__}")
