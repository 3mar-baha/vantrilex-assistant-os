"""Phase B (2026-09-06): GoogleCloudClient — the B4-B8 backend.

Doubles the GoogleSession transport + CacheEngine + QuotaGuard so every surface
is covered offline. The client must degrade to None on an unconfigured session,
on a cache-gate miss, and on a dead adapter — never a fabricated number.
"""

from __future__ import annotations

from datetime import UTC, datetime

from src.google_cloud_client import AMMAN_LAT, AMMAN_LON, GoogleCloudClient
from src.google_cloud_suite import CacheEngine


class _Resp:
    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


class _Session:
    """A GoogleSession-shaped fake: request(method, url, params) -> response."""

    def __init__(self, handler, *, fail: bool = False):
        self._handler = handler
        self.fail = fail
        self.calls: list[tuple] = []

    async def request(self, method, url, params=None, **kw):
        self.calls.append((method, url, params, kw))
        if self.fail:
            raise RuntimeError("upstream down")
        return self._handler(method, url, params, kw)


class _Quota:
    """QuotaGuard-shaped fake: allow() returns a configurable boolean."""

    def __init__(self, allowed: bool = True):
        self.allowed = allowed

    async def allow(self, service: str) -> bool:
        return self.allowed


def _cache() -> CacheEngine:
    return CacheEngine()


def _client(session, *, cache=None, quota=None, cse_key="k", cse_cx="c", places_key="p", now_fn=None):
    return GoogleCloudClient(
        session=session,
        cache=cache or _cache(),
        quota=quota or _Quota(True),
        custom_search_key=cse_key,
        custom_search_cx=cse_cx,
        places_key=places_key,
        now_fn=now_fn,
    )


# --- B4 places ---------------------------------------------------------------


async def test_places_happy_path_formats_results():
    def handler(method, url, params, kw):
        return _Resp({"places": [{"name": "مقهى كرك", "rating": 4.5, "address": "شارع الرينبو"}]})

    client = _client(_Session(handler))
    out = await client.places("كافيه")
    assert out and out[0]["name"] == "مقهى كرك"
    assert client._session.calls  # the adapter was invoked


async def test_places_without_session_is_none():
    assert await GoogleCloudClient().places("كافيه") is None


async def test_places_without_key_is_none():
    client = GoogleCloudClient(session=_Session(lambda *a: _Resp({})), places_key="")
    assert await client.places("كافيه") is None


async def test_places_dead_adapter_degrades():
    client = GoogleCloudClient(session=_Session(lambda *a: _Resp({}), fail=True), places_key="p")
    assert await client.places("كافيه") is None


# --- B5 deep_search ----------------------------------------------------------


async def test_deep_search_returns_items():
    def handler(method, url, params, kw):
        return _Resp({"items": [{"title": "عنوان", "link": "https://x"}]})

    client = _client(_Session(handler))
    out = await client.deep_search("شرح الفيزياء")
    assert out and out["items"][0]["title"] == "عنوان"


async def test_deep_search_no_key_is_none():
    client = GoogleCloudClient(session=_Session(lambda *a: _Resp({})), custom_search_key="", custom_search_cx="")
    assert await client.deep_search("x") is None


async def test_deep_search_quota_gate_returns_none():
    # A full cache budget must yield None (DO-NOT-CALL) rather than a call.
    client = _client(_Session(lambda *a: _Resp({"items": []})), cse_key="k", cse_cx="c")
    # Force the daily count to the cap by marking many keys of the same family.
    cache = client._cache
    now = datetime.now(UTC)
    for i in range(100):
        cache.get_or_mark(("custom_search", "web", f"q{i}"), now=now)
    assert await client.deep_search("drained") is None


# --- B6 fitness --------------------------------------------------------------


async def test_fitness_returns_raw_readout():
    def handler(method, url, params, kw):
        return _Resp({"dataSources": [{"id": "s1"}]})

    # Fitness syncs at 08:00/22:00 AMMAN time. Amman is UTC+3 (DST abolished),
    # so 08:00 Amman == 05:00 UTC. Inject that so the cache gate passes.
    at_amman_08_utc = datetime(2026, 9, 6, 5, 0, tzinfo=UTC)
    client = _client(_Session(handler), now_fn=lambda: at_amman_08_utc)
    out = await client.fitness()
    assert out and out.get("dataSources")


async def test_fitness_without_session_is_none():
    assert await GoogleCloudClient().fitness() is None


# --- B7 analytics ------------------------------------------------------------


async def test_analytics_degrades_honestly():
    """sqlite_life_analytics doesn't exist yet — analytics must return None
    (the honest offline line), never crash."""
    client = GoogleCloudClient()
    out = await client.analytics("وقت الشاشة")
    assert out is None


async def test_analytics_wraps_rows(monkeypatch):
    """When a data source IS provided, analytics wraps the rows dict."""
    # Patch the module-level lookup so the method finds a deterministic stub.
    client = GoogleCloudClient()
    rows = [("الكروم", 210)]
    monkeypatch.setitem(
        __import__("sys").modules["src.vault"].__dict__,
        "sqlite_life_analytics",
        lambda q: rows,
    )
    out = await client.analytics("وقت الشاشة")
    assert out and out["rows"] == rows


# --- B7 cloud_backup ---------------------------------------------------------


async def test_cloud_backup_without_session_is_false():
    assert await GoogleCloudClient().cloud_backup(b"x") is False


# --- B8 quota_safety ---------------------------------------------------------


async def test_quota_report_safe():
    client = GoogleCloudClient(session=_Session(lambda *a: _Resp({})), quota=_Quota(True))
    out = await client.quota_report()
    assert out and out["services"][0]["pct"] == 12


async def test_quota_report_unsafe():
    client = GoogleCloudClient(session=_Session(lambda *a: _Resp({})), quota=_Quota(False))
    out = await client.quota_report()
    assert out and out["services"][0]["pct"] == 95


async def test_quota_report_without_session_is_none():
    assert await GoogleCloudClient().quota_report() is None


# --- coordinate constants ----------------------------------------------------


def test_amman_anchor_is_exact():
    assert AMMAN_LAT == 31.9539 and AMMAN_LON == 35.9106
