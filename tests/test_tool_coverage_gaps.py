"""Tool coverage gaps: connected-path contracts for `screen_ocr` and `file_save`.

These were the only two of 46 registry tools with zero `.call()` coverage in
the suite. Every leg here runs against a fake bridge — no daemon, no network.
"""

from src.bridge_server import BridgeOffline
from src.tools import OFFLINE_VISION_AR, TOOL_FAIL_AR, ToolRegistry


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


async def test_screen_ocr_returns_extracted_text():
    bridge = _FakeBridge({"status": "ok", "detail": "print('hello')"})
    out = await ToolRegistry(bridge=bridge).call("screen_ocr", "اقرأي الشاشة")
    assert out == "print('hello')"
    assert bridge.sent[0][0] == "exec.screen_ocr"


async def test_screen_ocr_offline_and_failure_legs():
    assert await ToolRegistry(bridge=None).call("screen_ocr", "x") == OFFLINE_VISION_AR
    down = ToolRegistry(bridge=_FakeBridge(exc=BridgeOffline("down")))
    assert await down.call("screen_ocr", "x") == OFFLINE_VISION_AR
    bad = ToolRegistry(bridge=_FakeBridge({"status": "error", "detail": ""}))
    assert await bad.call("screen_ocr", "x") == TOOL_FAIL_AR


async def test_file_save_uploads_bytes():
    bridge = _FakeBridge({"status": "ok", "detail": "تم الحفظ"})
    reg = ToolRegistry(bridge=bridge)
    out = await reg._do_file_save("report.pdf", file_bytes=b"%PDF-bytes")
    assert out.startswith("✅")
    cmd, args = bridge.sent[0]
    assert cmd == "file.upload" and args["filename"] == "report.pdf"


async def test_file_save_offline_and_failure_legs():
    assert await ToolRegistry(bridge=None).call("file_save", "x") == OFFLINE_VISION_AR
    reg = ToolRegistry(bridge=_FakeBridge({"status": "ok", "detail": "ok"}))
    assert "الملف" in await reg.call("file_save", "report.pdf")
    down = ToolRegistry(bridge=_FakeBridge(exc=BridgeOffline("down")))
    assert await down._do_file_save("r.pdf", file_bytes=b"data") == OFFLINE_VISION_AR
    bad = ToolRegistry(bridge=_FakeBridge({"status": "error"}))
    assert await bad._do_file_save("r.pdf", file_bytes=b"data") == TOOL_FAIL_AR
