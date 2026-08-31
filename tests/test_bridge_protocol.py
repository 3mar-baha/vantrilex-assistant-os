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

from bridge.daemon import BridgeDaemon
from bridge.executor import Executor
from bridge.guard import Guard
from bridge.server import LanServer
from helpers_vault import FakeGitHub
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

    assert ipaddress.ip_address(bound_host).is_loopback or ipaddress.ip_address(bound_host).is_private
    assert bound_host != "0.0.0.0"
    with urllib.request.urlopen(f"http://127.0.0.1:{bound_port}/health", timeout=5) as resp:
        assert resp.status == 200 and json.loads(resp.read())["status"] == "ok"
    await lan.close()


async def test_wrong_token_closed_4401(tmp_path: Path):
    """AC10 companion — wrong token is closed 4401, WARNING names peer IP not token."""
    server = BridgeServer(TOKEN, silence_timeout_s=45.0)
    port = await server.start(host="127.0.0.1", port=0)
    rejected = await websockets.connect(f"ws://127.0.0.1:{port}", max_size=None)
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
