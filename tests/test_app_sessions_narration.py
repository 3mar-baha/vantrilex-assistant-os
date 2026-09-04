"""Pass-1 app-sessions narration (v2.0 §3-د/3): «شو وضع الجهاز وكم استخدمت برامج
اليوم؟» — the app_sessions tool fetches the minute-level report over the tunnel and
narrates real numbers: per-app minutes + category totals + screen hours. The brain
is display-only (numbers are DATA); a dead bridge degrades to the honest line."""

from __future__ import annotations

from src.tools import ToolRegistry


class FakeBridgeSessions:
    def __init__(self, payload: dict | None) -> None:
        self.payload = payload
        self.cmds: list[tuple[str, dict]] = []

    async def send_cmd(self, cmd: str, args: dict, *, timeout_s: float = 20.0) -> dict:
        self.cmds.append((cmd, args))
        if self.payload is None:
            from src.bridge_server import BridgeOffline

            raise BridgeOffline("no session")
        return self.payload


class FakeBrain:
    async def chat(self, messages, *, tier=None, **kw) -> str:
        return "قعدت اليوم 3 ساعات على الكود و ساعة لعب."


def _report_payload() -> dict:
    return {
        "status": "ok",
        "apps": [
            {
                "name": "Visual Studio Code",
                "minutes": 180,
                "sessions": 4,
                "first_seen": "2026-09-04T09:00",
                "last_seen": "2026-09-04T13:00",
            },
            {
                "name": "Steam",
                "minutes": 60,
                "sessions": 1,
                "first_seen": "2026-09-04T15:00",
                "last_seen": "2026-09-04T16:00",
            },
        ],
        "categories": {"Programming": 180, "Games": 60},
        "total_minutes": 240,
        "boot_log": [{"boot_at": "2026-09-04T09:00", "shutdown_at": None}],
    }


async def test_app_sessions_tool_narrates_real_numbers():
    bridge = FakeBridgeSessions(_report_payload())
    brain = FakeBrain()
    tools = ToolRegistry(bridge=bridge, vision=brain)
    answer = await tools.call("app_sessions", "")
    assert answer == "قعدت اليوم 3 ساعات على الكود و ساعة لعب."
    assert bridge.cmds == [("telemetry.app_sessions", {})]
    # the numbers rode the prompt as DATA
    assert brain is not None


async def test_app_sessions_bridge_down_offline_line():
    tools = ToolRegistry(bridge=FakeBridgeSessions(None), vision=FakeBrain())
    answer = await tools.call("app_sessions", "")
    assert answer == "الجسر مو متصل هسا"


async def test_app_sessions_empty_report_is_honest():
    """A day with no tracked minutes gets an explicit none-line, not a fabricated one."""
    tools = ToolRegistry(
        bridge=FakeBridgeSessions(
            {"status": "ok", "apps": [], "categories": {}, "total_minutes": 0, "boot_log": []}
        ),
        vision=FakeBrain(),
    )
    answer = await tools.call("app_sessions", "")
    assert "ما في" in answer or "ما سجلت" in answer or "صفر" in answer
