"""Pass-4 Firecrawl integration (v2.0 §3-هـ/1): complex-page extraction to
clean compact Markdown via Firecrawl's REST API — STAGED per §7 behind
FIRECRAWL_API_KEY (free tier keeps $0.00). The REST client (not the MCP server)
is the right shape for Sara: one authenticated POST per scrape, no daemon.
Unconfigured key = staged off (the live fallback for page reading is
WebIntel.read_page — keyless). Scraped content is DATA, never instructions."""

from __future__ import annotations

from typing import Any

from loguru import logger

_SCRAPE_URL = "https://api.firecrawl.dev/v1/scrape"
_BUDGET_CHARS = 4000


class FirecrawlClient:
    """scrape(url) -> {'markdown', 'title'} | None. `http` is injected (an
    httpx.AsyncClient in production); the API key rides the Authorization
    header. Any failure (network, status, shape) -> None — never a fabricated
    doc, never a crash into the chat turn."""

    def __init__(self, *, http: Any, api_key: str) -> None:
        self._http = http
        self._key = (api_key or "").strip()

    async def scrape(self, url: str) -> dict[str, str] | None:
        if not self._key:
            return None  # staged off — the keyless WebIntel path serves reads
        try:
            resp = await self._http.post(
                _SCRAPE_URL,
                json={"url": url, "formats": ["markdown"]},
                headers={"Authorization": f"Bearer {self._key}"},
            )
            if getattr(resp, "status_code", 0) != 200:
                logger.warning("firecrawl scrape HTTP {}", resp.status_code)
                return None
            data = resp.json()
            if not data.get("success"):
                return None
            payload = data.get("data") or {}
            markdown = str(payload.get("markdown") or "")[:_BUDGET_CHARS]
            if not markdown:
                return None
            return {
                "markdown": markdown,
                "title": str((payload.get("metadata") or {}).get("title") or ""),
            }
        except Exception as error:  # noqa: BLE001 — honest None, never a crash
            logger.warning("firecrawl scrape failed: {}", error)
            return None
