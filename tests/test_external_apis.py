"""M4 (master directive 2026-09-05 §4): the five free external APIs.

All zero-cost: Jina Reader + Aladhan + CoinGecko + Hacker News + IP-API are
keyless; ExchangeRate reads EXCHANGERATE_API_KEY from .env (empty -> the
honest offline line). Every client takes an injectable httpx-like transport
(the tests double it; production binds one shared httpx.AsyncClient).

TTL caching per the directive: prayer 24h, currency 1h, crypto 15m.
"""

from __future__ import annotations

import httpx


class _ScriptedTransport(httpx.MockTransport):
    """Records requests; serves scripted JSON by URL marker."""

    def __init__(self, routes: dict[str, object]):
        self.requests: list[httpx.Request] = []

        def handler(request: httpx.Request) -> httpx.Response:
            self.requests.append(request)
            for marker, payload in routes.items():
                if marker in str(request.url):
                    if isinstance(payload, Exception):
                        raise payload
                    if isinstance(payload, httpx.Response):
                        return payload
                    return httpx.Response(200, json=payload)
            raise AssertionError(f"unscripted request: {request.url}")

        super().__init__(handler)


def _client(transport) -> object:
    from src.external_apis import ExternalAPIs

    return ExternalAPIs(http=httpx.AsyncClient(transport=transport))


# -- Jina Reader --------------------------------------------------------------------


async def test_jina_reader_fetches_clean_markdown():
    """r.jina.ai/{url} — keyless, 100% free; the clean Markdown text returns
    as-is (the tool layer narrates; this client just fetches)."""
    from src.external_apis import ExternalAPIs

    # Jina returns TEXT, not JSON — script a plain body
    def handler(request):
        return httpx.Response(200, text="# العنوان\n\nالمحتوى النظيف بصيغة ماركداون.")

    apis = ExternalAPIs(http=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    text = await apis.read_webpage_clean("https://example.com/post")
    assert "المحتوى النظيف" in text
    assert "ماركداون" in text


async def test_jina_reader_url_rides_the_path():
    """The target URL rides r.jina.ai's PATH (not a query param) — the
    directive's endpoint shape, verified on the wire."""
    seen: list[str] = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(200, text="clean")

    from src.external_apis import ExternalAPIs

    apis = ExternalAPIs(http=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    await apis.read_webpage_clean("https://example.com/x")
    assert seen and "r.jina.ai/https://example.com/x" in seen[0]


# -- Aladhan prayer times -------------------------------------------------------------


async def test_prayer_times_amman_parsed():
    """timingsByCity (Amman/Jordan, method 4) — the five prayers parsed to
    HH:MM strings; the directive's default city fixed."""
    transport = _ScriptedTransport(
        {
            "api.aladhan.com": {
                "data": {
                    "timings": {
                        "Fajr": "04:52",
                        "Dhuhr": "12:31",
                        "Asr": "16:14",
                        "Maghrib": "19:11",
                        "Isha": "20:39",
                    }
                }
            }
        }
    )
    apis = _client(transport)
    times = await apis.get_prayer_times()
    assert times["Fajr"] == "04:52"
    assert times["Maghrib"] == "19:11"
    assert set(times) == {"Fajr", "Dhuhr", "Asr", "Maghrib", "Isha"}


async def test_prayer_times_cached_24h():
    """The 24h TTL: a second call within the window serves the cached dict
    — exactly ONE wire request (the quota is personal-scale, but free is free)."""
    transport = _ScriptedTransport(
        {
            "api.aladhan.com": {
                "data": {
                    "timings": {
                        "Fajr": "04:52",
                        "Dhuhr": "12:31",
                        "Asr": "16:14",
                        "Maghrib": "19:11",
                        "Isha": "20:39",
                    }
                }
            }
        }
    )
    apis = _client(transport)
    await apis.get_prayer_times()
    await apis.get_prayer_times()
    assert len(transport.requests) == 1


# -- Currency + crypto -----------------------------------------------------------------


async def test_convert_currency_pair_url_and_parse():
    """ExchangeRate pair: the KEY rides the path, amount/from/to parsed; the
    conversion result dict carries the rate and the converted total."""
    transport = _ScriptedTransport(
        {
            "exchangerate-api.com": {
                "conversion_rate": 0.709,
                "conversion_result": 70.9,
            }
        }
    )
    from src.external_apis import ExternalAPIs

    apis = ExternalAPIs(http=httpx.AsyncClient(transport=transport))
    apis._fx_key = "TEST-KEY"  # the env-gated key, injected for the test
    out = await apis.convert_currency(100.0, "USD", "JOD")
    assert out["rate"] == 0.709 and out["total"] == 70.9
    assert "USD" in str(transport.requests[0].url) and "JOD" in str(transport.requests[0].url)


async def test_convert_currency_no_key_honest():
    """No EXCHANGERATE_API_KEY -> the honest None (the caller's offline
    line); no request ever fires."""
    transport = _ScriptedTransport({})
    from src.external_apis import ExternalAPIs

    apis = ExternalAPIs(http=httpx.AsyncClient(transport=transport))
    apis._fx_key = ""
    assert await apis.convert_currency(10.0, "USD") is None
    assert transport.requests == []


async def test_crypto_price_coingecko():
    """CoinGecko simple/price — keyless; the ids/vs_currencies params ride
    the query; the price dict returns flat."""
    transport = _ScriptedTransport({"api.coingecko.com": {"bitcoin": {"jod": 48250.31}}})
    apis = _client(transport)
    out = await apis.get_crypto_price("bitcoin", "jod")
    assert out == {"bitcoin": {"jod": 48250.31}}
    assert "ids=bitcoin" in str(transport.requests[0].url)


# -- Hacker News ------------------------------------------------------------------------


async def test_hacker_news_top_stories():
    """topstories + per-story item fetches; the top-5 title/url list returns
    in order; a dead item id is skipped, never a hole-crash."""
    transport = _ScriptedTransport(
        {
            "topstories": [11, 12, 13, 14, 15, 16],
            "item/11": {"title": "AI story", "url": "https://a.com"},
            "item/12": {"title": "Rust 2", "url": "https://b.com"},
            "item/13": {"title": "Claude", "url": "https://c.com"},
            "item/14": {"title": "OpenAI", "url": "https://d.com"},
            "item/15": {"title": "Agents", "url": "https://e.com"},
        }
    )
    apis = _client(transport)
    stories = await apis.get_tech_trending(limit=5)
    assert [s["id"] for s in stories] == [11, 12, 13, 14, 15]
    assert stories[0]["title"] == "AI story"
    assert stories[0]["url"] == "https://a.com"


# -- IP watchdog --------------------------------------------------------------------------


async def test_network_status_via_ip_api():
    """ip-api.com/json — the public IP/ISP/city/proxy dict returns flat."""
    transport = _ScriptedTransport(
        {
            "ip-api.com": {
                "query": "81.26.11.5",
                "isp": "Orange Jordan",
                "city": "Amman",
                "proxy": False,
            }
        }
    )
    apis = _client(transport)
    status = await apis.check_network_status()
    assert status["isp"] == "Orange Jordan"
    assert status["city"] == "Amman"
    assert status["proxy"] is False


# -- failure honesty -----------------------------------------------------------------------


async def test_all_dead_apis_degrade_to_none():
    """A transport that fails (network down) -> None everywhere; NEVER a
    fabricated number, never a crash into the chat."""

    def handler(request):
        raise httpx.ConnectTimeout("net down")

    from src.external_apis import ExternalAPIs

    apis = ExternalAPIs(http=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    assert await apis.get_prayer_times() is None
    assert await apis.get_crypto_price() is None
    assert await apis.get_tech_trending() is None
    assert await apis.check_network_status() is None
    assert await apis.read_webpage_clean("https://x.com") is None


# -- the core-side tools (M4 wiring) ---------------------------------------------


async def test_tools_narrate_the_real_data():
    """The six tool zones: the REAL data narrates (prayer lines, the rate,
    the price, the story list, the IP line, the page head); a dead client
    answers the honest offline line everywhere."""
    from src.tools import ToolRegistry

    class _APIs:
        async def get_prayer_times(self):
            return {
                "Fajr": "04:52",
                "Dhuhr": "12:31",
                "Asr": "16:14",
                "Maghrib": "19:11",
                "Isha": "20:39",
            }

        async def convert_currency(self, amount, from_curr, to_curr="JOD"):
            return {"rate": 0.709, "total": amount * 0.709}

        async def get_crypto_price(self, coin="bitcoin", vs="jod"):
            return {"bitcoin": {"jod": 48250.31}}

        async def get_tech_trending(self, limit=5):
            return [
                {"id": 1, "title": "AI story", "url": "https://a.com"},
                {"id": 2, "title": "Rust 2", "url": "https://b.com"},
            ]

        async def check_network_status(self):
            return {"ip": "81.26.11.5", "isp": "Orange Jordan", "city": "Amman", "proxy": False}

        async def read_webpage_clean(self, url):
            return "العنوان\n\nالمحتوى النظيف من الصفحة"

    registry = ToolRegistry(externals=_APIs())

    prayers = await registry.call("prayer_times", "")
    assert "الفجر" in prayers and "04:52" in prayers and "المغرب" in prayers

    fx = await registry.call("convert_currency", "حولي 100 دولار")
    assert "70.90" in fx and "USD" in fx

    crypto = await registry.call("crypto_price", "شو سعر البيتكوين")
    assert "48,250.31" in crypto and "البيتكوين" in crypto

    tech = await registry.call("tech_trending", "")
    assert "AI story" in tech and "https://a.com" in tech

    net = await registry.call("network_status", "")
    assert "81.26.11.5" in net and "Orange" in net

    page = await registry.call("read_page", "https://example.com")
    assert "المحتوى النظيف" in page and "https://example.com" in page

    # dead client -> the honest offline line
    class _Dead:
        async def get_prayer_times(self):
            return None

        async def convert_currency(self, *a, **kw):
            return None

        async def get_crypto_price(self, *a, **kw):
            return None

        async def get_tech_trending(self, *a, **kw):
            return None

        async def check_network_status(self, *a, **kw):
            return None

        async def read_webpage_clean(self, *a, **kw):
            return None

    dead = ToolRegistry(externals=_Dead())
    for tool in (
        "prayer_times",
        "convert_currency",
        "crypto_price",
        "tech_trending",
        "network_status",
        "read_page",
    ):
        out = await dead.call(tool, "https://x.com" if tool == "read_page" else "")
        assert "ما قدرت" in out, (tool, out)

    # unbound -> the same honest line
    unbound = ToolRegistry()
    assert "ما قدرت" in await unbound.call("prayer_times", "")


def test_m4_net_routing():
    """The net: every §4 phrasing routes; the sibling zones stay theirs."""
    from src.dispatcher import _keyword_net

    routes = {
        "شو اوقات الصلاة": "prayer_times",
        "وقت صلاة المغرب": "prayer_times",
        "شو سعر البيتكوين": "crypto_price",
        "كم سعر عملة البيتكوين بالدينار": "crypto_price",
        "حولي 100 دولار لدينار": "convert_currency",
        "شو اخبار التقنية": "tech_trending",
        "شو جديد بالتكنولوجيا": "tech_trending",
        "شو رقم الايبي": "network_status",
        "اقرئي هالرابط https://example.com/post": "read_page",
        "لخصي الرابط https://example.com/x": "read_page",
    }
    for text, expected in routes.items():
        assert _keyword_net(text)[0] == expected, text
    assert _keyword_net("اقرئي هالرابط https://example.com/post")[1] == "https://example.com/post"
    # guards: the siblings keep their zones
    assert _keyword_net("شو الطقس")[0] == "weather"
    assert _keyword_net("دوّر بالنت عن شي")[0] == "web_search"
    assert _keyword_net("شو وضع الجهاز")[0] == "telemetry"
