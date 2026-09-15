"""Tier 1 — OpenClaw Phase-3.6 interactive browse verb. Hermetic.

The openclaw.browse tunnel verb drives an injected browser backend
(fakes only — Playwright wheels absent in dev/CI); the core handler
navigates on URLs with passive-fetch fallback, and stays staged-honest
otherwise. No window ever opens here.
"""

import json


class _FakeBrowser:
    def __init__(self, fail_with=None):
        self.calls = []
        self.fail_with = fail_with

    def _maybe_fail(self, what):
        if self.fail_with is not None:
            raise self.fail_with

    async def navigate(self, url):
        self._maybe_fail("navigate")
        self.calls.append(("navigate", url))
        return {"ok": True, "url": url}

    async def snapshot(self):
        self._maybe_fail("snapshot")
        self.calls.append(("snapshot",))
        return [{"id": "e1", "role": "link", "name": "x", "source": "dom"}]

    async def click_by_role(self, role, name=None):
        self._maybe_fail("click")
        self.calls.append(("click", role, name))
        return {"ok": True}

    async def type_into(self, role, name, text):
        self._maybe_fail("type")
        self.calls.append(("type", role, name, text))
        return {"ok": True, "chars": len(text)}

    async def scroll(self, direction="down"):
        self._maybe_fail("scroll")
        self.calls.append(("scroll", direction))
        return {"ok": True, "direction": direction}


def _controller(**kw):
    from bridge.openclaw.controller import OpenClawController

    return OpenClawController(**kw)


async def test_browse_routes_all_actions():
    controller = _controller(browser=_FakeBrowser())
    result = await controller.browse("navigate", {"url": "https://example.com"})
    assert result.status == "ok" and result.audit_code.startswith("PC-")
    result = await controller.browse("snapshot", {})
    assert json.loads(result.detail)["handles"][0]["id"] == "e1"
    assert (await controller.browse("click", {"role": "button", "name": "Go"})).status == "ok"
    assert (
        await controller.browse("type", {"role": "textbox", "name": "q", "text": "hi"})
    ).status == "ok"
    assert (await controller.browse("scroll", {"direction": "up"})).status == "ok"


async def test_browse_unknown_action_refused():
    controller = _controller(browser=_FakeBrowser())
    result = await controller.browse("delete-everything", {})
    assert result.status == "error"
    assert result.audit_code.startswith("PC-")


async def test_browse_backend_failure_is_honest():
    controller = _controller(browser=_FakeBrowser(fail_with=RuntimeError("boom")))
    result = await controller.browse("navigate", {"url": "https://example.com"})
    assert result.status == "error" and "boom" in result.detail


async def test_browse_unconfigured_is_honest():
    controller = _controller()
    result = await controller.browse("navigate", {"url": "https://example.com"})
    assert result.status == "error"
    assert "not configured" in result.detail


async def test_daemon_browse_verb(tmp_path):
    import json as _json

    from bridge.daemon import BridgeDaemon
    from bridge.executor import Executor
    from bridge.guard import Guard
    from common.protocol import new_envelope

    wl = tmp_path / "whitelist.json"
    wl.write_text(_json.dumps({"allowed_apps": [], "restricted_actions": []}), encoding="utf-8")
    daemon = BridgeDaemon(
        "ws://127.0.0.1:1",
        "t",
        Executor(Guard(str(wl))),
        openclaw=_controller(browser=_FakeBrowser()),
    )
    status, payload = await daemon._execute(
        new_envelope(
            type="cmd",
            cmd="openclaw.browse",
            args={"action": "navigate", "params": {"url": "https://example.com"}},
        )
    )
    assert status == "ok"
    assert payload["audit_code"].startswith("PC-")


async def test_daemon_browse_without_controller_is_honest(tmp_path):
    import json as _json

    from bridge.daemon import BridgeDaemon
    from bridge.executor import Executor
    from bridge.guard import Guard
    from common.protocol import new_envelope

    wl = tmp_path / "whitelist.json"
    wl.write_text(_json.dumps({"allowed_apps": [], "restricted_actions": []}), encoding="utf-8")
    daemon = BridgeDaemon("ws://127.0.0.1:1", "t", Executor(Guard(str(wl))))
    status, payload = await daemon._execute(
        new_envelope(type="cmd", cmd="openclaw.browse", args={"action": "navigate"})
    )
    assert status == "error" and "not configured" in payload["detail"]


async def test_browse_verb_registered_in_cmdname():
    import typing

    from common.protocol import CmdName

    assert "openclaw.browse" in typing.get_args(CmdName)


class _FakeBridge:
    def __init__(self, payload=None, exc=None):
        self.payload = payload
        self.exc = exc
        self.sent = []

    async def send_cmd(self, cmd, args, **kw):
        self.sent.append((cmd, args))
        if self.exc is not None:
            raise self.exc
        return self.payload


def _registry(bridge):
    from src.tools import ToolRegistry

    return ToolRegistry(bridge=bridge)


async def test_core_browse_url_navigates_via_verb():
    bridge = _FakeBridge(
        {"status": "ok", "detail": json.dumps({"ok": True, "url": "https://example.com"})}
    )
    out = await _registry(bridge).call("openclaw_browse", "https://example.com/x")
    assert bridge.sent and bridge.sent[0][0] == "openclaw.browse"
    assert bridge.sent[0][1]["action"] == "navigate"
    assert "example.com" in out


class _ScriptedBridge:
    """Ordered (payload|Exception) scripts keyed by call order."""

    def __init__(self, *script):
        self.script = list(script)
        self.sent = []

    async def send_cmd(self, cmd, args, **kw):
        self.sent.append((cmd, args))
        assert self.script, "script exhausted — unplanned tunnel call"
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


async def test_core_browse_falls_back_to_fetch_when_browser_down():
    bridge = _ScriptedBridge(
        {"status": "error", "detail": "openclaw browser not configured"},
        {"status": "ok", "detail": "page text via fetch"},
    )
    out = await _registry(bridge).call("openclaw_browse", "https://example.com/x")
    assert [cmd for cmd, _args in bridge.sent] == ["openclaw.browse", "openclaw.fetch"]
    assert "page text via fetch" in out


async def test_core_browse_honest_when_both_lanes_fail():
    bridge = _ScriptedBridge(
        {"status": "error", "detail": "browser exploded"},
        {"status": "error", "detail": "fetch exploded"},
    )
    out = await _registry(bridge).call("openclaw_browse", "https://example.com/x")
    assert out and "exploded" in out


async def test_core_browse_offline_without_bridge():
    out = await _registry(None).call("openclaw_browse", "https://example.com/x")
    assert "الجسر" in out


async def test_core_browse_non_url_stays_staged_no_tunnel():
    bridge = _ScriptedBridge()
    out = await _registry(bridge).call("openclaw_browse", "دوري على أسعار الذهب")
    assert bridge.sent == []
    assert "المرحلة" in out or "Phase 3" in out
