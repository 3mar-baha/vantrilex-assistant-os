"""Directive §2 (2026-09-04): «سكري الآلة الحاسبة» must CLOSE, never launch.
The close verbs route through the keyword net to the `close` tool, the
coordinator's request_close hits the daemon's exec.close, and the daemon
VERIFIES termination via psutil before any success confirmation — the live
3:22pm double-launch and the 3:23pm «لم يتم اغلاق ولا واحدة» hallucination
are both structurally dead."""

from __future__ import annotations

from src.dispatcher import _keyword_net


def test_close_verbs_route_to_close_never_launch():
    for phrase in (
        "سكري الآلة الحاسبة",
        "سكّري الآلة الحاسبة المفتوحة",
        "اغلقي الآلة الحاسبة",
        "طفي الآلة الحاسبة",
        "وقفي كروم",
        "اقفلي المفكرة",
        "kill chrome",
        "close chrome",
    ):
        tool, arg = _keyword_net(phrase)
        assert tool == "close", f"{phrase!r} must route close, got {tool}"
        assert arg, f"{phrase!r} must carry the app name"


def test_close_arg_strips_device_clauses():
    tool, arg = _keyword_net("سكري الآلة الحاسبة على جهازي")
    assert tool == "close"
    assert arg and "جهاز" not in arg  # clause stripped, name kept


def test_launch_verbs_still_launch():
    """The routing fix must not eat the open/start path."""
    tool, _arg = _keyword_net("شغّل كروم")
    assert tool == "launch"


class _FakeVault:
    async def upsert(self, *a, **kw):
        return None

    async def read(self, *a, **kw):
        raise FileNotFoundError


class _Notifier:
    def __init__(self):
        self.sent = []

    async def notify(self, text):
        self.sent.append(text)


class _Bridge:
    def __init__(self, payload=None, offline=False):
        self.payload = payload
        self.offline = offline
        self.cmds = []

    async def send_cmd(self, cmd, args, *, timeout_s=20.0):
        self.cmds.append((cmd, args))
        if self.offline:
            from src.bridge_server import BridgeOffline

            raise BridgeOffline("no session")
        return self.payload


async def test_coordinator_request_close_notifies_verified_count():
    """request_close -> daemon exec.close -> the owner sees the psutil-verified
    count, not a claimed success."""
    from src.pc_actions import PCActionCoordinator

    bridge = _Bridge(
        {
            "status": "ok",
            "detail": "closed 2 of 2",
            "audit_code": "PC-X",
            "killed_processes": 2,
        }
    )
    notifier = _Notifier()
    coordinator = PCActionCoordinator(bridge, _FakeVault(), notifier)
    status = await coordinator.request_close("calculator", origin="owner_chat")
    assert status.value == "executed"
    assert bridge.cmds[0][0] == "exec.close"
    assert any("2" in line for line in notifier.sent)  # the verified count


async def test_coordinator_close_no_running_copies_is_honest():
    """killed=0 gets its own honest line — never a bare «تم» claim."""
    from src.pc_actions import PCActionCoordinator

    bridge = _Bridge(
        {
            "status": "ok",
            "detail": "no running copies found",
            "audit_code": "PC-Y",
            "killed_processes": 0,
        }
    )
    notifier = _Notifier()
    coordinator = PCActionCoordinator(bridge, _FakeVault(), notifier)
    status = await coordinator.request_close("obsidian", origin="owner_chat")
    assert status.value == "executed"
    assert any("ما لقيت نسخة" in line for line in notifier.sent)


async def test_coordinator_close_offline_honest():
    from src.pc_actions import PCActionCoordinator

    coordinator = PCActionCoordinator(_Bridge(offline=True), _FakeVault(), _Notifier())
    status = await coordinator.request_close("calculator", origin="owner_chat")
    assert status.value == "refused"


async def test_close_tool_delegates_to_coordinator():
    from src.tools import ToolRegistry

    class _Coord:
        def __init__(self):
            self.calls = []

        async def request_close(self, name, *, origin):
            self.calls.append((name, origin))

    coord = _Coord()
    tools = ToolRegistry(coordinator=coord)
    result = await tools.call("close", "الآلة الحاسبة")
    assert result is None  # the coordinator notified the owner itself
    assert coord.calls == [("الآلة الحاسبة", "owner_chat")]


async def test_close_tool_no_coordinator_offline_line():
    from src.tools import ToolRegistry

    tools = ToolRegistry()
    answer = await tools.call("close", "كروم")
    assert "الجسر" in answer or "ما بقدر" in answer
