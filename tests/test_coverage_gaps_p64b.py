"""P6 coverage gap pins, batch 4b: memory lanes, associative edges, gateway
exhaustion paths, executor OS branches, coordinator close confirm flows."""

import asyncio
import json
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import httpx
import pytest

from tests.test_gateway_failfast import _chunk, _Scripted, _sse

TZ = ZoneInfo("Asia/Amman")
NOW = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)


class FakeVault:
    def __init__(self, reads=None):
        self.reads = dict(reads or {})
        self.appends = []

    async def read(self, path):
        if path not in self.reads:
            raise FileNotFoundError(path)
        value = self.reads[path]
        if isinstance(value, Exception):
            raise value
        return value

    async def upsert(self, *args, **kwargs):
        return None

    async def append_section(self, path, heading, lines, commit_prefix=""):
        self.appends.append((path, heading, tuple(lines), commit_prefix))
        return f"written:{path}"


class FakeBrain:
    def __init__(self, reply=""):
        self.reply = reply

    async def chat(self, messages, **kwargs):
        return self.reply


def test_joda_empty_bullets_skipped():
    from src.memory import joda_cues_block

    out = joda_cues_block("## banter\n\n- \n- ههههه تمام\n")
    assert "ههههه تمام" in out


def test_dialect_frontmatter_only_section_skipped():
    from src.memory import _load_long_term_uncached

    async def _run():
        vault = FakeVault({"02_Areas/Profile/Dialect_Notes.md": "---\nnotes: []\n---\n"})
        return await _load_long_term_uncached(vault, today=NOW.date())

    assert asyncio.run(_run()) == ""


def test_ledger_empty_body_skipped():
    from src.memory import _load_long_term_uncached

    async def _run():
        vault = FakeVault({"Daily_Logs/2026/09/2026-09-17.md": "---\ntitle: x\n---\n   \n"})
        return await _load_long_term_uncached(vault, today=NOW.date())

    assert asyncio.run(_run()) == ""


def test_malformed_frontmatter_falls_back_to_body(tmp_path):
    from src.associative import VaultIndex

    root = tmp_path / "v"
    root.mkdir()
    (root / "bad.md").write_text(
        "---\nfoo: [unclosed\n---\nplain body text here\n", encoding="utf-8"
    )
    index = VaultIndex(root)
    assert index.refresh_if_stale() is True
    hits = index.query("plain body text", top_k=1)
    assert hits and hits[0].doc.path == "bad.md"


def test_digest_empty_body_returns_empty(tmp_path):
    from src.associative import load_digest_block

    target = tmp_path / "02_Areas" / "Profile" / "Omar_Master_Digest.md"
    target.parent.mkdir(parents=True)
    target.write_text("---\ntitle: x\n---\n", encoding="utf-8")
    assert load_digest_block(tmp_path) == ""


def test_compose_residual_and_ceiling_break():
    from src.associative import compose_rag_block

    sections = [
        ("Misc/a.md", "جملة أولى مميزة. " * 30),
        ("Misc/b.md", "جملة ثانية مميزة. " * 30),
        ("Misc/c.md", "جملة ثالثة مميزة. " * 30),
    ]
    out = compose_rag_block(sections, domains=("kb",), quarantined=True)
    assert out
    assert len(out) <= 1500 + 60


def test_gateway_empty_attempt_quarantines(monkeypatch):
    import src.gateway as gateway_mod
    from src.gateway import GatewayError, OmniRouteClient, Tier

    async def _empty(self, model, payload):
        return
        yield  # pragma: no cover -- never reached, marks generator

    client = OmniRouteClient(
        "http://gw.test/v1",
        "k",
        chains={Tier.FAST: ["m:free"]},
        transport=httpx.MockTransport(lambda r: None),
    )
    client._attempt = _empty.__get__(client)

    async def _run():
        async with client:
            with pytest.raises(GatewayError):
                await client.chat([{"role": "user", "content": "hi"}])

    asyncio.run(_run())
    assert "m:free" in gateway_mod._MODEL_COOLDOWNS


def test_gateway_transport_exhausted_after_retries(monkeypatch):
    import src.gateway as gateway_mod
    from src.gateway import GatewayError, OmniRouteClient, Tier

    calls = {"n": 0}

    async def _down(self, model, payload):
        calls["n"] += 1
        raise httpx.ConnectError("down")
        yield  # pragma: no cover -- marks async generator; never reached

    async def _instant(delay):
        return None

    monkeypatch.setattr(gateway_mod, "_sleep", _instant)
    client = OmniRouteClient("http://gw.test/v1", "k", chains={Tier.FAST: ["m:free"]})
    client._attempt = _down.__get__(client)

    async def _run():
        async with client:
            with pytest.raises(GatewayError, match="exhausted"):
                await client.chat([{"role": "user", "content": "hi"}])

    asyncio.run(_run())
    assert calls["n"] == 3


def test_gateway_bare_429_streak_skips_live():

    from src.gateway import OmniRouteClient, Tier, _model_hot, _note_bare_429

    assert _note_bare_429("m-live:free") is False
    err = (
        "data: "
        + json.dumps({"error": {"message": "[m-live:free] [429]: hammered, try later"}})
        + "\n\n"
    )
    script = _Scripted(
        httpx.Response(200, content=_sse(err)),
        httpx.Response(200, content=_sse(_chunk("تم"))),
    )
    client = OmniRouteClient(
        "http://gw.test/v1",
        "k",
        chains={Tier.FAST: ["m-live:free", "m2-live:free"]},
        transport=script.transport(),
    )

    async def _run():
        async with client:
            out = [d async for d in client.stream_chat([{"role": "user", "content": "hi"}])]
            return out

    assert asyncio.run(_run()) == ["تم"]
    assert _model_hot("m-live:free") is not None


def _coordinator(bridge_payload, whitelist, notifier_vault):
    import json as _json

    from bridge.guard import Guard
    from src.pc_actions import PCActionCoordinator

    notifier, vault, tmp_path = notifier_vault
    path = tmp_path / "whitelist.json"
    path.write_text(_json.dumps(whitelist), encoding="utf-8")

    class _Bridge:
        def __init__(self):
            self.commands = []

        async def send_cmd(self, cmd, args, **kw):
            self.commands.append((cmd, dict(args)))
            return dict(bridge_payload)

    bridge = _Bridge()
    return PCActionCoordinator(bridge, vault, notifier, guard=Guard(path)), bridge, notifier


def _wl():
    return {
        "allowed_apps": [{"name": "calc", "executable": "calc.exe", "auto_approve": True}],
        "restricted_actions": [],
    }


class _Notify:
    def __init__(self):
        self.sent = []

    async def notify(self, text):
        self.sent.append(text)


def test_close_error_branch_honest_line(tmp_path):
    import asyncio as _aio

    from src.pc_actions import LaunchStatus

    coord, _, notifier = _coordinator(
        {"status": "error", "detail": "daemon boom", "audit_code": "PC-9"},
        _wl(),
        (_Notify(), FakeVault(), tmp_path),
    )
    assert _aio.run(coord.request_close("calc", origin="owner_chat")) == LaunchStatus.REFUSED
    assert any("daemon boom" in line for line in notifier.sent)


def test_close_confirm_execute_flow(tmp_path):
    import asyncio as _aio

    from src.pc_actions import LaunchStatus

    coord, bridge, notifier = _coordinator(
        {"status": "error", "detail": "needs confirmation", "audit_code": "PC-1"},
        _wl(),
        (_Notify(), FakeVault(), tmp_path),
    )

    async def _ok(cmd, args, **kw):
        bridge.commands.append((cmd, dict(args)))
        if "confirmation_id" in args:
            return {"status": "ok", "detail": "ok", "audit_code": "PC-1", "killed_processes": 3}
        return {"status": "error", "detail": "needs confirmation", "audit_code": "PC-1"}

    bridge.send_cmd = _ok
    assert (
        _aio.run(coord.request_close("calc", origin="owner_chat"))
        == LaunchStatus.CONFIRMATION_REQUIRED
    )
    assert _aio.run(coord.handle_owner_reply("نعم")) == "calc"
    assert any("نفّذت calc" in line for line in notifier.sent)


def test_close_confirm_execute_failure_line(tmp_path):
    import asyncio as _aio

    from src.pc_actions import LaunchStatus

    coord, bridge, notifier = _coordinator(
        {"status": "error", "detail": "needs confirmation", "audit_code": "PC-2"},
        _wl(),
        (_Notify(), FakeVault(), tmp_path),
    )

    async def _fail(cmd, args, **kw):
        bridge.commands.append((cmd, dict(args)))
        if "confirmation_id" in args:
            return {"status": "error", "detail": "taskkill crashed", "audit_code": "PC-2"}
        return {"status": "error", "detail": "needs confirmation", "audit_code": "PC-2"}

    bridge.send_cmd = _fail
    assert (
        _aio.run(coord.request_close("calc", origin="owner_chat"))
        == LaunchStatus.CONFIRMATION_REQUIRED
    )
    assert _aio.run(coord.handle_owner_reply("نعم")) is None
    assert any("taskkill crashed" in line for line in notifier.sent)
