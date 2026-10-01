"""Core-side WSS tunnel acceptor (sprint-3 3.4): exactly ONE authenticated bridge
session. The core listens (the daemon dials OUT through NAT); the token travels only
inside the first Hello frame and is NEVER logged; a peer silent past the watchdog is
dropped, and unresolved commands fail honestly with BridgeOffline.

Two accept-time gates live here (F-5), both on the unauthenticated edge:

  * PATH  — an upgrade is honoured only on ``bridge_path``. Before this, the
    handler never read the request path, so ``ws://host:PORT/admin`` reached a
    live tunnel exactly as ``/bridge`` did (``docs/AUDIT_REPORT.md:169``).
  * BACKOFF — N bad tokens from one peer inside a window lock that peer out for a
    cooldown. Dependency-free, in-memory and CAPPED: the peer key is
    attacker-chosen, so an uncapped dict is a memory leak
    (``docs/AUDIT_REPORT.md:159``).
"""

from __future__ import annotations

import asyncio
import hmac
import time
from typing import NamedTuple

from loguru import logger
from websockets.asyncio.server import ServerConnection, serve

from common.protocol import (
    AUTH_TIMEOUT_S,
    Envelope,
    Hello,
    HelloAck,
    ProtocolError,
    decode_frame,
    encode,
    new_envelope,
)

BRIDGE_PATH = "/bridge"
"""The one path an upgrade may arrive on.

``.env.example`` ships ``BRIDGE_SERVER_URL=wss://your-space-host/bridge`` and
``bridge/__main__.py`` dials that URL verbatim, so the deployed daemon already
requests this path — which is why enforcing it costs the owner nothing.

REACHABILITY, stated here because the acceptor cannot see the setting it
mirrors: nothing in ``src/`` reads ``BRIDGE_SERVER_URL``. It is a PC-side value
(``bridge/__main__.py:64``) and this process never receives it, so the path is a
constructor argument rather than a config key — no env var and no settings field
was added. A deployment serving the tunnel elsewhere passes ``bridge_path=``;
the GATE is unconditional either way.
"""

# --- F-5 auth backoff. Generous on purpose -------------------------------------
# The regression this risks is the OWNER's bridge, not the attacker's rate: the
# daemon redials with capped exponential backoff, and a rotated BRIDGE_TOKEN on
# the PC produces a steady drip of 4401s that a tight limit would turn into a
# self-inflicted outage. 20 bad tokens from one host in 5 minutes is a probe, not
# a flaky dial. Window <= lockout, so the slate is already clean the instant a
# cooldown lifts instead of re-locking on the next typo.
AUTH_FAIL_LIMIT = 20
AUTH_FAIL_WINDOW_S = 300.0
AUTH_LOCKOUT_S = 900.0

# Bounded state. AUTH_PEER_CAP is the ceiling on tracked peers — a host-keyed dict
# is still attacker-keyed. AUTH_LOG_CAP bounds the in-memory refusal sample; the
# COMPLETE record is the loguru stream, which every refusal writes to.
AUTH_PEER_CAP = 256
AUTH_LOG_CAP = 64

# Bad-token entries in the in-memory sample are additionally capped at 5 (the
# pre-existing cap). Every refusal is logged; only the sample is bounded.
AUTH_FAIL_LOG_CAP = 5

AUTH_LOCKOUT_CLOSE_CODE = 4429
"""Close code for "you are in a cooldown", distinct from 4401 "that token is wrong"
so an operator reading the core log can tell a backoff from a rejection."""


class _PeerAuth(NamedTuple):
    window_started: float
    failures: int
    locked_until: float


def _peer_key(remote_address) -> str:
    """The backoff bucket key for one peer — the HOST alone.

    Measured on websockets 15.0.1: ``connection.remote_address`` is a
    ``(host, port)`` tuple whose port is ephemeral per connection. Keying on the
    whole tuple would hand every attempt its own bucket, so the burst counter
    could never reach its threshold and the backoff would be dead code.
    """
    if isinstance(remote_address, (tuple, list)) and remote_address:
        return str(remote_address[0])
    return str(remote_address)


class BridgeOffline(RuntimeError):
    """No authenticated bridge session — commands cannot be delivered."""


class BridgeServer:
    def __init__(
        self,
        token: str,
        *,
        silence_timeout_s: float = 45.0,
        bridge_path: str = BRIDGE_PATH,
        auth_fail_limit: int = AUTH_FAIL_LIMIT,
        auth_fail_window_s: float = AUTH_FAIL_WINDOW_S,
        auth_lockout_s: float = AUTH_LOCKOUT_S,
    ):
        self._token = token
        self._silence_timeout_s = silence_timeout_s
        # Normalised so a deployment cannot lock ITSELF out with a stray slash:
        # "/bridge", "bridge" and "/bridge/" are one route, and a client dialing
        # a trailing slash is asking for the same resource.
        self._bridge_path = "/" + bridge_path.strip("/")
        self._auth_fail_limit = auth_fail_limit
        self._auth_fail_window_s = auth_fail_window_s
        self._auth_lockout_s = auth_lockout_s
        self._server = None
        self._session: ServerConnection | None = None
        self._pending: dict[str, asyncio.Future] = {}
        self.heartbeats = 0
        self.security_log: list[str] = []
        # AUTHZ-log-bounded: a bad-token burst stops growing the in-memory sample
        # after AUTH_FAIL_LOG_CAP entries; every refusal still reaches the log.
        self._auth_fails = 0
        self._peer_auth: dict[str, _PeerAuth] = {}

    async def start(self, host: str = "127.0.0.1", port: int = 0, *, process_request=None) -> int:
        self._server = await serve(
            self._handler,
            host,
            port,
            max_size=None,
            process_request=self._path_gate(process_request),
        )
        bound = self._server.sockets[0].getsockname()[1]
        # The enforced path is observable in the log, not only in the source: a
        # daemon that dials a different BRIDGE_SERVER_URL would otherwise fail
        # silently with a 404 the core never explains.
        logger.info(
            "bridge acceptor on {host}:{port} — the ONLY path that upgrades is {path}",
            host=host,
            port=bound,
            path=self._bridge_path,
        )
        return bound

    def _path_gate(self, responder):
        """PATH gate: refuse an upgrade on any path but the configured bridge path.

        Runs where the CALLER's ``process_request`` declined, so a surface sharing
        this port keeps answering first — ``src/main.py``'s ``/health`` responder
        returns a Response and never reaches the gate. Returning None is what
        permits the upgrade, which is why the check cannot live in the handler:
        by then the 101 is already on the wire and only a close code remains.

        404, not 403: a wrong path is not a resource, and 403 would confirm to a
        port-scanner that something IS mounted on this port. ``bridge/server.py``
        already answers 404 for an unknown route, so this is the house answer.
        """
        accepted = self._bridge_path

        async def process_request(connection, request):
            answered = None
            if responder is not None:
                answered = await responder(connection, request)
            if answered is not None:
                return answered
            if request.path.split("?")[0] == accepted:
                return None
            logger.warning(
                "bridge upgrade refused 404: path {path!r} is not the bridge path {accepted!r}"
                " (from {peer})",
                path=request.path,
                accepted=accepted,
                peer=connection.remote_address,
            )
            from websockets.datastructures import Headers
            from websockets.http11 import Response

            return Response(404, "Not Found", Headers(), b"not the bridge\n")

        return process_request

    # --- F-5 backoff bookkeeping ------------------------------------------------

    def _lockout_remaining(self, peer_key: str) -> float:
        """Seconds left on this peer's cooldown; 0.0 when it may try."""
        entry = self._peer_auth.get(peer_key)
        if entry is None:
            return 0.0
        return max(0.0, entry.locked_until - time.monotonic())

    def _record_auth_failure(self, peer_key: str) -> None:
        now = time.monotonic()
        entry = self._peer_auth.get(peer_key)
        if entry is None or now - entry.window_started >= self._auth_fail_window_s:
            entry = _PeerAuth(window_started=now, failures=0, locked_until=0.0)
        failures = entry.failures + 1
        locked_until = entry.locked_until
        if failures >= self._auth_fail_limit:
            locked_until = now + self._auth_lockout_s
        self._peer_auth[peer_key] = _PeerAuth(entry.window_started, failures, locked_until)
        self._evict_peer_auth()

    def _evict_peer_auth(self) -> None:
        """Hold the peer dict to AUTH_PEER_CAP — the DoS property.

        Evicts the entry closest to expiry (an already-unlocked one first, then
        the oldest window), so a full dict forgets STALE peers rather than new
        ones. Eviction can only ever release a cooldown, never impose one.
        """
        while len(self._peer_auth) > AUTH_PEER_CAP:
            victim = min(
                self._peer_auth,
                key=lambda key: (
                    self._peer_auth[key].locked_until,
                    self._peer_auth[key].window_started,
                ),
            )
            del self._peer_auth[victim]

    def _note_auth_refusal(
        self,
        peer,
        reason: str,
        *,
        sample: bool = True,
        cap: int = AUTH_LOG_CAP,
    ) -> None:
        """Log EVERY refusal; bound only the in-memory sample.

        The loguru warning is the complete record the owner reads — the requirement
        is that no refusal goes unlogged, not that an unbounded list grows with it.
        The `sample`/`cap` pair keeps each call site's own sampling law (the bad
        token path counts bad TOKENS, not list length); a refusal path that appended
        without a cap would be the memory leak this item exists to close.
        """
        logger.warning("bridge {reason} from {peer}", reason=reason, peer=peer)
        if sample and len(self.security_log) < cap:
            self.security_log.append(f"{reason} from {peer}")

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

    def online(self) -> bool:
        return self._session is not None

    async def send_cmd(self, cmd, args: dict, *, timeout_s: float = 20.0) -> dict:
        session = self._session
        if session is None:
            raise BridgeOffline("no bridge session")
        env = new_envelope(type="cmd", cmd=cmd, args=args)
        fut: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[env.id] = fut
        try:
            await session.send(encode(env))
            return await asyncio.wait_for(fut, timeout=timeout_s)
        except TimeoutError as exc:
            raise BridgeOffline(f"bridge did not answer {cmd} in {timeout_s}s") from exc
        finally:
            self._pending.pop(env.id, None)

    def _resolve_result(self, frame: Envelope) -> None:
        fut = self._pending.pop(frame.id, None)
        if fut is not None and not fut.done():
            fut.set_result(frame.payload)
        elif fut is None:
            logger.warning("result for unknown cmd id {id} — dropped", id=frame.id)

    async def _handler(self, connection: ServerConnection) -> None:
        peer = connection.remote_address
        peer_key = _peer_key(peer)
        # AUTHZ-peer-backoff: a peer in cooldown is refused BEFORE its first frame
        # is read, so the refusal costs no AUTH_TIMEOUT_S wait and no open socket.
        # This is the point of a cooldown — it throttles the CORRECT token too, so
        # an attacker cannot buy unlimited guesses by also sending a good one.
        remaining = self._lockout_remaining(peer_key)
        if remaining > 0:
            self._note_auth_refusal(peer, f"auth refused 4429: cooldown {remaining:.1f}s left")
            await connection.close(code=AUTH_LOCKOUT_CLOSE_CODE, reason="auth backoff")
            return
        try:
            raw = await asyncio.wait_for(connection.recv(), timeout=AUTH_TIMEOUT_S)
            frame = decode_frame(raw)
            if not isinstance(frame, Hello):
                self._note_auth_refusal(peer, "auth rejected: first frame not Hello")
                await connection.close(code=4400, reason="expected Hello")
                return
            if not hmac.compare_digest(frame.token, self._token):
                # AUTHZ-const-time: constant-time compare — timing the reject can
                # never leak the token's prefix.
                # AUTHZ-log-bounded: the in-memory bad-token sample stops growing at
                # AUTH_FAIL_LOG_CAP; the loguru warning is logged every time.
                self._auth_fails += 1
                self._record_auth_failure(peer_key)
                self._note_auth_refusal(
                    peer,
                    "auth rejected 4401: bad token",
                    sample=self._auth_fails <= AUTH_FAIL_LOG_CAP,
                )
                await connection.close(code=4401, reason="auth rejected")
                return
            # A peer that authenticates starts from a clean slate, so a transient
            # typo can never leave the owner one failure from a fresh cooldown.
            self._peer_auth.pop(peer_key, None)
            if self._session is not None:
                await connection.send(encode(HelloAck(ok=False, reason="another_session_active")))
                await connection.close(code=4400, reason="another session active")
                return
        except (TimeoutError, ProtocolError) as exc:
            self._note_auth_refusal(peer, f"auth rejected: {exc}")
            await connection.close(code=4400, reason="auth timeout")
            return

        self._session = connection
        await connection.send(encode(HelloAck(ok=True)))
        logger.info("bridge session online from {peer}", peer=peer)
        try:
            while True:
                raw = await asyncio.wait_for(connection.recv(), timeout=self._silence_timeout_s)
                frame = decode_frame(raw)
                if not isinstance(frame, Envelope):
                    continue
                if frame.type == "heartbeat":
                    self.heartbeats += 1
                elif frame.type == "result":
                    self._resolve_result(frame)
        except (TimeoutError, ProtocolError) as exc:
            logger.warning("bridge peer dropped: {exc}", exc=exc)
        finally:
            if self._session is connection:
                self._session = None
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_exception(BridgeOffline("bridge session dropped"))
            self._pending.clear()
            logger.info("bridge session ended ({peer})", peer=peer)
