---
tags: [architecture]
---

# Sara's Tools — Uses & Benefits (46 tools)

> User-facing companion to the audit-grade
> [Full System Audit](./SARA_FULL_SYSTEM_AUDIT_AND_LIVE_BENCHMARK_REPORT.md)
> (§45-tool catalog) and the
> [API Wiring Audit](./API_WIRING_AND_USAGE_AUDIT.md). Every tool below is
> dispatched by Sara autonomously from natural Jordanian phrasing — Omar never
> names tools, only goals.

## Workspace (Google suite)

| Tool | Use | Benefit |
|---|---|---|
| `gmail` | Unread-mail digest with sender + subject lines | Triage the inbox in one glance, hands-free |
| `calendar` | Next-24 h agenda with Amman-local times | Never miss or double-book a meeting |
| `tasks` | Today's due tasks | Daily focus list without opening apps |
| `create_event` | Books a Calendar entry from chat («سجلي موعد») | Scheduling in one sentence |
| `create_task` | Inserts into Google Tasks | Capture todos before they evaporate |
| `schedule` | Smart reminders: timed lane + scheduled lane | The right nudge at the right hour |
| `list_reminders` | Reads back armed reminders | Full visibility of pending nudges |
| `cancel_reminder` | Cancels by id or sweeps all | One-word cleanup |
| `drive` | Searches Drive by name, returns links | Any file in seconds |
| `contacts` | Compact contact card (phone/email) lookup | Reach anyone without digging |
| `brief` | Morning brief: agenda + tasks + critical mail | Start the day briefed like an executive |

## PC & bridge (Windows daemon, confirmation-gated)

| Tool | Use | Benefit |
|---|---|---|
| `telemetry` | Live CPU/RAM readout narrated in Arabic | Know the machine's state instantly |
| `running_apps` | Names every running app | See what's open without looking |
| `app_sessions` | Minute-level usage report | Where did the day actually go |
| `whitelist_apps` | Reads the real launch allowlist | Transparency on what Sara may open |
| `launch` | Opens whitelisted apps (Arabic aliases; `cmd` confirm-gated) | «افتحي الآلة الحاسبة» just works — safely |
| `close` | Real process termination, psutil-verified count | Actually closed, not "probably closed" |
| `open_path` | Opens files/folders inside allowed roots | Jump to any document by voice |
| `screenshot` | In-memory full-screen capture, zero disk writes | Eyes on the PC from anywhere |
| `screen_ocr` | Verbatim code/terminal/error extraction to the vision lane | Read the error without retyping it |
| `volume` | Mute/up/down/set-X% via key events | Hands-free audio control |
| `media` | Play/pause/next/previous | Control playback mid-task |
| `file_save` | Phone → PC file drop into Downloads | Send yourself files effortlessly |
| `file_fetch` | PC → phone file read (roots + type wall enforced) | Pull any allowed file remotely |

## Knowledge, memory & vault

| Tool | Use | Benefit |
|---|---|---|
| `knowledge_graph` | Relations web («مين بيحكي عن مين») over the vault | Navigate memory, not noise |
| `create_folder` | Dynamic Obsidian folder creation | Vault grows with the work |
| `read_page` | Clean Markdown of any URL into context | Read the article, skip the clutter |
| `deep_search` | Google Custom Search (keyless DDG fallback) | Grounded answers with real sources |

## Web, media & daily life

| Tool | Use | Benefit |
|---|---|---|
| `web_search` | Live keyless web search | Current facts, no hallucination |
| `weather` | Open-Meteo conditions for any city | Dress and plan right |
| `youtube` | Data API v3 video search | The right video first try |
| `tech_trending` | Top Hacker News stories + links | Stay current in one message |
| `crypto_price` | Coin prices, JOD default | Market glance |
| `convert_currency` | Amount + currency parsing | Travel/shop math instantly |
| `prayer_times` | Amman's five daily prayers | Never miss a prayer |
| `network_status` | Core egress IP/ISP/city/proxy | Diagnose connectivity fast |
| `places` | Nearby cafés/restaurants with ratings + navigation | «وين في كافيه» answered properly |

## OpenClaw desktop substrate

| Tool | Use | Benefit |
|---|---|---|
| `openclaw_inspect` | Full diagnostic transcript (screenshot + foreground + OCR) | Sara sees the desktop like you do |
| `openclaw_desktop` | Desktop actuation entry (screenshot probe) | Observed automation, staged safely |
| `openclaw_fetch` | Read-only page retrieval | Safe web reads through the tunnel |
| `openclaw_browse` | URL navigation in the isolated browser | Real profile never touched without opt-in |

## Cloud, safety & self-knowledge

| Tool | Use | Benefit |
|---|---|---|
| `cloud_backup` | Encrypted vault snapshot to GCS | Memory survives anything |
| `analytics` | Life-analytics rows (screen/app rhythms) | Quantified self, honestly measured |
| `quota_safety` | Free-tier headroom within $0.00 | The zero-cost invariant, visibly held |
| `fitness` | Steps, active minutes, calories | Health glance |
| `multi_task` | Decomposes multi-part requests (HEAVY plan, MEDIUM narration) | One message, many errands, tracked |

## See also (graph links)

- [Full System Audit & Live Benchmark](./SARA_FULL_SYSTEM_AUDIT_AND_LIVE_BENCHMARK_REPORT.md)
- [API Wiring & Usage Audit](./API_WIRING_AND_USAGE_AUDIT.md)
- [04 — System Architecture](../04-ARCHITECTURE.md)
- [Map of Architecture](../00-MAP-OF-ARCHITECTURE.md)
