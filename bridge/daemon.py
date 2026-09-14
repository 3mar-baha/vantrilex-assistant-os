"""PC-side bridge daemon (sprint-3 3.4): dials OUT to the core tunnel (outbound-only,
survives NAT, NEVER binds a listening socket), authenticates with the shared token inside
the first Hello, keeps the session warm with heartbeats, executes guard-checked commands,
and reconnects with capped exponential backoff + jitter."""

from __future__ import annotations

import asyncio
import platform
import random
from contextlib import suppress
from datetime import UTC, datetime
from typing import Any

from loguru import logger
from websockets.asyncio.client import connect
from websockets.exceptions import WebSocketException

from bridge.app_sessions import AppSessionTracker, UnknownForeground
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


def _suppress_cancel():
    """Session-state flush during task teardown: a CancelledError must not
    interrupt the final save, and must still propagate afterwards."""
    return suppress(asyncio.CancelledError)


class BridgeDaemon:
    def __init__(
        self,
        url: str,
        token: str,
        executor: Executor,
        *,
        heartbeat_interval_s: float = HEARTBEAT_INTERVAL_S,
        backoff_cap_s: float = BACKOFF_CAP_S,
        sessions: AppSessionTracker | None = None,
        session_tick_s: float = 60.0,
        openclaw: Any = None,
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
        self._openclaw = openclaw
        self._heartbeat_interval_s = heartbeat_interval_s
        self._backoff_cap_s = backoff_cap_s
        # pass-1 (v2.0 §3-د/3): minute-level app-session tracking on the daemon
        self._sessions = sessions
        self._session_tick_s = session_tick_s
        # OpenClaw Phase 2: the injected controller (breaker + backends).
        # None = chassis without backends (production default until Phase 3
        # binds Win32/Playwright/Scrapling) — verbs answer honestly.

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
            sessions_task = (
                asyncio.create_task(self._session_loop()) if self._sessions is not None else None
            )
            try:
                await self._serve_frames(ws, stop)
            finally:
                heartbeat.cancel()
                if sessions_task is not None:
                    sessions_task.cancel()
                    # flush the partial minute's state so a restart keeps the day
                    with _suppress_cancel():
                        self._sessions.save(now=datetime.now(UTC))

    async def _heartbeat_loop(self, ws) -> None:
        while True:
            await asyncio.sleep(self._heartbeat_interval_s)
            await ws.send(encode(new_envelope(type="heartbeat")))

    async def _session_loop(self) -> None:
        """Pass-1: sample the foreground app once per minute; a sample = a minute
        on that app's row. Locked/idle screens are gaps, probe failures are gaps —
        the loop itself never dies (best-effort telemetry, never a dependency)."""
        from bridge.app_sessions import categorize, whitelist_categories

        categories = whitelist_categories("config/whitelist.json")
        while True:
            try:
                from bridge.app_sessions import windows_foreground_app

                app = windows_foreground_app()
            except UnknownForeground:
                app = None
            except Exception:  # noqa: BLE001 — probe must never kill the loop
                app = None
            try:
                if app is not None:
                    self._sessions.tick(
                        app,
                        now=datetime.now(UTC),
                        category=categorize(app, categories),
                    )
            except Exception:  # noqa: BLE001
                logger.warning("app-session tick failed (skipped)")
            await asyncio.sleep(self._session_tick_s)

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
            elif frame.cmd == "exec.close":
                result = await self._executor.close(
                    args["name"],
                    confirmation_id=args.get("confirmation_id"),
                    audit_code=args.get("audit_code"),
                )
            elif frame.cmd == "exec.screenshot":
                result = await self._executor.screenshot(audit_code=args.get("audit_code"))
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
            elif frame.cmd == "telemetry.app_sessions":
                # pass-1 (v2.0 §3-د/3): the live tracker's day report — apps,
                # category totals, boot log. Missing tracker (legacy ctor) is
                # the honest empty report, never a crash.
                if self._sessions is not None:
                    return "ok", self._sessions.report(now=datetime.now(UTC))
                return "ok", {
                    "apps": [],
                    "categories": {},
                    "total_minutes": 0,
                    "screen_hours": 0.0,
                    "boot_log": [],
                }
            elif frame.cmd == "exec.list_apps":
                # STT-2 (owner 2026-09-04 7:07pm) + gap-ج (2026-09-05): the
                # REAL running processes — read-only, no confirmation gate
                # (telemetry.state class). Whitelist display names preferred;
                # every app named, nothing filtered.
                from bridge.app_sessions import running_apps_report

                return "ok", running_apps_report("config/whitelist.json")
            elif frame.cmd == "file.upload":
                # M2 (§3-A): phone -> PC drop — bytes + sanitized name; the
                # executor's roots wall decides where it lives
                import base64 as _b64

                result = await self._executor.file_upload(
                    _b64.b64decode(frame.args.get("data", "")),
                    str(frame.args.get("filename", "")),
                )
            elif frame.cmd == "file.download":
                # M2 (§3-A): PC -> phone read — whitelisted roots only
                result = await self._executor.file_download(str(frame.args.get("path", "")))
            elif frame.cmd == "exec.volume":
                # M2 (§3-B): the volume master — read-only-in-effect key events
                level = frame.args.get("level")
                result = await self._executor.volume(
                    str(frame.args.get("action", "")),
                    int(level) if level is not None else None,
                )
            elif frame.cmd == "exec.media_control":
                # M2 (§3-B): play/pause/next/prev media keys
                result = await self._executor.media(str(frame.args.get("command", "")))
            elif frame.cmd == "exec.screen_ocr":
                # M2 (§3-C): instant screen OCR — the core's vision lane rides
                # as an injected extractor; the daemon captures, the lane reads
                extractor = getattr(self, "_screen_vision", None)
                if extractor is None:
                    return "error", {
                        "detail": "screen OCR vision lane not configured",
                        "audit_code": mint_audit_code(),
                    }
                result = await self._executor.screen_ocr(extractor)
            elif frame.cmd == "openclaw.perceive":
                # Phase 2: read-only tree/screen scan via the injected
                # controller; unconfigured backends answer honestly.
                # Phase 3.1: full=true serves the diagnostic transcript
                # (screenshot + foreground + OCR) alongside the handles.
                if self._openclaw is None:
                    return "error", {
                        "detail": "openclaw controller not configured",
                        "audit_code": mint_audit_code(),
                    }
                if args.get("full"):
                    result = await self._openclaw.inspect(str(args.get("scope", "desktop")))
                    if result.status != "ok":
                        return result.status, result.model_dump()
                    import json as _json

                    result = ExecResult(
                        status="ok",
                        detail=_json.dumps(
                            {"handles": [], "inspection": _json.loads(result.detail)},
                            ensure_ascii=False,
                        ),
                        audit_code=result.audit_code,
                    )
                else:
                    result = await self._openclaw.perceive(str(args.get("scope", "desktop")))
            elif frame.cmd == "openclaw.act":
                # Phase 2: ONE pre-classified op through the breaker + the
                # injected actuator. Confirmation rides args (fail-closed).
                if self._openclaw is None:
                    return "error", {
                        "detail": "openclaw controller not configured",
                        "audit_code": mint_audit_code(),
                    }
                result = await self._openclaw.act(args.get("op") or {}, args.get("confirmation_id"))
            elif frame.cmd == "openclaw.fetch":
                # Phase 2: passive read-only web extraction (first-class
                # routing path, never a GUI fallback).
                if self._openclaw is None:
                    return "error", {
                        "detail": "openclaw controller not configured",
                        "audit_code": mint_audit_code(),
                    }
                result = await self._openclaw.fetch(str(args.get("url", "")))
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
