"""Tier 1 — OpenClaw Phase-2 bridge-daemon verbs. Hermetic.

The three `openclaw.*` verbs dispatch through an injected controller —
Win32/ctypes and browser handles are NEVER touched here (fakes record
calls; the unconfigured daemon answers honestly). Follows the existing
`daemon._execute` + `new_envelope` test pattern.
"""

import json

from bridge.executor import Executor
from bridge.guard import Guard
from common.protocol import new_envelope


def _daemon(tmp_path, openclaw=None):
    from bridge.daemon import BridgeDaemon

    wl = tmp_path / "whitelist.json"
    wl.write_text(json.dumps({"allowed_apps": [], "restricted_actions": []}), encoding="utf-8")
    return BridgeDaemon("ws://127.0.0.1:1", "t", Executor(Guard(str(wl))), openclaw=openclaw)


class _FakeBackend:
    """Phase-3 stand-in: records mechanical calls, touches no OS."""

    def __init__(self):
        self.acted = []
        self.perceived = []

    async def act(self, op):
        self.acted.append(op)
        return {"ok": True, "evidence": f"{op.op.value} done"}

    async def snapshot(self, scope="desktop"):
        self.perceived.append(scope)
        return [
            {
                "id": "e1",
                "role": "button",
                "name": "حفظ",
                "bbox": None,
                "hotkey": None,
                "source": "uia",
            }
        ]


async def _fetch_fake(url: str) -> str:
    return f"# fake\n\ncontent of {url}"


def _controller(**kw):
    from bridge.openclaw.controller import OpenClawController

    return OpenClawController(**kw)


async def test_verbs_without_controller_answer_honestly(tmp_path):
    """Unconfigured daemon (production default until Phase 3 binds backends):
    honest errors, audit codes present, nothing raises out of _execute."""
    daemon = _daemon(tmp_path)
    for cmd, args in (
        ("openclaw.perceive", {}),
        ("openclaw.act", {"op": {"op": "screenshot"}}),
        ("openclaw.fetch", {"url": "https://example.com"}),
    ):
        status, payload = await daemon._execute(new_envelope(type="cmd", cmd=cmd, args=args))
        assert status == "error", cmd
        assert payload["audit_code"].startswith("PC-"), cmd
        assert payload["detail"], cmd


async def test_perceive_returns_handles(tmp_path):
    daemon = _daemon(tmp_path, openclaw=_controller(perception=_FakeBackend()))
    status, payload = await daemon._execute(new_envelope(type="cmd", cmd="openclaw.perceive"))
    assert status == "ok"
    handles = json.loads(payload["detail"])
    assert handles[0]["name"] == "حفظ" and handles[0]["source"] == "uia"
    assert payload["audit_code"].startswith("PC-")


async def test_act_reversible_executes_without_confirmation(tmp_path):
    backend = _FakeBackend()
    daemon = _daemon(tmp_path, openclaw=_controller(actuator=backend))
    status, payload = await daemon._execute(
        new_envelope(type="cmd", cmd="openclaw.act", args={"op": {"op": "screenshot"}})
    )
    assert status == "ok"
    transcript = json.loads(payload["detail"])
    assert transcript["success"] is True and len(transcript["audit_codes"]) == 1
    assert len(backend.acted) == 1


async def test_act_irreversible_without_id_is_refused(tmp_path):
    backend = _FakeBackend()
    daemon = _daemon(tmp_path, openclaw=_controller(actuator=backend))
    status, payload = await daemon._execute(
        new_envelope(
            type="cmd", cmd="openclaw.act", args={"op": {"op": "hotkey", "value": "Alt+F4"}}
        )
    )
    assert status == "error"
    assert "confirmation" in payload["detail"]
    assert backend.acted == []  # the backend never saw it


async def test_act_irreversible_with_id_executes(tmp_path):
    backend = _FakeBackend()
    daemon = _daemon(tmp_path, openclaw=_controller(actuator=backend))
    status, _payload = await daemon._execute(
        new_envelope(
            type="cmd",
            cmd="openclaw.act",
            args={"op": {"op": "hotkey", "value": "Alt+F4"}, "confirmation_id": "c1"},
        )
    )
    assert status == "ok"
    assert len(backend.acted) == 1


async def test_act_forbidden_is_rejected(tmp_path):
    backend = _FakeBackend()
    daemon = _daemon(tmp_path, openclaw=_controller(actuator=backend))
    status, payload = await daemon._execute(
        new_envelope(
            type="cmd",
            cmd="openclaw.act",
            args={
                "op": {"op": "type_text", "value": "powershell -c whoami"},
                "confirmation_id": "c1",
            },
        )
    )
    assert status == "error"
    assert "forbidden" in payload["detail"].lower()
    assert backend.acted == []


async def test_act_malformed_op_is_rejected(tmp_path):
    daemon = _daemon(tmp_path, openclaw=_controller(actuator=_FakeBackend()))
    status, payload = await daemon._execute(
        new_envelope(type="cmd", cmd="openclaw.act", args={"op": {"op": "run_command"}})
    )
    assert status == "error"
    assert payload["audit_code"].startswith("PC-")


async def test_fetch_serves_injected_backend(tmp_path):
    daemon = _daemon(tmp_path, openclaw=_controller(fetcher=_fetch_fake))
    status, payload = await daemon._execute(
        new_envelope(type="cmd", cmd="openclaw.fetch", args={"url": "https://example.com/x"})
    )
    assert status == "ok"
    assert "example.com/x" in payload["detail"]


async def test_fetch_refuses_non_http(tmp_path):
    daemon = _daemon(tmp_path, openclaw=_controller(fetcher=_fetch_fake))
    for url in ("file:///etc/passwd", "ftp://x/y", "javascript:alert(1)", ""):
        status, _payload = await daemon._execute(
            new_envelope(type="cmd", cmd="openclaw.fetch", args={"url": url})
        )
        assert status == "error", url


async def test_verbs_registered_in_cmdname():
    """AC8 pattern (test_desktop_telemetry): new verbs are first-class wire citizens."""
    import typing

    from common.protocol import CmdName

    for verb in ("openclaw.perceive", "openclaw.act", "openclaw.fetch"):
        assert verb in typing.get_args(CmdName), verb
