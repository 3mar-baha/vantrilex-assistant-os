"""Core-side WSS tunnel acceptor (sprint-3 3.4): exactly ONE authenticated bridge
session. The core listens (the daemon dials OUT through NAT); the token travels only
inside the first Hello frame and is NEVER logged; a peer silent past the watchdog is
dropped, and unresolved commands fail honestly with BridgeOffline."""

from __future__ import annotations

import asyncio

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


class BridgeOffline(RuntimeError):
    """No authenticated bridge session — commands cannot be delivered."""


class BridgeServer:
    def __init__(self, token: str, *, silence_timeout_s: float = 45.0):
        self._token = token
        self._silence_timeout_s = silence_timeout_s
        self._server = None
        self._session: ServerConnection | None = None
        self._pending: dict[str, asyncio.Future] = {}
        self.heartbeats = 0
        self.security_log: list[str] = []

    async def start(self, host: str = "127.0.0.1", port: int = 0) -> int:
        self._server = await serve(self._handler, host, port, max_size=None)
        return self._server.sockets[0].getsockname()[1]

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

    async def _handler(self, connection: ServerConnection) -> None:
        peer = connection.remote_address
        try:
            raw = await asyncio.wait_for(connection.recv(), timeout=AUTH_TIMEOUT_S)
            frame = decode_frame(raw)
            if not isinstance(frame, Hello):
                self.security_log.append(f"auth rejected: first frame not Hello from {peer}")
                await connection.close(code=4400, reason="expected Hello")
                return
            if frame.token != self._token:
                # log the peer and the verdict, never the presented token itself
                self.security_log.append(f"auth rejected 4401: bad token from {peer}")
                await connection.close(code=4401, reason="auth rejected")
                return
            if self._session is not None:
                await connection.send(encode(HelloAck(ok=False, reason="another_session_active")))
                await connection.close(code=4400, reason="another session active")
                return
        except (TimeoutError, ProtocolError) as exc:
            self.security_log.append(f"auth rejected: {exc} from {peer}")
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
                    fut = self._pending.pop(frame.id, None)
                    if fut is not None and not fut.done():
                        fut.set_result(frame.payload)
                    elif fut is None:
                        logger.warning("result for unknown cmd id {id} — dropped", id=frame.id)
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
