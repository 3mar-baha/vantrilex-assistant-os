"""Sprint-3 §3.5: desktop telemetry — one psutil snapshot, one tunnel client, one
Arabic narration. Contract: docs/specs/sprint-3.md §3.5.

Boundaries: the real tunnel pair (BridgeServer + BridgeDaemon) and the real LAN HTTP
server are exercised for real (same rig as §3.4); only the BRAIN is doubled (its edge
is the OmniRoute free pool) and the OS psutil edge is patched only where a metric must
be forced to fail (AC5).
"""

from __future__ import annotations

import asyncio
import json
import time
import typing
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta

import psutil
import pytest

from bridge.daemon import BridgeDaemon
from bridge.executor import Executor
from bridge.guard import Guard
from bridge.server import LanServer
from bridge.telemetry import LiveState, live_state
from common.protocol import CmdName, new_envelope
from src.bridge_server import BridgeServer
from src.telemetry import OFFLINE_TEXT_AR, TelemetryClient

TOKEN = "your-github-test-pat-abcdef0123456789"
WHITELIST = json.dumps({"allowed_apps": [], "restricted_actions": []})

STATE_FIELDS = set(LiveState.model_fields)


def _sample_state(**overrides) -> LiveState:
    values = {
        "cpu_percent": 23.0,
        "ram_used_gb": 5.2,
        "ram_total_gb": 16.0,
        "disk_c_used_gb": 120.0,
        "disk_c_total_gb": 500.0,
        "disk_d_used_gb": 250.0,
        "uptime_hours": 3.5,
        "top_process": "chrome.exe",
        "top_process_cpu": 7.0,
        "captured_at": datetime.now(UTC),
    }
    values.update(overrides)
    return LiveState(**values)


class _Brain:
    """Scripted brain double recording (messages, kwargs) per chat call."""

    def __init__(self, reply: str | None = None, error: Exception | None = None):
        self.reply = reply
        self.error = error
        self.calls: list[tuple[list[dict], dict]] = []

    async def chat(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        if self.error is not None:
            raise self.error
        assert self.reply is not None
        return self.reply


def _tmp_guard(tmp_path) -> Guard:
    path = tmp_path / "whitelist.json"
    path.write_text(WHITELIST, encoding="utf-8")
    return Guard(str(path))


def _http_get(url: str, *, token: str | None = None) -> tuple[int, bytes]:
    request = urllib.request.Request(url)
    if token is not None:
        request.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(request, timeout=5) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


async def test_live_state_snapshot_shape():
    """AC1 — real snapshot on the test host: fields in range, captured_at ISO-UTC, <2 s."""
    started = time.perf_counter()
    state = live_state()
    elapsed = time.perf_counter() - started
    assert elapsed < 2.0, f"snapshot took {elapsed:.2f}s (budget 2s)"
    assert isinstance(state, LiveState)
    assert state.cpu_percent is not None and 0.0 <= state.cpu_percent <= 100.0
    assert state.ram_used_gb is not None and state.ram_total_gb is not None
    assert 0.0 < state.ram_used_gb <= state.ram_total_gb
    assert state.disk_c_used_gb is not None and state.disk_c_total_gb is not None
    assert 0.0 <= state.disk_c_used_gb <= state.disk_c_total_gb
    assert state.disk_d_used_gb is None or state.disk_d_used_gb >= 0.0
    assert state.uptime_hours is not None and state.uptime_hours >= 0.0
    assert isinstance(state.top_process, str) and state.top_process
    assert state.top_process_cpu >= 0.0
    assert state.captured_at.tzinfo is not None and state.captured_at.utcoffset() == timedelta(0)


async def test_lan_endpoint_token_gated(tmp_path):
    """AC2 — GET /telemetry/live-state: 401 without/wrong Bearer; 200 + LiveState with it."""
    provider_calls: list[bool] = []

    def provider() -> LiveState:
        provider_calls.append(True)
        return _sample_state(disk_d_used_gb=None)

    lan = LanServer(0, token=TOKEN, provider=provider)
    _, port = await lan.start()
    base = f"http://127.0.0.1:{port}/telemetry/live-state"
    try:
        status, _ = await asyncio.to_thread(_http_get, base)
        assert status == 401
        status, _ = await asyncio.to_thread(_http_get, base, token="wrong-token")
        assert status == 401
        status, body = await asyncio.to_thread(_http_get, base, token=TOKEN)
        assert status == 200
        state = LiveState.model_validate(json.loads(body))
        assert state.cpu_percent == 23.0
        assert provider_calls == [True]
    finally:
        await lan.close()

    # route must NOT exist when the provider is not wired (served only over authed surface)
    lan_bare = LanServer(0)
    _, port_bare = await lan_bare.start()
    try:
        status, _ = await asyncio.to_thread(
            _http_get, f"http://127.0.0.1:{port_bare}/telemetry/live-state", token=TOKEN
        )
        assert status == 404
    finally:
        await lan_bare.close()


async def test_telemetry_via_tunnel_roundtrip(tmp_path):
    """AC3 — core cmd telemetry.state -> daemon live_state() -> validated LiveState."""
    server = BridgeServer(TOKEN, silence_timeout_s=45.0)
    port = await server.start(host="127.0.0.1", port=0)
    executor = Executor(_tmp_guard(tmp_path))
    daemon = BridgeDaemon(
        f"ws://127.0.0.1:{port}", TOKEN, executor, heartbeat_interval_s=0.05, backoff_cap_s=0.1
    )
    stop = asyncio.Event()
    runner = asyncio.create_task(daemon.run(stop))
    try:
        for _ in range(100):
            await asyncio.sleep(0.05)
            if server.online():
                break
        assert server.online(), "daemon never registered"
        payload = await server.send_cmd("telemetry.state", {}, timeout_s=5.0)
        state = LiveState.model_validate(payload)
        assert state.cpu_percent is not None
        assert state.captured_at.tzinfo is not None
    finally:
        stop.set()
        await asyncio.wait_for(runner, timeout=5)
        await server.close()


async def test_narration_contains_real_numbers_and_fallback():
    """AC4 — narration carries the state's real numbers verbatim (FAST tier); brain
    unreachable -> deterministic fallback line with the raw numbers."""
    state = _sample_state()

    brain = _Brain(reply="المعالج 23% والرام 5.2 من 16 جيجا، كل شي تمام.")
    client = TelemetryClient(BridgeServer(TOKEN), brain)
    line = await client.narrate(state)
    assert "23" in line and "5.2" in line
    assert brain.calls, "brain never called"
    messages, kwargs = brain.calls[0]
    prompt = json.dumps(messages, ensure_ascii=False)
    assert "23" in prompt and "5.2" in prompt  # numbers travel as DATA
    from src.gateway import Tier

    assert kwargs.get("tier") == Tier.FAST
    assert kwargs.get("temperature") == 0.0

    boom = _Brain(error=RuntimeError("omniroute down"))
    fallback_client = TelemetryClient(BridgeServer(TOKEN), boom)
    fallback = await fallback_client.narrate(state)
    assert "23" in fallback and "5.2" in fallback and "16" in fallback
    assert "chrome.exe" in fallback
    assert fallback_client._bridge is not None  # chat layer object intact, nothing raised


async def test_missing_second_disk_degrades(monkeypatch):
    """AC5 — no D: drive -> disk_d_used_gb None; narration omits any D mention."""
    real_disk_usage = psutil.disk_usage

    def no_d_drive(path):
        if str(path).upper().startswith("D"):
            raise FileNotFoundError(2, "no such drive D:")
        return real_disk_usage(path)

    monkeypatch.setattr(psutil, "disk_usage", no_d_drive)
    state = live_state()
    assert state.disk_d_used_gb is None
    assert state.disk_c_used_gb is not None  # C: still measured

    boom = _Brain(error=RuntimeError("gateway down"))
    client = TelemetryClient(BridgeServer(TOKEN), boom)
    line = await client.narrate(state)
    assert "القرص دي" not in line and "D:" not in line  # the second disk is never mentioned


async def test_offline_bridge_reported_honestly():
    """AC6 — bridge offline -> the exact honest Arabic line, no raise, no fabricated numbers."""
    never_started = BridgeServer(TOKEN)  # no session -> send_cmd raises BridgeOffline
    brain = _Brain(reply="المعالج 99%")  # must never be called
    client = TelemetryClient(never_started, brain)
    line = await client.report()
    assert line == OFFLINE_TEXT_AR == "الجسر مو متصل هسا"
    assert brain.calls == []

    # a TIMEOUT mid-tunnel degrades the same way
    class _SlowBridge:
        async def send_cmd(self, cmd, args, *, timeout_s=20.0):
            await asyncio.sleep(timeout_s * 10)

    slow_client = TelemetryClient(_SlowBridge(), _Brain(reply="x"))
    assert await slow_client.report(timeout_s=0.05) == OFFLINE_TEXT_AR


async def test_payload_free_of_secrets():
    """AC7 — the served payload carries no token, no hostname, no file paths."""
    body_holder: dict[str, bytes] = {}

    def provider() -> LiveState:
        return _sample_state()

    lan = LanServer(0, token=TOKEN, provider=provider)
    _, port = await lan.start()
    try:
        status, body = await asyncio.to_thread(
            _http_get, f"http://127.0.0.1:{port}/telemetry/live-state", token=TOKEN
        )
        assert status == 200
        body_holder["body"] = body
    finally:
        await lan.close()

    text = body_holder["body"].decode("utf-8")
    assert TOKEN not in text
    assert "\\" not in text and "C:/" not in text  # no Windows paths
    payload = json.loads(text)
    assert set(payload) == STATE_FIELDS  # exact schema — no extra keys (no hostname)
    assert not any("hostname" in key for key in payload)


async def test_cmd_registered_and_correlated(tmp_path):
    """AC8 — telemetry.state is a registered CmdName and the daemon handler serves a
    real LiveState; unknown-id results are WARNed and dropped, never crash."""
    assert "telemetry.state" in typing.get_args(CmdName)

    executor = Executor(_tmp_guard(tmp_path))
    daemon = BridgeDaemon("ws://127.0.0.1:1", TOKEN, executor)
    frame = new_envelope(type="cmd", cmd="telemetry.state", args={})
    status, payload = await daemon._execute(frame)
    assert status == "ok"
    state = LiveState.model_validate(payload)
    assert state.cpu_percent is not None

    # unknown-id result: WARN + drop (3.4 correlation reuse) — no exception, no hang
    from loguru import logger

    records: list[dict] = []
    handler_id = logger.add(records.append, level="WARNING")
    try:
        server = BridgeServer(TOKEN)
        server._resolve_result(new_envelope(type="result", status="ok", payload={}))
        assert any("unknown" in r.record["message"].lower() for r in records)
    finally:
        logger.remove(handler_id)


@pytest.mark.parametrize(
    "broken_attr",
    ["cpu_percent", "virtual_memory", "boot_time", "process_iter"],
)
async def test_psutil_failure_degrades_never_crashes(monkeypatch, broken_attr):
    """Error-mode guard — psutil failing on ANY metric degrades that metric to None
    (or 'unknown') instead of crashing the snapshot."""

    def broken(*args, **kwargs):
        raise psutil.Error(f"psutil.{broken_attr} exploded")

    monkeypatch.setattr(psutil, broken_attr, broken)
    state = live_state()  # must not raise
    assert isinstance(state, LiveState)
    assert state.captured_at.tzinfo is not None
