---
tags: [testing]
---

# Tool Connection Matrix — 46/46 verified (2026-09-16)

> Proof tiers per tool: **TESTED-CONNECTED** (a suite test drives the backend
> seam with fakes) · **TESTED-DEGRADED** (honest offline line asserted).
> Live-API posture from the
> [API Wiring Audit](./API_WIRING_AND_USAGE_AUDIT.md): Telegram LIVE,
> gateway down (LLM tiers DEGRADED), OAuth ready, YouTube/Fish/ExchangeRate
> keys set, Places/Firecrawl/Instagram keys missing, Open-Meteo/DDG keyless.
> Coverage audit 2026-09-16 found 44/46 tools called in-suite; the 2 gaps
> (`file_save`, `screen_ocr`) are closed by `tests/test_tool_coverage_gaps.py`.

## Google-backed (OAuth sealed token present)

| Tool | Backend | Suite proof | Live |
|---|---|---|---|
| `gmail`, `calendar`, `tasks`, `brief` | Gmail/Calendar APIs + triage/composer | `test_tools.py` (rich + offline legs) | Ready (polling-only) |
| `drive`, `contacts`, `create_event`, `create_task` | Drive/People/Calendar/Tasks APIs | `test_tools_expansion.py` (rich + offline) | Ready |
| `schedule`, `list_reminders`, `cancel_reminder` | Task engine + suite | `test_task_orchestrator.py`, `test_reminder_live.py`, `test_reminder_manage.py` | Ready |

## Bridge-backed (daemon WSS + Bearer; daemon offline at audit)

| Tool | Backend | Suite proof | Live |
|---|---|---|---|
| `telemetry`, `running_apps`, `app_sessions` | Tunnel telemetry verbs | `test_tools.py`, `test_running_apps*.py`, `test_app_sessions_narration.py` | Needs daemon |
| `launch`, `close` | Guard + executor over tunnel | `test_tools.py`, `test_close_routing.py` | Needs daemon |
| `screenshot`, `screen_ocr` | `exec.screenshot` / `exec.screen_ocr` verbs | `test_*screenshot*.py`, `test_tool_coverage_gaps.py` | Needs daemon |
| `volume`, `media` | Executor key-event verbs | `test_bridge_extensions.py` | Needs daemon |
| `open_path`, `file_fetch`, `file_save` | Typed file verbs + roots/type walls | `test_open_path_tool.py`, `test_bridge_extensions.py`, `test_tool_coverage_gaps.py` | Needs daemon |
| `whitelist_apps` | Guard read | covered (offline + narration tests) | Needs daemon |
| `openclaw_desktop/fetch/inspect/browse` | OpenClaw tunnel verbs | suite bench + protocol tests | Staged (bench harness) |

## Keyless live-capable (no secret; needs network only)

| Tool | Backend | Suite proof | Live |
|---|---|---|---|
| `web_search`, `read_page`, `deep_search` | DDG html / Jina / Custom Search w/ DDG fallback | `test_external_apis.py` | Capable |
| `weather` | Open-Meteo geocode + forecast | `test_live_defects_2026_09_05.py`, `test_tools.py` | Capable |
| `prayer_times`, `convert_currency`, `crypto_price`, `tech_trending`, `network_status` | Bundled public endpoints (ExchangeRate keyed) | `test_external_apis.py` | Capable/Ready |

## Key-gated staged (adapter written, key missing)

| Tool | Backend | Suite proof | Live |
|---|---|---|---|
| `places` | Places (New) `searchNearby` | offline leg; adapter unit-tested | **Missing `GOOGLE_PLACES_KEY`** |
| `youtube` | Data API v3 (env-gated client) | `test_google_extras.py` (rich) | Ready (`YOUTUBE_API_KEY` set) |
| `fitness` | Fitness API adapter | adapter tests | Ready (OAuth) |
| `cloud_backup`, `analytics`, `quota_safety` | GCS / life-analytics / quota guard | offline + registry tests | Ready (project) |

## Vault/memory/knowledge (local-first)

| Tool | Backend | Suite proof | Live |
|---|---|---|---|
| `knowledge_graph` | Vault snapshots over `VaultIndex` | `test_tool_lane_pass2.py`, `test_knowledge_graph.py` | Live (local) |
| `create_folder` | Vault writer + traversal wall | `test_dynamic_folders.py`, `test_live_defects_2026_09_05.py` | Live (local) |
| `multi_task` | Agent manager over the real tool set | `test_agent_manager.py` | Live (local) |

## Verdict

**46/46 tools**: connected-path tested, honestly degrading, honestly documented.
Zero tools call unmocked networks in-suite; zero tools lack a backend seam.
Live blockers are credentials/hosts only: OmniRoute down, bridge daemon down,
3 missing optional keys — no code gaps remain.

## See also (graph links)

- [API Wiring & Usage Audit](./API_WIRING_AND_USAGE_AUDIT.md)
- [Sara's Tools — Uses & Benefits](./SARA_TOOLS_USES_AND_BENEFITS.md)
- [11 — Testing](../11-TESTING.md)
- [Map of Testing & Audits](../00-MAP-OF-TESTING-AND-AUDITS.md)
