"""M2 (master directive 2026-09-05 §3): Desktop Bridge extensions —
bidirectional file drop, media/volume master, instant screen OCR.

Contracts:
- file.upload: bytes ride the wire; the daemon saves into the whitelisted
  roots ONLY (Downloads / project inbox); traversal and absolute paths die
  loudly; filenames sanitized.
- file.download: the daemon reads a file from the whitelisted roots ONLY;
  nothing outside them ever leaves the PC.
- exec.volume: mute/unmute/up/down/set-X% via Windows virtual keys (ctypes,
  no new dependency); set% = stepped presses from a known anchor.
- exec.media_control: play/pause/next/prev via the media virtual keys.
- exec.screen_ocr: screenshot buffer -> the vision lane extracts code/
  terminal/error text verbatim in Markdown code blocks.
"""

from __future__ import annotations

import base64
import json

# -- path safety (the shared wall) ------------------------------------------------


def test_sanitize_filename_strips_traversal():
    """Filenames are basename-only: traversal (..), absolute paths, drive
    letters, and separators all die at the wall."""
    from bridge.executor import sanitize_filename

    for hostile in (
        "../../windows/system32/cmd.exe",
        "..\\..\\secrets.env",
        "C:\\Users\\omarb\\ Desktop\\x.txt",
        "/etc/passwd",
        "a/b/c.txt",
        "a\\b\\c.txt",
        "   ",
        "",
    ):
        out = sanitize_filename(hostile)
        assert "/" not in out and "\\" not in out, hostile
        assert ".." not in out
        assert out == "" or out.strip() == out


def test_resolve_in_roots_accepts_only_whitelisted_roots(tmp_path):
    """A relative path resolves inside the whitelisted roots; anything that
    escapes (traversal, other dirs, absolute) is refused — read AND write."""
    from bridge.executor import resolve_in_roots

    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    roots = (downloads, inbox)

    ok = resolve_in_roots("report.pdf", roots)
    assert ok is not None and ok.parent == downloads  # default root

    ok2 = resolve_in_roots("notes.txt", roots, preferred=inbox)
    assert ok2 is not None and ok2.parent == inbox

    for hostile in ("../outside.txt", "..\\..\\x", "C:/Windows/system32/config"):
        assert resolve_in_roots(hostile, roots) is None, hostile

    # a real path INSIDE a root passes; outside every root it does not
    inside = downloads / "sub"
    inside.mkdir()
    assert resolve_in_roots("sub/deep.txt", roots) is not None
    outside = tmp_path / "Other"
    outside.mkdir()
    assert resolve_in_roots(str(outside / "x.txt"), roots) is None


# -- the executor methods -----------------------------------------------------------


async def test_file_upload_saves_bytes(tmp_path):
    """The happy upload: sanitized name, canonical path inside Downloads,
    the EXACT bytes on disk, an ok ExecResult."""
    from bridge.executor import Executor
    from bridge.guard import Guard

    wl = tmp_path / "whitelist.json"
    wl.write_text(json.dumps({"allowed_apps": [], "restricted_actions": []}), encoding="utf-8")
    downloads = tmp_path / "Downloads"
    downloads.mkdir(parents=True)
    exec_ = Executor(Guard(str(wl)), file_roots=(downloads,))
    result = await exec_.file_upload(b"FILE-BYTES-HERE", "خطة العمل.pdf")
    assert result.status == "ok"
    saved = downloads / "خطة العمل.pdf"
    assert saved.read_bytes() == b"FILE-BYTES-HERE"
    assert "التنزيلات" in result.detail or "Downloads" in result.detail


async def test_file_upload_traversal_refused(tmp_path):
    """A traversal name NEVER writes: the sanitizer reduces it to a basename
    inside the root — the file lands where the root says, not the attacker."""
    from bridge.executor import Executor
    from bridge.guard import Guard

    wl = tmp_path / "whitelist.json"
    wl.write_text(json.dumps({"allowed_apps": [], "restricted_actions": []}), encoding="utf-8")
    downloads = tmp_path / "Downloads"
    downloads.mkdir(parents=True)
    exec_ = Executor(Guard(str(wl)), file_roots=(downloads,))
    result = await exec_.file_upload(b"x", "../../evil.exe")
    assert result.status == "ok"  # sanitized into the root — never refused-to-crash
    assert not (tmp_path / "evil.exe").exists()
    assert downloads.joinpath("evil.exe").read_bytes() == b"x"  # basename only


async def test_file_download_reads_and_guards(tmp_path):
    """Download: a file inside a root returns its bytes; a path outside every
    root is refused with an error result — nothing leaves the PC."""
    from bridge.executor import Executor
    from bridge.guard import Guard

    wl = tmp_path / "whitelist.json"
    wl.write_text(json.dumps({"allowed_apps": [], "restricted_actions": []}), encoding="utf-8")
    downloads = tmp_path / "Downloads"
    downloads.mkdir(parents=True)
    (downloads / "doc.txt").write_text("PC-CONTENT", encoding="utf-8")
    (downloads / "secret.key").write_text("NEVER", encoding="utf-8")
    exec_ = Executor(Guard(str(wl)), file_roots=(downloads,), blocked_suffixes=(".key",))

    ok = await exec_.file_download("doc.txt")
    assert ok.status == "ok" and base64.b64decode(ok.detail) == b"PC-CONTENT"

    outside = await exec_.file_download("../Other/doc.txt")
    assert outside.status == "error"  # refused loudly

    blocked = await exec_.file_download("secret.key")
    assert blocked.status == "error"  # sensitive suffix never leaves


async def test_volume_and_media_keys(monkeypatch):
    """volume/media inject the RIGHT Windows virtual keys — the ctypes seam
    records every press; the semantics map to the directive's commands."""
    import bridge.executor as ex
    from bridge.executor import Executor
    from bridge.guard import Guard

    pressed: list[int] = []

    async def fake_press(vk: int, times: int = 1) -> None:
        pressed.extend([vk] * times)

    monkeypatch.setattr(ex, "_press_vk", fake_press)

    exec_ = Executor(Guard(_wl_path := "config/whitelist.json"))

    await exec_.volume("mute")
    await exec_.volume("unmute")
    await exec_.volume("up")
    await exec_.volume("down")
    await exec_.volume("set", level=30)  # stepped presses

    await exec_.media("play_pause")
    await exec_.media("next")
    await exec_.media("prev")

    assert ex.VK_VOLUME_MUTE in pressed
    assert pressed.count(ex.VK_VOLUME_UP) >= 1 and ex.VK_VOLUME_DOWN in pressed
    assert pressed.count(ex.VK_VOLUME_UP) >= 1  # set-30% pressed UP steps
    assert ex.VK_MEDIA_PLAY_PAUSE in pressed
    assert ex.VK_MEDIA_NEXT_TRACK in pressed
    assert ex.VK_MEDIA_PREV_TRACK in pressed


async def test_screen_ocr_extracts_via_vision(monkeypatch):
    """screen_ocr: the screenshot buffer -> the vision lane with the
    verbatim-extraction prompt; the answer is the extracted text itself."""
    from bridge.executor import Executor
    from bridge.guard import Guard

    calls: list[tuple[bytes, str]] = []

    async def fake_vision(jpeg: bytes, prompt: str) -> str:
        calls.append((jpeg, prompt))
        return "```python\nprint('hello')\n```"

    def fake_grab() -> bytes:  # sync like _grab_real (to_thread wraps it)
        return b"FAKE-JPEG"

    exec_ = Executor(Guard("config/whitelist.json"))
    exec_._grab = fake_grab  # the instance seam (the OS edge)
    result = await exec_.screen_ocr(vision=fake_vision)
    assert result.status == "ok"
    assert "print" in result.detail
    assert calls, "the vision lane was never called"
    assert "verbatim" in calls[0][1] or "code" in calls[0][1].lower()
    assert calls[0][0] == b"FAKE-JPEG"  # the real buffer reached the lane


# -- the core-side tools (M2 wiring) ----------------------------------------------


async def test_volume_tool_routes_actions_and_level():
    """The volume tool: the Arabic verbs map to the wire action; the % level
    parses (Western AND Arabic-Indic digits) into the set-level."""
    from src.tools import ToolRegistry

    sent: list[tuple[str, dict]] = []

    class _Bridge:
        async def send_cmd(self, cmd, args, *, timeout_s=20.0):
            sent.append((cmd, dict(args)))
            return {"status": "ok", "detail": f"الصوت {args.get('action')}"}

    registry = ToolRegistry(bridge=_Bridge())

    await registry.call("volume", "اكتمي الصوت")
    assert sent[-1] == ("exec.volume", {"action": "mute", "level": None})

    await registry.call("volume", "حطي الصوت على 30%")
    assert sent[-1] == ("exec.volume", {"action": "set", "level": 30})

    await registry.call("volume", "حطي الصوت على ٥٠%")  # Arabic-Indic
    assert sent[-1] == ("exec.volume", {"action": "set", "level": 50})

    await registry.call("volume", "ارفعي الصوت")
    assert sent[-1] == ("exec.volume", {"action": "up", "level": None})

    await registry.call("volume", "نزلي الصوت")
    assert sent[-1] == ("exec.volume", {"action": "down", "level": None})


async def test_media_tool_commands():
    """The media tool: playback verbs map to the media keys."""
    from src.tools import ToolRegistry

    sent: list[dict] = []

    class _Bridge:
        async def send_cmd(self, cmd, args, *, timeout_s=20.0):
            sent.append(dict(args))
            return {"status": "ok", "detail": "media"}

    registry = ToolRegistry(bridge=_Bridge())
    await registry.call("media", "وقفي الفيديو")
    assert sent[-1] == {"command": "play_pause"}
    await registry.call("media", "الأغنية التالية")
    assert sent[-1] == {"command": "next"}
    await registry.call("media", "المقطع السابق")
    assert sent[-1] == {"command": "prev"}


async def test_file_fetch_tool_dispatches_document():
    """PC->phone: the bytes dispatch via the document sender with the basename;
    the tool returns None (the document IS the delivery, launch-style)."""
    from src.tools import ToolRegistry

    dispatched: list[tuple[bytes, str]] = []

    class _DocSender:
        async def __call__(self, data, filename):
            dispatched.append((data, filename))

    class _Bridge:
        async def send_cmd(self, cmd, args, *, timeout_s=20.0):
            assert cmd == "file.download"
            import base64 as b64

            return {"status": "ok", "detail": b64.b64encode(b"PC-FILE").decode()}

    registry = ToolRegistry(bridge=_Bridge(), document_sender=_DocSender())
    out = await registry.call("file_fetch", "خطة.pdf من التنزيلات")
    assert out is None  # the document already delivered it
    assert dispatched == [(b"PC-FILE", "خطة.pdf")]


async def test_file_fetch_refusals_honest():
    """outside-roots and sensitive suffixes answer honestly — no fabricated
    bytes, no crash."""
    from src.tools import ToolRegistry

    class _Bridge:
        def __init__(self, detail):
            self._detail = detail

        async def send_cmd(self, cmd, args, *, timeout_s=20.0):
            return {"status": "error", "detail": self._detail}

    outside = ToolRegistry(bridge=_Bridge("outside_allowed_roots: refused"))
    assert "المسموحة" in await outside.call("file_fetch", "../x.txt")

    sensitive = ToolRegistry(bridge=_Bridge("sensitive file type: refused"))
    assert "حساس" in await sensitive.call("file_fetch", "secret.key")


def test_m2_net_routing():
    """The net: every §3 trigger routes to its tool; the sibling words stay
    with their owners (screenshot/close/launch/telemetry un-stolen)."""
    from src.dispatcher import _keyword_net

    routes = {
        "اكتمي الصوت": "volume",
        "شغلي الصوت": "volume",
        "ارفعي الصوت": "volume",
        "وطي الصوت": "volume",
        "حطي الصوت على 30%": "volume",
        "وقفي الفيديو": "media",
        "تابعي التشغيل": "media",
        "الأغنية التالية": "media",
        "المقطع السابق": "media",
        "اقرأي النص اللي عالشاشة": "screen_ocr",
        "استخرجي الكود من الشاشة": "screen_ocr",
        "شو كود الخطأ اللي بالشاشة": "screen_ocr",
        "ابعثيلي ملف خطة العمل.pdf من التنزيلات": "file_fetch",
        "ابعثيلي ملف notes.txt من سطح المكتب": "file_fetch",
    }
    for text, expected in routes.items():
        assert _keyword_net(text)[0] == expected, text
    # guards
    assert _keyword_net("ارسلي لقطة الشاشة")[0] == "screenshot"
    assert _keyword_net("سكري كروم")[0] == "close"
    assert _keyword_net("افتحي كروم")[0] == "launch"


# -- the daemon wire branches ------------------------------------------------------


async def test_daemon_serves_m2_commands(tmp_path, monkeypatch):
    """The daemon _execute: file.upload/download, exec.volume/media_control
    carry the executor's results over the wire; screen_ocr honors the
    unconfigured-vision honesty."""
    import json as _json

    from bridge.daemon import BridgeDaemon
    from bridge.executor import Executor
    from bridge.guard import Guard
    from common.protocol import new_envelope

    wl = tmp_path / "whitelist.json"
    wl.write_text(_json.dumps({"allowed_apps": [], "restricted_actions": []}), encoding="utf-8")
    downloads = tmp_path / "Downloads"
    downloads.mkdir(parents=True)

    async def no_vk(vk, times=1):  # the key seam: nothing presses in tests
        pass

    import bridge.executor as ex_mod

    monkeypatch.setattr(ex_mod, "_press_vk", no_vk)

    daemon = BridgeDaemon(
        "ws://127.0.0.1:1", "t", Executor(Guard(str(wl)), file_roots=(downloads,))
    )

    # upload
    import base64 as _b64

    frame = new_envelope(
        type="cmd",
        cmd="file.upload",
        args={"data": _b64.b64encode(b"BYTES").decode(), "filename": "x.pdf"},
    )
    status, payload = await daemon._execute(frame)
    assert status == "ok" and (downloads / "x.pdf").read_bytes() == b"BYTES"

    # download
    (downloads / "x.pdf").write_bytes(b"BYTES")
    frame = new_envelope(type="cmd", cmd="file.download", args={"path": "x.pdf"})
    status, payload = await daemon._execute(frame)
    assert status == "ok" and _b64.b64decode(payload["detail"]) == b"BYTES"

    # volume + media (the key seam records nothing; the executor returns ok)
    frame = new_envelope(type="cmd", cmd="exec.volume", args={"action": "mute"})
    status, _payload = await daemon._execute(frame)
    assert status == "ok"

    frame = new_envelope(type="cmd", cmd="exec.media_control", args={"command": "next"})
    status, _payload = await daemon._execute(frame)
    assert status == "ok"

    # screen_ocr without the vision lane -> the honest error
    frame = new_envelope(type="cmd", cmd="exec.screen_ocr", args={})
    status, payload = await daemon._execute(frame)
    assert status == "error" and "vision" in payload["detail"]
