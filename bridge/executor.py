"""Whitelist-guarded PC executor (sprint-3 3.4): the ONLY code path that touches the
owner's machine. Every action returns an ExecResult carrying an audit code; spawns are
detached, shell-free, and mirrored to the audit ledger by the core coordinator."""

from __future__ import annotations

import asyncio
import os
import secrets
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path, PureWindowsPath

from loguru import logger
from pydantic import BaseModel

from bridge.guard import Guard


def mint_audit_code() -> str:
    return f"PC-{datetime.now(UTC):%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"


class ExecResult(BaseModel):
    status: str  # "ok" | "error"
    detail: str = ""
    audit_code: str


POWER_ARGV = {
    "shutdown": ["shutdown", "/s", "/t", "0"],
    "restart": ["shutdown", "/r", "/t", "0"],
    "sleep": ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
}

# double-click equivalents: opening one of these IS launching it, so it must
# go through the app whitelist, never through open_path
OPEN_BLOCKED_SUFFIXES = {".exe", ".bat", ".cmd", ".com", ".scr", ".msi", ".ps1", ".vbs", ".js"}


class Executor:
    """Runs guard-checked actions. _spawn/_open are the OS edges (spy points for tests)."""

    def __init__(self, guard: Guard):
        self._guard = guard
        self._spawn = self._spawn_real
        self._open = self._open_real

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
        del confirmation_id  # open_path is never auto-approved past these checks
        code = audit_code or mint_audit_code()
        win = PureWindowsPath(path)
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
                detail="executable must go through the app whitelist",
                audit_code=code,
            )
        await self._open(str(win))
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
