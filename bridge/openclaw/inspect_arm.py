"""Screen-inspection engine (Phase 3.1): aggregated live diagnostics.

Aggregates the PROVEN primitives — in-memory screenshot
(`Executor._grab_real`), foreground-window title
(`app_sessions.windows_foreground_app`), OCR extractor — into ONE
transcript the core narrates in ≤2 lines. All three backends injectable;
defaults bind the real ones (used ONLY by the PC daemon, never in tests).

UIA tree enumeration is 3.4 scope: snapshot() returns a valid empty list
until then — never invented handles.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any, Final

from loguru import logger

from bridge.app_sessions import UnknownForeground, windows_foreground_app
from bridge.executor import Executor
from bridge.openclaw.protocol import ElementHandle

OCR_MAX_CHARS: Final[int] = 500

_INSPECT_PROMPT: Final[str] = (
    "Describe errors, dialogs, and the active window contents verbatim in "
    "one short paragraph. No advice, no steps."
)


def _default_grab() -> bytes:
    return Executor._grab_real()


def _default_foreground() -> str | None:
    try:
        return windows_foreground_app()
    except UnknownForeground:
        return None


class ScreenInspector:
    """Read-only aggregation: screenshot + foreground + OCR -> transcript."""

    def __init__(
        self,
        *,
        grab: Callable[[], bytes] | None = None,
        foreground: Callable[[], str | None] | None = None,
        ocr: Callable[[bytes, str], Awaitable[str | None]] | None = None,
    ) -> None:
        self._grab = grab or _default_grab
        self._foreground = foreground or _default_foreground
        self._ocr = ocr

    async def snapshot(self, scope: str = "desktop") -> list[ElementHandle]:
        """No tree backend in 3.1 (3.4 scope) — valid empty list, never
        invented handles."""
        return []

    async def inspect(self, scope: str = "desktop") -> dict[str, Any]:
        """Aggregate diagnostics. NEVER raises — every backend failure lands
        inside the transcript as an honest negative."""
        jpeg: bytes = b""
        try:
            jpeg = await asyncio.to_thread(self._grab)
        except Exception as exc:  # noqa: BLE001 — capture failure is data
            logger.warning("inspect screenshot failed: {}", exc)
        try:
            foreground = await asyncio.to_thread(self._foreground)
        except Exception as exc:  # noqa: BLE001 — locked/idle reads as None
            logger.warning("inspect foreground probe failed: {}", exc)
            foreground = None
        ocr_text: str | None = None
        if self._ocr is None:
            ocr_status = "unavailable (no vision extractor bound)"
        elif not jpeg:
            ocr_status = "skipped (no screenshot)"
        else:
            try:
                raw = await self._ocr(jpeg, _INSPECT_PROMPT)
                ocr_text = (raw or "").strip()[:OCR_MAX_CHARS] or None
                ocr_status = "ok" if ocr_text else "empty"
            except Exception as exc:  # noqa: BLE001
                logger.warning("inspect OCR failed: {}", exc)
                ocr_status = f"failed: {exc}"
        return {
            "scope": scope,
            "screenshot_ok": bool(jpeg),
            "jpeg_bytes": len(jpeg),
            "foreground": foreground,
            "ocr_available": ocr_text is not None,
            "ocr_status": ocr_status,
            "ocr_text": ocr_text,
            "handles": 0,
        }
