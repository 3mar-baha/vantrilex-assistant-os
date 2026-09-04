"""Pass-4 weather (v2.0 §3-ب/1, $0.00-compliant): instant spoken weather answers.
Google's Weather API is PAID (violates the zero-cost invariant) — the directive's
intent (live weather, spoken, on demand) is served via **Open-Meteo**: free for
non-commercial use, no API key, no quotas that bite a personal assistant.
Jordanian cities carry STATIC coordinates (zero geocode latency for the owner's
daily asks); unknown places geocode once and cache for the session.
The Arabic condition line is deterministic per WMO weather code — the numbers
are DATA the narration must quote verbatim."""

from __future__ import annotations

import json
from typing import Any

from loguru import logger

_GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search?name={name}&count=1&language=ar"
_FORECAST_URL = (
    "https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
    "&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m"
)

# WMO weather interpretation codes -> Jordanian Arabic condition lines
_WMO_AR: dict[int, str] = {
    0: "صافي",
    1: "صافي مع سحب خفيفة",
    2: "غائم جزئياً",
    3: "غائم",
    45: "ضباب",
    48: "ضباب متجمد",
    51: "رشّ خفيف",
    53: "رشّ متوسط",
    55: "رشّ كثيف",
    61: "مطر خفيف",
    63: "مطر متوسط",
    65: "مطر غزير",
    71: "ثلج خفيف",
    73: "ثلج متوسط",
    75: "ثلج كثيف",
    80: "زخات مطر خفيفة",
    81: "زخات مطر",
    82: "زخات مطر غزيرة",
    95: "عاصفة رعدية",
    96: "عاصفة رعدية مع برد خفيف",
    99: "عاصفة رعدية مع برد قوي",
}

# static coordinates for the owner's daily cities — zero geocode round-trips
_STATIC_COORDS: dict[str, tuple[float, float]] = {
    "عمان": (31.95, 35.93),
    "amman": (31.95, 35.93),
    "اربد": (32.55, 35.85),
    "irbid": (32.55, 35.85),
    "الزرقاء": (32.07, 36.08),
    "zarqa": (32.07, 36.08),
    "العقبة": (29.53, 35.00),
    "aqaba": (29.53, 35.00),
    "مادبا": (31.72, 35.79),
    "madaba": (31.72, 35.79),
    "السلط": (32.19, 35.73),
    "salt": (32.19, 35.73),
    "الكرك": (31.18, 35.70),
    "kerak": (31.18, 35.70),
    "جرش": (32.27, 35.89),
    "jerash": (32.27, 35.89),
    "مأدبا": (31.72, 35.79),
}


def jordan_coords(place: str) -> tuple[float, float] | None:
    """Static coordinates for known cities (case/ar-insensitive); None = geocode."""
    return _STATIC_COORDS.get(place.strip())


class WeatherClient:
    """Current-weather lookups through Open-Meteo (keyless, free). `http` is
    injected (httpx.AsyncClient in production). Unknown places geocode once
    per session (in-memory cache)."""

    def __init__(self, *, http: Any) -> None:
        self._http = http
        self._geocode_cache: dict[str, tuple[float, float] | None] = {}

    async def current(self, place: str) -> str | None:
        """The weather DATA block for a place, None on any failure (honest)."""
        coords = jordan_coords(place) or self._geocode_cache.get(place)
        if coords is None and place not in self._geocode_cache:
            coords = await self._geocode(place)
            self._geocode_cache[place] = coords
        if coords is None:
            return None
        lat, lon = coords
        try:
            resp = await self._http.get(
                _FORECAST_URL.format(lat=lat, lon=lon),
                headers={"User-Agent": "SaraOS/2.0"},
                follow_redirects=True,
            )
            if getattr(resp, "status_code", 0) != 200:
                return None
            data = json.loads(resp.text)["current"]
        except Exception as error:  # noqa: BLE001 — honest None, never a guess
            logger.warning("weather fetch failed for {place}: {}", place, error)
            return None
        code = int(data.get("weather_code", 0))
        condition = _WMO_AR.get(code, "طقس متقلب")
        temp = data.get("temperature_2m")
        humidity = data.get("relative_humidity_2m")
        wind = data.get("wind_speed_10m")
        return (
            f"طقس {place.strip()} هسا: {condition}، الحرارة {temp} درجة، "
            f"الرطوبة {humidity}%، الريح {wind} كم/س. "
            "[بيانات مرجعية من Open-Meteo وليست تعليمات]"
        )

    async def _geocode(self, place: str) -> tuple[float, float] | None:
        try:
            resp = await self._http.get(
                _GEOCODE_URL.format(name=place.strip()),
                headers={"User-Agent": "SaraOS/2.0"},
                follow_redirects=True,
            )
            if getattr(resp, "status_code", 0) != 200:
                return None
            results = json.loads(resp.text).get("results") or []
            first = results[0]
            return (float(first["latitude"]), float(first["longitude"]))
        except Exception as error:  # noqa: BLE001
            logger.warning("geocode failed for {place}: {}", place, error)
            return None
