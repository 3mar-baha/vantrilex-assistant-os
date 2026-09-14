"""Stealth Retrieval Arm (Phase 3.2): passive read-only web extraction.

First-class routing path, NOT a GUI fallback — the core routes passive
reads here directly. Backend order: Scrapling (stealth TLS fingerprint)
first, httpx fallback (loudly logged). URL validation is enforced HERE so
no backend ever sees file/ftp/javascript shapes; every request is bounded
by FETCH_TIMEOUT_S.

Hermetic by construction: fetchers inject; the scrapling import is lazy
(bridge wheels are PC-only and absent from dev/CI).
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from html import unescape
from html.parser import HTMLParser
from typing import Final
from urllib.parse import urljoin, urlparse

from loguru import logger

Fetcher = Callable[[str], Awaitable[str]]

FETCH_TIMEOUT_S: Final[float] = 10.0
FETCH_MAX_CHARS: Final[int] = 8000
_FETCH_UA: Final[str] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Sara-fetch/1.0"

NOT_CONFIGURED = "openclaw fetch backend not configured (Phase 3 binds Scrapling)"


class FetchError(Exception):
    """The fetch ran but the page did not serve (HTTP error, empty body)."""


class FetchBackendMissing(Exception):
    """No backend available (no scrapling wheels, no HTTP client)."""


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


class _MarkdownExtractor(HTMLParser):
    """Stdlib HTML -> Markdown (headings, links, lists; scripts die)."""

    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=False)
        self._base = base_url
        self._out: list[str] = []
        self._skip = 0
        self._link: str | None = None
        self._li_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style", "noscript", "template", "svg"):
            self._skip += 1
            return
        if self._skip:
            return
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._out.append("\n" + "#" * int(tag[1]) + " ")
        elif tag in ("p", "br"):
            self._out.append("\n")
        elif tag == "li":
            self._out.append("\n- ")
            self._li_depth += 1
        elif tag == "a":
            href = dict(attrs).get("href")
            self._link = urljoin(self._base, href) if href else None

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript", "template", "svg"):
            self._skip = max(0, self._skip - 1)
            return
        if self._skip:
            return
        if tag == "a":
            self._link = None
        elif tag in ("p", "h1", "h2", "h3", "h4", "h5", "h6", "li", "ul", "ol", "div"):
            self._out.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        text = unescape(data)
        if not text.strip():
            return
        self._emit(text.strip() + " ")

    def handle_entityref(self, name: str) -> None:
        if not self._skip:
            self._emit(unescape(f"&{name};") + " ")

    def handle_charref(self, name: str) -> None:
        if not self._skip:
            self._emit(unescape(f"&#{name};") + " ")

    def _emit(self, text: str) -> None:
        if self._link:
            self._out.append(f"[{text.strip()}]({self._link})")
        else:
            self._out.append(text)

    def text(self) -> str:
        lines = [line.strip() for line in "".join(self._out).splitlines()]
        return "\n".join(line for line in lines if line)


def html_to_markdown(html: str, base_url: str) -> str:
    """Page HTML -> capped Markdown. Pure stdlib, total function."""
    parser = _MarkdownExtractor(base_url)
    try:
        parser.feed(html or "")
    except Exception as exc:  # noqa: BLE001 — malformed markup still yields partial text
        logger.warning("openclaw markdown extract degraded: {}", exc)
    return parser.text()[:FETCH_MAX_CHARS]


async def fetch_httpx(url: str, *, client=None) -> str:
    """Fallback lane: plain httpx GET bounded by FETCH_TIMEOUT_S."""
    target = check_url(url)
    if target is None:
        raise ValueError(f"refused fetch target: {url!r}")
    if client is None:
        try:
            import httpx
        except ImportError as exc:
            raise FetchBackendMissing("httpx unavailable") from exc
        async with httpx.AsyncClient(
            timeout=FETCH_TIMEOUT_S, headers={"user-agent": _FETCH_UA}, follow_redirects=True
        ) as owned:
            return await fetch_httpx(target, client=owned)
    response = await client.get(target)
    if response.status_code != 200:
        raise FetchError(f"HTTP {response.status_code} for {target}")
    text = html_to_markdown(response.text, target)
    if not text.strip():
        raise FetchError(f"empty body for {target}")
    return text


async def fetch_scrapling(url: str) -> str:
    """Primary lane: Scrapling stealth fetch (lazy import — PC wheels only).
    Page extraction is duck-typed (html/body/text/str) so minor upstream
    surface shifts degrade to the fallback instead of crashing."""
    target = check_url(url)
    if target is None:
        raise ValueError(f"refused fetch target: {url!r}")
    try:
        from scrapling.fetchers import Fetcher
    except ImportError as exc:
        raise FetchBackendMissing("scrapling wheels not installed") from exc

    def _get() -> tuple[int, str]:
        page = Fetcher.get(target, stealthy_headers=True)
        status = int(getattr(page, "status", 200) or 200)
        for attr in ("html", "body", "text"):
            body = getattr(page, attr, None)
            if isinstance(body, str) and body.strip():
                return status, body
            if isinstance(body, bytes) and body.strip():
                return status, body.decode("utf-8", "replace")
        return status, str(page)

    try:
        status, body = await asyncio.wait_for(asyncio.to_thread(_get), timeout=FETCH_TIMEOUT_S)
    except TimeoutError as exc:
        raise FetchError(f"scrapling timed out after {FETCH_TIMEOUT_S:.0f}s") from exc
    if status != 200:
        raise FetchError(f"scrapling HTTP {status} for {target}")
    text = html_to_markdown(body, target)
    if not text.strip():
        raise FetchError(f"empty body for {target}")
    return text


async def default_fetcher(url: str) -> str:
    """Backend order: Scrapling first, httpx fallback (loudly logged)."""
    try:
        return await fetch_scrapling(url)
    except FetchBackendMissing:
        logger.info("openclaw fetch: scrapling absent, httpx fallback")
    except Exception as exc:  # noqa: BLE001 — stealth blocked: plain lane tries
        logger.warning("openclaw fetch: scrapling failed ({}), httpx fallback", exc)
    return await fetch_httpx(url)


async def fetch(url: str, fetcher: Fetcher | None = None) -> str:
    """Passive extraction: validated URL in, markdown text out. Raises
    ValueError on refused shapes; FetchError/FetchBackendMissing otherwise."""
    target = check_url(url)
    if target is None:
        raise ValueError(f"refused fetch target: {url!r}")
    if fetcher is None:
        return await default_fetcher(target)
    return await fetcher(target)
