"""M4 (master directive 2026-09-05 §4): five free external APIs.

Zero-cost contract: Jina Reader / Aladhan / CoinGecko / Hacker News / IP-API
are keyless; ExchangeRate reads EXCHANGERATE_API_KEY from .env (empty -> the
honest None — never a fabricated rate). One injectable httpx-like client
rides them all; every failure degrades to None, never a crash, never a
made-up number. TTL caching per the directive: prayer 24h, currency 1h,
crypto 15m (a cache hit serves; a miss fetches).
"""

from __future__ import annotations

import time
from typing import Any, Final

from loguru import logger

PRAYER_TTL_S: Final[int] = 24 * 3600
CURRENCY_TTL_S: Final[int] = 3600
CRYPTO_TTL_S: Final[int] = 15 * 60

_PRAYERS: Final[tuple[str, ...]] = ("Fajr", "Dhuhr", "Asr", "Maghrib", "Isha")


class ExternalAPIs:
    """The five-API client. `http` is any httpx.AsyncClient-shaped object
    (the tests double the transport; production binds one shared client)."""

    def __init__(self, *, http: Any, fx_key: str = "") -> None:
        self._http = http
        self._fx_key = fx_key
        self._cache: dict[str, tuple[float, Any]] = {}

    def bind_fx_key(self, key: str) -> None:
        """Production wires the env key after settings load."""
        self._fx_key = (key or "").strip()

    # -- the shared fetch ------------------------------------------------------

    async def _get_json(self, url: str, *, params: dict | None = None) -> Any:
        try:
            response = await self._http.get(url, params=params, timeout=15.0)
        except Exception as error:  # noqa: BLE001 — dead net -> None, never a crash
            logger.warning("external api fetch failed {url}: {error}", url=url, error=error)
            return None
        if response.status_code != 200:
            logger.warning("external api HTTP {code} {url}", code=response.status_code, url=url)
            return None
        try:
            return response.json()
        except ValueError:
            logger.warning("external api non-JSON body {url}", url=url)
            return None

    async def _get_text(self, url: str) -> str | None:
        try:
            response = await self._http.get(url, timeout=30.0)
        except Exception as error:  # noqa: BLE001
            logger.warning("external text fetch failed {url}: {error}", url=url, error=error)
            return None
        if response.status_code != 200:
            return None
        return response.text

    def _cached(self, key: str, ttl_s: int) -> Any:
        hit = self._cache.get(key)
        if hit is not None and hit[0] > time.time():
            return hit[1]
        return None

    def _store(self, key: str, ttl_s: int, value: Any) -> None:
        self._cache[key] = (time.time() + ttl_s, value)

    # -- 1) Jina Reader -----------------------------------------------------------

    async def read_webpage_clean(self, url: str) -> str | None:
        """https://r.jina.ai/{target} — keyless clean Markdown; the URL rides
        the PATH (the directive's endpoint shape)."""
        target = (url or "").strip()
        if not target:
            return None
        return await self._get_text(f"https://r.jina.ai/{target}")

    # -- 2) Aladhan prayer times ----------------------------------------------------

    async def get_prayer_times(self, date_str: str | None = None) -> dict[str, str] | None:
        """Amman/Jordan, method 4 — the five prayers, TTL 24h."""
        cache_key = f"prayer:{date_str or ''}"
        cached = self._cached(cache_key, PRAYER_TTL_S)
        if cached is not None:
            return cached
        params: dict[str, str] = {"city": "Amman", "country": "Jordan", "method": "4"}
        if date_str:
            params["date"] = date_str
        data = await self._get_json("https://api.aladhan.com/v1/timingsByCity", params=params)
        if not isinstance(data, dict):
            return None
        timings = (data.get("data") or {}).get("timings") or {}
        times = {name: str(timings.get(name, ""))[:5] for name in _PRAYERS}
        if not all(times.values()):
            return None
        self._store(cache_key, PRAYER_TTL_S, times)
        return times

    # -- 3) currency + crypto -------------------------------------------------------

    async def convert_currency(
        self, amount: float, from_curr: str, to_curr: str = "JOD"
    ) -> dict[str, float] | None:
        """ExchangeRate pair API — the key rides the path; empty key -> None
        (the honest offline line). TTL 1h."""
        if not self._fx_key:
            return None
        cache_key = f"fx:{from_curr}:{to_curr}:{amount}"
        cached = self._cached(cache_key, CURRENCY_TTL_S)
        if cached is not None:
            return cached
        data = await self._get_json(
            f"https://v6.exchangerate-api.com/v6/{self._fx_key}/pair/{from_curr}/{to_curr}/{amount}"
        )
        if not isinstance(data, dict) or "conversion_rate" not in data:
            return None
        out = {
            "rate": float(data["conversion_rate"]),
            "total": float(data.get("conversion_result", 0.0)),
        }
        self._store(cache_key, CURRENCY_TTL_S, out)
        return out

    async def get_crypto_price(
        self, coin: str = "bitcoin", vs_currency: str = "jod"
    ) -> dict | None:
        """CoinGecko simple/price — keyless; TTL 15m."""
        cache_key = f"cg:{coin}:{vs_currency}"
        cached = self._cached(cache_key, CRYPTO_TTL_S)
        if cached is not None:
            return cached
        data = await self._get_json(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": coin, "vs_currencies": vs_currency},
        )
        if not isinstance(data, dict) or not data:
            return None
        self._store(cache_key, CRYPTO_TTL_S, data)
        return data

    # -- 4) Hacker News radar ---------------------------------------------------------

    async def get_tech_trending(self, limit: int = 5) -> list[dict] | None:
        """Top stories (Y Combinator Firebase) — id/title/url list; dead item
        ids skip, never a hole-crash."""
        data = await self._get_json("https://hacker-news.firebaseio.com/v0/topstories.json")
        if not isinstance(data, list):
            return None
        stories: list[dict] = []
        for item_id in data[: max(1, limit) * 2]:  # headroom for dead items
            if len(stories) >= limit:
                break
            item = await self._get_json(
                f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json"
            )
            if isinstance(item, dict) and item.get("title"):
                stories.append(
                    {"id": item_id, "title": str(item["title"]), "url": str(item.get("url") or "")}
                )
        return stories or None

    # -- 5) IP watchdog -------------------------------------------------------------------

    async def check_network_status(self) -> dict | None:
        """ip-api.com/json — public IP/ISP/city/proxy (public non-commercial
        tier). Executed by the CORE (its own egress), reported to the owner."""
        data = await self._get_json("http://ip-api.com/json")
        if not isinstance(data, dict) or not data.get("query"):
            return None
        return {
            "ip": data.get("query"),
            "isp": data.get("isp"),
            "city": data.get("city"),
            "proxy": bool(data.get("proxy")),
        }
