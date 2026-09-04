"""Directive §7 (owner 2026-09-04): the exhaustive Google Cloud 41-API suite
with the intelligent $0.00 caching engine. **Gemini API STRICTLY EXCLUDED**
(ADR-16 — Sara's brain runs MiniMax-M3 + Nemotron 550B only; this module
never speaks to Gemini).

THE CACHE ENGINE (this file) is the zero-cost invariant made structural:
- TTL rules per service family (directive-mandated): weather 6h, places 7d,
  custom-search results 24h + a HARD 80 queries/day cap (under the 100 free
  tier), fitness 2 scheduled syncs/day (08:00 + 22:00) + 1h on-demand cache,
  YouTube analytics once daily (23:30).
- Daily budgets (per local day) with explicit maxima; a spent budget returns
  None (= DO NOT CALL) — the honest degrade, never a paid overage.
- QuotaGuard: the Service Usage API circuit breaker — above 90% free-tier
  consumption, high-volume calls refuse; a dead usage API fails CONSERVATIVE
  (cache-only mode), never open.

get_or_mark(key, now) -> (fresh, cached):
  (True, _)  = cache miss inside budget -> the caller MAY call the API now
  (False, True) = cached copy serves, zero API cost
  (None, False) = budget/window exhausted -> the caller must NOT call
Ponytail ceiling: in-memory dict + a wall-clock — a personal assistant does
not need redis; persist only if the bot restarts matter for multi-hour TTLs
(a restart costs at most one refresh per service — acceptable)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from loguru import logger

AMMAN = ZoneInfo("Asia/Amman")

TTL_RULES: dict[str, timedelta] = {
    "weather": timedelta(hours=6),
    "places": timedelta(days=7),
    "custom_search": timedelta(hours=24),
    "fitness": timedelta(hours=1),  # on-demand cache; syncs gated separately
    "youtube_analytics": timedelta(days=1),
    "youtube": timedelta(hours=1),  # plain search: modest cache, cheap quota
    "gmail": timedelta(seconds=30),  # near-realtime reads, low quota anyway
    "default": timedelta(minutes=30),
}


@dataclass
class CacheBudget:
    """Per-local-day call budgets — the $0.00 invariant as numbers."""

    weather_day_max: int = 4  # explicit-demand refreshes (directive)
    custom_search_day_max: int = 80  # strictly under the 100 free/day
    fitness_sync_hours: tuple[int, int] = (8, 22)  # the two daily syncs


@dataclass
class _Entry:
    family: str
    cached_at: datetime
    value: Any = None


class CacheEngine:
    """TTL + budget gate for one service family call. Pure given `now` — the
    caller injects the clock (tests) or uses the real Amman wall."""

    def __init__(self, *, budget: CacheBudget | None = None) -> None:
        self.budget = budget or CacheBudget()
        self._entries: dict[tuple, _Entry] = {}
        self._daily_counts: dict[tuple[str, str], int] = {}

    def get_or_mark(
        self, key: tuple, *, now: datetime, value: Any = None
    ) -> tuple[bool | None, bool]:
        """The one gate every cached API call passes through. See module doc."""
        family = key[0]
        ttl = TTL_RULES.get(family, TTL_RULES["default"])
        day = now.astimezone(AMMAN).date().isoformat()
        count_key = (family, day)

        # fitness: fresh syncs ONLY in the 08:00/22:00 windows; outside them,
        # on-demand reads serve the 1h cache and never sync
        if family == "fitness":
            hour = now.astimezone(AMMAN).hour
            if hour not in self.budget.fitness_sync_hours:
                entry = self._entries.get(key)
                if entry and now - entry.cached_at < ttl:
                    return (False, True)  # cached copy serves
                return (None, False)  # no sync outside windows — honest no
            entry = self._entries.get(key)
            if entry and now - entry.cached_at < ttl:
                return (False, True)
            self._daily_counts[count_key] = self._daily_counts.get(count_key, 0) + 1
            self._entries[key] = _Entry(family, now, value)
            return (True, False)

        # day-capped families: weather (explicit demand), custom_search (hard 80)
        if family in ("weather", "custom_search"):
            cap = (
                self.budget.weather_day_max
                if family == "weather"
                else self.budget.custom_search_day_max
            )
            if self._daily_counts.get(count_key, 0) >= cap:
                # a cached copy may still serve — zero-cost reads always pass
                entry = self._entries.get(key)
                if entry and now - entry.cached_at < ttl:
                    return (False, True)
                return (None, False)  # budget spent: DO NOT CALL today
            entry = self._entries.get(key)
            if entry and now - entry.cached_at < ttl:
                return (False, True)  # TTL hit: free
            self._daily_counts[count_key] = self._daily_counts.get(count_key, 0) + 1
            self._entries[key] = _Entry(family, now, value)
            return (True, False)

        # generic TTL families
        entry = self._entries.get(key)
        if entry and now - entry.cached_at < ttl:
            return (False, True)
        self._entries[key] = _Entry(family, now, value)
        return (True, False)

    def store(self, key: tuple, value: Any, *, now: datetime) -> None:
        """The caller lands the fetched value into the just-marked entry."""
        entry = self._entries.get(key)
        if entry is not None:
            entry.value = value
            entry.cached_at = now

    def peek(self, key: tuple) -> Any | None:
        entry = self._entries.get(key)
        return entry.value if entry is not None else None

    def remaining_today(self, family: str, *, now: datetime) -> int:
        day = now.astimezone(AMMAN).date().isoformat()
        used = self._daily_counts.get((family, day), 0)
        if family == "weather":
            return max(0, self.budget.weather_day_max - used)
        if family == "custom_search":
            return max(0, self.budget.custom_search_day_max - used)
        return 0


class QuotaGuard:
    """The Service Usage API circuit breaker (directive §7 Cluster 5): before
    any high-volume call, check the consumed free-tier percentage; >90% blocks
    (degrade gracefully). A dead usage API fails CONSERVATIVE (cache-only)."""

    def __init__(self, *, usage: Any, threshold_pct: float = 90.0) -> None:
        self._usage = usage
        self._threshold = threshold_pct

    async def allow(self, service: str) -> bool:
        try:
            consumed = await self._usage.free_tier_usage_percent()
        except Exception as error:  # noqa: BLE001 — conservative fail
            logger.warning("quota check failed for {} — cache-only mode: {}", service, error)
            return False
        if consumed > self._threshold:
            logger.warning(
                "quota breaker OPEN for {}: {}% of the free tier consumed",
                service,
                consumed,
            )
            return False
        return True


# ===================== The 41-API adapter registry (directive §7) =====================
# Gemini API STRICTLY EXCLUDED (ADR-16). Every adapter = ONE thin typed client
# over the same GoogleSession-style transport, named for its enabled service,
# carrying its free-tier ceiling + cache family (the $0.00 invariant structural).
# Clusters follow the directive: 1 Workspace (Gmail/MCP/Calendar/Tasks/Drive/
# MCP/People) · 2 Health&Gaming (Fitness/Health/PlayGames/PlayDev) · 3 Media&
# Search (YT Data/Analytics/Reporting/CustomSearch/MapsGrounding/MapsSDK/
# Places/Weather) · 4 BigQuery&Storage (14 always-free data services) ·
# 5 Observability&Quota (8). Sum = 41, Gemini absent.


@dataclass
class Adapter:
    name: str
    cluster: int
    base_url: str
    cache_family: str
    free_tier_note: str

    async def call(self, http: Any, op: str, **kw) -> Any:
        """One transport call: GET {base_url}/{op} with the params."""
        resp = await http.request("GET", f"{self.base_url}/{op}", params=kw)
        return resp.json()


API_REGISTRY: tuple[Adapter, ...] = (
    # -- Cluster 1: Workspace & Communications (7)
    Adapter(
        "gmail",
        1,
        "https://gmail.googleapis.com/gmail/v1/users/me",
        "gmail",
        "free 1B quota units/day",
    ),
    Adapter(
        "gmail_mcp",
        1,
        "https://gmail.googleapis.com/gmail/v1/mcp",
        "gmail",
        "rides the Gmail free quota — the structured-tool surface",
    ),
    Adapter(
        "google_calendar",
        1,
        "https://www.googleapis.com/calendar/v3",
        "default",
        "free calendar read/write",
    ),
    Adapter(
        "google_tasks",
        1,
        "https://tasks.googleapis.com/tasks/v1",
        "default",
        "free tasks read/write",
    ),
    Adapter(
        "google_drive",
        1,
        "https://www.googleapis.com/drive/v3",
        "default",
        "free 15GB storage, read/search",
    ),
    Adapter(
        "drive_mcp",
        1,
        "https://www.googleapis.com/drive/v3/mcp",
        "default",
        "rides the Drive free tier — the agent-tool surface",
    ),
    Adapter(
        "people",
        1,
        "https://people.googleapis.com/v1",
        "default",
        "free contact read (1000 units/min)",
    ),
    # -- Cluster 2: Health, Fitness & Gaming (4)
    Adapter(
        "fitness",
        2,
        "https://www.googleapis.com/fitness/v1",
        "fitness",
        "free fitness read; 2 syncs/day (08:00+22:00) + 1h cache",
    ),
    Adapter(
        "google_health",
        2,
        "https://healthcare.googleapis.com/v1",
        "default",
        "free healthcare read (sleep cycles)",
    ),
    Adapter(
        "play_games",
        2,
        "https://www.googleapis.com/games/v1",
        "default",
        "free games services read",
    ),
    Adapter(
        "play_android_dev",
        2,
        "https://www.googleapis.com/androidpublisher/v3",
        "default",
        "free developer API read",
    ),
    # -- Cluster 3: Media, YouTube & Search (8)
    Adapter(
        "youtube_data",
        3,
        "https://www.googleapis.com/youtube/v3",
        "youtube",
        "free 10k units/day (search=100)",
    ),
    Adapter(
        "youtube_analytics",
        3,
        "https://youtubeanalytics.googleapis.com/v2",
        "youtube_analytics",
        "free analytics read; daily sync 23:30",
    ),
    Adapter(
        "youtube_reporting",
        3,
        "https://youtubereporting.googleapis.com/v1",
        "youtube_analytics",
        "free bulk reports; daily 23:30",
    ),
    Adapter(
        "custom_search",
        3,
        "https://customsearch.googleapis.com/customsearch/v1",
        "custom_search",
        "free 100/day — HARD-CAPPED at 80 by the engine",
    ),
    Adapter(
        "maps_grounding",
        3,
        "https://mapsgrounding.googleapis.com/v1",
        "places",
        "free-tier grounding; cached with places (7d)",
    ),
    Adapter(
        "maps_sdk_android",
        3,
        "https://maps.googleapis.com/maps/api",
        "places",
        "static-map URL formation — zero API calls",
    ),
    Adapter(
        "places",
        3,
        "https://places.googleapis.com/v1",
        "places",
        "free-tier place search; 7-day cache",
    ),
    Adapter(
        "weather_google",
        3,
        "https://weather.googleapis.com/v1",
        "weather",
        "free-tier lookups; 6h TTL + 4/day cap (Open-Meteo is the active keyless lane)",
    ),
    # -- Cluster 4: BigQuery & Cloud Storage (14) — the always-free data vault
    Adapter(
        "bigquery",
        4,
        "https://bigquery.googleapis.com/bigquery/v2",
        "default",
        "free 1TB query/month + 10GB storage",
    ),
    Adapter(
        "bigquery_storage",
        4,
        "https://bigquerystorage.googleapis.com/v1",
        "default",
        "free 10GB streamed storage",
    ),
    Adapter(
        "bigquery_connection",
        4,
        "https://bigqueryconnection.googleapis.com/v1",
        "default",
        "free connection management",
    ),
    Adapter(
        "bigquery_data_policy",
        4,
        "https://bigquerydatapolicy.googleapis.com/v1",
        "default",
        "free policy management",
    ),
    Adapter(
        "bigquery_data_transfer",
        4,
        "https://bigquerydatatransfer.googleapis.com/v1",
        "default",
        "free transfer scheduling (1000 runs/day)",
    ),
    Adapter(
        "bigquery_migration",
        4,
        "https://bigquerymigration.googleapis.com/v2",
        "default",
        "free migration validation",
    ),
    Adapter(
        "bigquery_reservation",
        4,
        "https://bigqueryreservation.googleapis.com/v1",
        "default",
        "free shared-slot verification",
    ),
    Adapter(
        "cloud_storage",
        4,
        "https://storage.googleapis.com/storage/v1",
        "default",
        "free 5GB object storage — encrypted backups",
    ),
    Adapter(
        "cloud_storage_api",
        4,
        "https://storage.googleapis.com/storage/v1",
        "default",
        "same free 5GB — the upload surface",
    ),
    Adapter(
        "gcs_json",
        4,
        "https://storage.googleapis.com/storage/v1",
        "default",
        "the JSON REST interface over the free 5GB",
    ),
    Adapter(
        "datastore",
        4,
        "https://datastore.googleapis.com/v1",
        "default",
        "free 1GB document store — agent states",
    ),
    Adapter(
        "dataplex",
        4,
        "https://dataplex.googleapis.com/v1",
        "default",
        "free metadata governance tier",
    ),
    Adapter(
        "dataform",
        4,
        "https://dataform.googleapis.com/v1beta2",
        "default",
        "free SQL workflow tier",
    ),
    Adapter(
        "cloud_sql",
        4,
        "https://sqladmin.googleapis.com/v1beta4",
        "default",
        "admin-verify only; data stays LOCAL SQLite ($0.00)",
    ),
    # -- Cluster 5: Observability, Quota Guard & System Management (8)
    Adapter(
        "service_usage",
        5,
        "https://serviceusage.googleapis.com/v1",
        "default",
        "free usage inspection — THE quota circuit breaker",
    ),
    Adapter(
        "service_management",
        5,
        "https://servicemanagement.googleapis.com/v1",
        "default",
        "free service config inspection",
    ),
    Adapter(
        "cloud_logging",
        5,
        "https://logging.googleapis.com/v2",
        "default",
        "free 50GB/month log ingestion",
    ),
    Adapter(
        "cloud_monitoring",
        5,
        "https://monitoring.googleapis.com/v3",
        "default",
        "free metrics (5MB writes/day)",
    ),
    Adapter(
        "cloud_trace",
        5,
        "https://cloudtrace.googleapis.com/v2",
        "default",
        "free 2.5M spans/month tracing",
    ),
    Adapter(
        "telemetry_api",
        5,
        "https://telemetry.googleapis.com/v1",
        "default",
        "free telemetry aggregation — unifies bridge/server health",
    ),
    Adapter(
        "analytics_hub",
        5,
        "https://analyticshub.googleapis.com/v1",
        "default",
        "free data-exchange exploration",
    ),
    Adapter(
        "core_sdk",
        5,
        "https://www.googleapis.com",
        "default",
        "the central OAuth transport — no per-call cost",
    ),
    # 41 total. Gemini API deliberately ABSENT (ADR-16 ruling).
)


def register_adapters(http: Any) -> list[Adapter]:
    """The 41 typed adapters over one transport (the GoogleSession in prod)."""
    _ = http  # transport binding is per-call (Adapter.call(http, op)); the
    # registry itself is transport-agnostic so any session plugs in
    return list(API_REGISTRY)


class GoogleCloudSuite:
    """The orchestrating facade: adapters + the cache engine + the quota
    breaker, one surface for ToolRegistry. $0.00 is the cache-first order:
    EVERY call passes get_or_mark BEFORE any wire request."""

    def __init__(self, *, http: Any, usage: Any, engine: CacheEngine | None = None) -> None:
        self._http = http
        self._engine = engine or CacheEngine()
        self._quota = QuotaGuard(usage=usage)
        self._by_name = {a.name: a for a in API_REGISTRY}

    def adapter(self, name: str) -> Adapter:
        return self._by_name[name]

    async def call(self, name: str, op: str, **kw) -> Any:
        """Cache-gated adapter call: fresh=True fetches; cached serves; the
        budget spent or the breaker open -> None (the honest no-call)."""
        adapter = self._by_name[name]
        key = (adapter.cache_family, f"{name}:{op}:{kw}")
        now = datetime.now(AMMAN)
        fresh, cached = self._engine.get_or_mark(key, now=now)
        if cached:
            return self._engine.peek(key)
        if not fresh:  # None (budget/window) — the honest degrade
            return None
        if not await self._quota.allow(name):
            return None  # breaker open — cache-only mode
        result = await adapter.call(self._http, op, **kw)
        self._engine.store(key, result, now=now)
        return result

    async def custom_search(self, query: str) -> Any:
        """The directive's capped lane: 80/day hard, 24h result cache."""
        return await self.call("custom_search", "search", q=query)
