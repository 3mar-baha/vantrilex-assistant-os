---
tags: [security]
---

# API Wiring & Usage Audit — Vantrilex Assistant OS (2026-09-16)

> Method: static mapping of every external endpoint in `src/` to its handler,
> env-key presence check (names only — **no secret values are recorded here**),
> and a non-destructive smoke pass (Telegram `getMe`, local gateway probe,
> offline OAuth-cache decrypt). No quota was spent: LLM/free-pool endpoints
> were presence-checked only, never called.
> Statuses: **LIVE** (credential set + probed) · **WIRED & READY**
> (handlers + unit tests green, awaiting live secret or host) ·
> **STAGED** (code behind a credential gate) · **REGISTERED** (endpoint in
> the B1-B8 registry, no calling adapter yet).

## A. Core LLM & brain (100% via OmniRoute — zero direct vendor SDKs)

| Service | Module | Role | Key | Status |
|---|---|---|---|---|
| OmniRoute gateway | `src/gateway.py` (3-tier chains, 4 s guillotine, 15 min quarantine) | Sole LLM transport; free-tier guard (`PaidModelBlockedError`) | `OMNIROUTE_BASE_URL`, `OMNIROUTE_API_KEY` | **WIRED & READY** (gateway down at audit → DEGRADED) |
| Groq (gpt-oss-120b) | FAST/MEDIUM tiers + fallbacks | Sara's voice + worker lanes | `GROQ_API_KEY` | **WIRED & READY** (key set) |
| OpenRouter `:free` pool | HEAVY tier + Fish speech transport | Deep reasoning + voice synthesis transport | `OPENROUTER_API_KEY` | **WIRED & READY** (key set) |
| Anthropic Claude (direct) | — | None: no `anthropic` SDK import anywhere; Claude-class reasoning arrives only via OmniRoute-routed pools | — | **Not wired by design** |
| Google Gemini (direct) | — | None: retired 2026-08-30 (Google 403); no `google-generativeai` import | — | **Not wired by design** |
| DeepSeek / SiliconFlow | — | No direct integration; available only if owner adds OmniRoute pools | — | **Optional** |

## B. Google Workspace & productivity (OAuth, `src/google_auth.py` + `src/google_suite.py`)

| Service | Module | Role | Key | Status |
|---|---|---|---|---|
| Gmail API | `src/gmail.py` (watch/poll/digest/triage) | Inbox monitoring, triage, digests | OAuth client + sealed token | **WIRED & READY** (client JSON + decryptable token cache; `GMAIL_PUBSUB_TOPIC` empty → polling only) |
| Calendar API | `src/google_suite.py` + `src/daily_brief.py` | Scheduling, conflict logic, 24 h agenda | Same OAuth | **WIRED & READY** |
| Drive API (+ MCP shape) | `src/google_suite.py` (`drive/v3`, `drive/v3/mcp` registered) | File search/retrieval | Same OAuth | **WIRED & READY** |
| Tasks API | `src/google_suite.py` (`tasks/v1`) | Task tracking, reminders, todo sync | Same OAuth | **WIRED & READY** |
| People API | `src/google_suite.py` (`people:searchContacts`) | Contact discovery, profile lookup | Same OAuth | **WIRED & READY** |
| Gmail/Drive MCP endpoints | `src/google_cloud_suite.py` registry | MCP-shaped mirrors of the above | Same OAuth | **REGISTERED** |

## C. Search, media & geo

| Service | Module | Role | Key | Status |
|---|---|---|---|---|
| Web grounding (keyless) | `src/skills/web_intel.py` (DDG html) | Live search + page reads, zero key | — | **LIVE-capable** (needs network only) |
| Custom Search API | `src/google_cloud_client.py` (`customsearch/v1`, called adapter) | Quota-backed search upgrade | Google Cloud project | **WIRED & READY** (adapter + cache; key via project) |
| YouTube Data v3 (+ Analytics/Reporting registered) | `src/skills/google_extras.py::YouTubeClient`, wired in `src/bot.py:1305` (env-gated) | Video discovery, channel stats, transcripts | `YOUTUBE_API_KEY` | **WIRED & READY** (key set) |
| Places (New) + Maps Grounding Lite | `src/google_cloud_client.py` (`places:searchNearby`, called) + `mapsgrounding`/`maps/api` registered | Geo-search, local places | `GOOGLE_PLACES_KEY` | **STAGED** (adapter written, key **missing**) |
| Weather (Open-Meteo, keyless) | `src/skills/weather.py` (geocoding + forecast, 6 h TTL) | Forecasts, atmospheric conditions | — | **LIVE-capable** |
| Google Weather API | `src/google_cloud_suite.py` registry | Keyed upgrade path | Google Cloud project | **REGISTERED** |
| Firecrawl | `src/skills/firecrawl.py` (`api.firecrawl.dev/v1/scrape`) | Complex-page Markdown behind WebIntel fallback | `FIRECRAWL_API_KEY` | **STAGED** (key **missing**) |
| ExchangeRate | `src/external_apis.py` (pair API; empty key → honest offline) | Currency conversion | `EXCHANGERATE_API_KEY` | **WIRED & READY** (key set) |
| Instagram | `src/skills/instagram_sandbox.py` (`is_live()` gate) | Sandboxed; live needs session | `INSTAGRAM_SESSION` | **STAGED** (key **missing**) |

## D. Cloud infrastructure & telemetry

| Service | Module | Role | Key | Status |
|---|---|---|---|---|
| Cloud Storage (GCS) | `src/google_cloud_client.py` (called adapter) | Encrypted vault backup archives | Google Cloud project | **WIRED & READY** |
| Cloud Logging / Monitoring / Trace | `src/google_cloud_suite.py` registry | Distributed telemetry, error tracing | Google Cloud project | **REGISTERED** |
| BigQuery family / Datastore / Cloud SQL / Dataform / Dataplex / Health / ServiceUsage | `src/google_cloud_suite.py` registry (37 URLs) | Future structured-data surface (B1-B8) | Google Cloud project | **REGISTERED** (no calling adapters) |
| GitHub Contents API (vault transport) | `src/vault.py` (Bearer + `?ref=`) | Git-backed Obsidian vault read/write | `VAULT_GITHUB_TOKEN`, `VAULT_GITHUB_REPO` | **WIRED & READY** (token set) |
| PC bridge (WSS + Bearer) | `bridge/` daemon + `src/bridge_server.py` | Device control, telemetry | `BRIDGE_TOKEN`, `BRIDGE_SERVER_URL` | **WIRED & READY** (token set; live test needs the daemon) |

## E. Speech & voice

| Service | Module | Role | Key | Status |
|---|---|---|---|---|
| Fish Audio (via OpenRouter speech) | `src/fish_voice.py` (`FishFirstVoice`; `fish-audio/s2.1-pro-free:free`) | Sara's ONLY voice (Ogg Opus 64k) | `FISH_AUDIO_API_KEY` (+ OpenRouter fallback) | **WIRED & READY** (key set; unit-tested incl. 429→honest-text) |
| Local Whisper (faster-whisper, CPU int8) | `src/skills/voice_to_vault_transcriber.py` | Speech-to-text, voice memos | `WHISPER_MODEL_SIZE` (local download) | **WIRED & READY** (never cloud STT by ruling) |
| Edge-TTS | — | Purged 2026-09-03/09-12; `assert_no_edge` enforced | — | **Removed by design** |

## Smoke-test results (2026-09-16, non-destructive)

| Probe | Result |
|---|---|
| Telegram `getMe` | **LIVE** — `@Sara_Vantrilex_bot` |
| OmniRoute `GET /v1/models` | **UNREACHABLE** (all LLM tiers DEGRADED) |
| Google OAuth cache (`vault/State/google_token.json.enc`) | **Decryptable** with `VAULT_ENC_KEY`; Gmail/Calendar/Drive/Tasks/People can bootstrap (live refresh still to prove) |
| `.env` posture | 47 keys set; only `TELEGRAM_USER_SESSION_STRING`, `OBSIDIAN_API_KEY` empty |
| Missing live keys | `FIRECRAWL_API_KEY`, `GOOGLE_PLACES_KEY`, `INSTAGRAM_SESSION`, `GMAIL_PUBSUB_TOPIC` |

## Owner action list (to flip STAGED → LIVE)

1. Start OmniRoute with provider keys (unblocks all LLM tiers).
2. Google consent refresh on first run (watch the known 403 on the Cloud project).
3. Optional keys as needed: Firecrawl, Places, Instagram session, PubSub topic (else polling).
4. Rotate the exposed OpenRouter key (still sitting in untracked `opencode.json`).

## See also (graph links)

- [04 — System Architecture](../04-ARCHITECTURE.md)
- [12 — Security](../12-SECURITY.md)
- [Master Roadmap](../MASTER_ROADMAP_AND_REMAINING_WORK.md)
- [Map of Architecture](../00-MAP-OF-ARCHITECTURE.md)
