"""PC-side bridge daemon (sprint-3 3.4): dials OUT to the core tunnel (outbound-only,
survives NAT, NEVER binds a listening socket), authenticates with the shared token inside
the first Hello, keeps the session warm with heartbeats, executes guard-checked commands,
and reconnects with capped exponential backoff + jitter."""

from __future__ import annotations

import asyncio
import platform
import random

from loguru import logger
from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException

from bridge.executor import ExecResult, Executor, mint_audit_code
from bridge.telemetry import live_state
from bridge.wol import send_wol
from common.protocol import (
    AUTH_TIMEOUT_S,
    BACKOFF_CAP_S,
    HEARTBEAT_INTERVAL_S,
    Envelope,
    Hello,
    HelloAck,
    ProtocolError,
    decode_frame,
    encode,
    new_envelope,
)


class BridgeDaemon:
    def __init__(
        self,
        url: str,
        token: str,
        executor: Executor,
        *,
        heartbeat_interval_s: float = HEARTBEAT_INTERVAL_S,
        backoff_cap_s: float = BACKOFF_CAP_S,
    ):
        self._url = url
        # S-6 (deferred queue): a PLAIN ws:// dial (not wss://) is a
        # deployment smell on the public internet — one loud warning at
        # startup so the owner sees it. (ws://127.0.0.1 local testing stays
        # quiet-safe: the warning is informational, never blocking.)
        if url.startswith("ws://") and "127.0.0.1" not in url and "localhost" not in url:
            logger.warning(
                "daemon dialing a PLAINTEXT ws:// endpoint ({}) — the bridge token "
                "crosses the internet unencrypted; set BRIDGE_SERVER_URL to wss://",
                url,
            )
        self._token = token
        self._executor = executor
        self._heartbeat_interval_s = heartbeat_interval_s
        self._backoff_cap_s = backoff_cap_s

    async def run(self, stop: asyncio.Event) -> None:
        attempt = 0
        delay = 0.0
        while not stop.is_set():
            try:
                await self._connect_once(stop)
                attempt = 0  # a full session happened — backoff restarts from the floor
            except (OSError, WebSocketException, ProtocolError) as exc:
                attempt += 1
                delay = min(self._backoff_cap_s, 2.0 ** (attempt - 1)) * random.uniform(0.8, 1.2)
                logger.warning("bridge down ({exc}); redial in {d:.1f}s", exc=exc, d=delay)
            if stop.is_set():
                return
            try:
                await asyncio.wait_for(stop.wait(), timeout=delay)
            except TimeoutError:
                pass

    async def _connect_once(self, stop: asyncio.Event) -> None:
        async with connect(self._url, max_size=None) as ws:
            await ws.send(encode(Hello(token=self._token, hostname=platform.node())))
            ack = decode_frame(await asyncio.wait_for(ws.recv(), timeout=AUTH_TIMEOUT_S))
            if not isinstance(ack, HelloAck) or not ack.ok:
                reason = getattr(ack, "reason", None) or "auth rejected"
                raise ProtocolError(f"auth refused: {reason}")
            logger.info("bridge session established")
            heartbeat = asyncio.create_task(self._heartbeat_loop(ws))
            try:
                await self._serve_frames(ws, stop)
            finally:
                heartbeat.cancel()

    async def _heartbeat_loop(self, ws) -> None:
        while True:
            await asyncio.sleep(self._heartbeat_interval_s)
            await ws.send(encode(new_envelope(type="heartbeat")))

    async def _serve_frames(self, ws, stop: asyncio.Event) -> None:
        while not stop.is_set():
            # race recv against stop so shutdown never waits on a silent peer
            recv = asyncio.ensure_future(ws.recv())
            stop_wait = asyncio.ensure_future(stop.wait())
            _done, _ = await asyncio.wait({recv, stop_wait}, return_when=asyncio.FIRST_COMPLETED)
            stop_wait.cancel()
            if stop.is_set():
                recv.cancel()
                return
            frame = decode_frame(recv.result())
            if not isinstance(frame, Envelope) or frame.type != "cmd":
                continue
            status, payload = await self._execute(frame)
            await ws.send(
                encode(new_envelope(type="result", id=frame.id, status=status, payload=payload))
            )

    async def _execute(self, frame: Envelope) -> tuple[str, dict]:
        args = frame.args
        try:
            if frame.cmd == "exec.launch":
                result = await self._executor.launch(
                    args["name"],
                    confirmation_id=args.get("confirmation_id"),
                    audit_code=args.get("audit_code"),
                )
            elif frame.cmd == "exec.open":
                result = await self._executor.open_path(
                    args["path"],
                    confirmation_id=args.get("confirmation_id"),
                    audit_code=args.get("audit_code"),
                )
            elif frame.cmd == "power":
                result = await self._executor.power(
                    args["action"],
                    confirmation_id=args["confirmation_id"],
                    audit_code=args.get("audit_code"),
                )
            elif frame.cmd == "wol":
                sent = await send_wol(
                    args["mac"], args.get("ip", "255.255.255.255"), args.get("port", 9)
                )
                result = ExecResult(
                    status="ok",
                    detail=f"magic packet sent ({sent} bytes)",
                    audit_code=mint_audit_code(),
                )
            elif frame.cmd == "telemetry.state":
                # never raises: live_state degrades unmeasurable metrics to None
                return "ok", live_state().model_dump(mode="json")
            else:
                result = ExecResult(
                    status="error",
                    detail=f"unknown cmd {frame.cmd!r}",
                    audit_code=mint_audit_code(),
                )
        except KeyError as exc:
            return "error", {"detail": f"missing arg {exc}", "audit_code": mint_audit_code()}
        except Exception as exc:  # noqa: BLE001 - the daemon must survive any handler crash
            logger.exception("command {cmd} crashed", cmd=frame.cmd)
            return "error", {"detail": str(exc), "audit_code": mint_audit_code()}
        return result.status, result.model_dump()


if __name__ == "__main__":
    # `python -m bridge.daemon` used to be a SILENT no-op (no main guard — the
    # module imported, exited rc=0, and the bridge NEVER started; live finding
    # 2026-09-04). Both entries now run the real daemon.
    import asyncio as _asyncio

    from bridge.__main__ import main as _main

    raise SystemExit(_asyncio.run(_main()))
