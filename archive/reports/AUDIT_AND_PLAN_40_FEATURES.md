# 🔍 AUDIT & EXECUTION PLAN — The Complete 40+ Features Audit

> **Artifact**: `AUDIT_AND_PLAN_40_FEATURES.md` — exhaustive literal audit of every shipped
> feature across `src/`, `bridge/`, `common/`, `tests/`, plus the root-cause analysis of the
> six verified live defects (owner live test 2026-09-05) and the phased execution roadmap.
> **Audit date**: 2026-09-06 · **Branch**: `main` · **Read-only pass** — ZERO production code touched.
> **Critical finding up front**: all six live defects of 2026-09-05 (A–F, plus G) are **already
> fixed in the working tree**, pinned by `tests/test_live_defects_2026_09_05.py` — but the seven
> modified source files and the new test file are **UNCOMMITTED / UNTRACKED** (`git status`
> evidence below). Phase A therefore shifts from "write patches" to "commit + gate + live retest".

---

## 1. Architectural Baseline & Invariants

### 1.1 System Topology (verified)

**Vantrilex Assistant OS** is an owner-only, strictly-zero-cost executive AI assistant named
**Sara (سارة)** speaking warm Jordanian Arabic (`ar-JO`):

- **Transport**: Telegram via **Aiogram 3.x** long-polling (`src/bot.py`, 1,189 lines) — text chat
  with progressive delivery (instant placeholder → ack edit → 750 ms-coalesced deltas → verbatim
  final; 2-3 bubble re-split for long replies), Ogg Opus voice notes (Fish Audio primary via
  OpenRouter's `/v1/audio/speech`, «سمسم» reference voice; Edge-TTS `ar-EG-SalmaNeural` as the
  unconfigured default and the **demanded-note failover**), native m3 image/video comprehension,
  and a real-Telegram-photo screenshot surface.
- **Brain (3-tier, ADR-16 amended)**: OmniRoute gateway `http://localhost:20128/v1`
  (`src/gateway.py`) — TIER 1 `openrouter/minimax/minimax-m3:free` (conversation lane),
  TIER 2 `groq/openai/gpt-oss-120b`, TIER 3 `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free`
  (tool lane), behind the **Fast Front-Door Dispatcher** (ADR-18, `src/dispatcher.py`, 660 lines)
  with a Tier-1 JSON router verdict + the deterministic `_keyword_net` anti-hallucination
  backstop (fires only on a router miss, logs every coercion loudly).
- **Runtime host (ADR-15 amended 2026-08-31)**: Oracle Cloud Always-Free VM — ONE Docker
  container co-locating core + OmniRoute, single public port behind Caddy TLS (WSS bridge
  endpoint + `/health`), `restart: unless-stopped`. All durable state lives in the git-backed
  Obsidian vault (disposable-filesystem principle).
- **PC Bridge** (`bridge/`): a Windows daemon that dials OUT over TLS WebSocket (zero inbound
  ports, token in the first Hello frame only, `common/protocol.py` v1 framing — 14 command
  names from `exec.launch` to `telemetry.app_sessions`), executing whitelist-guarded actions
  (`bridge/guard.py` re-reads `config/whitelist.json` every check, corrupt file fails CLOSED),
### 1.2 Test Baseline Status

- **Ledger claim** (`.claude/PHASE-STATE.md`, final gate of the 2026-09-04 §1-§9 directive run):
  **661 passed / 1 skipped / 85.29% branch / security+docs green; sacred floors green**.
- **This audit's verification (executed 2026-09-06)**: `pytest -q` on the current working tree
  (which already includes the uncommitted live-defect fixes + the new regression floor) →
  **851 passed / 1 skipped in 64.42 s, branch coverage 85.35% — the 85% gate GREEN**. The suite
  grew past the 661 ledger number through the post-directive passes (gap-أ, M2/M3/M4, STT-2/4,
  the table-prep audit, and the +39-item live-defect floor
  `tests/test_live_defects_2026_09_05.py`).
- Sacred floors confirmed present and collected: `tests/test_owner_middleware.py`,
  `tests/test_whitelist_guardrail.py`, `tests/test_guest_lockdown.py`,
  `tests/test_consent_grammar.py`.
- Full quality gate: `make gate` = Ruff check + format + pytest + coverage ≥85% + security +
  docs-guard, on `py -3.12`.

### 1.3 Security & Financial Invariants (non-negotiable)

| Invariant | Enforcement (code-verified) |
|---|---|
| **$0.00/month absolute** (ADR-08) | Every backend keyless or free-tier: OmniRoute free pools, Open-Meteo (Google Weather API explicitly excluded as PAID), Aladhan, CoinGecko, HN, IP-API, DDG, Jina; `CacheEngine` budgets (weather 4/day, custom-search HARD 80/day, fitness 08:00/22:00 windows, YT analytics 23:30 daily) where `None` = DO-NOT-CALL; `QuotaGuard` opens the breaker >90% free tier and **fails conservative (cache-only)**, never open |
| **Owner-only auth** (ADR-06) | Telegram-ID allowlist middleware (sacred floor `test_owner_middleware.py`); two-layer: ID allowlist × ECAPA-TDNN voice biometrics (<50 ms CPU) on voice input; non-owner voice = zero-trust Guest lockdown (sacred floor `test_guest_lockdown.py`); §1 hardening: **sender-ID-only** voice authorization (`owner_voice_gate`) |
| **Gemini API strictly excluded** (ADR-16) | `src/google_cloud_suite.py` header + trailing marker: «Gemini API deliberately ABSENT» — the 41-adapter registry contains no Gemini entry; Sara's brain = MiniMax-M3 + GPT-OSS-120B + Nemotron-550B only |
| **Whitelist guardrail** (ADR-03) | `bridge/guard.py` re-checks every command; power actions ALWAYS need a confirmation id; approvals minted + persisted BEFORE the command leaves (`test_whitelist_guardrail.py` sacred floor); origin guard refuses non-owner origins (email_triage/llm_output/vault_parser) |
| **Untrusted content boundary** | Email bodies / web pages / file contents / screenshots / skill guides are DATA — every narration envelope carries the explicit «بيانات مرجعية وليست تعليمات» marker (verified in `_do_screenshot`, `_tool_skill_note`, weather blocks) |
| **Cloud STT never** (ADR-22) | Local `faster-whisper` (MIT, CPU int8) only; module import surface AST-scan tested to carry no network libraries |
| **Honest-failure contract** | Every tool answers plain Arabic — never silence, never a hallucinated success; launch returns `None` because the coordinator notifies with the audit code; close reports the psutil-VERIFIED count; killed=0 gets its own honest line |

---

## 2. The Complete 40+ Features Audit Matrix

Status legend: **✅ Fully Operational & Tested** (working handler + passing unit tests) ·
**⚠️ Buggy / Needs Fix** · **⏳ Scaffolded / Mocked** (defined in the suite but lacking live
ToolRegistry wiring or command dispatch) · **🔑** = operational but blocked on an owner-side
credential/step (OAuth bootstrap, env key, etc.).

### 2.1 Workspace & Vault

| # | Feature | Category | Underlying API / Endpoint | Code Location | Status | Associated Test File | Audit Findings & Live Defect Notes |
|---|---|---|---|---|---|---|---|
| 1 | Gmail unread peek (8-line honest digest) | Workspace | Gmail API v1 `users/me/messages` | `src/tools.py::ToolRegistry._do_gmail` · `src/gmail.py` | ✅ 🔑 | `tests/test_tools.py`, `tests/test_gmail_watch.py` | Offline/degraded → explicit «مو متصلين هسا» line; empty inbox → «ما في بريد جديد». Live-blocked only by the missing one-time OAuth bootstrap (vault/State empty) |
| 2 | Gmail watch/poll + triage loop | Workspace | Gmail poll + TokenJuice compaction (ADR-19) | `src/gmail.py::run_gmail_poll` · `src/email_triage.py` | ✅ 🔑 | `tests/test_gmail_watch.py`, `tests/test_email_triage.py` | Wired through `start_background_loops`; critical mail escalates to priority voice-note + repeat ping |
| 3 | Calendar next-24h listing | Workspace | Calendar API v3 `events.list` | `src/tools.py::_do_calendar` · `src/google_suite.py::list_events` | ✅ 🔑 | `tests/test_tools.py`, `tests/test_google_suite.py` | TZ-aware Amman rendering; NO_EVENTS honest line; blocked on OAuth bootstrap only |
| 4 | Tasks due-today | Workspace | Tasks API v1 `tasks.list` | `src/tools.py::_do_tasks` · `src/google_suite.py::list_tasks` | ✅ 🔑 | `tests/test_tools.py`, `tests/test_google_suite.py` | status→completed coercion validated; honest «ما في مهام مستحقة اليوم» |
| 5 | Event/task creation via GoogleSuite | Workspace | Calendar/Tasks write endpoints | `src/google_suite.py::create_event`/`add_task` | ✅ (unit-tested; thin live use) | `tests/test_google_suite.py` | Methods exist and are tested; heavier creation flows ride the scheduled-tasks mirror (#6) |
| 6 | Scheduled-tasks vault↔Google mirror | Workspace | Vault Contents API + Calendar/Tasks | `src/skills/scheduled_tasks.py::ScheduledTasksEngine` | ✅ | pass-2 suite | ONE note per task in `01_Projects/Scheduled_Tasks/` with `[sara:task:id]`; idempotent; Google-down parks + ~10-min catch-up loop (`bot.py::_run_task_sync`) |
| 7 | Obsidian vault transport | Workspace | GitHub Contents + Git Data API | `src/vault.py::VaultClient` | ✅ | `tests/test_obsidian_para.py` (+ `tests/helpers_vault.py`) | sha-first upsert, one 409 retry, `VaultConflictError`, 1 MB pre-flight bound, `redact_secret`; PARA backbone immutable (`BackboneImmutableError`) |
| 8 | Dynamic folder creation | Workspace | GitHub Contents API (dir = first note) | `src/tools.py::_do_create_folder` + `src/vault.py::_sanitize_component` | ✅ (defect G fixed, uncommitted) | `tests/test_live_defects_2026_09_05.py` (3 tests), `tests/test_dynamic_folders.py` | Live defect G: a vault write failure used to surface as `KeyError:'name'` from the loguru formatter INSIDE the except block — the owner saw a crash («صار في مشكلة»). Fixed: honest «ما قدرت أنشئ الفولدر» line; traversal sanitized («../Escape» dies); one `_index.md` commit |
| 9 | Daily ledger + 23:50 summarizer | Workspace | Obsidian + MEDIUM-model call | `src/memory.py::DailySummarizer` | ✅ | `tests/test_memory.py` | Last-150-turns + Obsidian envelope → SEPARATE end-of-day summary appended to the day's ledger note |
| 10 | Morning brief 07:30 | Workspace | Multi-source brief composition | `src/daily_brief.py::BriefComposer` | ✅ | `tests/test_daily_brief.py` | One of the five background loops through the single `start_background_loops` stitch; `BRIEF_ENABLED` gate |
| 11 | Evening journaler 18:00–19:30 | Workspace | Ledger write + randomized window | `src/skills/evening_journaler.py` | ✅ | `tests/test_evening_journaler.py` | Calendar-conflict guard; state-loss same-day re-run appends a corrigenda line instead of duplicating |
| 12 | Knowledge graph (wikilink web) | Workspace | Vault scan (contents-API `list_dir`) | `src/skills/knowledge_graph.py` · `src/tools.py::_do_knowledge_graph` | ✅ | `tests/test_knowledge_graph.py` | Alias-aware, dangling links honest nodes, backlinks/neighbors/orphans; Arabic DATA brief |
| 13 | Voice-to-vault transcription | Workspace | Local faster-whisper (ADR-22) | `src/skills/voice_to_vault_transcriber.py` | ✅ | `tests/test_voice_to_vault*.py` (+ `tests/helpers_voice.py`) | 16 kHz mono s16le in-memory ffmpeg decode; files `Voice_Memos/YYYY-MM-DD-HHMM.md`; runs ONLY after the biometric gate |
| 14 | Dialect learning loop («تعلمي:») | Workspace | Vault + live lexicon refresh | `src/dialect.py` · `src/bot.py` learning hook | ✅ | `tests/test_dialect.py` | «تعلمي:» pairs land in the vault + refresh the Edge shaper lexicon WITHOUT reboot (`VoicePipeline.update_notes`) |
| 15 | Proactive outreach engine | Workspace | HEAVY-judged check-ins | `src/skills/proactive_outreach.py` | ✅ | `tests/test_proactive_outreach.py` | ~45-min loop, 08:00–22:30, max 3/day, cooldown + calendar guard |
| 16 | Self-evolution reflection (f4) | Workspace | Nightly HEAVY proposals | `src/skills/self_evolution.py` | ✅ | pass-4 suite | ~23:40, proposals only, never silent; loop rides `start_background_loops` |

### 2.2 Desktop Bridge (PC Control)

| # | Feature | Category | Underlying API / Endpoint | Code Location | Status | Associated Test File | Audit Findings & Live Defect Notes |
|---|---|---|---|---|---|---|---|
| 17 | App launch + Arabic aliases + live whitelist guard | Desktop Bridge | Windows spawn (detached, shell-free) | `src/pc_actions.py::PCActionCoordinator.request_launch` · `_APP_ALIASES`/`resolve_app_alias` · `src/tools.py::_do_launch` | ✅ | `tests/test_pc_actions.py`, `tests/test_whitelist_guardrail.py` (sacred floor) | «الآلة الحاسبة»→calculator, «أوبسيديان»→obsidian, «المفكرة»→Notepad… resolved BEFORE the wire; unknown name → honest «مش موجود بالقائمة المعتمدة» immediately (no doomed round-trip); guard re-reads whitelist per check |
| 18 | App close with psutil-verified termination | Desktop Bridge | `taskkill /IM /F /T` + psutil count | `src/tools.py::_do_close` → `request_close` → `bridge/executor.py::close` + `close_images` + `PROCESS_IMAGE_ALIASES` | ✅ (defect A fixed, uncommitted) | `tests/test_live_defects_2026_09_05.py` (4), `tests/test_close_routing.py`, `tests/test_close_app.py`, `tests/test_chrome_close_live.py` | **Live defect A**: Windows 10/11 Calculator runs as `CalculatorApp.exe` while whitelist/aliases say `calc.exe` — old code killed only calc.exe, reported «ما لقيت نسخة شغالة هسا» with windows still open. Fixed: `close_images()` hunts every image the app can run as (`CalculatorApp.exe`, `Calculator.exe`, `calc.exe`); killed=0 keeps its own honest line |
| 19 | Close-verb routing (سكري/اغلقي never launch) | Desktop Bridge | Dispatcher keyword net | `src/dispatcher.py::_TOOL_NET` close entry (before launch) | ✅ | `tests/test_close_routing.py` | Live 2026-09-04: «سكري الآلة الحاسبة» misrouted to LAUNCH and spawned duplicates; close verbs now win over everything, arg strips «على جهازي/لو سمحت» |
| 20 | Power actions (shutdown/restart/sleep) | Desktop Bridge | shutdown/rundll32 | `bridge/executor.py::POWER_ARGV` · `src/pc_actions.py::request_power` | ✅ | `tests/test_whitelist_guardrail.py`, `tests/test_bridge_extensions.py` | ALWAYS need a confirmation id regardless of whitelist flags; origin guard refuses non-owner origins |
| 21 | Wake-on-LAN | Desktop Bridge | LAN magic packet (UDP) | `bridge/wol.py` · `src/bot.py::_bridge_handshake_probe` (M3 chain) | ✅ | `tests/test_bridge_protocol.py`, `tests/test_bridge_extensions.py` | Boot → auto-logon → ONLOGON daemon handshake probe; MAC pinned in env |
| 22 | Desktop telemetry snapshot | Desktop Bridge | psutil one-shot | `bridge/telemetry.py::live_state` · `src/telemetry.py::TelemetryClient` · `src/tools.py::_do_telemetry` | ✅ | `tests/test_desktop_telemetry.py` | Degrades any psutil metric to None, never crashes; payload carries no secrets; Tier-1 FAST Arabic narration + deterministic numeric fallback; honest «الجسر مو متصل هسا» |
| 23 | Minute-level app usage (app_sessions) | Desktop Bridge | psutil foreground poll (60 s) | `bridge/app_sessions.py` · `src/tools.py::_do_app_sessions` | ✅ | `tests/test_app_sessions.py`, `tests/test_app_sessions_narration.py` | Category roll-up (Games/Programming/Study/Productivity) + boot/shutdown log; JSON state survives daemon restarts; whitelist exe→display-name map (gap-ج) |
| 24 | Running apps list (by name, unfiltered) | Desktop Bridge | psutil process table | `src/tools.py::_do_running_apps` · `bridge/executor.py` (`exec.list_apps`) | ✅ | STT-2 suite | STT-2 + gap-ج: every app BY NAME; whitelisted exes carry their display name; read-only, no confirmation gate |
| 25 | Whitelist report (what CAN be opened) | Desktop Bridge | `config/whitelist.json` read | `src/tools.py::_do_whitelist_apps` | ✅ | Live-6 suite | «شو في تطبيقات عندك في القائمة» — count + names, mirrored to the vault |
| 26 | Volume control (mute/up/down/set %) | Desktop Bridge | Windows VK_VOLUME_* key events (ctypes, $0.00) | `bridge/executor.py::volume` · `src/tools.py::_do_volume` | ✅ | M2 suite (`tests/test_bridge_extensions.py`) | set-X% = X/2 VOLUME_UP presses from the level anchor (Windows steps 2%); honest result both ways |
| 27 | Media playback control | Desktop Bridge | Media key events | `bridge/executor.py` (`exec.media_control`) · `src/tools.py::_do_media` | ✅ | M2 suite | «وقفي الفيديو» = PLAYBACK pause, routed BEFORE close in the net; sibling-word guard vs الصوت |
| 28 | Screen OCR (read-the-screen) | Desktop Bridge | Capture + vision extraction | `bridge/executor.py` (`exec.screen_ocr`) · `src/tools.py::_do_screen_ocr` | ✅ | M2 suite | Daemon captures, vision lane extracts verbatim; the code IS the answer (no re-narration) |
| 29 | Screenshot → native vision → real photo | Desktop Bridge | In-memory capture + m3 image_url | `src/tools.py::_do_screenshot` (+ `photo_sender`) | ✅ | `tests/test_screenshot_tool.py`, `tests/test_live_planner_photo.py` | §4: delivery requests get the REAL JPEG dispatched first; Live-5 negation «لا ترسلي الصورة» → description only; untrusted-content marker rides the prompt |
| 30 | File upload (phone → PC) | Desktop Bridge | Sanitized write into first file root | `bridge/executor.py::file_upload` (`file.upload`) | ✅ | M2 suite | Traversal/absolute names sanitize to basename; root decides location |
| 31 | File fetch (PC → phone document) | Desktop Bridge | Whitelisted-roots read + base64 | `bridge/executor.py::file_download` · `src/tools.py::_do_file_fetch` (+ `document_sender`) | ✅ | M2 suite | Outside-roots refused loudly; sensitive suffixes blocked; rides as a REAL Telegram document |
| 32 | Idle sleep/shutdown offer | Desktop Bridge | Activity-watch + offer once per window | `bridge/idle.py` | ✅ | Sprint-3 suite | >20 min idle → ONE offer; real activity re-arms; same confirmation flow |

### 2.3 Places, Weather, Search & External APIs (M4)

| # | Feature | Category | Underlying API / Endpoint | Code Location | Status | Associated Test File | Audit Findings & Live Defect Notes |
|---|---|---|---|---|---|---|---|
| 33 | Weather (current conditions) | Places/Weather | Open-Meteo forecast + geocoding (keyless) | `src/skills/weather.py::WeatherClient` · `src/tools.py::_do_weather` | ✅ (defect C fixed, uncommitted) | `tests/test_live_defects_2026_09_05.py` (2), pass-4 weather suite | **Live defect C**: geocode loguru crash — an empty results list was an exception path (`[0]` IndexError) and the logging format raised. Fixed: `results or []`, unknown-place memory (`self.unknown`), honest «ما لقيت X على خريطة الطقس»; static Jordanian coords zero-latency for daily cities |
| 34 | Prayer times (Amman) | Places/Weather | Aladhan `/v1/timings/{DD-MM-YYYY}` | `src/external_apis.py::get_prayer_times` · `src/tools.py::_do_prayer_times` | ✅ (defect B fixed, uncommitted) | `tests/test_live_defects_2026_09_05.py` (2), `tests/test_external_apis.py` | **Live defect B**: textual geocoding mismatch (Amman vs Oman) + Aladhan city-table drift (30–40 min) + missing tz. Fixed: EXACT coordinates `31.9539, 35.9106`, `timezonestring=Asia/Amman`, `method=23` (Hashemite Ministry of Awqaf — Fajr/Isha 18.0°), UTC+3 constant (DST abolished 2022), explicit date segment (date-less endpoints 302 and the shared client does not follow redirects — the old call silently returned None) |
| 35 | Web search (keyless) | Search | DuckDuckGo HTML | `src/skills/web_intel.py::WebIntel.search_block` · `src/tools.py::_do_web_search` | ✅ (web_intel modified, uncommitted) | pass-4 web-intel suite | Real result titles + links as DATA; empty results degrade honestly, never fabricated; net entry ordered before topic-noun tools |
| 36 | Page read / Jina Reader | Search | `https://r.jina.ai/{target}` (keyless) | `src/external_apis.py::read_webpage_clean` · `src/tools.py::_do_read_page` | ✅ (defect D-part fixed, uncommitted) | `tests/test_live_defects_2026_09_05.py` (2 bare-URL tests) | **Live defect D-part**: a BARE pasted URL («https://adamlankamer.com/ai») fell through to a plain web search and never reached Jina; the net's `read_page` regex now captures `https?://\S+` with no verb required |
| 37 | Currency conversion | External APIs | ExchangeRate v6 `/pair` (env key) | `src/external_apis.py::convert_currency` · `src/tools.py::_do_convert_currency` | ✅ 🔑 | `tests/test_external_apis.py` | Empty key → honest None (never a fabricated rate); TTL 1h |
| 38 | Crypto price | External APIs | CoinGecko `simple/price` (keyless) | `src/external_apis.py::get_crypto_price` · `src/tools.py::_do_crypto_price` | ✅ | `tests/test_external_apis.py` | JOD default vs-currency; TTL 15m; dead net → honest line |
| 39 | Tech trending radar | External APIs | Hacker News Firebase topstories | `src/external_apis.py::get_tech_trending` · `src/tools.py::_do_tech_trending` | ✅ | `tests/test_external_apis.py` | Top-5 title+link; dead item ids skip, never a hole-crash |
| 40 | Network status (public IP) | External APIs | ip-api.com | `src/external_apis.py` · `src/tools.py::_do_network_status` | ✅ | `tests/test_external_apis.py` | IP/ISP/city/proxy of the core's egress; no secrets in payload |
| 41 | YouTube search | Media/YouTube | YouTube Data API v3 (env-gated free quota) | `src/tools.py::_do_youtube` (+ pass-4 YouTubeClient) | ✅ 🔑 | pass-4 youtube suite | `YOUTUBE_API_KEY` unset → honest «المفتاح مو مفعّل أو الحصة خلصت»; 1h cache family |
| 42 | Instagram sandbox | Media/YouTube | Session-gated surface | `src/skills/instagram_sandbox.py` | ⏳ 🔑 | `tests/test_instagram_sandbox.py` | §7 staging only — needs `INSTAGRAM_SESSION`; no ToolRegistry dispatch yet |
| 43 | Firecrawl deep scrape | Search | Firecrawl REST | `src/skills/firecrawl.py` | ⏳ 🔑 | `tests/test_firecrawl.py` | §7 staging; needs `FIRECRAWL_API_KEY`; not wired into a tool handler |

### 2.4 Google Cloud 41-API Suite (§7) & BigQuery/Storage/Observability

| # | Feature | Category | Underlying API / Endpoint | Code Location | Status | Associated Test File | Audit Findings & Live Defect Notes |
|---|---|---|---|---|---|---|---|
| 44 | CacheEngine (TTL + daily budgets) | BigQuery/Storage/Observability | In-memory (Amman wall-clock) | `src/google_cloud_suite.py::CacheEngine` | ✅ | `tests/test_google_cloud_suite.py` | weather 6h/4-day · places 7d · custom-search 24h + HARD 80/day · fitness 08:00+22:00 + 1h · YT analytics daily · `None` = DO-NOT-CALL |
| 45 | QuotaGuard circuit breaker | Observability | Service Usage API | `src/google_cloud_suite.py::QuotaGuard` | ✅ (unit-tested; consumer surface scaffolded) | `tests/test_google_cloud_suite.py` | >90% free tier → breaker open; dead usage API fails CONSERVATIVE (cache-only), never open |
| 46 | Cluster 1 — Workspace adapters (7) | Workspace | gmail, gmail_mcp, google_calendar, google_tasks, google_drive, drive_mcp, people | `src/google_cloud_suite.py::API_REGISTRY` | ⏳ | `tests/test_google_cloud_suite.py`, `tests/test_google_clients.py` | Typed adapters defined; live read/write flows run through `src/google_suite.py` clients (#1–#5); the *adapter registry* itself has no ToolRegistry dispatch |
| 47 | Cluster 2 — Health & Gaming adapters (4) | Health/Fitness | fitness, google_health, play_games, play_android_dev | `src/google_cloud_suite.py::API_REGISTRY` | ⏳ 🔑 | `tests/test_google_cloud_suite.py` | Fitness sync windows enforced by CacheEngine; Fitness OAuth scopes not yet in `AUTH_SCOPES`; no tool handler |
| 48 | Cluster 3 — Media & Search adapters (8) | Media/YouTube | youtube_data, youtube_analytics, youtube_reporting, custom_search, maps_grounding, maps_sdk_android, places, weather_google | `src/google_cloud_suite.py::API_REGISTRY` | ⏳ | `tests/test_google_cloud_suite.py` | weather_google kept as the PAID-avoidance pair (Open-Meteo is the active keyless lane); places/maps/custom-search have zero live callers |
| 49 | Cluster 4 — BigQuery & Storage adapters (14) | BigQuery/Storage | bigquery(+storage/connection/policy/transfer/migration/reservation), cloud_storage(+api/gcs_json), datastore, dataplex, dataform, cloud_sql | `src/google_cloud_suite.py::API_REGISTRY` | ⏳ | `tests/test_google_cloud_suite.py` | The always-free data vault; data stays LOCAL SQLite per the $0.00 ruling (cloud_sql admin-verify only); no tool handlers yet |
| 50 | Cluster 5 — Observability adapters (8) | Observability | service_usage, service_management, cloud_logging, cloud_monitoring, cloud_trace, telemetry_api, analytics_hub, core_sdk | `src/google_cloud_suite.py::API_REGISTRY` | ⏳ | `tests/test_google_cloud_suite.py` | service_usage is the QuotaGuard's backend; the rest have zero live callers |
| 51 | Gemini exclusion guard | Observability | — (ADR-16 ruling) | `src/google_cloud_suite.py` header/footer markers | ✅ | suite contract tests | «Gemini API deliberately ABSENT» — structural, not just documented |

### 2.5 Task Engine (§5)

| # | Feature | Category | Underlying API / Endpoint | Code Location | Status | Associated Test File | Audit Findings & Live Defect Notes |
|---|---|---|---|---|---|---|---|
| 52 | Timed reminders (relative delay) | Task Engine | Real asyncio timers + JSON state | `src/task_orchestrator.py::parse_delay_ar` · `Orchestrator` | ✅ | orchestrator + live-defect suites | «بعد 60 ثانية ذكريني اشتري بيض» — registered AND fires proactively (`bot.send_message` to the owner chat); state persists (`State/task_reminders.json`), restart re-arms pending; dispatch failure retries in a minute — never silent |
| 53 | Timed reminders (wallclock) | Task Engine | Amman TZ parsing | `src/task_orchestrator.py::parse_wallclock_ar`/`_WALL_RE` | ✅ | orchestrator suite | Any clock shape («على الساعة 3:47 مساء») anywhere in the sentence; Arabic-Indic digits normalized; audit round-3 fixed the title prefix («مساء ذكريني» leak) |
| 54 | Sequential step-DAG chains | Task Engine | Ordered awaits, fail-fast | `src/task_orchestrator.py::run_chain` | ✅ | orchestrator suite | STOP at first failure and report WHERE it died — anti-hallucination contract, no claimed completions |
| 55 | Parallel swarm | Task Engine | `asyncio.gather(return_exceptions=True)` | `src/task_orchestrator.py::run_parallel` | ✅ | orchestrator suite | ONE unified confirmation; per-step honest failure report («نجحت X، وY ما اشتغلت») |
| 56 | Composite scheduled workflows | Task Engine | Timer + steps | `src/task_orchestrator.py::_Job.has_steps` | ✅ | orchestrator suite | timer fires the chain; step chains re-arm as message + fresh id |
| 57 | Multi-task manager (STT-4) | Task Engine | HEAVY plan → MEDIUM sub-agents → real handlers | `src/agent_manager.py` · `src/tools.py::_do_multi_task` | ✅ | `tests/test_agent_manager.py`, `tests/test_multi_task_narration.py` | 2+ imperative verbs joined by و/بعدين/ثم = multi_task in the net; results stream AS-IS (honest ✅/📤/⚠️ markers, no second narration round) |
| 58 | Reminder management (list/cancel) | Task Engine | Orchestrator state | `src/tools.py::_do_list_reminders`/`_do_cancel_reminder` | ✅ | gap-أ suite | list exempted from re-narration (Live-2: narration dropped the job ids — the owner's cancel targets); cancel by job id / number / الكل sweep, honest result both ways |

### 2.6 Voice Pipeline & Persona

| # | Feature | Category | Underlying API / Endpoint | Code Location | Status | Associated Test File | Audit Findings & Live Defect Notes |
|---|---|---|---|---|---|---|---|
| 59 | Fish Audio voice notes («سمسم») | Voice Pipeline | OpenRouter `POST /v1/audio/speech`, `fish-audio/s2.1-pro-free:free`, voice-ref 56c2f0c2… | `src/fish_voice.py::FishVoice`/`FishFirstVoice` · `src/bot.py::build_voice` | ✅ 🔑 | `tests/test_fish_audio_pipeline.py` | speed=0.9 on the wire (`FISH_AUDIO_SPEED`); 429 window-aware retry (bounded ≤8 s); re-raises on failure for ordinary turns (honest text, NO foreign voice — owner directive 2026-09-03); needs `OPENROUTER_API_KEY` |
| 60 | Demanded-voice Edge failover (P0-A) | Voice Pipeline | Edge-TTS `ar-EG-SalmaNeural` local lane | `src/bot.py::_speak_demanded` (+ `edge_lane` wired in `run_bot`) | ✅ (defect E fixed, uncommitted) | `tests/test_bot_voice_demand.py`, `tests/test_live_defects_2026_09_05.py` (2) | **Live defect E**: a DEMANDED voice note silently fell back to TEXT when Fish 429'd. Fixed: `_speak_demanded` — Fish tries once → local Edge synthesizes the SAME text → only a DOUBLE failure lands the honest apology; the demand law: the audio bubble itself must arrive |
| 61 | Edge-TTS → ffmpeg → Ogg Opus 64k pipeline | Voice Pipeline | edge-tts MP3 → libopus in-memory | `src/voice.py::VoicePipeline` | ✅ | `tests/test_edge_tts_pipeline.py`, `tests/test_audio_stream_opus.py` | `-probesize 32` (~30 ms first chunk), 64k `audio` application (24k voip choked every voice — live 2026-09-02), dialect shaper first (emoji strip + lexicon + تسكين الأواخر), 30 s total synthesis wall (V-1), every path reaps ffmpeg |
| 62 | Voice biometrics + Guest Mode | Voice Pipeline | ECAPA-TDNN cosine (<50 ms CPU) | `src/skills/voice_biometric_auth.py` · `verify_or_lockdown` | ✅ | `tests/test_guest_lockdown.py` (sacred floor), biometrics suite | Threshold calibrated to 0.60 after the owner intra-speaker 0.7637 incident; guest = warm greeting + zero-trust lockdown + message filing; sender-ID-only authorization (§1) |
| 63 | STT + transcription intake | Voice Pipeline | Local faster-whisper after the gate | `src/skills/voice_to_vault_transcriber.py` | ✅ | whisper suite | Pinned to Jordanian Arabic; transcript enters the standard owner-text pipeline (tier choice = dispatcher's, never this module's) |
| 64 | Reply-modality mirror (70/30) | Voice Pipeline | Router `voice_reply` verdict | `src/skills/reply_modality.py` · dispatcher `voice_hint` | ✅ | reply-modality suite | text origin 70% text / voice origin 70% voice; explicit «رد صوتي/رد نصي» always wins; one surface only |
| 65 | Voice-forcing patterns | Voice Pipeline | Keyword net / voice lane | `src/dispatcher.py` voice patterns | ✅ | bot-voice-demand suite | «ابعثي/ارسلي رسالة صوتية» / «رسالة صوتية» / «ملاحظة صوتية» force the voice lane |
| 66 | Photo/video native comprehension | Voice Pipeline | m3 `image_url`/`video_url` blocks | `src/bot.py` media turns · `dispatcher.handle(media=…)` | ✅ | `tests/test_live_planner_photo.py` | Media turns skip tool routing entirely; >10 MiB → honest line; brain untouched |
| 67 | External media-link sanitizer | Voice Pipeline | Regex stripper (S3/CDN/mp3 links) | `src/voice.py::strip_external_media_links` | ✅ | voice suite | The 3:42pm hallucinated `sara-voice.s3.amazonaws.com` class is structurally dead; rides the voice lane only |
| 68 | Live calls (PyTgCalls) | Voice Pipeline | PyTgCalls WebRTC + VAD/barge-in | `src/skills/live_calls.py` · `src/telegram_login.py` | ⏳ 🔑 | `tests/test_live_calls.py`, `tests/test_acoustic_nuance.py` | v1.1 staged: routes the moment `TELEGRAM_USER_SESSION_STRING` lands (10-minute owner login, `docs/OWNER_ACTION_REQUIRED.md` §1); ZERO live-call code paths active in v1.0 (scope-locked by test) |
| 69 | Acoustic nuance + affect engine | Voice Pipeline | Prosody/energy analysis (local) | `src/skills/acoustic_nuance.py` · `src/skills/affect_engine.py` | ✅ | `tests/test_acoustic_nuance.py`, `tests/test_affect_engine.py` | v1.1 intelligence suite landed local-first; persona-preservation invariant tested |

### 2.7 Dispatcher, Brain & Auth

| # | Feature | Category | Underlying API / Endpoint | Code Location | Status | Associated Test File | Audit Findings & Live Defect Notes |
|---|---|---|---|---|---|---|---|
| 70 | 3-tier brain routing (ADR-16/18) | Dispatcher | OmniRoute `/v1` SSE chains | `src/gateway.py::OmniRouteClient` · `src/dispatcher.py` | ✅ | `tests/test_omniroute_gateway.py`, `tests/test_dispatcher.py`, `tests/test_chat_streamer.py` | Tier-1 router JSON verdict (<250 ms TTFT ack); quota/transient/fatal classified, mid-stream SSE errors never swallowed; router failure degrades to Tier 2 loudly |
| 71 | Deterministic keyword net (`_keyword_net`) | Dispatcher | Ordered regex net behind a router miss | `src/dispatcher.py::_TOOL_NET` (30+ entries) | ✅ (defect D fixed, uncommitted) | `tests/test_live_defects_2026_09_05.py`, `tests/test_dispatcher.py` | **Live defect D**: «اكتمي الصوت» misclassified as app-close (اكتم is a VOLUME verb, not a close verb) and raw URLs/Bitcoin/IP queries bypassed their dedicated tools. Fixed: priority-ordered net — multi_task (2+ verbs) → volume (اكتمي/اسكتي + الصوت) → media → screen_ocr → file_fetch → read_page (incl. bare URL) → prayer/currency/crypto/trending/network → close → web_search → youtube → weather → reminders → gmail/calendar/screenshot…; every coercion logged loudly |
| 72 | Tool narration envelopes + skill guides (M6) | Dispatcher | HEAVY tool lane | `src/dispatcher.py::_tool_skill_note`/`_tool_lane` | ✅ | dispatcher suite | Tool result is DATA («النتيجة فوق هي الحقيقة الكاملة»); per-tool vault guides ride the system prompt; launch returns None (coordinator already notified); multi_task + list_reminders stream as-is |
| 73 | Progressive chat delivery + re-split | Dispatcher | Telegram edit/splice | `src/skills/telegram_chat_streamer.py` · `src/bot.py` | ✅ | `tests/test_chat_streamer.py`, `tests/test_multi_bubble.py` | 750 ms coalescing, newer-message cancel, 2-3 bubble re-split |
| 74 | Google OAuth consent (single scope) | Dispatcher/Auth | Google OAuth 2.0 loopback flow | `src/google_auth.py::build_consent_url`/`AUTH_SCOPES` | ✅ (defect F fixed, uncommitted) 🔑 | `tests/test_live_defects_2026_09_05.py` (2), `tests/test_google_clients.py` | **Live defect F**: Google rejected «OAuth 2 parameters can only have a single value: scope» — scopes rode as repeated query params. Fixed: `" ".join(AUTH_SCOPES)` into ONE quoted param (`%20`-encoded); state CSRF compare_digest; Fernet-sealed atomic token cache; consent surface still needs the one-time owner bootstrap 🔑 |
| 75 | Owner middleware + whitelist guardrail floors | Dispatcher/Auth | Aiogram middleware | `src/middleware.py` · `bridge/guard.py` | ✅ | `tests/test_owner_middleware.py`, `tests/test_whitelist_guardrail.py` (SACRED) | Untouchable safety floor; fail-closed on corrupt whitelist with CRITICAL log |
| 76 | Consent grammar (standalone affirmative) | Dispatcher/Auth | Lexical gate | `common/consent.py::is_affirmative` | ✅ | `tests/test_consent_grammar.py` (sacred) | ≤3 tokens, no بس/لا/مش reservations; «نعم بس استنى» NEVER executes |
| 77 | Civ6 fair-play staging | Task Engine/Gaming | Fog-enforcer contract core | `src/skills/civ6.py` | ⏳ | `tests/test_civ6_staging.py` | Fair-play contract core landed; fog enforcer structural; awaits the Civ6 mod drop (owner-pending) |
| 78 | Speaker diarization (v1.1 suite) | Voice Pipeline | Energy windows + ECAPA clustering | `src/skills/speaker_diarization.py` | ✅ | diarization suite | Per-speaker dialogue turns on CPU; part of the §6c intelligence suite |

**Matrix totals: 78 features audited — 53 ✅ operational & tested (7 of them carrying an
uncommitted live-defect fix, ~8 carrying an owner-side 🔑 prerequisite), 24 ⏳ scaffolded/mocked
(the §7 adapter clusters, Instagram/Firecrawl, Civ6, live calls), 1 mixed guard (Gemini
exclusion ✅ inside the scaffolded registry). ZERO features remain in the ⚠️ state in code —
all six 2026-09-05 live defects are fixed in the working tree awaiting commit + owner live
retest.**

## 3. Detailed Root-Cause Analysis of the Verified Live Defects

> Evidence base: the owner live Telegram session of **2026-09-05**, the seven modified files in
> the working tree (`git status`: `bridge/executor.py`, `src/bot.py`, `src/dispatcher.py`,
> `src/external_apis.py`, `src/skills/weather.py`, `src/skills/web_intel.py`, `src/tools.py`),
> and the untracked regression floor `tests/test_live_defects_2026_09_05.py` (**39 collected
> test items** across defects A–G). For every defect below: symptom → root cause → the fix now
> standing in the tree → pinning tests.

### 3.1 Defect A — Windows Calculator UWP Close (`bridge/executor.py`)

- **Live symptom**: «سكري الآلة الحاسبة» → Sara answered «ما لقيت نسخة شغالة هسا» while BOTH
  calculator windows stayed open on screen. A claimed-nothing-found plus a still-running app.
- **Root cause (code-level)**: Windows 10/11 ships Calculator as a UWP app whose process image
  is **`CalculatorApp.exe`**, while the entire chain — `config/whitelist.json`
  (`{"name": "calculator", "executable": "calc.exe"}`), the legacy shortcut discovery, and the
  Arabic alias table in `pc_actions.py` — carries `calc.exe`. The close path built its kill
  list from the whitelist executable alone, so `taskkill /IM calc.exe` matched zero processes.
  The psutil verification then honestly reported `killed=0` — the verification worked; the
  kill list was wrong. The whitelisted-truth assumption («the whitelist's executable IS the
  image») is false for UWP apps in general.
- **Fix in the tree**: `PROCESS_IMAGE_ALIASES` map + `close_images(name, executable)` — the
  whitelist basename FIRST, then every known image alias, deduped case-insensitively,
  order preserved; unknown apps keep exactly one image (unchanged behavior). `close()` iterates
  the tuple and sums the psutil-verified kills.
- **Pinning tests** (6 in the live-defect floor): `test_calculator_close_targets_the_uwp_image`,
  `test_arabic_app_name_still_resolves_to_every_image` (Arabic alias → calculator → all images),
  `test_chrome_cmd_and_obsidian_aliases`, `test_unknown_app_gets_exactly_one_image`,
  `test_close_kills_the_running_uwp_calculator` (a fake psutil table that must really EMPTY),
  `test_close_reports_zero_when_nothing_runs`.
- **Residual risk**: other UWP apps (Photos, Settings, Store) may carry different image names —
  the alias table must grow per-app as the owner uses close on them.

### 3.2 Defect B — Amman Prayer Times Geocoding & Calculation (`src/external_apis.py`)

- **Live symptom**: «اوقات الصلاة» → wrong times (30–40 minutes drifted), or no answer at all.
- **Root cause (three stacked causes)**:
  1. **Textual geocoding ambiguity** — a city-name lookup for «Amman» is ambiguous in upstream
     gazetteers and can resolve toward the **Sultanate of Oman** (the country's egress in the
     name) — coordinates are the only unambiguous key.
  2. **Aladhan's own city tables drifted** — resolving by city name inside Aladhan produced
     times 30–40 minutes off for Amman.
  3. **Method + timezone + date gaps** — the old call used method 4 (Umm Al-Qura/Saudi — the
     wrong convention for Jordan; the owner ruled method **23**, the Hashemite Ministry of
     Awqaf, Fajr/Isha 18.0°), omitted `timezonestring` (silently shifting the whole day), and
     hit the DATE-LESS `/v1/timings` endpoint which answers **302** — the shared client does
     not follow redirects, so the call silently returned None and Sara reported nothing.
- **Fix in the tree**: module constants `AMMAN_LATITUDE=31.9539`, `AMMAN_LONGITUDE=35.9106`,
  `AMMAN_TIMEZONE="Asia/Amman"`, `AMMAN_UTC_OFFSET_H=3` (Jordan is UTC+3 permanent — DST
  abolished 2022 — so no tzdata dependency on the Windows bridge/slim containers),
  `PRAYER_METHOD="23"`, and `_prayer_date()` guaranteeing the explicit `DD-MM-YYYY` date
  segment (default = today in Amman) on `/v1/timings/{day}`.
- **Pinning tests** (6 in the live-defect floor):
  `test_prayer_times_anchor_to_exact_amman_coordinates` (no city name on the wire),
  `test_prayer_times_use_the_jordanian_awqaf_method` (method 23),
  `test_prayer_times_pin_the_amman_timezone`, `test_prayer_times_never_send_a_city_name`,
  `test_prayer_times_url_carries_a_date_segment` (`/v1/timings/DD-MM-YYYY`),
  `test_prayer_times_parsed_and_cached` (HH:MM five prayers + 24h TTL serves the second call) —
  plus `tests/test_external_apis.py`.

### 3.3 Defect C — Weather Geocode Loguru Crash (`src/skills/weather.py` ~line 129)

- **Live symptom**: an unresolvable place name («خريبة السوف»-style typo) killed the whole turn
  with a crash instead of an answer.
- **Root cause (two bugs compounding)**:
  1. **Empty-results-as-exception**: the geocoder indexed `results[0]` without guarding the
     common no-match case — Open-Meteo returns `{"results": []}` for a typo, so `IndexError`
     fired on the NORMAL path (not an exceptional one).
  2. **The loguru formatting bug that masked it**: the exception handler logged with a NAMED
     placeholder style (`logger.warning("... {place} ...")`) fed positional args — loguru
     raised `KeyError: 'place'` from INSIDE the except block, so the original honest-degrade
     path itself crashed and the owner saw the generic «صار في مشكلة».
- **Fix in the tree**: `results = json.loads(resp.text).get("results") or []` with an explicit
  empty branch that records the place in `self.unknown` and logs positionally
  (`logger.warning("geocode failed for {}: {}", place, error)`); `is_unknown_place()` lets the
  tool distinguish «الاسم غلط» from «الخدمة تعطّلت»; `_do_weather` answers
  «ما لقيت «X» على خريطة الطقس 🌸» for unknowns and the outage line otherwise.
- **Pinning tests** (4 in the live-defect floor, incl. one structural guard):
  `test_geocode_empty_results_returns_none_instead_of_indexerror` (a typo'd place → None),
  `test_unknown_place_is_flagged_and_named_in_the_reply` («خريبة السوف» named in the honest line),
  `test_weather_outage_still_uses_the_retry_line` (a DEAD service keeps «جربها بعد شوي» — the
  two failures never conflate),
  `test_no_mixed_loguru_format_strings_in_the_tree` (an AST/text sweep over `src/` + `bridge/`
  that fails on ANY recurrence of the named-placeholder + positional-args loguru mix).
- **Note**: the same KeyError-from-loguru-inside-except pattern was the ROOT of defect G's
  crash surface (`_do_create_folder`) — one sweeping lesson: NEVER use named placeholders with
  positional args in except-block logging.

### 3.4 Defect D — Dispatcher Keyword Collisions (`src/dispatcher.py`)

- **Live symptom (four collision classes from the same session)**:
  1. «اكتمي الصوت» was misclassified as an APP-CLOSE intent — Sara answered «الصوت مش موجود
     بالقائمة المعتمدة» (it tried to close an app literally named «الصوت») — the volume tool
     never fired.
  2. A raw pasted URL («https://adamlankamer.com/ai») with no verb fell through to a plain web
     search — Jina Reader never saw it.
  3. «شو سعر البيتكوين» / crypto asks bypassed the CoinGecko tool into generic chat.
  4. «شو رقم الايبي» / network asks likewise bypassed the IP tool.
- **Root cause (code-level)**: the Tier-1 router returned `tool="none"` (or an unknown tool)
  for these colloquial shapes, and the deterministic net either lacked entries for the
  external-API zones entirely (crypto/network/read_page) or ordered its regexes so a
  shared-word entry (close verbs) swallowed a sibling intent (volume). The net also treated
  «اكتمي الصوت»'s اكتم as a termination verb because close's verb class matched first.
- **Fix in the tree**: a priority-ordered `_TOOL_NET` with explicit precedence —
  multi_task (2+ action verbs + connector) FIRST, then **volume** (اكتمي/اسكتي/ارفعي/وطي +
  الصوت, or الصوت على N%) BEFORE media BEFORE screen_ocr BEFORE file_fetch BEFORE read_page
  (with the bare-URL alternative `https?://\S+`), then the M4 external zones
  (prayer_times → convert_currency → crypto_price → tech_trending → network_status), then
  close → web_search → youtube → weather → cancel/list_reminders → schedule → gmail →
  screenshot → calendar. Multi-action-verb coverage extended with the feminine control verbs
  (ارفعي/زيدي/كبّري/وطي/خفّضي/اكتمي/اسكتي/فكّي) and the post-waw hamza-drop stems (وفتحي…).
  Unknown router tool strings are logged loudly in `_parse_router`; every net coercion logs.
- **Pinning tests** (16 collected items in the live-defect floor):
  `test_bare_url_routes_to_the_jina_reader` (×3 real URLs, parametrized),
  `test_verb_led_url_still_routes_to_the_reader`, `test_volume_phrases_beat_the_app_launcher`
  (×5: اكتمي/وطي/ارفعي الصوت، الصوت على 40، حطي الصوت على ٧٠ — Arabic-Indic digits included),
  `test_crypto_questions_beat_plain_web_search` (×3), `test_ip_and_network_questions_route_to_
  network_status` (×4) — plus the dispatcher/net suites.

### 3.5 Defect E — Voice Note Synthesis Drop on Fish 429 (`src/bot.py`, `src/voice.py`)

- **Live symptom**: the owner explicitly demanded a voice note («ابعثي رسالة صوتية») while the
  Fish Audio free pool was 429-rate-limited — Sara silently degraded to a TEXT bubble. The
  demand's whole point (the audio bubble) evaporated without an honest word.
- **Root cause (code-level)**: the primary lane's failure path funneled every voice failure
  into the text flush (`send_split`) — there was no second synthesis lane and no distinction
  between an ORDINARY voice turn (where honest text is correct per the 2026-09-03 identity
  ruling: Fish only, no foreign voice) and a DEMANDED note (where the directive 2026-09-05
  P0-A says the bubble itself must arrive). Note the tension by design: `FishFirstVoice`
  re-raises for ordinary turns (no Edge fallback — identity purity), so a demanded note had
  nowhere to go but text.
- **Fix in the tree**: `src/bot.py::_speak_demanded(voice, edge, text, *, bot, chat_id)` —
  Fish tries ONCE → on ANY failure the local `edge_lane` (`VoicePipeline(ar-EG-SalmaNeural)`,
  built in `run_bot` and threaded through `_deliver_voice_reply`) synthesizes the SAME text →
  only a DOUBLE failure returns False (the honest apology, with a loud `logger.error`).
  Mid-stream: a failed tail tries Edge before any text. The 2026-09-03 no-fallback law stays
  for ordinary turns; a demand is the documented exception.
- **Pinning tests**: `test_demanded_note_falls_back_to_edge_when_fish_429s` (a
  `FishVoiceError("429…", retry_in_s=3600)` → Edge speaks the SAME text and the bubble
  dispatches), `test_demanded_note_reports_failure_only_when_both_lanes_die`, plus the
  `tests/test_bot_voice_demand.py` triangle (`test_demanded_note_fails_over_to_edge` ·
  `test_healthy_fish_never_touches_edge` · `test_both_engines_dead_honest_apology`) and the
  full-shell proof `test_shell_demand_fish_dead_edge_saves_the_bubble` (a SendVoice call still
  lands in the wire log).

### 3.6 Defect F — Google OAuth 400 Scope Encoding (`src/google_auth.py`)

- **Live symptom**: the one-time consent bootstrap died with Google's HTTP 400: «OAuth 2
  parameters can only have a single value: scope» — so no tokens were ever cached, which is
  ALSO the local cause of the live Gmail/Calendar offline answers (audit §14: vault/State
  empty).
- **Root cause (code-level)**: the consent-URL builder emitted the scopes as REPEATED query
  parameters (`scope=a&scope=b…`, the list-to-query duplication shape) instead of the
  RFC 6749 §3.3 form — ONE `scope` parameter carrying a space-separated scope list.
  Google's OAuth front-end enforces single-value semantics and rejects the repeated form with
  a 400 before the consent screen ever renders.
- **Fix in the tree**: `build_consent_url` now emits
  `scope=` + `urllib.parse.quote(" ".join(AUTH_SCOPES), safe="")` — exactly one `scope=`
  occurrence, spaces `%20`-encoded; `verify_state` guards the callback CSRF; tokens land in
  the Fernet-sealed atomic cache (`save_tokens`).
- **Pinning tests**: `test_consent_url_carries_exactly_one_scope_parameter` (parse_qs →
  `query["scope"] == [" ".join(AUTH_SCOPES)]`), `test_consent_url_scope_is_a_single_encoded_value`
  (`url.count("scope=") == 1`, `%20` present).
- **Downstream unlock**: this defect F was the gate hiding behind the 🔑 markers on features
  #1–#4 — once the owner re-runs the bootstrap, Gmail/Calendar/Tasks/Drive go live in one step.

### 3.7 Bonus Defect G — Vault Folder Crash (found in the same session)

Covered in matrix row #8: the loguru named-placeholder `KeyError:'name'` escaping the
`except` block of `_do_create_folder`, masking the honest Arabic failure line. Fixed with
positional logging + the honest line; pinned by three live-defect tests (honest failure ·
index-note creation · traversal sanitization).

## 4. Phased Execution Roadmap

> Sequenced P0 → P2, each step with its acceptance proof. The closed-loop discipline applies:
> every step carries its pre-specified tests, lands on `main`, and HALTS for the owner's
> «التالي» (except the already-completed remediation items marked ✅).

### Phase A — P0: Make Live Telegram Testing 100% Green (commit + verify + retest)

The six defects are fixed in code; what remains is SEALING and PROVING them:

- **A1 (P0) — Commit the live-defect remediation.** `git status` shows 7 modified files
  (`bridge/executor.py`, `src/bot.py`, `src/dispatcher.py`, `src/external_apis.py`,
  `src/skills/weather.py`, `src/skills/web_intel.py`, `src/tools.py`) and 1 untracked test
  file (`tests/test_live_defects_2026_09_05.py`). Land them as granular commits per defect
  (A, B, C+G, D, E, F — the branch directive: directly on `main`, pushed immediately),
  each with its pinning tests in the same commit. **Proof**: `git log` shows one commit per
  defect; `git status` clean (except the owner's `litellm_config.yaml`).
- **A2 (P0) — Full quality gate.** `make gate` on `py -3.12` (Ruff check + format, pytest,
  coverage ≥85%, security gate, docs guard). Verified in this audit: **851 passed / 1 skipped /
  85.35%**. **Proof**: gate output pasted in the task report.
- **A3 (P0) — Docs sync ride-along** (same commit as the behavior it describes): append the
  2026-09-05 live-defect arc to `.claude/PHASE-STATE.md`, `docs/10-CHECKPOINT.md`, and
  `CHANGELOG.md`; update `docs/06-API-SPECIFICATION.md` wire table with the volume/media/
  screen_ocr/file args + the `read_page` bare-URL form; RUNBOOK §Google-OAuth gains the
  re-bootstrap note (defect F fix live).
- **A4 (P0) — Owner live retest list** (the definitive green):
  1. «سكري الآلة الحاسبة» → both windows gone + the psutil-verified count line (A).
  2. «شو اوقات الصلاة اليوم» → five times matching the Awqaf calendar (B).
  3. «شو الطقس بخريبة السوف» → honest named-place line, no crash; «شو الطقس» → real numbers (C).
  4. «اكتمي الصوت» → volume drops; paste a bare URL → Jina summary; «شو سعر البيتكوين» →
     JOD price; «شو رقم الايبي» → IP line (D).
  5. «ابعثي رسالة صوتية» while Fish is 429-limited → ONE Edge voice bubble, never text (E).
  6. Re-run the Google consent bootstrap → consent screen renders, tokens cached (F).
  7. «انشئي فولدر RoutineTasks» → vault commit + wikilink (G).
- **A5 (P0, owner-side prerequisites riding the same session)**: OmniRoute up
  (`http://localhost:20128/v1/models` 200, pools non-empty) · Google OAuth bootstrap (A4-6
  unlocks Gmail/Calendar/Tasks) · `/enroll-voice` ≥5 s · optional `YOUTUBE_API_KEY` /
  `EXCHANGERATE_API_KEY`.

### Phase B — Tool Wiring: expose the scaffolded surface into `src/tools.py`

Ordered by owner value-per-effort; every step TDD (failing test first), behind CacheEngine
where a family applies:

- **B1 (P1) — Drive listing + file dispatch to the phone**: `GoogleSuite.list_drive_files` is
  built and tested but has no `_do_drive` handler nor router/net entry. Add a `drive` tool →
  honest top-N files → optional download via the existing `file_fetch` document surface.
  Wire `_VALID_TOOLS` + `_TOOL_NET` («ملفاتي بدرايف / جيبي ملف X من درايف»).
- **B2 (P1) — Contacts search**: `GoogleSuite.search_contacts` exists unexposed. Add a
  `contacts` tool («مين هو X بمعلوماتي») → one-line dossier answer; feeds the social graph.
- **B3 (P1) — Calendar/Tasks WRITE verbs**: `create_event`/`add_task` are unit-tested but the
  dispatcher only reads. Add `create_event`/`add_task` tools with a confirmation echo
  («سجلتها للتقويم: X على الساعة Y») — pure wiring + tests, no new backend code.
- **B4 (P2) — Places & Maps grounding (Cluster 3)**: wire the `places` + `maps_grounding`
  adapters behind the 7-day places cache family into a `places` tool («فين أقرب X»); static
  map URLs via `maps_sdk_android` (zero API calls). Needs Places API enablement (free tier).
- **B5 (P2) — Custom Search (Cluster 3)**: the 24h TTL + HARD-80/day budget machinery is
  built; add a `deep_search` tool as the DDG upgrade (CSE JSON API, free 100/day). Needs the
  CSE cx+key from the owner.
- **B6 (P2) — Fitness (Cluster 2)**: the 08:00/22:00 sync windows + 1h on-demand cache are
  enforced with no consumer. Add a `fitness` read + a morning-brief section rider. Needs
  Fitness scopes added to `AUTH_SCOPES` + re-consent.
- **B7 (P2) — BigQuery/Storage (Cluster 4, 14 adapters)**: first consumer (smallest
  abstraction): nightly `cloud_storage` backup of the `State/` directory (voiceprints already
  Fernet-sealed), then BigQuery for the app-usage analytics the bridge already collects. The
  rest stays scaffolded until a real consumer exists (ponytail ceiling — no speculative
  layers).
- **B8 (P3) — Observability (Cluster 5)**: surface `service_usage` free-tier percentages as a
  Sara command («شو حصة غوغل») + `cloud_logging` for the audit-ledger mirror. Remaining
  adapters stay scaffolded.
- **B9 (P3) — YouTube analytics/reporting daily 23:30 sync** once `YOUTUBE_API_KEY` is live
  (the cache family is already coded).
- **B10 (P3) — Staged integrations activation**: Instagram sandbox (`INSTAGRAM_SESSION`),
  Firecrawl (`FIRECRAWL_API_KEY`), Civ6 mod drop, PyTgCalls live calls
  (`TELEGRAM_USER_SESSION_STRING` — the 10-minute owner login), clip-farming only if the
  owner re-activates it (parked by directive, ZERO code).
- **B11 (P3) — UWP alias growth**: extend `PROCESS_IMAGE_ALIASES` per-app as live use
  surfaces them (Photos/Settings/Store), each with a one-line test.

### Phase C — Regression Gate: the verification protocol

Run in this exact order before any task can be reported done:

1. **Lint/format**: `make lint` (Ruff check + format check) — zero diffs.
2. **Full suite**: `make test` → `pytest -q` — currently **851 passed / 1 skipped**; any red
   blocks the merge (circuit breaker: 3 failed fix attempts on one defect = full halt + DIR).
3. **Coverage**: the ≥85% branch gate inside `make gate` — currently **85.35%**; new modules
   must not dilute it.
4. **Sacred floors**: `pytest tests/test_owner_middleware.py tests/test_whitelist_guardrail.py
   tests/test_guest_lockdown.py tests/test_consent_grammar.py` — 100% green, always.
5. **Live-defect floor**: `pytest tests/test_live_defects_2026_09_05.py` — 39 items green;
   any new live defect joins this file (never a private test).
6. **Docs + security gates**: the `make gate` docs-guard (canonical files) + security scan.
7. **Commit hygiene**: `.githooks` active (no Co-Authored-By trailers) · docs in the same
   commit as behavior · push to `main` immediately · a ≤5-line report WITH proof · HALT for
   «التالي».
8. **Per-sprint exit**: skill teardown protocol (`.claude/skills/*` wiped, outcomes recorded
   in `docs/10-CHECKPOINT.md`) + Guide review.

---

## 5. Closing Summary (one screen)

- **Topology verified**: Aiogram 3.x core + 3-tier OmniRoute brain behind the ADR-18
  dispatcher + TLS-WebSocket Windows bridge + git-backed Obsidian vault; Oracle one-container
  host; $0.00 structural (CacheEngine budgets + QuotaGuard), Gemini absent, owner-only with
  biometric composition.
- **78 features audited** across 7 categories; **53 ✅**, **24 ⏳ scaffolded** (mostly the §7
  41-adapter Google Cloud registry, which is deliberately spec-first), **0 left broken in
  code**.
- **All six 2026-09-05 live defects (A–F) + bonus G are fixed in the working tree**, pinned by
  39 regression items — the deliverable-critical next action is **committing them** and the
  owner retest list (Phase A).
- **Baseline verified today**: `pytest -q` → **851 passed / 1 skipped / 85.35% branch
  coverage** — gate green.
- **The single biggest unlock** is defect F: the OAuth single-scope fix turns every 🔑 Google
  feature live after the one-time bootstrap.

*End of artifact — awaiting owner review before any implementation pass begins.*

  psutil telemetry, minute-level app-usage tracking, WoL, volume/media/OCR, and two-way file
  dispatch — every action minting a `PC-YYYYMMDD-HHMMSS-4hex` audit code.
- **Knowledge base**: git-backed Obsidian vault (PARA + Zettelkasten) via GitHub Contents API
  (`src/vault.py`, 400 lines) — 5 mandatory directories + 2 profile files (first-boot guard
  tested), Fernet-sealed voiceprints under `State/`, Git Data API multi-file commits,
  1 MB pre-flight payload bound, `redact_secret` on every log/exception/URL path.

---
