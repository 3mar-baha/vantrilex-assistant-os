"""Shared wire protocol between the core tunnel and the PC bridge daemon (sprint-3 3.4).

Framing is one JSON document per websocket text frame, newline-free. The token travels
ONLY inside the first Hello frame and is never logged.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ValidationError

PROTOCOL_VERSION = 1
HEARTBEAT_INTERVAL_S = 15
DEAD_PEER_MULTIPLIER = 3  # drop a peer after HEARTBEAT_INTERVAL_S * 3 of silence (45 s)
AUTH_TIMEOUT_S = 10
MAX_FRAME_BYTES = 1_048_576
BACKOFF_CAP_S = 30.0

# v2.0 pass-1: +exec.screenshot (in-memory capture), +exec.close (guard-checked
# app close), +telemetry.app_sessions (minute-level usage report)
# STT-2 (owner 2026-09-04 7:07pm): +exec.list_apps — read-only running-process
# report (same class as telemetry.state: no confirmation gate)
# M2 (master directive 2026-09-05 §3): +exec.volume, +exec.media_control,
# +exec.screen_ocr, +file.upload, +file.download — the desktop-bridge tools
CmdName = Literal[
    "exec.launch",
    "exec.open",
    "exec.close",
    "exec.screenshot",
    "exec.list_apps",
    "exec.volume",
    "exec.media_control",
    "exec.screen_ocr",
    "file.upload",
    "file.download",
    "power",
    "wol",
    "telemetry.state",
    "telemetry.app_sessions",
]


class ProtocolError(Exception):
    """A frame violated the protocol (non-JSON, wrong version, wrong shape/size)."""


class Hello(BaseModel):
    v: int = PROTOCOL_VERSION
    token: str
    hostname: str


class HelloAck(BaseModel):
    v: int = PROTOCOL_VERSION
    ok: bool
    reason: str | None = None


class Envelope(BaseModel):
    v: int = PROTOCOL_VERSION
    id: str
    type: Literal["heartbeat", "cmd", "result", "event"]
    ts: datetime
    cmd: CmdName | None = None
    args: dict = {}
    status: Literal["ok", "error"] | None = None
    payload: dict = {}


def _now() -> datetime:
    return datetime.now(UTC)


def encode(msg: Hello | HelloAck | Envelope) -> bytes:
    return msg.model_dump_json().encode("utf-8")


def decode_frame(raw: bytes | str) -> Hello | HelloAck | Envelope:
    if len(raw) > MAX_FRAME_BYTES:
        raise ProtocolError(f"frame exceeds {MAX_FRAME_BYTES} bytes")
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ProtocolError(f"non-JSON frame ({exc})") from exc
    if not isinstance(data, dict):
        raise ProtocolError("frame is not a JSON object")
    if data.get("v") != PROTOCOL_VERSION:
        raise ProtocolError(f"unsupported protocol version: {data.get('v')!r}")
    try:
        if "type" in data:
            if "ts" not in data:
                data["ts"] = _now()
            return Envelope.model_validate(data)
        if "ok" in data:
            return HelloAck.model_validate(data)
        if "token" in data:
            return Hello.model_validate(data)
    except ValidationError as exc:
        raise ProtocolError(f"invalid frame shape: {exc.error_count()} error(s)") from exc
    raise ProtocolError("frame is neither Envelope, HelloAck, nor Hello")


def new_envelope(*, type: str, cmd: CmdName | None = None, **fields) -> Envelope:
    fields.setdefault("id", uuid.uuid4().hex)
    return Envelope(type=type, ts=_now(), cmd=cmd, **fields)
