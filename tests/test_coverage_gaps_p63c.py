"""P6 coverage gap pins, batch 3c: bridge executor OS edges.

Every OS boundary here runs through injectable doubles (the module's own
documented seams: _spawn/_open/_grab spies, ctypes stub, PIL-memory images).
No real keypresses, no real processes, no real screen capture — Windows stays
untouched while every honest-error branch executes for real.
"""

import asyncio
import base64
import sys
from pathlib import Path

from bridge.executor import (
    Executor,
    mint_audit_code,
    resolve_in_roots,
    sanitize_filename,
)
from bridge.guard import Guard


def _guard(tmp_path, apps=None, restricted=None):
    import json as _json

    path = tmp_path / "whitelist.json"
    path.write_text(
        _json.dumps(
            {
                "allowed_apps": apps
                or [{"name": "calc", "executable": "calc.exe", "auto_approve": True}],
                "restricted_actions": restricted or [],
            }
        ),
        encoding="utf-8",
    )
    return Guard(path)


def test_count_running_psutil_failure_reads_zero(monkeypatch):
    from bridge import executor as executor_mod

    monkeypatch.setitem(sys.modules, "psutil", None)
    assert executor_mod._count_running("anything.exe") == 0


def test_resolve_absolute_oserror_refuses(monkeypatch):
    import pathlib

    def _boom(self, *args, **kwargs):
        raise OSError("unresolvable")

    monkeypatch.setattr(pathlib.Path, "resolve", _boom)
    assert resolve_in_roots("C:\\Windows\\x.txt", (Path("C:\\root"),)) is None


def test_volume_up_presses_five_times(monkeypatch):
    import ctypes

    presses = []

    class _User32:
        @staticmethod
        def keybd_event(*args):
            presses.append(args)

    monkeypatch.setattr(ctypes.windll.user32, "keybd_event", _User32.keybd_event)
    result = asyncio.run(Executor(_guard(Path("."))).volume("up"))
    assert result.status == "ok"
    assert len(presses) == 5 * 2  # down+up per press


def test_volume_set_level_validation():
    executor = Executor(_guard(Path(".")))
    assert asyncio.run(executor.volume("set", level=101)).status == "error"
    assert asyncio.run(executor.volume("set", level=None)).status == "error"
    assert asyncio.run(executor.volume("frobnicator")).status == "error"


def test_media_unknown_and_key_failure(monkeypatch):
    import bridge.executor as executor_mod

    executor = Executor(_guard(Path(".")))
    assert asyncio.run(executor.media("rewind")).status == "error"

    async def _boom(vk, times=1):
        raise RuntimeError("key dead")

    monkeypatch.setattr(executor_mod, "_press_vk", _boom)
    out = asyncio.run(executor.media("next"))
    assert out.status == "error" and "key injection failed" in out.detail


def test_screenshot_capture_failure_and_empty():
    def _raise():
        raise OSError("no display")

    def _empty():
        return b""

    executor = Executor(_guard(Path(".")))
    executor._grab = _raise
    assert "failed" in asyncio.run(executor.screenshot()).detail
    executor._grab = _empty
    assert "empty capture" in asyncio.run(executor.screenshot()).detail


def test_screenshot_ok_base64():
    def _bytes():
        return b"\xff\xd8fakejpeg"

    executor = Executor(_guard(Path(".")))
    executor._grab = _bytes
    out = asyncio.run(executor.screenshot())
    assert out.status == "ok"
    assert base64.b64decode(out.detail) == b"\xff\xd8fakejpeg"


def test_grab_real_downsizes_wide_image():
    from PIL import Image

    import bridge.executor as executor_mod

    class _Grab:
        def __enter__(self):
            return Image.new("RGB", (2000, 1000))

        def __exit__(self, *args):
            return False

    import PIL.ImageGrab as imagegrab

    real_grab = imagegrab.grab
    imagegrab.grab = lambda: _Grab()
    try:
        data = executor_mod.Executor._grab_real()
    finally:
        imagegrab.grab = real_grab
    assert data[:2] == b"\xff\xd8"


def test_close_taskkill_partial_failure_continues(monkeypatch, tmp_path):
    import bridge.executor as executor_mod

    async def _flaky(argv):
        if argv[2] == "CalculatorApp.exe":
            raise OSError("not installed")

    executor = Executor(_guard(tmp_path))
    executor._spawn = _flaky
    monkeypatch.setattr(executor_mod, "_count_running", lambda image: 0)
    out = asyncio.run(executor.close("calculator", confirmation_id="cid"))
    assert out.status == "ok"


def test_launch_oserror_honest_detail(tmp_path):
    async def _denied(argv):
        raise OSError("denied by policy")

    executor = Executor(_guard(tmp_path))
    executor._spawn = _denied
    out = asyncio.run(executor.launch("calc.exe", confirmation_id="cid"))
    assert out.status == "error" and "denied by policy" in out.detail


def test_power_not_listed_unknown_action_and_spawn_fail(tmp_path):
    executor = Executor(_guard(tmp_path))
    out = asyncio.run(executor.power("naps", confirmation_id="cid"))
    assert out.status == "error" and "not in whitelist" in out.detail

    executor2 = Executor(
        _guard(
            tmp_path,
            restricted=[{"action": "hibernate", "requires_confirmation": True}],
        )
    )
    out = asyncio.run(executor2.power("hibernate", confirmation_id="cid"))
    assert out.status == "error" and "hibernate" in out.detail

    async def _denied(argv):
        raise OSError("no power")

    executor3 = Executor(
        _guard(
            tmp_path,
            restricted=[{"action": "shutdown", "requires_confirmation": True}],
        )
    )
    executor3._spawn = _denied
    out = asyncio.run(executor3.power("shutdown", confirmation_id="cid"))
    assert out.status == "error" and "no power" in out.detail


def test_open_path_walls_and_open(tmp_path):
    opened = []

    async def _spy(path):
        opened.append(path)

    executor = Executor(_guard(tmp_path))
    executor._open = _spy
    assert "UNC" in asyncio.run(executor.open_path("\\\\srv\\share\\f.txt")).detail
    assert "traversal" in asyncio.run(executor.open_path("..\\secret.txt")).detail
    assert "whitelist" in asyncio.run(executor.open_path("evil.exe")).detail
    out = asyncio.run(executor.open_path("C:\\Users\\note.txt"))
    assert out.status == "ok" and opened == ["C:\\Users\\note.txt"]


def test_file_roots_missing_wall(tmp_path):
    executor = Executor(_guard(tmp_path))
    assert "not configured" in asyncio.run(executor.file_upload(b"x", "a.txt")).detail
    assert "not configured" in asyncio.run(executor.file_download("a.txt")).detail


def test_file_upload_empty_name_and_write_fail(tmp_path):
    executor = Executor(_guard(tmp_path), file_roots=(tmp_path,))
    assert "empty filename" in asyncio.run(executor.file_upload(b"x", "   ")).detail
    blocker = tmp_path / "file"
    blocker.write_bytes(b"")
    executor2 = Executor(_guard(tmp_path), file_roots=(blocker,))
    assert "write failed" in asyncio.run(executor2.file_upload(b"x", "a.txt")).detail


def test_file_download_walls_and_roundtrip(tmp_path):
    root = tmp_path / "dl"
    root.mkdir()
    (root / "notes.txt").write_bytes(b"hello")
    (root / "secret.key").write_bytes(b"k")
    executor = Executor(_guard(tmp_path), file_roots=(root,), blocked_suffixes=(".key",))
    assert (
        "outside_allowed_roots" in asyncio.run(executor.file_download("C:\\Windows\\x.txt")).detail
    )
    assert "sensitive file type" in asyncio.run(executor.file_download("secret.key")).detail
    out = asyncio.run(executor.file_download("notes.txt"))
    assert out.status == "ok" and base64.b64decode(out.detail) == b"hello"
    assert "read failed" in asyncio.run(executor.file_download(str(root))).detail


def test_screen_ocr_legs():
    def _boom_grab():
        raise OSError("no screen")

    def _empty_grab():
        return b""

    def _bytes_grab():
        return b"\xff\xd8jpeg"

    async def _vision_ok(jpeg, prompt):
        assert jpeg == b"\xff\xd8jpeg"
        return "code here"

    async def _vision_boom(jpeg, prompt):
        raise RuntimeError("vision down")

    executor = Executor(_guard(Path(".")))
    executor._grab = _boom_grab
    assert "capture failed" in asyncio.run(executor.screen_ocr(_vision_ok)).detail
    executor._grab = _empty_grab
    assert "empty capture" in asyncio.run(executor.screen_ocr(_vision_ok)).detail
    executor._grab = _bytes_grab
    assert "extraction failed" in asyncio.run(executor.screen_ocr(_vision_boom)).detail
    out = asyncio.run(executor.screen_ocr(_vision_ok))
    assert out.status == "ok" and out.detail == "code here"


def test_spawn_real_missing_binary():
    import pytest

    executor = Executor(_guard(Path(".")))
    with pytest.raises(FileNotFoundError):
        asyncio.run(executor._spawn_real(["definitely-not-a-real-binary-xyz"]))


def test_sanitize_and_mint_shapes():
    assert sanitize_filename("..\\..\\evil.txt") == "evil.txt"
    assert sanitize_filename("  ") == ""
    assert mint_audit_code().startswith("PC-")


def test_spawn_real_existing_binary_spawns_nothing_real(monkeypatch, tmp_path):
    import asyncio as _aio
    import sys

    import bridge.executor as executor_mod

    calls = []

    async def _fake_spawn(*args, **kwargs):
        calls.append(args)

    monkeypatch.setattr(executor_mod.asyncio, "create_subprocess_exec", _fake_spawn)
    executor = Executor(_guard(tmp_path))
    _aio.run(executor._spawn_real([sys.executable, "-c", "pass"]))
    assert calls and calls[0][0] == sys.executable


def test_open_real_delegates_to_startfile(monkeypatch, tmp_path):
    import asyncio as _aio
    import os as _os

    seen = []
    monkeypatch.setattr(_os, "startfile", lambda path: seen.append(path), raising=False)
    executor = Executor(_guard(tmp_path))
    _aio.run(executor._open_real("C:\\note.txt"))
    assert seen == ["C:\\note.txt"]


def test_volume_key_failure_honest(monkeypatch, tmp_path):
    import asyncio as _aio

    import bridge.executor as executor_mod

    async def _boom(vk, times=1):
        raise RuntimeError("keys dead")

    monkeypatch.setattr(executor_mod, "_press_vk", _boom)
    out = _aio.run(Executor(_guard(tmp_path)).volume("up"))
    assert out.status == "error" and "key injection failed" in out.detail


def test_resolve_relative_and_bare_names(tmp_path):
    root = tmp_path / "r"
    root.mkdir()
    assert resolve_in_roots("", (root,)) is None
    assert resolve_in_roots("a.txt", (root,)) == (root / "a.txt").resolve()
