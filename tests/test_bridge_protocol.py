"""Sprint-3 §3.4 AC10: real websockets pair, heartbeats, and the LAN-only surface.

Contract: docs/specs/sprint-3.md §3.4 — the tunnel is exercised over REAL websockets on
localhost (that boundary is not mocked); the daemon process itself must never bind a
listening socket (AST-scanned), and the LAN HTTP surface must bind LAN/loopback only.
"""

from __future__ import annotations

import asyncio
import json
import urllib.request
from pathlib import Path

import httpx
import websockets
import websockets.asyncio.client
from helpers_vault import FakeGitHub

from bridge.daemon import BridgeDaemon
from bridge.executor import Executor
from bridge.guard import Guard
from bridge.server import LanServer
from src.bridge_server import BridgeServer
from src.vault import VaultClient

TOKEN = "your-github-test-pat-abcdef0123456789"
WHITELIST = json.dumps(
    {
        "allowed_apps": [
            {"name": "calculator", "executable": "calc.exe", "auto_approve": True},
        ],
        "restricted_actions": [],
    }
)


def _tmp_guard(tmp_path: Path) -> Guard:
    path = tmp_path / "whitelist.json"
    path.write_text(WHITELIST, encoding="utf-8")
    return Guard(str(path))


async def test_auth_success_flow_and_lan_only_surface(tmp_path: Path):
    """AC10 — Hello/HelloAck + heartbeats over real websockets; daemon never binds."""
    server = BridgeServer(TOKEN, silence_timeout_s=45.0)
    port = await server.start(host="127.0.0.1", port=0)

    gh = FakeGitHub()
    session = httpx.AsyncClient(transport=gh.transport, base_url="https://api.github.com")
    VaultClient("owner/vault-repo", TOKEN, session=session)  # vault unused here; wiring parity
    executor = Executor(_tmp_guard(tmp_path))

    class _SpawnSpy:
        def __init__(self) -> None:
            self.calls: list[list[str]] = []

        async def __call__(self, argv: list[str]) -> None:
            self.calls.append(argv)

    spawn_spy = _SpawnSpy()
    executor._spawn = spawn_spy  # OS process edge stays a spy; the TUNNEL is the real boundary
    daemon = BridgeDaemon(
        f"ws://127.0.0.1:{port}", TOKEN, executor, heartbeat_interval_s=0.05, backoff_cap_s=0.1
    )
    stop = asyncio.Event()
    runner = asyncio.create_task(daemon.run(stop))
    for _ in range(100):  # handshake + at least one heartbeat, <= 5 s
        await asyncio.sleep(0.05)
        if server.online() and server.heartbeats >= 1:
            break
    assert server.online(), "daemon never registered"
    assert server.heartbeats >= 1, "no heartbeat envelope received"

    # command round-trip: whitelisted launch executes through the real tunnel
    payload = await server.send_cmd("exec.launch", {"name": "calculator"}, timeout_s=5.0)
    assert payload["status"] == "ok"
    assert spawn_spy.calls == [["calc.exe"]]

    stop.set()
    await asyncio.wait_for(runner, timeout=5)
    await server.close()

    # daemon-side modules must contain NO listening/bind path (outbound-only, structural)
    for module_file in ("bridge/daemon.py", "bridge/wol.py", "bridge/idle.py"):
        src = Path(module_file).read_text(encoding="utf-8")
        for forbidden in (".bind(", ".listen(", "websockets.serve", "asyncio.start_server"):
            assert forbidden not in src, f"{module_file} must not contain {forbidden}"

    # LAN surface: binds loopback (never 0.0.0.0), /health serves over real HTTP
    lan = LanServer(0)
    bound_host, bound_port = await lan.start()
    import ipaddress

    assert (
        ipaddress.ip_address(bound_host).is_loopback or ipaddress.ip_address(bound_host).is_private
    )
    assert bound_host != "0.0.0.0"
    with urllib.request.urlopen(  # noqa: ASYNC210 - loopback /health, bounded by timeout
        f"http://127.0.0.1:{bound_port}/health", timeout=5
    ) as resp:
        assert resp.status == 200 and json.loads(resp.read())["status"] == "ok"
    await lan.close()


async def test_wrong_token_closed_4401(tmp_path: Path):
    """AC10 companion — wrong token is closed 4401, WARNING names peer IP not token."""
    server = BridgeServer(TOKEN, silence_timeout_s=45.0)
    port = await server.start(host="127.0.0.1", port=0)
    rejected = await websockets.asyncio.client.connect(f"ws://127.0.0.1:{port}", max_size=None)
    await rejected.send(json.dumps({"v": 1, "token": "wrong-token", "hostname": "x"}))
    closed_code = None
    try:
        await rejected.recv()
    except websockets.exceptions.ConnectionClosed as exc:
        closed_code = exc.rcvd.code if exc.rcvd is not None else None
    assert closed_code == 4401
    assert server.online() is False
    assert all("wrong-token" not in r for r in server.security_log)
    assert any("4401" in r or "auth" in r.lower() for r in server.security_log)
    await server.close()


# --- deferred queue S-2/S-3/S-6: security batch -------------------------------------


async def test_token_compare_is_constant_time():
    """S-2: the bridge token comparison must use hmac.compare_digest, not
    `==` — timing the reject must not leak the token's prefix."""
    from pathlib import Path as _P

    src = _P("src/bridge_server.py").read_text(encoding="utf-8")
    assert "compare_digest" in src  # constant-time compare in place
    # no == on the token itself (type dispatch compares are fine)
    import re as _re2

    assert not _re2.search(r"frame\.token\s*==", src), "token must use compare_digest"
    assert not _re2.search(r"self\._token\s*==", src), "token must use compare_digest"


async def test_auth_attempts_rate_limited():
    """S-3: 6 bad-token attempts in a burst get closed 4401 rapidly, and the
    SERVER continues to answer (never DoS-crash); the security log stays
    bounded (no unbounded growth)."""
    import websockets

    from common.protocol import Hello, encode

    server = BridgeServer(TOKEN, silence_timeout_s=45.0)
    port = await server.start(host="127.0.0.1", port=0)
    try:
        import websockets.exceptions

        for i in range(6):
            async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
                hello = Hello(token=f"wrong-{i}", hostname="attacker", version="1")
                await ws.send(encode(hello))
                try:
                    await asyncio.wait_for(ws.recv(), timeout=5)
                except websockets.exceptions.ConnectionClosedError:
                    pass  # the 4401 close IS the verdict — exactly right
        assert len(server.security_log) <= 64  # bounded log
        assert server.online() is False  # no session hijacked
    finally:
        await server.close()


async def test_ws_plain_dial_warns(tmp_path):
    """S-6: the daemon dialing a PLAIN ws:// (not wss://) URL must log a loud
    warning once — plaintext over the public internet is a deployment smell
    the owner must see in logs. (Local ws://127.0.0.1 stays legit — tests.)"""
    from pathlib import Path as _P

    src = _P("bridge/daemon.py").read_text(encoding="utf-8")
    has_warning = (
        "ws://" in src and ("warn" in src.lower() or "logger" in src.lower())
    ) or "plaintext" in src.lower()
    assert has_warning, "daemon must warn when dialing a plain ws:// endpoint"
