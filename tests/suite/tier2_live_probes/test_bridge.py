"""Tier 2c — PC Bridge loopback auth + port-8000 daemon probe (fail-soft)."""

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
            # Keep the session honest: exercise the envelope seam too.
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
                await ws.recv()
            except Exception:  # noqa: BLE001, S110 — drop is a valid rejection
                pass
            assert not server.online(), "bad token must never authenticate"
    finally:
        await server.close()


async def test_bridge_lan_port_8000_probe():
    """Non-blocking: report whether anything answers on the Windows daemon port."""
    import asyncio

    import websockets

    for url in ("ws://127.0.0.1:8000/", "ws://127.0.0.1:8000/bridge"):
        try:
            async with asyncio.timeout(3):
                async with websockets.connect(url):
                    pass
            print(f"\n[LIVE] bridge daemon answering at {url}")
            return
        except Exception:  # noqa: BLE001, S112 — next URL is the fallback
            continue
    pytest.skip("bridge daemon port 8000 offline — honest skip (daemon not running)")
