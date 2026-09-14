"""Perception seam (Phase 2): read-only element resolution interface.

The T1 (UIA) / DOM snapshot backends land in Phase 3 behind this protocol.
Nothing here touches Win32 or a browser — resolution is injected, so unit
tests run headless and the daemon stays honest until backends bind.
"""

from __future__ import annotations

from typing import Protocol

from bridge.openclaw.protocol import ElementHandle


class PerceptionEngine(Protocol):
    """Deterministic element resolution: scope in, handles out. Never acts."""

    async def snapshot(self, scope: str = "desktop") -> list[ElementHandle]: ...
