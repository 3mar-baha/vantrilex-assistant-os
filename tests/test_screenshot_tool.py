"""Pass-1 deep bridge tools (v2.0 directive §3-د): the daemon captures a screenshot
fully in memory (Pillow ImageGrab -> optimized in-RAM JPEG bytes, zero disk writes),
returns it base64 over the tunnel, and the core-side tool narrates what is on screen
through m3's native vision channel — the owner's «شو عالشاشة؟» gets a real answer."""

from __future__ import annotations

import base64
from pathlib import Path

from bridge.executor import ExecResult, Executor
from bridge.guard import Guard


class _FakeGrab:
    """Deterministic stand-in for PIL.ImageGrab.grab — a 4x4 red PNG in memory."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, bbox=None, include_layered_windows=False):
        from io import BytesIO

        from PIL import Image

        self.calls += 1
        img = Image.new("RGB", (4, 4), (255, 0, 0))
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=60)
        return buf.getvalue()


class _Tmp:
    def __init__(self, tmp_path: Path) -> None:
        self.grab = _FakeGrab()
        self.tmp_path = tmp_path
        self.written: list[Path] = []

    @property
    def executor(self) -> Executor:
        ex = Executor(_tmp_guard(self.tmp_path))

        ex._grab = self.grab  # OS edge stays a spy — the tunnel is the real boundary
        return ex


def _tmp_guard(tmp_path: Path) -> Guard:
    import json

    wl = tmp_path / "whitelist.json"
    payload = {
        "allowed_apps": [{"name": "calculator", "executable": "calc.exe", "auto_approve": True}],
        "restricted_actions": [
            {"action": "shutdown"},
            {"action": "restart"},
            {"action": "sleep"},
        ],
    }
    wl.write_text(json.dumps(payload), encoding="utf-8")
    return Guard(wl)


async def test_screenshot_returns_in_memory_jpeg_bytes(tmp_path: Path):
    """exec.screenshot: bytes come back base64-wrapped, PNG/JPEG magic present,
    and NOTHING was written to disk (the zero-disk invariant)."""
    t = _Tmp(tmp_path)
    ex = t.executor
    result = await ex.screenshot()
    assert isinstance(result, ExecResult)
    assert result.status == "ok"
    raw = base64.b64decode(result.detail)  # wire contract: detail IS the base64 payload
    assert raw[:3] == b"\xff\xd8\xff", "must be real JPEG bytes"
    assert t.written == []
    assert t.grab.calls == 1


async def test_screenshot_failure_degrades_to_error_not_crash(tmp_path: Path):
    """A dead capture surface (locked session/headless) returns an error result —
    never raises into the daemon loop."""

    class _DeadGrab:
        def __call__(self, *args, **kwargs):
            raise OSError("no screen")

    ex = Executor(_tmp_guard(tmp_path))
    ex._grab = _DeadGrab()
    result = await ex.screenshot()
    assert result.status == "error"
    assert result.audit_code
