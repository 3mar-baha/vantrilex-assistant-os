"""P6 coverage gap pins, batch 2 (master transformation plan, Phase P6).

Gateway retry/quarantine branches and coordinator close-flow branches with
zero prior coverage. All doubles sit at system boundaries (transport, bridge,
vault, clock); assertions target observable outcomes.
"""

from datetime import UTC, datetime, timedelta

import httpx
import pytest

from src.gateway import GatewayError, OmniRouteClient, Tier
from tests.test_gateway_failfast import _chunk, _Scripted, _sse


@pytest.fixture(autouse=True)
def _clear_cooldowns():
    from src.gateway import _429_STREAK, _MODEL_COOLDOWNS

    _MODEL_COOLDOWNS.clear()
    _429_STREAK.clear()
    yield
    _MODEL_COOLDOWNS.clear()
    _429_STREAK.clear()


def _client(script, chains):
    return OmniRouteClient(
        "http://gw.test/v1", "test-key", chains=chains, transport=script.transport()
    )


async def _collect(gen):
    return [d async for d in gen]


def test_classify_quota_keyword_fatal_default_transient():
    from src.gateway import _classify

    assert _classify(429, "provider says quota exhausted for the key") == "quota"
    assert _classify(429, "billing credit insufficient") == "quota"
    assert _classify(418, "teapot") == "fatal"
    assert _classify(503, "overloaded") == "transient"


async def test_mid_stream_failure_reports_delta_count():
    async def _flaky(self, model, payload):
        yield "part"
        raise httpx.ConnectError("rst mid-stream")

    client = _client(_Scripted(), {Tier.FAST: ["m:free"]})
    client._attempt = _flaky.__get__(client)
    async with client:
        with pytest.raises(GatewayError, match=r"mid-stream failure.*after 1 deltas"):
            await _collect(client.stream_chat([{"role": "user", "content": "hi"}]))


async def test_transport_retry_then_serves(monkeypatch):
    import src.gateway as gateway_mod

    calls = {"n": 0}

    async def _flaky_then_ok(self, model, payload):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("blip")
        yield "recovered"

    async def _instant(delay):
        return None

    monkeypatch.setattr(gateway_mod, "_sleep", _instant)
    client = _client(_Scripted(), {Tier.FAST: ["m:free"]})
    client._attempt = _flaky_then_ok.__get__(client)
    async with client:
        # FAST guillotine needs the first delta fast even on retry legs
        monkeypatch.setattr("src.gateway.FIRST_TOKEN_TIMEOUT_S", 30.0)
        assert await _collect(client.stream_chat([{"role": "user", "content": "hi"}])) == [
            "recovered"
        ]
    assert calls["n"] == 2


async def test_all_hot_models_honest_cooldown_cause():
    import time

    from src.gateway import _MODEL_COOLDOWNS

    _MODEL_COOLDOWNS["m1:free"] = time.time() + 600
    _MODEL_COOLDOWNS["m2:free"] = time.time() + 600
    client = _client(_Scripted(), {Tier.FAST: ["m1:free", "m2:free"]})
    async with client:
        with pytest.raises(GatewayError, match="rate-limit cooldown"):
            await _collect(client.stream_chat([{"role": "user", "content": "hi"}]))


async def test_sse_junk_lines_skipped():
    body = (
        b":keepalive\n"
        + b"not-a-data-line\n"
        + _sse(_chunk("نظيف")).replace(b"data: [DONE]\n\n", b"")
    )
    script = _Scripted(httpx.Response(200, content=body + b"data: [DONE]\n\n"))
    client = _client(script, {Tier.FAST: ["m:free"]})
    async with client:
        assert await client.chat([{"role": "user", "content": "hi"}]) == "نظيف"


class _Bridge:
    def __init__(self, payload):
        self.payload = payload
        self.commands = []

    async def send_cmd(self, cmd, args, **kw):
        self.commands.append((cmd, dict(args)))
        return self.payload


class _Notifier:
    def __init__(self):
        self.sent = []

    async def notify(self, text):
        self.sent.append(text)


class _Vault:
    async def upsert(self, *args, **kwargs):
        pass

    async def read(self, *args, **kwargs):
        raise FileNotFoundError


async def test_pending_expiry_clears_state():
    from src.pc_actions import PENDING_TTL, _Pending

    coord, _, _ = _rig()
    coord._pending = _Pending("launch", "x", datetime.now(UTC) - PENDING_TTL - timedelta(seconds=1))
    assert coord.pending_active() is False
    assert coord._pending is None


def _rig(payload=None, whitelist=None, tmp_root=None):
    from pathlib import Path

    bridge = _Bridge(payload or {"status": "error", "detail": "boom", "audit_code": "PC-9"})
    notifier = _Notifier()

    from bridge.guard import Guard
    from src.pc_actions import PCActionCoordinator

    guard = None
    if whitelist is not None:
        import json as _json

        from bridge.guard import Guard

        root = tmp_root if tmp_root is not None else Path(".")
        path = root / "whitelist.json"
        path.write_text(_json.dumps(whitelist), encoding="utf-8")
        guard = Guard(path)
    return PCActionCoordinator(bridge, _Vault(), notifier, guard=guard), bridge, notifier


async def test_close_unknown_app_honest_line(tmp_path):
    coord, _, notifier = _rig(
        whitelist={
            "allowed_apps": [{"name": "calc", "executable": "calc.exe", "auto_approve": True}],
            "restricted_actions": [],
        },
        tmp_root=tmp_path,
    )
    from src.pc_actions import LaunchStatus

    assert await coord.request_close("برنامج مو", origin="owner_chat") == LaunchStatus.REFUSED
    assert any("مش موجود بالقائمة" in line for line in notifier.sent)


async def test_close_ok_reports_killed_count():
    coord, _, notifier = _rig()
    coord._bridge = _Bridge(
        {"status": "ok", "detail": "ok", "audit_code": "PC-1", "killed_processes": 2}
    )
    from src.pc_actions import LaunchStatus

    assert await coord.request_close("calc", origin="owner_chat") == LaunchStatus.EXECUTED
    assert any("2 نسخة" in line for line in notifier.sent)


async def test_close_zero_killed_honest_line():
    coord, _, notifier = _rig()
    coord._bridge = _Bridge(
        {"status": "ok", "detail": "ok", "audit_code": "PC-1", "killed_processes": 0}
    )
    from src.pc_actions import LaunchStatus

    assert await coord.request_close("calc", origin="owner_chat") == LaunchStatus.EXECUTED
    assert any("ما لقيت نسخة" in line for line in notifier.sent)


async def test_close_confirm_required_flow():
    coord, _, notifier = _rig(
        {"status": "error", "detail": "needs confirmation", "audit_code": "PC-7"}
    )
    from src.pc_actions import LaunchStatus

    assert (
        await coord.request_close("calc", origin="owner_chat") == LaunchStatus.CONFIRMATION_REQUIRED
    )
    assert coord.pending_active()
    assert any("PC-7" in line for line in notifier.sent)
