"""Directive §7 (owner 2026-09-04): the exhaustive Google Cloud suite with the
intelligent $0.00 caching engine. Gemini API STRICTLY EXCLUDED (ADR-16 — the
brain runs MiniMax-M3/Nemotron only).

The engine's contracts (offline-mock tested):
- TTL cache: weather 6h (max 4 refreshes/day), places 7d, custom-search
  results 24h + a hard 80 queries/day cap (under the 100 free/day),
  fitness 2 syncs/day (08:00/22:00) + 1h on-demand cache, YouTube analytics
  daily at 23:30
- Service Usage API = the quota circuit breaker: NO high-volume call proceeds
  when >90% of the free tier is consumed — degrade gracefully, stay free
- every adapter is a thin typed client over the same GoogleSession transport;
  results are DATA"""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from src.google_cloud_suite import (
    TTL_RULES,
    CacheBudget,
    CacheEngine,
    QuotaGuard,
)

AMMAN = ZoneInfo("Asia/Amman")


def _at(hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 9, 4, hour, minute, tzinfo=AMMAN)


# -- TTL rules ----------------------------------------------------------------


def test_ttl_rules_match_the_directive():
    assert TTL_RULES["weather"] == timedelta(hours=6)
    assert TTL_RULES["places"] == timedelta(days=7)
    assert TTL_RULES["custom_search"] == timedelta(hours=24)
    assert TTL_RULES["fitness"] == timedelta(hours=1)
    assert TTL_RULES["youtube_analytics"] == timedelta(days=1)


def test_weather_refresh_capped_at_4_per_day():
    """4 explicit demands/day, each a DISTINCT place (each demand costs a call;
    the TTL only dedupes repeats of the same place within 6h)."""
    engine = CacheEngine(budget=CacheBudget(weather_day_max=4))
    for place in ("عمان", "اربد", "الزرقاء", "العقبة", "مادبا", "السلط"):
        fresh, _cached = engine.get_or_mark(("weather", place), now=_at(8))
        assert fresh in (True, None)
    assert engine.remaining_today("weather", now=_at(8)) == 0  # capped at 4
    # the 5th distinct demand DEGRADES (None = do-not-call) — $0.00 structural
    fresh_fifth, _ = engine.get_or_mark(("weather", "الطفيلة"), now=_at(8))
    assert fresh_fifth is None
    # within the 6h TTL the fetched places re-serve FREE (zero-cost reads);
    # past the TTL with the budget spent, the answer is the honest no-call
    _, cached_hit = engine.get_or_mark(("weather", "عمان"), now=_at(13))
    assert cached_hit is True
    _, late = engine.get_or_mark(("weather", "عمان"), now=_at(20))  # TTL expired
    assert late is False  # no budget for a refresh — honest no


def test_cache_hit_within_ttl_saves_the_call():
    engine = CacheEngine()
    key = ("places", "كافيه عمان")
    fresh1, _ = engine.get_or_mark(key, now=_at(10))
    fresh2, _ = engine.get_or_mark(key, now=_at(12))  # 2h later, TTL 7d
    assert fresh1 is True and fresh2 is False  # second is served from cache


def test_cache_expiry_after_ttl_refetches():
    engine = CacheEngine()
    key = ("custom_search", "أسعار الرام")
    engine.get_or_mark(key, now=_at(10))
    fresh_later, _ = engine.get_or_mark(key, now=_at(11))  # 1h < 24h TTL
    assert fresh_later is False
    fresh_next_day, _ = engine.get_or_mark(key, now=_at(10) + timedelta(days=1, minutes=1))
    assert fresh_next_day is True  # TTL expired -> refetch


def test_custom_search_hard_cap_80_per_day():
    """Strictly below the 100/day free tier: the 81st query of the day REFUSES
    (degrades honestly) — the $0.00 invariant is structural, not a promise."""
    engine = CacheEngine(budget=CacheBudget(custom_search_day_max=80))
    for i in range(80):
        engine.get_or_mark(("custom_search", f"q{i}"), now=_at(9) + timedelta(seconds=i))
    fresh, _ = engine.get_or_mark(("custom_search", "q-new"), now=_at(10))
    assert fresh is None  # None = budget exhausted: the caller must NOT call
    # a cached query still serves (no API hit needed)
    _, cached = engine.get_or_mark(("custom_search", "q0"), now=_at(10))
    assert cached is True


def test_fitness_sync_windows():
    """Fitness data syncs exactly twice daily (08:00 + 22:00); on-demand reads
    outside those windows serve the 1h cache and NEVER trigger a fresh sync."""
    engine = CacheEngine(budget=CacheBudget(fitness_sync_hours=(8, 22)))
    fresh_morning, _ = engine.get_or_mark(("fitness", "daily"), now=_at(8))
    assert fresh_morning is True  # the 08:00 sync window
    fresh_afternoon, _ = engine.get_or_mark(("fitness", "daily"), now=_at(16))
    assert fresh_afternoon is None  # outside windows: cached only, no sync


# -- quota circuit breaker ------------------------------------------------------


class FakeUsageAPI:
    def __init__(self, consumed_percent: float) -> None:
        self.consumed = consumed_percent
        self.calls = 0

    async def free_tier_usage_percent(self) -> float:
        self.calls += 1
        return self.consumed


async def test_quota_guard_blocks_above_90_percent():
    guard = QuotaGuard(usage=FakeUsageAPI(95.0))
    assert await guard.allow("youtube_data") is False  # degrade, stay free
    assert await guard.allow("custom_search") is False


async def test_quota_guard_allows_under_90_percent():
    guard = QuotaGuard(usage=FakeUsageAPI(60.0))
    assert await guard.allow("youtube_data") is True


async def test_quota_guard_usage_api_failure_fails_conservative():
    """A dead Service Usage API never blocks the flow — it fails to the
    cache-only mode (no fresh heavy calls, but cached data still serves)."""

    class Dead:
        async def free_tier_usage_percent(self):
            raise RuntimeError("service usage down")

    guard = QuotaGuard(usage=Dead())
    assert await guard.allow("heavy_call") is False  # conservative: cached only


# -- the 41-API adapter registry ------------------------------------------------


class _AdaptResp:
    def __init__(self, status_code: int, body) -> None:
        self.status_code = status_code
        self._body = body

    def json(self):
        return self._body


class FakeHTTPAdapter:
    """One transport double for every adapter test: records calls, replies
    deterministic JSON. ZERO network — the suite is offline by contract."""

    def __init__(self, responses: dict | None = None, status: int = 200) -> None:
        self.responses = responses or {}
        self.status = status
        self.calls: list[tuple[str, dict]] = []

    async def request(self, method: str, url: str, **kw):
        self.calls.append((url, kw.get("params") or kw.get("json") or {}))
        body = self.responses.get(url, {})
        return _AdaptResp(self.status, body)


def test_41_api_registry_complete_gemini_excluded():
    """The directive's 41 services, Gemini ABSENT — the suite is the whole
    enabled surface minus the retired brain lane (ADR-16)."""
    from src.google_cloud_suite import API_REGISTRY, register_adapters

    adapters = register_adapters(FakeHTTPAdapter())
    names = {a.name for a in adapters}
    assert len(API_REGISTRY) == 41
    assert len(names) == 41
    assert all("gemini" not in n for n in names), "Gemini is STRICTLY EXCLUDED"
    # cluster spot-checks: the directive's named services exist as adapters
    for expected in (
        "gmail",
        "google_calendar",
        "google_tasks",
        "google_drive",
        "people",
        "fitness",
        "youtube_data",
        "youtube_analytics",
        "youtube_reporting",
        "custom_search",
        "places",
        "maps_grounding",
        "weather_google",
        "bigquery",
        "bigquery_storage",
        "cloud_storage",
        "datastore",
        "service_usage",
        "cloud_logging",
        "cloud_monitoring",
        "cloud_trace",
        "telemetry_api",
        "analytics_hub",
        "core_sdk",
    ):
        assert expected in names, f"missing adapter: {expected}"


def test_every_adapter_declares_free_tier_shape():
    """$0.00 is structural: each adapter carries its free-tier ceiling + a
    cache family — an adapter without both cannot be admitted."""
    from src.google_cloud_suite import register_adapters

    for adapter in register_adapters(FakeHTTPAdapter()):
        assert adapter.free_tier_note, f"{adapter.name}: no free-tier note"
        assert adapter.cache_family, f"{adapter.name}: no cache family"
        assert adapter.cache_family in (
            {
                "weather",
                "places",
                "custom_search",
                "fitness",
                "youtube_analytics",
                "youtube",
                "gmail",
                "default",
            }
        ), f"{adapter.name}: unknown cache family"


async def test_workspace_adapter_reads_gmail_shape():
    """Cluster 1 sample: the Gmail adapter reads unread threads through the
    same transport (the live Gmail code stays authoritative; this adapter is
    the registered surface for the 41-API contract)."""
    from src.google_cloud_suite import register_adapters

    http = FakeHTTPAdapter(
        responses={
            "https://gmail.googleapis.com/gmail/v1/users/me/threads?unread": {
                "threads": [{"id": "t1", "snippet": "مرحبا"}]
            }
        }
    )
    adapters = {a.name: a for a in register_adapters(http)}
    result = await adapters["gmail"].call(http, "threads?unread")
    assert result and "t1" in str(result)


async def test_custom_search_adapter_respects_cache_and_cap():
    """The adapter MUST route through the CacheEngine: the second identical
    query is served from cache (ONE wire call), the cap refuses fresh calls."""
    from src.google_cloud_suite import GoogleCloudSuite

    http = FakeHTTPAdapter(
        responses={
            "https://customsearch.googleapis.com/customsearch/v1/search": {
                "items": [{"title": "نتيجة"}]
            }
        }
    )
    suite = GoogleCloudSuite(http=http, usage=FakeUsageAPI(10.0))
    q1 = await suite.custom_search("أسعار الرام")
    q2 = await suite.custom_search("أسعار الرام")  # cache hit
    assert q1 == q2 and q1
    wire_calls = [u for u, _ in http.calls]
    assert wire_calls.count("https://customsearch.googleapis.com/customsearch/v1/search") == 1


async def test_bigquery_family_adapters_present():
    """Cluster 4: the BigQuery family (6 APIs + storage trio) registers as
    typed adapters with the free-tier notes (1TB query/mo, 10GB storage)."""
    from src.google_cloud_suite import register_adapters

    names = {a.name: a for a in register_adapters(FakeHTTPAdapter())}
    for bq in (
        "bigquery",
        "bigquery_storage",
        "bigquery_connection",
        "bigquery_data_policy",
        "bigquery_data_transfer",
        "bigquery_migration",
        "bigquery_reservation",
        "cloud_storage",
        "cloud_storage_api",
        "gcs_json",
        "datastore",
        "dataplex",
        "dataform",
        "cloud_sql",
    ):
        assert bq in names, f"missing cluster-4 adapter: {bq}"
        note = names[bq].free_tier_note.lower()
        assert "free" in note or "$0.00" in note


async def test_observability_cluster_registers():
    """Cluster 5: quota guard + observability + management surfaces."""
    from src.google_cloud_suite import register_adapters

    names = {a.name for a in register_adapters(FakeHTTPAdapter())}
    for obs in (
        "service_usage",
        "service_management",
        "cloud_logging",
        "cloud_monitoring",
        "cloud_trace",
        "telemetry_api",
        "analytics_hub",
        "core_sdk",
    ):
        assert obs in names, f"missing cluster-5 adapter: {obs}"
