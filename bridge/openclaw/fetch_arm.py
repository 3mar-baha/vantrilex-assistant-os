"""Stealth Retrieval Arm seam (Phase 2): passive read-only web extraction.

First-class routing path, NOT a GUI fallback — the core routes passive
reads here directly. The Scrapling binding lands in Phase 3 (wheels live in
requirements-bridge.txt); until then the fetcher is injected, and the
unconfigured path answers honestly. URL validation is enforced HERE so no
backend ever sees file/ftp/javascript shapes.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from urllib.parse import urlparse

Fetcher = Callable[[str], Awaitable[str]]

NOT_CONFIGURED = "openclaw fetch backend not configured (Phase 3 binds Scrapling)"


def check_url(url: str) -> str | None:
    """Normalized http(s) URL, or None when the shape is refused."""
    clean = (url or "").strip()
    if not clean:
        return None
    try:
        parts = urlparse(clean)
    except ValueError:
        return None
    if parts.scheme.casefold() not in ("http", "https") or not parts.netloc:
        return None
    return clean


async def fetch(url: str, fetcher: Fetcher | None = None) -> str:
    """Passive extraction: validated URL in, markdown text out. Raises
    ValueError on refused shapes; returns the honest line when unconfigured."""
    target = check_url(url)
    if target is None:
        raise ValueError(f"refused fetch target: {url!r}")
    if fetcher is None:
        return NOT_CONFIGURED
    return await fetcher(target)
