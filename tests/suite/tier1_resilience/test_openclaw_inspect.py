"""Tier 1 — OpenClaw Phase-3.1 screen-inspection engine. Hermetic.

ScreenInspector aggregates the PROVEN primitives (in-memory screenshot,
foreground-window probe, OCR extractor) into one diagnostic transcript —
all three injectable, so no test ever touches Win32, Pillow, or vision.
Every failure mode degrades inside the transcript; inspect() never raises.
"""

import json

from bridge.openclaw.inspect_arm import OCR_MAX_CHARS, ScreenInspector


def _grab_ok() -> bytes:
    return b"JPEG-BYTES" * 100


def _grab_dead():
    raise OSError("no display")


def _fg():
    return "Notepad - report.txt"


def _fg_dead():
    raise RuntimeError("locked")


async def _ocr_ok(jpeg: bytes, prompt: str) -> str:
    assert jpeg.startswith(b"JPEG")
    assert prompt
    return "Error 404 on line 12 " * 100


async def _ocr_dead(jpeg: bytes, prompt: str) -> str:
    raise RuntimeError("vision lane down")


async def test_inspect_aggregates_all_three_primitives():
    inspector = ScreenInspector(grab=_grab_ok, foreground=_fg, ocr=_ocr_ok)
    transcript = await inspector.inspect()
    assert transcript["screenshot_ok"] is True
    assert transcript["jpeg_bytes"] == len(_grab_ok())
    assert transcript["foreground"] == "Notepad - report.txt"
    assert transcript["ocr_available"] is True
    assert transcript["ocr_text"].startswith("Error 404")
    assert len(transcript["ocr_text"]) <= OCR_MAX_CHARS
    assert transcript["scope"] == "desktop"


async def test_inspect_survives_every_backend_failure():
    inspector = ScreenInspector(grab=_grab_dead, foreground=_fg_dead, ocr=_ocr_dead)
    transcript = await inspector.inspect()
    assert transcript["screenshot_ok"] is False
    assert transcript["jpeg_bytes"] == 0
    assert transcript["foreground"] is None
    assert transcript["ocr_available"] is False
    assert transcript["ocr_text"] is None


async def test_inspect_without_ocr_is_honest_not_broken():
    inspector = ScreenInspector(grab=_grab_ok, foreground=_fg, ocr=None)
    transcript = await inspector.inspect()
    assert transcript["screenshot_ok"] is True
    assert transcript["ocr_available"] is False
    assert "ocr" in transcript["ocr_status"].lower() or transcript["ocr_text"] is None


async def test_snapshot_without_tree_backend_is_empty_but_valid():
    """3.1 has no UIA enumeration yet (3.4 scope) — snapshot() returns a
    valid empty handle list instead of pretending."""
    inspector = ScreenInspector(grab=_grab_ok, foreground=_fg)
    assert await inspector.snapshot() == []


async def test_controller_inspect_wraps_transcript():
    from bridge.openclaw.controller import OpenClawController

    controller = OpenClawController(
        inspector=ScreenInspector(grab=_grab_ok, foreground=_fg, ocr=_ocr_ok)
    )
    result = await controller.inspect()
    assert result.status == "ok"
    assert result.audit_code.startswith("PC-")
    payload = json.loads(result.detail)
    assert payload["foreground"] == "Notepad - report.txt"
    assert payload["screenshot_ok"] is True


async def test_controller_inspect_unconfigured_is_honest():
    from bridge.openclaw.controller import OpenClawController

    result = await OpenClawController().inspect()
    assert result.status == "error"
    assert result.audit_code.startswith("PC-")


async def test_daemon_perceive_full_returns_inspection(tmp_path):
    """openclaw.perceive with full=true serves the diagnostic transcript;
    the bare call keeps the Phase-2 handle-list shape."""
    import json as _json

    from bridge.daemon import BridgeDaemon
    from bridge.executor import Executor
    from bridge.guard import Guard
    from bridge.openclaw.controller import OpenClawController
    from common.protocol import new_envelope

    wl = tmp_path / "whitelist.json"
    wl.write_text(_json.dumps({"allowed_apps": [], "restricted_actions": []}), encoding="utf-8")
    # The inspector doubles as the perception backend (Phase-3.1: no tree
    # enumeration yet — snapshot() is honestly empty; prod wires it the same).
    inspector = ScreenInspector(grab=_grab_ok, foreground=_fg, ocr=_ocr_ok)
    controller = OpenClawController(inspector=inspector, perception=inspector)
    daemon = BridgeDaemon("ws://127.0.0.1:1", "t", Executor(Guard(str(wl))), openclaw=controller)
    status, payload = await daemon._execute(
        new_envelope(type="cmd", cmd="openclaw.perceive", args={"full": True})
    )
    assert status == "ok"
    envelope = _json.loads(payload["detail"])
    assert envelope["inspection"]["foreground"] == "Notepad - report.txt"
    assert isinstance(envelope["handles"], list)

    status, payload = await daemon._execute(
        new_envelope(type="cmd", cmd="openclaw.perceive", args={})
    )
    assert status == "ok"
    assert isinstance(_json.loads(payload["detail"]), list)


async def test_core_inspect_narrates_facts_in_two_lines():
    """Sara's ground truth for an inspection: foreground app + OCR head,
    short enough for the ≤2-line tool-lane narration contract."""
    import json as _json

    from src.tools import ToolRegistry

    inspection = {
        "scope": "desktop",
        "screenshot_ok": True,
        "jpeg_bytes": 1000,
        "foreground": "Notepad - report.txt",
        "ocr_available": True,
        "ocr_text": "Error 404 on line 12",
        "handles": 0,
    }
    envelope = {"handles": [], "inspection": inspection}

    class _FakeBridge:
        async def send_cmd(self, cmd, args, **kw):
            assert cmd == "openclaw.perceive" and args.get("full") is True
            return {"status": "ok", "detail": _json.dumps(envelope)}

    out = await ToolRegistry(bridge=_FakeBridge()).call("openclaw_inspect", "")
    assert "Notepad - report.txt" in out
    assert "Error 404" in out
    assert len(out.strip().splitlines()) <= 2


async def test_core_inspect_without_inspection_keeps_count_line():
    """Back-compat: a bare handle list (older daemon) still narrates."""
    import json as _json

    from src.tools import ToolRegistry

    class _FakeBridge:
        async def send_cmd(self, cmd, args, **kw):
            return {"status": "ok", "detail": _json.dumps([])}

    out = await ToolRegistry(bridge=_FakeBridge()).call("openclaw_inspect", "")
    assert "0" in out
