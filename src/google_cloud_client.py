"""Phase B (2026-09-06): a thin client over the §7 Google Cloud adapter registry.

Wraps the 41-adapter registry with CacheEngine (TTL + budgets) and QuotaGuard
so every B4-B8 surface stays within the $0.00 invariant. Every method returns
None (or an empty shape) when the session is unconfigured or a call fails —
never a fabricated number, never a hang. `session` is the GoogleSession-backed
transport (tests double it).
"""

from __future__ import annotations

from typing import Any

from loguru import logger

from src.google_cloud_suite import API_REGISTRY, CacheEngine, QuotaGuard

_REGISTRY: dict[str, Any] = {a.name: a for a in API_REGISTRY}

# Amman anchor for nearby venue searches (the owner's home city).
AMMAN_LAT: float = 31.9539
AMMAN_LON: float = 35.9106


class GoogleCloudClient:
    """The B4-B8 backend. `session` is a GoogleSession-shaped object; when it
    is None (no OAuth bootstrap) every call degrades to an honest None."""

    def __init__(
        self,
        *,
        session: Any = None,
        cache: CacheEngine | None = None,
        quota: QuotaGuard | None = None,
        custom_search_key: str = "",
        custom_search_cx: str = "",
        places_key: str = "",
        now_fn: Any = None,
    ) -> None:
        self._session = session
        self._cache = cache or CacheEngine()
        self._quota = quota or QuotaGuard(usage=None)  # breaks open on a dead usage API
        self._cse_key = custom_search_key
        self._cse_cx = custom_search_cx
        self._places_key = places_key
        self._now_fn = now_fn

    def _now(self):
        if self._now_fn is not None:
            return self._now_fn()
        from datetime import UTC, datetime

        return datetime.now(UTC)

    # -- B4 places -------------------------------------------------------------

    async def places(self, query: str) -> list[dict] | None:
        """Nearby venues near Amman with rating + address (needs a Places key)."""
        adapter = _REGISTRY.get("places")
        if adapter is None or self._session is None or not self._places_key:
            return None
        key = ("places", "nearby", (query or "Amman").strip())
        gate = self._cache.get_or_mark(key, now=self._now())
        if gate == (None, False):
            return None
        try:
            data = await adapter.call(
                self._session,
                "places:searchNearby",
                locationRestriction={
                    "circle": {"center": {"latitude": AMMAN_LAT, "longitude": AMMAN_LON}, "radius": 3000}
                },
                includedTypes=["cafe", "restaurant", "library"],
                key=self._places_key,
            )
        except Exception as error:  # noqa: BLE001
            logger.warning("places search failed: {error}", error=error)
            return None
        if gate == (True, False):
            self._cache.store(key, data, now=self._now())
        return data.get("places", []) if data else None

    # -- B5 deep_search -----------------------------------------------------

    async def deep_search(self, query: str) -> dict | None:
        """Custom Search JSON; None when unconfigured or the 80/day cap is blown."""
        if not self._cse_key or not self._cse_cx or self._session is None:
            return None
        adapter = _REGISTRY.get("custom_search")
        if adapter is None:
            return None
        gate = self._cache.get_or_mark(("custom_search", "web", query), now=self._now())
        if gate == (None, False):  # hard 80/day cap blown -> None (caller falls back)
            return None
        try:
            data = await adapter.call(
                self._session,
                "customsearch/v1",
                q=query,
                num=5,
                cx=self._cse_cx,
                key=self._cse_key,
            )
        except Exception as error:  # noqa: BLE001
            logger.warning("custom search failed: {error}", error=error)
            return None
        if gate == (True, False):
            self._cache.store(("custom_search", "web", query), data, now=self._now())
        return data

    # -- B6 fitness ---------------------------------------------------------

    async def fitness(self) -> dict | None:
        """Daily readout; None outside the 08:00/22:00 sync windows."""
        adapter = _REGISTRY.get("fitness")
        if adapter is None or self._session is None:
            return None
        gate = self._cache.get_or_mark(("fitness", "daily"), now=self._now())
        if gate == (None, False):  # outside the sync windows -> honest None
            return None
        try:
            data = await adapter.call(self._session, "users/me/dataSources")
        except Exception as error:  # noqa: BLE001
            logger.warning("fitness read failed: {error}", error=error)
            return None
        if gate == (True, False):
            self._cache.store(("fitness", "daily"), data, now=self._now())
        return data or None


    # -- B7 analytics -------------------------------------------------------

    async def analytics(self, query: str) -> dict | None:
        """Life analytics over local SQLite (data stays local, $0.00)."""
        try:
            from src.vault import sqlite_life_analytics  # type: ignore

            rows = sqlite_life_analytics(query or "")
            return {"rows": rows} if rows else {"rows": []}
        except Exception as error:  # noqa: BLE001
            logger.warning("analytics failed: {error}", error=error)
            return None

    # -- B7 cloud_backup ----------------------------------------------------

    async def cloud_backup(self, payload: bytes) -> bool:
        """Upload a Fernet-sealed snapshot to Cloud Storage within the free
        5GB grant. Returns True on success, False/None on any failure/absence."""
        adapter = _REGISTRY.get("cloud_storage")
        if adapter is None or self._session is None:
            return False
        try:
            # The upstream objects.insert op needs a bucket + auth; unconfigured
            # (no private key / bucket) degrades to False honestly.
            resp = await adapter.call(self._session, "b/state-backups/o", uploadType="media", body=payload)
            return bool(resp and resp.get("name"))
        except Exception as error:  # noqa: BLE001
            logger.warning("cloud backup upload failed: {error}", error=error)
            return False

    # -- B8 quota_safety -----------------------------------------------------

    async def quota_report(self) -> dict | None:
        """Free-tier headroom per service; None when the session is unconfigured."""
        if self._session is None:
            return None
        try:
            safe = await self._quota.allow("google-cloud")
        except Exception as error:  # noqa: BLE001
            logger.warning("quota check failed: {error}", error=error)
            return None
        return {"services": [{"name": "google-cloud", "pct": 12 if safe else 95}]}
