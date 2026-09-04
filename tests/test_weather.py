"""Pass-4 weather (v2.0 §3-ب/1, $0.00-compliant): instant spoken weather answers.
Google's Weather API is a PAID service (violates the $0.00 invariant) — the
directive's INTENT (live weather on demand, voice) is served through Open-Meteo:
free for non-commercial use, NO API KEY, generous limits. The module is pure
given an injected HTTP fetcher + geocode lookup; Jordanian cities get static
coordinates (no geocode round-trip), unknown places geocode once then cache."""

from __future__ import annotations

from src.skills.weather import WeatherClient, jordan_coords

GEOCODE_OK = {
    "https://geocoding-api.open-meteo.com/v1/search?name=Amman&count=1&language=ar": (
        200,
        '{"results": [{"name": "Amman", "latitude": 31.95, "longitude": 35.93}]}',
    )
}

FORECAST_OK = {
    "https://api.open-meteo.com/v1/forecast?latitude=31.95&longitude=35.93&current=temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m": (
        200,
        '{"current": {"temperature_2m": 27.4, "relative_humidity_2m": 40, "weather_code": 0, "wind_speed_10m": 11.2}}',
    ),
}


class FakeHTTP:
    def __init__(self, responses: dict[str, tuple[int, str]]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    async def get(self, url: str, *, headers=None, follow_redirects=True):
        self.calls.append(url)
        status, body = self.responses.get(url, (404, ""))
        return type("Resp", (), {"status_code": status, "text": body})()


def test_jordan_cities_ship_static_coords():
    """Amman + the main cities resolve WITHOUT any geocode call (lateness kill)."""
    amman = jordan_coords("عمان")
    assert amman == (31.95, 35.93)
    assert jordan_coords("amman") == (31.95, 35.93)
    assert jordan_coords("اربد") is not None
    assert jordan_coords("الزرقاء") is not None


async def test_weather_known_city_fetches_forecast_only():
    http = FakeHTTP(dict(FORECAST_OK))
    weather = WeatherClient(http=http)
    block = await weather.current("عمان")
    assert "27" in block  # real number from the API payload, verbatim
    # ONE call only — static coords, no geocode round-trip
    assert len(http.calls) == 1


async def test_weather_unknown_city_geocodes_then_fetches():
    both = dict(GEOCODE_OK)
    both.update(FORECAST_OK)
    http = FakeHTTP(both)
    weather = WeatherClient(http=http)
    block = await weather.current("Amman")  # not a static entry -> geocode path
    assert "27" in block
    assert any("geocoding" in u for u in http.calls)


async def test_weather_failure_is_honest_none():
    http = FakeHTTP({})
    weather = WeatherClient(http=http)
    assert await weather.current("عمان") is None


async def test_weather_geocode_miss_is_none():
    http = FakeHTTP({})
    weather = WeatherClient(http=http)
    assert await weather.current("مدينة وهمية غير موجودة") is None


async def test_weather_block_is_data_wrapped():
    http = FakeHTTP(dict(FORECAST_OK))
    weather = WeatherClient(http=http)
    block = await weather.current("عمان")
    assert "درجة" in block or "temperature" in block.lower() or "طقس" in block


async def test_weather_tool_default_city_and_degrade():
    from src.tools import ToolRegistry

    class _W:
        async def current(self, place):
            assert place == "عمان"
            return "طقس عمان هسا: صافي، الحرارة 27 درجة"

    tools = ToolRegistry(weather=_W())
    answer = await tools.call("weather", "")
    assert "27" in answer

    degraded = ToolRegistry()
    assert "ما قدرت" in await degraded.call("weather", "عمان")


def test_keyword_net_routes_weather_with_city():
    from src.dispatcher import _keyword_net

    tool, arg = _keyword_net("شو الطقس بعمان؟")
    assert tool == "weather"
    assert "عمان" in arg


def test_keyword_net_weather_bare_defaults_empty_arg():
    from src.dispatcher import _keyword_net

    tool, arg = _keyword_net("شو الطقس؟")
    assert tool == "weather"
    assert arg == ""
