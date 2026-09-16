---
tags: [architecture]
---

# Tools & API Compendium (2026-09-16)

> Executive summary: one navigable reference over tools and APIs — what Sara
> can do (46 tools with uses + benefits), what backends power it, and the
> proof each connection works. Consolidated 2026-09-16: absorbs the pruned
> uses-catalog, wiring audit, and connection matrix (history in git).

## 46 tools — uses & benefits (absorbed 2026-09-16)

### Workspace (Google suite)

| Tool | Use | Benefit |
|---|---|---|
| `gmail` | Unread-mail digest with sender + subject | Triage the inbox in one glance |
| `calendar` | Next-24 h agenda, Amman-local times | Never miss or double-book |
| `tasks` | Today's due tasks | Focus list without opening apps |
| `create_event` / `create_task` | Book Calendar entries / Google Tasks from chat | Scheduling in one sentence |
| `schedule` / `list_reminders` / `cancel_reminder` | Timed + scheduled nudges, read-back, cancel | Right nudge at the right hour |
| `drive` | Drive search by name with links | Any file in seconds |
| `contacts` | Contact card (phone/email) lookup | Reach anyone without digging |
| `brief` | Morning brief: agenda + tasks + critical mail | Start briefed like an executive |

### PC & bridge (confirmation-gated daemon)

| Tool | Use | Benefit |
|---|---|---|
| `telemetry` / `running_apps` / `app_sessions` | Live CPU/RAM, open apps, usage report | Know the machine's state instantly |
| `whitelist_apps` | Reads the real launch allowlist | Transparency on what Sara may open |
| `launch` / `close` | Open apps (Arabic aliases) / verified termination | Works safely — actually closed, not "probably" |
| `open_path` / `file_save` / `file_fetch` | Files/folders in allowed roots, both directions | Jump to / send any document by voice |
| `screenshot` / `screen_ocr` | In-memory capture / verbatim code-error extraction | Eyes + reading on the PC from anywhere |
| `volume` / `media` | Audio + playback control | Hands-free control mid-task |

### Knowledge, web & daily life

| Tool | Use | Benefit |
|---|---|---|
| `knowledge_graph` / `create_folder` / `read_page` / `deep_search` | Vault relations, folder growth, clean URL reads, grounded search | Navigate memory; answers with sources |
| `web_search` / `weather` / `youtube` / `tech_trending` | Live search, Open-Meteo, Data API v3, Hacker News | Current facts first try |
| `crypto_price` / `convert_currency` / `prayer_times` / `network_status` / `places` | Market, travel math, prayers, connectivity, venues | Daily-life answers instantly |

### OpenClaw substrate, cloud & self

| Tool | Use | Benefit |
|---|---|---|
| `openclaw_inspect` / `openclaw_desktop` / `openclaw_fetch` / `openclaw_browse` | Desktop transcript, actuation probe, safe reads, isolated browsing | Observed automation, real profile untouched |
| `cloud_backup` / `analytics` / `quota_safety` / `fitness` / `multi_task` | Encrypted snapshots, life rows, $0.00 headroom, health, multi-errand plans | Memory survives; cost visibly zero |

## Rollup: backend → tools → key → status

| Backend / API | Tools powered | Key | Status |
|---|---|---|---|
| OmniRoute (Groq + OpenRouter pools) | All chat, narration, triage refinement, vision lane | `OMNIROUTE_API_KEY`, `GROQ_API_KEY`, `OPENROUTER_API_KEY` | Keys set; gateway down → DEGRADED |
| Gmail/Calendar/Tasks/Drive/People (OAuth) | gmail, calendar, tasks, brief, schedule, drive, contacts, create_event/task, fitness | OAuth client + sealed token | Ready (polling-only) |
| Fish Audio (via OpenRouter speech) | Voice replies (sole engine) | `FISH_AUDIO_API_KEY` | Ready; 429 → honest text |
| Local Whisper (faster-whisper int8) | Voice transcription → vault memos | `WHISPER_MODEL_SIZE` | Ready |
| YouTube Data v3 | youtube | `YOUTUBE_API_KEY` | Ready |
| Open-Meteo / DDG (keyless) | weather, web_search, read_page, deep_search fallback | — | Live-capable |
| ExchangeRate | convert_currency | `EXCHANGERATE_API_KEY` | Ready |
| Places (New) / Firecrawl / Instagram | places, deep_search upgrade, social | keys missing | Staged adapters |
| GCS / Logging / BigQuery family | cloud_backup, analytics, quota_safety (+30 registered) | Cloud project | Ready / Registered |
| GitHub Contents API | Vault transport (PARA+Zettel) | `VAULT_GITHUB_TOKEN` | Ready |
| Bridge WSS + Bearer | Telemetry, apps, launch/close, files, screenshot/OCR, OpenClaw verbs | `BRIDGE_TOKEN` | Needs daemon live |
| Telegram Bot API | Chat + voice transport | `TELEGRAM_BOT_TOKEN` | **LIVE** (`@Sara_Vantrilex_bot`) |

## Appendix — credential posture (names only)

`.env`: 47 keys set; empty only `TELEGRAM_USER_SESSION_STRING`,
`OBSIDIAN_API_KEY`. Present on disk: OAuth client JSON, sealed token cache,
gmail state, voiceprint. Missing: Firecrawl, Places, Instagram session,
PubSub topic. Rotate: exposed OpenRouter key, GitHub PAT, Telegram API_HASH.

## Connection proof (absorbed 2026-09-16)

46/46 tools connected-path tested in-suite (`test_tools.py`,
`test_tools_expansion.py`, `test_tool_coverage_gaps.py` for `file_save` +
`screen_ocr`, bench + protocol suites for the rest); every handler degrades
to an honest Arabic line on missing backends with zero crashes. Live posture:
Telegram **LIVE**; gateway down (tiers DEGRADED); OAuth ready; YouTube/Fish/
ExchangeRate keys set; Places/Firecrawl/Instagram keys missing; Open-Meteo/DDG
keyless. No code gaps — blockers are hosts and credentials only.

## See also (graph links)

- [04 — System Architecture](../04-ARCHITECTURE.md)
- [12 — Security](../12-SECURITY.md)
- [Map of Architecture](../00-MAP-OF-ARCHITECTURE.md)
