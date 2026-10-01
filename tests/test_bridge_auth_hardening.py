"""F-5 — the bridge acceptor's two auth gaps, plus the two folded-in Quick Wins.

Four properties, one guard each (plus the collateral that keeps them honest):

| Property | What it defends |
|---|---|
| PATH     | An upgrade arriving on any path but the configured bridge path is refused (404). Any-path upgrade is the audit's `S-3` (`docs/AUDIT_REPORT.md:169`). |
| BACKOFF  | N bad tokens from one peer lock that peer out, then release it when the cooldown expires. |
| BOUND    | The per-peer auth state is attacker-keyed, so it is capped — and the refusal log cannot grow either. |
| CONST    | The LAN token compare is constant-time AND cannot raise on a non-ASCII header. |

The boundary is REAL websockets over loopback and a REAL stdlib HTTP socket — no
mock at the auth surface, because the properties under test *are* the wire
behaviour. Only the peer key is injected, and only where a property genuinely
needs many distinct peers (loopback gives exactly one).

Measured, not assumed (websockets 15.0.1):
  * `connection.remote_address` is a `(host, port)` tuple and the port is
    EPHEMERAL per connection — so a peer bucket keyed on the whole tuple would
    hand every attempt its own bucket and the burst counter could never fire.
  * `hmac.compare_digest`'s `str` overload RAISES `TypeError: comparing strings
    with non-ASCII characters is not supported`, and `http.server` decodes
    headers as iso-8859-1, so any remote client can reach that raise on the LAN
    auth path. The compare must therefore be over BYTES.
"""

from __future__ import annotations

import asyncio
import io
import json
import socket
import tokenize
import urllib.error
import urllib.request
from pathlib import Path

import websockets.asyncio.client
from websockets.exceptions import ConnectionClosed, InvalidStatus

from bridge.server import LanServer
from common.protocol import Hello, encode
from src import bridge_server as bs
from src.bridge_server import BridgeServer

TOKEN = "your-f5-bridge-token-0123456789"


# --- helpers ------------------------------------------------------------------


async def _hello_close_code(url: str, token: str) -> int | None:
    """Connect, send one Hello, and report the close code the server answers with.

    Returns None when the connection is still open (the server neither closed nor
    answered), so a caller asserting a specific code cannot pass on a hang.
    """
    async with websockets.asyncio.client.connect(url, max_size=None) as ws:
        await ws.send(encode(Hello(token=token, hostname="probe")))
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=5)
        except ConnectionClosed as exc:
            return exc.rcvd.code if exc.rcvd is not None else None
        try:
            return json.loads(raw).get("code")
        except (ValueError, AttributeError):
            return None


async def _upgrade_status(url: str) -> int:
    """The HTTP status the handshake produced, or -1 when it upgraded (101)."""
    try:
        async with websockets.asyncio.client.connect(url, max_size=None):
            return 101
    except InvalidStatus as exc:
        return exc.response.status_code


def _raw_get(port: int, request_bytes: bytes) -> str:
    """One raw HTTP/1.1 request with full control of the header BYTES."""
    with socket.create_connection(("127.0.0.1", port), timeout=5) as sock:
        sock.sendall(request_bytes)
        chunks = []
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            chunks.append(chunk)
    return b"".join(chunks).decode("iso-8859-1")


def _http_get(url: str) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:  # noqa: ASYNC210 - loopback, bounded
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def _comments(path: str) -> list[str]:
    """Every COMMENT token in a file (code comments only — not docstrings/strings)."""
    src = Path(path).read_text(encoding="utf-8")
    return [
        tok.string
        for tok in tokenize.generate_tokens(io.StringIO(src).readline)
        if tok.type == tokenize.COMMENT
    ]


# --- PATH ---------------------------------------------------------------------


async def test_upgrade_on_the_root_path_is_refused_with_404():
    """The root path is the canonical attacker dial on a shared public port: it is
    not the bridge path, so it must never reach an upgrade."""
    server = BridgeServer(TOKEN)
    port = await server.start()
    try:
        assert await _upgrade_status(f"ws://127.0.0.1:{port}/") == 404
        assert server.online() is False
    finally:
        await server.close()


async def test_upgrade_on_an_arbitrary_path_is_refused_with_404():
    """Any path but the configured one is refused — not just the root, and not
    merely a prefix of the bridge path."""
    server = BridgeServer(TOKEN)
    port = await server.start()
    try:
        for path in ("/admin", "/bridge/extra", "/health/../bridge", "/bridge2"):
            assert await _upgrade_status(f"ws://127.0.0.1:{port}{path}") == 404, path
        assert server.online() is False
    finally:
        await server.close()


async def test_the_configured_bridge_path_upgrades_and_authenticates():
    """The gate must not cost the daemon its tunnel: the configured path still
    upgrades AND still authenticates."""
    server = BridgeServer(TOKEN)
    port = await server.start()
    try:
        async with websockets.asyncio.client.connect(
            f"ws://127.0.0.1:{port}/bridge", max_size=None
        ) as ws:
            await ws.send(encode(Hello(token=TOKEN, hostname="pc")))
            assert json.loads(await asyncio.wait_for(ws.recv(), timeout=5))["ok"] is True
            assert server.online() is True
    finally:
        await server.close()


async def test_a_query_string_does_not_defeat_the_path_gate():
    """`request.path` carries the query, so the gate compares the path component
    only — the same normalisation `src/main.py`'s health responder uses."""
    server = BridgeServer(TOKEN)
    port = await server.start()
    try:
        assert await _upgrade_status(f"ws://127.0.0.1:{port}/bridge?token=abc") == 101
        assert await _upgrade_status(f"ws://127.0.0.1:{port}/nope?path=/bridge") == 404
    finally:
        await server.close()


async def test_a_non_default_bridge_path_is_the_only_one_that_upgrades():
    """The path is a constructor argument, not a hardcoded literal: a deployment
    serving the tunnel elsewhere must be able to say so."""
    server = BridgeServer(TOKEN, bridge_path="/tunnel")
    port = await server.start()
    try:
        assert await _upgrade_status(f"ws://127.0.0.1:{port}/tunnel") == 101
        assert await _upgrade_status(f"ws://127.0.0.1:{port}/bridge") == 404
    finally:
        await server.close()


async def test_a_caller_supplied_health_responder_still_answers_before_the_gate():
    """The production port serves `/health` AND the tunnel (`src/main.py:25-31`).
    The gate runs only where the caller's responder declined, so `/health` keeps
    its 200 — a gate that swallowed it would kill the Space keep-alive."""
    from websockets.datastructures import Headers
    from websockets.http11 import Response

    async def health_responder(connection, request):
        """Mirrors src/main.py:25-28 — the shape this gate must not break."""
        if request.path.split("?")[0] == "/health":
            return Response(200, "OK", Headers(), b'{"status":"ok"}\n')
        return None

    server = BridgeServer(TOKEN)
    port = await server.start(process_request=health_responder)
    try:
        # urllib, not a raw socket: a plain (non-Upgrade) GET against the
        # websockets handshake server is answered by process_request and then
        # dies as handshake-failure log spam — measured, and the documented
        # reason `sara.ps1` probes /health with a complete Upgrade request
        # (docs/10-CHECKPOINT.md:560). urllib reads the response; a raw socket
        # waits for an EOF that never comes.
        status, body = await asyncio.to_thread(_http_get, f"http://127.0.0.1:{port}/health")
        assert status == 200 and json.loads(body)["status"] == "ok"
        assert await _upgrade_status(f"ws://127.0.0.1:{port}/bridge") == 101
        assert await _upgrade_status(f"ws://127.0.0.1:{port}/elsewhere") == 404
    finally:
        await server.close()


# --- BACKOFF ------------------------------------------------------------------


async def test_a_burst_of_bad_tokens_locks_the_peer_out():
    """Past the burst limit the peer is refused BEFORE its Hello is even read."""
    server = BridgeServer(TOKEN, auth_fail_limit=3, auth_fail_window_s=60.0, auth_lockout_s=60.0)
    port = await server.start()
    try:
        for i in range(3):
            assert await _hello_close_code(f"ws://127.0.0.1:{port}/bridge", f"bad-{i}") == 4401
        assert await _hello_close_code(f"ws://127.0.0.1:{port}/bridge", f"bad-3") != 4401
        assert server.online() is False
    finally:
        await server.close()


async def test_the_lockout_refuses_even_the_correct_token():
    """THE point of a cooldown: after a burst, the CORRECT token is refused too.
    A backoff that only throttled guesses would not slow an attacker down."""
    server = BridgeServer(TOKEN, auth_fail_limit=3, auth_fail_window_s=60.0, auth_lockout_s=60.0)
    port = await server.start()
    try:
        for i in range(3):
            await _hello_close_code(f"ws://127.0.0.1:{port}/bridge", f"bad-{i}")
        code = await _hello_close_code(f"ws://127.0.0.1:{port}/bridge", TOKEN)
        assert code == bs.AUTH_LOCKOUT_CLOSE_CODE, f"expected the lockout code, saw {code}"
        assert server.online() is False, "a locked-out peer must never open a session"
    finally:
        await server.close()


async def test_the_lockout_expires_and_the_correct_token_is_accepted_again():
    """A cooldown that never lifted would be a permanent ban on the owner's own
    bridge — the exact regression this guard exists to prevent."""
    server = BridgeServer(TOKEN, auth_fail_limit=3, auth_fail_window_s=0.2, auth_lockout_s=0.2)
    port = await server.start()
    try:
        for i in range(3):
            await _hello_close_code(f"ws://127.0.0.1:{port}/bridge", f"bad-{i}")
        assert await _hello_close_code(f"ws://127.0.0.1:{port}/bridge", TOKEN) == (
            bs.AUTH_LOCKOUT_CLOSE_CODE
        )
        await asyncio.sleep(0.35)  # past both the cooldown and the failure window
        async with websockets.asyncio.client.connect(
            f"ws://127.0.0.1:{port}/bridge", max_size=None
        ) as ws:
            await ws.send(encode(Hello(token=TOKEN, hostname="pc")))
            assert json.loads(await asyncio.wait_for(ws.recv(), timeout=5))["ok"] is True
            assert server.online() is True
    finally:
        await server.close()


async def test_a_successful_auth_clears_the_peer_backoff_record():
    """The owner must never be one typo away from an instant re-lock: a peer that
    authenticates successfully starts from a clean slate."""
    server = BridgeServer(TOKEN, auth_fail_limit=5, auth_fail_window_s=60.0, auth_lockout_s=60.0)
    port = await server.start()
    try:
        for i in range(2):
            await _hello_close_code(f"ws://127.0.0.1:{port}/bridge", f"bad-{i}")
        async with websockets.asyncio.client.connect(
            f"ws://127.0.0.1:{port}/bridge", max_size=None
        ) as ws:
            await ws.send(encode(Hello(token=TOKEN, hostname="pc")))
            assert json.loads(await asyncio.wait_for(ws.recv(), timeout=5))["ok"] is True
        assert server._peer_auth == {}, "a successful auth must clear the peer's record"
    finally:
        await server.close()


# --- BOUND --------------------------------------------------------------------


def test_peer_auth_state_is_bounded_however_many_distinct_peers_appear():
    """THE DoS property: the peer key is attacker-chosen, so the dict it feeds is
    capped. Asserted on the ACCOUNTING (the dict itself), not on a derived
    counter — a missing entry that left a separate counter untouched would pass
    a count-only check.

    Eviction, not insert-refusal: the most recent peer must still be tracked, so
    a full dict degrades to forgetting old peers rather than forgetting new ones.
    """
    server = BridgeServer(TOKEN)
    cap = bs.AUTH_PEER_CAP
    for i in range(cap * 3):
        server._record_auth_failure(f"10.0.{i // 256}.{i % 256}")
    assert len(server._peer_auth) <= cap
    assert f"10.0.{(cap * 3 - 1) // 256}.{(cap * 3 - 1) % 256}" in server._peer_auth


def test_cooldown_refusals_cannot_grow_the_security_log_without_bound():
    """A refusal logged on EVERY attempt is the owner's explicit requirement — so
    the in-memory sample must stay capped, or the fix ships the very leak the
    audit's V-9 named. The complete record is the loguru stream."""
    server = BridgeServer(TOKEN, auth_fail_limit=2, auth_fail_window_s=60.0, auth_lockout_s=60.0)
    for _ in range(bs.AUTH_PEER_CAP * 2):
        server._note_auth_refusal("1.2.3.4", "cooldown")
    assert len(server.security_log) <= bs.AUTH_LOG_CAP


def test_shipped_auth_thresholds_are_generous_enough_not_to_lock_out_a_flaky_owner():
    """The real regression risk is the OWNER's bridge, not the attacker's rate.
    These are laws, not a snapshot: tightening any of them below the floor turns a
    transient dial failure into a self-inflicted outage, and the window must not
    outlast the lockout or the owner re-locks the instant the cooldown lifts."""
    assert bs.AUTH_FAIL_LIMIT >= 10, "under 10 bad tokens is a flaky dial, not an attacker"
    assert bs.AUTH_FAIL_WINDOW_S >= 120.0, "a 2-minute window is too tight for a slow retry loop"
    assert bs.AUTH_LOCKOUT_S >= 300.0, "a lockout under 5 minutes outlives the daemon's backoff"
    assert bs.AUTH_FAIL_WINDOW_S <= bs.AUTH_LOCKOUT_S, (
        "the failure window must not outlast the lockout, or a good auth re-locks instantly"
    )


# --- CONST (QW-6: the LAN token compare) --------------------------------------


def test_the_lan_token_compare_is_constant_time():
    """The LAN surface gated the Bearer token with `!=`, which short-circuits on
    the first differing byte. Presence is the practical check — behavioural timing
    is not reliable in CI — so this pins the call AND the absence of the `!=` form.
    """
    src = Path("bridge/server.py").read_text(encoding="utf-8")
    assert "compare_digest" in src
    assert "import hmac" in src
    assert 'auth != f"Bearer' not in src, "the Bearer token must not use =="
    # The compared operands must be BYTES: the str overload raises TypeError on a
    # non-ASCII header, which is remotely reachable (measured — see module docstring).
    assert ".encode(" in src.split("compare_digest(")[1].split(")")[0], (
        "compare_digest must receive bytes, not str"
    )


async def test_the_lan_surface_answers_401_on_a_non_ascii_authorization_header():
    """HAZARD GUARD for the constant-time fix, not a RED against the shipped `!=`.

    `http.server` decodes headers as iso-8859-1, so any remote client can put a
    non-ASCII byte in `Authorization` (sent here as raw bytes — urllib refuses
    to encode one). `hmac.compare_digest`'s **str** overload raises
    `TypeError: comparing strings with non-ASCII characters is not supported`
    inside the request thread, which would turn a bad header into a dead
    connection instead of a 401. This asserts a clean 401 and a live surface
    afterwards; it is proven real by the str-overload mutant in the mutation run,
    not by the pre-fix code (`!=` cannot raise, so it is green before the fix).
    """
    from bridge.telemetry import live_state

    lan = LanServer(0, token=TOKEN, provider=live_state)
    _, port = await lan.start()
    try:
        raw = _raw_get(
            port,
            b"GET /telemetry/live-state HTTP/1.1\r\nHost: x\r\n"
            b"Authorization: Bearer \xff\xfe\r\nConnection: close\r\n\r\n",
        )
        assert " 401 " in raw.splitlines()[0], raw.splitlines()[:1]
        # the surface survived: /health still answers
        assert " 200 " in _raw_get(
            port, b"GET /health HTTP/1.1\r\nHost: x\r\nConnection: close\r\n\r\n"
        ).splitlines()[0]
    finally:
        await lan.close()


# --- QW-4: audit ids must not collide with code comments ----------------------


def test_audit_finding_ids_do_not_collide_with_the_comments_in_the_auth_paths():
    """`docs/AUDIT_REPORT.md` owns the `S-n` numbering (S-2 = executor
    confirmation_id, S-3 = the any-path upgrade, S-6 = the app-indexer
    whitelist). Code comments in these two files reused the same tokens for
    unrelated findings, so a grep for a finding landed on the wrong file. The
    comments now carry property tags instead; no `S-<digit>` may survive."""
    for path in ("src/bridge_server.py", "bridge/daemon.py"):
        text = Path(path).read_text(encoding="utf-8")
        assert "S-2" not in text and "S-3" not in text, f"{path} still cites an audit id"
        for comment in _comments(path):
            assert not any(
                token in comment for token in ("S-1", "S-2", "S-3", "S-4", "S-5", "S-6")
            ), f"{path}: colliding audit id in comment {comment!r}"
