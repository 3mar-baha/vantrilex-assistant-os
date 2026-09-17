"""P6 coverage batch 6a: bridge tunnel handshake matrix (master plan, Phase P6).

Real client/server over loopback ephemeral ports — no mocks at the security
boundary: auth accept/reject paths, session exclusivity, heartbeat counting,
result resolution, timeout honesty, and drop cleanup.
"""

import asyncio
import json
from datetime import UTC, datetime

from websockets.asyncio.client import connect

from common.protocol import Envelope, Hello, encode, new_envelope
from src.bridge_server import BridgeOffline, BridgeServer


async def _hello(token):
    return encode(Hello(token=token, hostname="pc"))


def _result_frame(env_id, payload):
    return encode(Envelope(v=1, id=env_id, type="result", ts=datetime.now(UTC), payload=payload))


async def test_happy_path_heartbeat_and_result():
    server = BridgeServer("tok", silence_timeout_s=5.0)
    port = await server.start()
    try:
        async with connect(f"ws://127.0.0.1:{port}") as ws:
            await ws.send(await _hello("tok"))
            raw = await ws.recv()
            assert json.loads(raw)["ok"] is True
            assert server.online()
            await ws.send(encode(new_envelope(type="heartbeat")))
            await asyncio.sleep(0.2)
            assert server.heartbeats >= 1
            result = {"status": "ok", "detail": "hi"}
            pending = asyncio.ensure_future(server.send_cmd("exec.screenshot", {}, timeout_s=5.0))
            for _ in range(100):
                if server._pending:
                    break
                await asyncio.sleep(0.02)
            env_id = next(iter(server._pending))
            await ws.send(_result_frame(env_id, result))
            assert await pending == result
    finally:
        await server.close()
    assert not server.online()


async def test_bad_token_rejected_and_capped():
    server = BridgeServer("tok", silence_timeout_s=5.0)
    port = await server.start()
    try:
        for _ in range(7):
            try:
                async with connect(f"ws://127.0.0.1:{port}") as ws:
                    await ws.send(await _hello("wrong"))
                    await ws.recv()
            except Exception:
                pass
        assert server._auth_fails == 7
        assert len(server.security_log) == 5
        assert not server.online()
    finally:
        await server.close()


async def test_non_hello_first_frame_rejected():
    server = BridgeServer("tok", silence_timeout_s=5.0)
    port = await server.start()
    try:
        async with connect(f"ws://127.0.0.1:{port}") as ws:
            await ws.send(b"not-json{{{")
            try:
                await ws.recv()
            except Exception:
                pass
        assert any("auth rejected" in line for line in server.security_log)
        assert not server.online()
    finally:
        await server.close()


async def test_second_session_rejected_while_first_live():
    server = BridgeServer("tok", silence_timeout_s=5.0)
    port = await server.start()
    try:
        async with connect(f"ws://127.0.0.1:{port}") as first:
            await first.send(await _hello("tok"))
            await first.recv()
            assert server.online()
            async with connect(f"ws://127.0.0.1:{port}") as second:
                await second.send(await _hello("tok"))
                raw = await second.recv()
                assert json.loads(raw)["ok"] is False
    finally:
        await server.close()


async def test_send_cmd_without_session_and_timeout():
    server = BridgeServer("tok", silence_timeout_s=5.0)
    try:
        await server.send_cmd("x", {})
    except BridgeOffline:
        pass
    else:
        raise AssertionError("expected BridgeOffline with no session")

    port = await server.start()
    try:
        async with connect(f"ws://127.0.0.1:{port}") as ws:
            await ws.send(await _hello("tok"))
            await ws.recv()
            try:
                await server.send_cmd("exec.screenshot", {}, timeout_s=0.2)
            except BridgeOffline as exc:
                assert "did not answer" in str(exc)
            else:
                raise AssertionError("expected timeout BridgeOffline")
    finally:
        await server.close()


async def test_unknown_result_id_dropped_and_drop_cleans_session():
    server = BridgeServer("tok", silence_timeout_s=0.3)
    port = await server.start()
    try:
        async with connect(f"ws://127.0.0.1:{port}") as ws:
            await ws.send(await _hello("tok"))
            await ws.recv()
            stray = new_envelope(type="result", cmd="exec.screenshot")
            stray.id = "no-such-id"
            await ws.send(encode(stray))
            await asyncio.sleep(0.6)
            assert not server.online()
            assert server._pending == {}
    finally:
        await server.close()
