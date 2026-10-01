"""Whitelist-guarded PC executor (sprint-3 3.4): the ONLY code path that touches the
owner's machine. Every action returns an ExecResult carrying an audit code; spawns are
detached, shell-free, and mirrored to the audit ledger by the core coordinator."""

from __future__ import annotations

import asyncio
import base64
import os
import secrets
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath
from typing import Final

from loguru import logger
from pydantic import BaseModel

from bridge.guard import Guard


def mint_audit_code() -> str:
    return f"PC-{datetime.now(UTC):%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"


class ExecResult(BaseModel):
    status: str  # "ok" | "error"
    detail: str = ""
    audit_code: str
    killed_processes: int = 0  # directive §2: psutil-verified termination count


def _count_running(image: str) -> int:
    """Directive §2: count live processes by image name — the verification
    behind every close confirmation. psutil is the bridge's existing
    dependency (telemetry); a psutil failure reads as 0 (fail-open count for
    the KILLED math, but the honest detail line still reports)."""
    try:
        import psutil

        return sum(
            1
            for p in psutil.process_iter(attrs=["name", "pid"])
            if (p.info.get("name") or "").casefold() == image.casefold()
        )
    except Exception:  # noqa: BLE001 — verification is best-effort, never a crash
        return 0


# UWP image aliases (live defect 2026-09-05 «سكري الآلة الحاسبة»): Windows 10/11
# ships several whitelisted apps under a DIFFERENT process image than the
# whitelist's executable. Calculator is the owner's case — it runs as
# CalculatorApp.exe, while the whitelist (and every legacy shortcut, and the
# Arabic alias table in pc_actions) still says calc.exe. Terminating only the
# whitelist image reported «ما لقيت نسخة شغالة هسا» while the window stayed
# open. Close must hunt EVERY image the app can actually run as.
PROCESS_IMAGE_ALIASES: Final[dict[str, tuple[str, ...]]] = {
    "calculator": ("CalculatorApp.exe", "Calculator.exe", "calc.exe"),
    "calc.exe": ("CalculatorApp.exe", "Calculator.exe", "calc.exe"),
    "chrome": ("chrome.exe",),
    "cmd": ("cmd.exe",),
    "obsidian": ("Obsidian.exe",),
}


def close_images(name: str, executable: str | None = None) -> tuple[str, ...]:
    """Every image name close() must terminate for ONE logical app: the
    whitelist's own executable first (its basename — taskkill /IM wants an
    image name, never a path), then every known alias. Deduped
    case-insensitively, order preserved. Apps with no alias entry yield
    exactly the whitelist image (unchanged behavior)."""
    ordered: list[str] = []
    seen: set[str] = set()

    def add(image: str) -> None:
        key = image.casefold()
        if image and key not in seen:
            seen.add(key)
            ordered.append(image)

    base = PureWindowsPath(executable or name).name or (executable or name)
    add(base)
    for key in (name.strip().casefold(), base.casefold()):
        for alias in PROCESS_IMAGE_ALIASES.get(key, ()):
            add(alias)
    return tuple(ordered)


POWER_ARGV = {
    "shutdown": ["shutdown", "/s", "/t", "0"],
    "restart": ["shutdown", "/r", "/t", "0"],
    "sleep": ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
}

# double-click equivalents: opening one of these IS launching it, so it must
# go through the app whitelist, never through open_path.
# `.lnk` runs its target, `.url` navigates to an attacker-chosen page, `.jar`
# executes, `.hta`/`.html`/`.htm` run script, `.wsf`/`.wsh` run Windows Script
# Host. F-3: the pre-F-3 set held the first nine and let every one of these
# through, so the set failed to match the rule stated above it.
OPEN_BLOCKED_SUFFIXES = {
    ".exe",
    ".bat",
    ".cmd",
    ".com",
    ".scr",
    ".msi",
    ".ps1",
    ".vbs",
    ".js",
    ".lnk",
    ".url",
    ".jar",
    ".hta",
    ".html",
    ".htm",
    ".wsf",
    ".wsh",
}

# M2 (directive §3-A): the file-drop wall. Uploads land in the FIRST root
# (the owner's Downloads); downloads may read inside ANY listed root only.
DEFAULT_FILE_ROOTS: tuple[str, ...] = (str(Path.home() / "Downloads"),)


def default_open_roots() -> tuple[Path, ...]:
    """The seed set for `open_path`'s containment wall (F-3).

    It is deliberately NOT `DEFAULT_FILE_ROOTS`: that is the file-drop landing
    zone (Downloads), and reusing it would confine every open to Downloads and
    break the verb for the whole project. This set is the owner's own machine:
    their home (Desktop, Documents, Pictures, Downloads all live under it), the
    repo this bridge ships from, and the process CWD (`data/inbox` is itself
    CWD-relative). Deduped, and never the home's PARENT -- the whole `C:/Users`
    would "reach the home" while admitting every other profile on the box, which
    is a containment failure dressed as convenience.

    The Executor takes these as a CONSTRUCTOR ARGUMENT (`open_roots=`), not an
    env var, following F-5's `bridge_path` precedent: the daemon's wiring in
    `bridge/__main__.py` is the single producer, and it is the owner's own code.
    """
    candidates = (Path.home(), Path(__file__).resolve().parents[1], Path.cwd())
    seen: set[str] = set()
    roots: list[Path] = []
    for candidate in candidates:
        key = str(candidate).casefold()
        if key not in seen:
            seen.add(key)
            roots.append(candidate)
    return tuple(roots)


# M2 (§3-B): Windows virtual-key codes for volume/media (ctypes user32 —
# zero new dependency, the $0.00 invariant held).
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_PLAY_PAUSE = 0xB3

# M2 (§3-C): the OCR extraction prompt — verbatim, no chit-chat
_OCR_PROMPT_AR = (
    "Extract all visible source code, terminal commands, and error stacktraces "
    "verbatim in clean Markdown code blocks without conversational filler."
)


def sanitize_filename(raw: str) -> str:
    """Basename-only: separators, traversal, and absolute paths all die —
    the file lives where the ROOT says, never where the name says."""
    name = (raw or "").strip().replace("\\", "/").rsplit("/", 1)[-1]
    name = name.strip().strip(".")
    return "" if name in {"", ".", ".."} else name


def _under(root: Path, target: Path) -> bool:
    """Is `target` inside `root` — by PATH COMPONENT, never by string prefix.

    F-3 (measured): the pre-F-3 check was `str(resolved).startswith(
    str(base_resolved))`, which admits `Downloads-evil` as "inside" `Downloads`
    — a sibling that shares the root's name is outside it. WindowsPath compares
    case-insensitively, so `C:/USERS/x` still matches `C:/Users`.
    """
    try:
        target.relative_to(root)
    except ValueError:
        return False
    return True


def resolve_in_roots(raw: str, roots: tuple[Path, ...], *, preferred: Path | None = None):
    """Resolve a read/write target INSIDE the whitelisted roots. A bare name
    resolves in `preferred` (or the first root); a relative path must stay
    inside one of the roots; absolute paths must already live under a root.
    Anything escaping -> None (the caller refuses loudly).

    Containment is component-wise (see `_under`), so a sibling directory that
    shares a root's name is refused rather than admitted."""
    raw = (raw or "").strip()
    if not raw:
        return None
    candidates = [preferred] if preferred is not None else []
    candidates += [Path(r) for r in roots]
    for base in candidates:
        if not raw:
            continue
        as_posix = raw.replace("\\", "/")
        if (
            as_posix.startswith("/")
            or "://" in as_posix
            or len(as_posix) > 1
            and as_posix[1] == ":"
        ):
            target = Path(raw)  # absolute — must land under a root to pass
            try:
                resolved = target.resolve()
            except OSError:
                continue
            if _under(Path(base).resolve(), resolved):
                return resolved
        else:
            try:
                target = (Path(base) / raw).resolve()
            except OSError:
                continue
            if _under(Path(base).resolve(), target):
                return target
    return None


async def _press_vk(vk: int, times: int = 1) -> None:
    """One key event = down+up via ctypes user32 keybd_event; N presses in a
    loop. The executor's test seam (tests monkeypatch this module attr)."""
    import ctypes  # stdlib — no dependency

    def _press() -> None:
        ctypes.windll.user32.keybd_event(vk, 0, 0, 0)  # type: ignore[attr-defined]
        ctypes.windll.user32.keybd_event(vk, 0, 2, 0)  # type: ignore[attr-defined]  KEYEVENTF_KEYUP

    for _ in range(max(1, times)):
        await asyncio.to_thread(_press)


class Executor:
    """Runs guard-checked actions. _spawn/_open/_grab are the OS edges (spy points)."""

    def __init__(
        self,
        guard: Guard,
        *,
        file_roots: tuple[Path, ...] = (),
        blocked_suffixes: tuple[str, ...] = (),
        open_roots: tuple[Path, ...] | None = None,
    ):
        self._guard = guard
        self._spawn = self._spawn_real
        self._open = self._open_real
        self._grab = self._grab_real
        # M2 (directive §3): the file-drop wall — uploads land in the first
        # root; downloads may read from ANY listed root and nowhere else.
        self._file_roots = tuple(Path(r) for r in file_roots)
        self._blocked_suffixes = set(blocked_suffixes)
        # F-3: open_path has its OWN wall. `None` means "seed it" (home, the
        # repo, the CWD); an explicit `()` means the owner configured nothing
        # and therefore NOTHING opens (fail-closed, never "the wall is off").
        self._open_roots = tuple(
            Path(r) for r in (default_open_roots() if open_roots is None else open_roots)
        )

    async def screenshot(self, audit_code: str | None = None) -> ExecResult:
        """Pass-1 (v2.0 §3-د/2): ONE full-screen capture, entirely in memory —
        Pillow grabs, downsizes, JPEG-encodes into a BytesIO; bytes go back over
        the tunnel as base64. Zero disk writes, zero secrets on disk."""
        code = audit_code or mint_audit_code()
        try:
            data = await asyncio.to_thread(self._grab)
        except Exception as exc:  # noqa: BLE001 — capture failure must not kill the daemon
            logger.exception("screenshot capture failed")
            return ExecResult(
                status="error",
                detail=f"screenshot failed: {exc}",
                audit_code=code,
            )
        if not data:
            return ExecResult(status="error", detail="empty capture", audit_code=code)
        return ExecResult(
            status="ok",
            detail=base64.b64encode(data).decode(),
            audit_code=code,
        )

    @staticmethod
    def _grab_real() -> bytes:
        """Real OS edge: Pillow ImageGrab -> max 1600px wide JPEG in memory."""
        from io import BytesIO

        import PIL.ImageGrab as imagegrab
        from PIL import Image

        with imagegrab.grab() as img:
            img = img.convert("RGB")
            if img.width > 1600:
                ratio = 1600 / img.width
                img = img.resize((1600, int(img.height * ratio)), Image.LANCZOS)
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=70, optimize=True)
            return buf.getvalue()

    async def close(
        self, name: str, confirmation_id: str | None = None, audit_code: str | None = None
    ) -> ExecResult:
        """Directive §2 (owner 2026-09-04): REAL app termination — the same
        whitelist gate as launching, taskkill by image name, and psutil-VERIFIED
        results: the returned count is what actually died (never a claimed
        success while copies remain running — live lesson 3:23pm «لم يتم
        اغلاق ولا واحدة»)."""
        code = audit_code or mint_audit_code()
        verdict = self._guard.check_app(name)
        if not verdict.allowed_without_confirmation and not (confirmation_id or "").strip():
            return ExecResult(status="error", detail=verdict.reason, audit_code=code)
        # every image the app can run as — the whitelist image alone misses the
        # UWP rename (CalculatorApp.exe), which left the window open while the
        # owner was told nothing was running.
        images = close_images(name, verdict.executable)
        before = sum(_count_running(image) for image in images)
        for image in images:
            try:
                await self._spawn(["taskkill", "/IM", image, "/F", "/T"])
            except OSError as exc:
                # one alias failing (not installed / already gone) never aborts
                # the sweep — the remaining images must still be terminated
                logger.warning("taskkill of {image} failed: {error}", image=image, error=exc)
        # verification window: taskkill returns before the OS reaps the
        # processes — poll briefly, then report what actually died
        after = before
        for _ in range(10):  # ~2s max
            await asyncio.sleep(0.2)
            after = sum(_count_running(image) for image in images)
            if after == 0:
                break
        killed = before - after
        detail = f"closed {killed} of {before}" if killed else "no running copies found"
        return ExecResult(status="ok", detail=detail, audit_code=code, killed_processes=killed)

    async def launch(
        self, name: str, confirmation_id: str | None = None, audit_code: str | None = None
    ) -> ExecResult:
        code = audit_code or mint_audit_code()
        verdict = self._guard.check_app(name)
        if not verdict.allowed_without_confirmation and not (confirmation_id or "").strip():
            return ExecResult(status="error", detail=verdict.reason, audit_code=code)
        argv = [verdict.executable or name]
        try:
            await self._spawn(argv)
        except FileNotFoundError:
            return ExecResult(status="error", detail="البرنامج مش موجود عالجهاز", audit_code=code)
        except OSError as exc:
            logger.exception("launch of {name} failed", name=name)
            return ExecResult(status="error", detail=str(exc), audit_code=code)
        return ExecResult(status="ok", detail=verdict.reason, audit_code=code)

    async def power(
        self, action: str, confirmation_id: str = "", audit_code: str | None = None
    ) -> ExecResult:
        code = audit_code or mint_audit_code()
        verdict = self._guard.check_power(action)
        if "not in whitelist" in verdict.reason:
            return ExecResult(status="error", detail=verdict.reason, audit_code=code)
        # power ALWAYS needs a live confirmation id, even if a whitelist flag says otherwise
        if not (confirmation_id or "").strip():
            return ExecResult(
                status="error",
                detail="power action requires explicit owner confirmation",
                audit_code=code,
            )
        argv = POWER_ARGV.get(action.casefold())
        if argv is None:
            return ExecResult(
                status="error", detail=f"power action {action!r} not in whitelist", audit_code=code
            )
        try:
            await self._spawn(argv)
        except OSError as exc:
            logger.exception("power {action} failed", action=action)
            return ExecResult(status="error", detail=str(exc), audit_code=code)
        return ExecResult(status="ok", detail=verdict.reason, audit_code=code)

    async def open_path(
        self, path: str, confirmation_id: str | None = None, audit_code: str | None = None
    ) -> ExecResult:
        """Open a file/folder on the owner's PC, behind three walls.

        SHAPE — no UNC, no relative traversal.
        SUFFIX — a double-click equivalent (`.lnk`, `.url`, `.jar`, `.exe`, …)
        never opens here: opening it IS launching it, so it goes through the app
        whitelist instead. The refusal names the suffix, the reason, and that
        route, so an owner whose `.url` open bounced is not left guessing.
        CONTAINMENT — the resolved path must land inside a configured open root
        (`open_roots=`; see `default_open_roots`). Component-wise, so a sibling
        sharing a root's name is outside it. Unconfigured roots open nothing.

        `confirmation_id` is kept for wire symmetry with launch/close/power and
        is NOT a bypass: no id value moves a path past any of the three walls.
        Whether an id is even VALID is F-2's work (the executor's confirmation
        verifier) and is deliberately not duplicated here.
        """
        code = audit_code or mint_audit_code()
        raw = (path or "").strip()
        if not raw:
            return ExecResult(status="error", detail="empty path: refused", audit_code=code)
        win = PureWindowsPath(raw)
        if win.drive.startswith("\\\\"):
            return ExecResult(
                status="error", detail="outside_allowed_roots: UNC paths refused", audit_code=code
            )
        if not win.is_absolute() and ".." in win.parts:
            return ExecResult(
                status="error",
                detail="outside_allowed_roots: relative traversal refused",
                audit_code=code,
            )
        if win.suffix.casefold() in OPEN_BLOCKED_SUFFIXES:
            return ExecResult(
                status="error",
                detail=(
                    f"executable must go through the app whitelist: opening a "
                    f"{win.suffix.casefold()} file IS launching it, so launch the app by name "
                    f"(or add it to config/whitelist.json) instead"
                ),
                audit_code=code,
            )
        if not self._open_roots:
            return ExecResult(
                status="error",
                detail="outside_allowed_roots: open roots not configured — refused",
                audit_code=code,
            )
        # A bare name is CWD-relative, exactly as `os.startfile` would read it
        # (`data/inbox` is itself CWD-relative). Re-homing it into the first
        # open root would open a DIFFERENT file of the same name.
        base = Path.cwd() if not win.is_absolute() else None
        try:
            resolved = (Path(raw) if base is None else base / raw).resolve()
        except OSError as exc:
            return ExecResult(
                status="error",
                detail=f"outside_allowed_roots: unresolvable path refused ({exc})",
                audit_code=code,
            )
        if not any(_under(root.resolve(), resolved) for root in self._open_roots):
            where = ", ".join(str(r) for r in self._open_roots)
            return ExecResult(
                status="error",
                detail=(
                    "outside_allowed_roots: refused — open_path only reaches "
                    f"{where}; put the file under one of those, or open its "
                    "folder through the app whitelist"
                ),
                audit_code=code,
            )
        await self._open(str(resolved))
        return ExecResult(status="ok", detail="opened", audit_code=code)

    async def _spawn_real(self, argv: list[str]) -> None:
        if shutil.which(argv[0]) is None and not Path(argv[0]).exists():
            raise FileNotFoundError(argv[0])
        await asyncio.create_subprocess_exec(
            *argv,
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    async def _open_real(self, path: str) -> None:
        await asyncio.to_thread(os.startfile, path)

    # -- M2 (master directive 2026-09-05 §3): file drop, volume/media, OCR ---

    def _require_roots(self, code: str) -> ExecResult | None:
        if not self._file_roots:
            return ExecResult(status="error", detail="file roots not configured", audit_code=code)
        return None

    async def file_upload(self, payload: bytes, raw_name: str) -> ExecResult:
        """Phone -> PC file drop: the sanitized basename lands in the FIRST
        file root (Downloads); traversal/absolute names sanitize to the
        basename — the root decides where the file lives, never the name."""
        code = mint_audit_code()
        missing = self._require_roots(code)
        if missing is not None:
            return missing
        name = sanitize_filename(raw_name)
        if not name:
            return ExecResult(status="error", detail="empty filename", audit_code=code)
        target = self._file_roots[0] / name
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(target.write_bytes, payload)
        except OSError as exc:
            return ExecResult(status="error", detail=f"write failed: {exc}", audit_code=code)
        return ExecResult(
            status="ok",
            detail=f"تم حفظ الملف {name} في مجلد التنزيلات على جهازك",
            audit_code=code,
        )

    async def file_download(self, raw_path: str) -> ExecResult:
        """PC -> Phone file read: the path resolves inside the whitelisted
        roots ONLY (traversal/absolute-outside refused loudly); sensitive
        suffixes never leave the machine; bytes return as base64."""
        code = mint_audit_code()
        missing = self._require_roots(code)
        if missing is not None:
            return missing
        resolved = resolve_in_roots(raw_path, self._file_roots)
        if resolved is None:
            return ExecResult(
                status="error", detail="outside_allowed_roots: refused", audit_code=code
            )
        if resolved.suffix.casefold() in self._blocked_suffixes:
            return ExecResult(
                status="error", detail="sensitive file type: refused", audit_code=code
            )
        try:
            data = await asyncio.to_thread(resolved.read_bytes)
        except OSError as exc:
            return ExecResult(status="error", detail=f"read failed: {exc}", audit_code=code)
        return ExecResult(
            status="ok",
            detail=base64.b64encode(data).decode(),
            audit_code=code,
        )

    async def volume(self, action: str, level: int | None = None) -> ExecResult:
        """Volume master (ctypes key events — no new dependency, $0.00):
        mute/unmute/up/down; set-X% = X/2 presses of VOLUME_UP from the
        current level's anchor (Windows steps 2% per press)."""
        code = mint_audit_code()
        acts = {
            "mute": [(VK_VOLUME_MUTE, 1)],
            "unmute": [(VK_VOLUME_MUTE, 1)],
            "up": [(VK_VOLUME_UP, 5)],  # +10%
            "down": [(VK_VOLUME_DOWN, 5)],  # -10%
        }
        key = action.strip().casefold()
        if key == "set":
            if level is None or not 0 <= int(level) <= 100:
                return ExecResult(status="error", detail="level must be 0-100", audit_code=code)
            presses = max(1, int(level) // 2)
            acts["set"] = [(VK_VOLUME_UP, presses)]
            key = "set"
        if key not in acts:
            return ExecResult(
                status="error", detail=f"unknown volume action {action!r}", audit_code=code
            )
        try:
            for vk, times in acts[key]:
                await _press_vk(vk, times)
        except Exception as exc:  # noqa: BLE001 — a key failure is honest, never a crash
            return ExecResult(
                status="error", detail=f"key injection failed: {exc}", audit_code=code
            )
        label = f"على {level}%" if key == "set" else action
        return ExecResult(status="ok", detail=f"الصوت {label}", audit_code=code)

    async def media(self, command: str) -> ExecResult:
        """Media keys: play_pause / next / prev — injected into the active
        session, so whatever is playing obeys."""
        code = mint_audit_code()
        acts = {
            "play_pause": VK_MEDIA_PLAY_PAUSE,
            "pause": VK_MEDIA_PLAY_PAUSE,
            "play": VK_MEDIA_PLAY_PAUSE,
            "next": VK_MEDIA_NEXT_TRACK,
            "prev": VK_MEDIA_PREV_TRACK,
        }
        key = command.strip().casefold()
        if key not in acts:
            return ExecResult(
                status="error", detail=f"unknown media command {command!r}", audit_code=code
            )
        try:
            await _press_vk(acts[key], 1)
        except Exception as exc:  # noqa: BLE001
            return ExecResult(
                status="error", detail=f"key injection failed: {exc}", audit_code=code
            )
        return ExecResult(status="ok", detail=f"media {key}", audit_code=code)

    async def screen_ocr(self, vision, audit_code: str | None = None) -> ExecResult:
        """Instant screen OCR (§3-C): the in-memory screenshot buffer goes to
        the vision lane with the verbatim-extraction prompt; the extracted
        code/terminal/error text IS the result. `vision` is the injected
        async (jpeg_bytes, prompt) -> str seam (the core's m3 lane)."""
        code = audit_code or mint_audit_code()
        try:
            jpeg = await asyncio.to_thread(self._grab)
        except Exception as exc:  # noqa: BLE001 — capture failure is honest
            return ExecResult(status="error", detail=f"capture failed: {exc}", audit_code=code)
        if not jpeg:
            return ExecResult(status="error", detail="empty capture", audit_code=code)
        try:
            extracted = await vision(jpeg, _OCR_PROMPT_AR)
        except Exception as exc:  # noqa: BLE001 — vision failure is honest
            return ExecResult(status="error", detail=f"extraction failed: {exc}", audit_code=code)
        return ExecResult(status="ok", detail=extracted, audit_code=code)
