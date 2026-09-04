"""Pass-1 core-side screenshot narration (v2.0 §3-د/2): the screenshot tool fetches
JPEG bytes over the tunnel and describes them through the CONVERSATION lane's native
vision channel (m3 image_url) — the owner asks «شو عالشاشة؟», Sara SEES the screen.
Bridge down -> honest offline line; vision failure -> honest apology line."""

from __future__ import annotations

import base64

from src.tools import SCREENSHOT_TOOL_NAME, ToolRegistry

JPEG_MAGIC = b"\xff\xd8\xff\xd8"  # fake but recognizable jpeg payload


class FakeBridgeForShot:
    def __init__(self, payload: dict | None) -> None:
        self.payload = payload
        self.cmds: list[tuple[str, dict]] = []

    async def send_cmd(self, cmd: str, args: dict, *, timeout_s: float = 20.0) -> dict:
        self.cmds.append((cmd, args))
        if self.payload is None:
            from src.bridge_server import BridgeOffline

            raise BridgeOffline("no session")
        return self.payload


class FakeVisionBrain:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def chat(self, messages, *, tier=None, **kw) -> str:
        self.calls.append({"messages": messages, "tier": tier})
        # honesty: the reply must quote only what the image actually contains
        return "شايفها — عندك كروم مفتوح فيه يوتيوب."


async def test_screenshot_tool_describes_screen_through_vision():
    """Wire cmd exec.screenshot -> base64 jpeg -> m3 vision call -> her line."""
    bridge = FakeBridgeForShot({"status": "ok", "detail": base64.b64encode(JPEG_MAGIC).decode()})
    brain = FakeVisionBrain()
    tools = ToolRegistry(bridge=bridge, vision=brain)
    answer = await tools.call("screenshot", "")
    assert answer == "شايفها — عندك كروم مفتوح فيه يوتيوب."
    assert bridge.cmds == [("exec.screenshot", {})]
    # the vision message carries an image_url data-URI block
    user = brain.calls[0]["messages"][-1]
    assert isinstance(user["content"], list)
    img_block = next(b for b in user["content"] if b.get("type") == "image_url")
    assert img_block["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert base64.b64decode(img_block["image_url"]["url"].split(",", 1)[1]) == JPEG_MAGIC


async def test_screenshot_tool_bridge_down_is_the_honest_offline_line():
    tools = ToolRegistry(bridge=FakeBridgeForShot(None), vision=FakeVisionBrain())
    answer = await tools.call("screenshot", "")
    assert answer == "الجسر مو متصل هسا"


async def test_screenshot_tool_bad_payload_is_an_apology():
    """A malformed daemon result (no jpeg_b64) never crashes the chat turn."""
    tools = ToolRegistry(bridge=FakeBridgeForShot({"status": "ok"}), vision=FakeVisionBrain())
    answer = await tools.call("screenshot", "")
    assert "عطل" in answer or "ما قدرت" in answer


async def test_screenshot_tool_vision_failure_is_an_apology():
    class DeadBrain:
        async def chat(self, messages, *, tier=None, **kw) -> str:
            raise RuntimeError("model down")

    tools = ToolRegistry(
        bridge=FakeBridgeForShot({"status": "ok", "detail": base64.b64encode(JPEG_MAGIC).decode()}),
        vision=DeadBrain(),
    )
    answer = await tools.call("screenshot", "")
    assert "عطل" in answer or "ما قدرت" in answer


def test_screenshot_wire_name_is_stable():
    assert SCREENSHOT_TOOL_NAME == "screenshot"
