"""Pass-4 Google extras (v2.0 §3-ب/1): the directive's Google-API breadth lands
here as EXPLICITLY STAGED adapters — real wire format, free-tier quotas, all
gated behind env credentials that don't exist yet (owner drops them in .env and
the tools go live with zero code change, per the §7 staging contract).

What's IN (free within quota): YouTube Data API v3 search (10,000 units/day;
one search = 100 units). What's deliberately OUT (PAID — violates the $0.00
invariant, recorded in docs): Places API (New), Maps Grounding, Cloud Storage
writes beyond free tier, Cloud Logging/Monitoring ingestion. Weather was
re-served via Open-Meteo (see weather.py header)."""

from __future__ import annotations

from typing import Any

from loguru import logger

_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
_VIDEOS_URL = "https://www.googleapis.com/youtube/v3/videos"


class YouTubeClient:
    """YouTube Data API v3 search. `session` is the GoogleSession-backed HTTP
    object (request(method, url, **kw) -> resp with status_code/json()); the
    API key rides every call. Free tier: 10k units/day, search=100 units."""

    def __init__(self, session: Any, *, api_key: str) -> None:
        self._session = session
        self._key = api_key

    async def search(self, query: str, *, limit: int = 5) -> list[dict[str, str]]:
        """[{title, channel, url}] — real results only; empty on failure/quota
        (logged loudly, never fabricated)."""
        try:
            resp = await self._session.request(
                "GET",
                _SEARCH_URL,
                params={
                    "part": "snippet",
                    "q": query,
                    "type": "video",
                    "maxResults": str(limit),
                    "key": self._key,
                },
            )
            if getattr(resp, "status_code", 0) != 200:
                logger.warning("youtube search HTTP {} — quota or key problem", resp.status_code)
                return []
            items = resp.json().get("items", [])
        except Exception as error:  # noqa: BLE001 — honest empty, never a crash
            logger.warning("youtube search failed: {}", error)
            return []
        results: list[dict[str, str]] = []
        for item in items:
            video_id = (item.get("id") or {}).get("videoId")
            snippet = item.get("snippet") or {}
            if not video_id:
                continue
            results.append(
                {
                    "title": snippet.get("title", ""),
                    "channel": snippet.get("channelTitle", ""),
                    "url": f"https://youtu.be/{video_id}",
                }
            )
        return results

    async def video_stats(self, video_id: str) -> dict[str, str] | None:
        """View/like counts for one video (1 quota unit) — None on failure."""
        try:
            resp = await self._session.request(
                "GET",
                _VIDEOS_URL,
                params={"part": "statistics", "id": video_id, "key": self._key},
            )
            if getattr(resp, "status_code", 0) != 200:
                return None
            stats = (resp.json().get("items") or [{}])[0].get("statistics", {})
        except Exception as error:  # noqa: BLE001
            logger.warning("youtube stats failed: {}", error)
            return None
        return {
            "views": stats.get("viewCount", ""),
            "likes": stats.get("likeCount", ""),
        }
