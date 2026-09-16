---
tags: [architecture]
---

# Tools & API Compendium (2026-09-16)

> Executive summary: one navigable reference over the three specialist
> documents — what Sara can do (46 tools), what backends power it (APIs),
> and the proof each connection actually works. This page rolls up; the
> linked reports carry the full tables.

## The three pillars

- [Sara's Tools — Uses & Benefits](./SARA_TOOLS_USES_AND_BENEFITS.md) — plain-language Use + Benefit per tool, by family (Workspace 11 · PC & bridge 13 · Knowledge 4 · Web & daily life 9 · OpenClaw 4 · Cloud & self 5).
- [API Wiring & Usage Audit](./API_WIRING_AND_USAGE_AUDIT.md) — every external service → module → env key → LIVE/READY/STAGED status (names only, no secrets).
- [Tool Connection Matrix](./TOOL_CONNECTION_MATRIX.md) — per-tool backend, suite proof, live status; 46/46 connected-path tested.

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

## See also (graph links)

- [04 — System Architecture](../04-ARCHITECTURE.md)
- [12 — Security](../12-SECURITY.md)
- [Map of Architecture](../00-MAP-OF-ARCHITECTURE.md)
