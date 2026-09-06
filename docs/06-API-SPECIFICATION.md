# 06 — API Specification: PC Bridge & Vault Write Surfaces

Machine-facing contracts realized in sprint 3 (§3.1–§3.4): the core↔bridge wire
protocol, the PC command catalog, the confirmation/audit lifecycle, the vault-record
schemas, and the owner-intent tool surface. Implemented by `common/protocol.py`,
`bridge/*`, `src/pc_actions.py`, `src/vault.py`; the tests in `tests/` are the
executable form of this document.

## 1. Wire protocol (core ↔ bridge tunnel)

Transport: ONE JSON document per WebSocket text frame. The core LISTENS on its single
public port (ADR-15, path `/bridge`); the daemon dials OUT — the PC holds zero inbound
ports. Token auth only (the tunnel rides the host's TLS termination — Caddy 2 on the
Oracle VM, ADR-15 as amended 2026-08-31).

Constants (`common/protocol.py`):

| Constant | Value | Meaning |
|---|---|---|
| `PROTOCOL_VERSION` | 1 | every frame carries `v`; mismatch → ProtocolError |
| `HEARTBEAT_INTERVAL_S` | 15 | daemon app-level heartbeat cadence |
| `DEAD_PEER_MULTIPLIER` | 3 | peer silent > 45 s is dropped |
| `AUTH_TIMEOUT_S` | 10 | Hello must arrive within 10 s of connect |
| `MAX_FRAME_BYTES` | 1_048_576 | 1 MiB frame cap |
| `BACKOFF_CAP_S` | 30.0 | reconnect backoff ceiling (exponential, ±20% jitter, reset on a full session) |

Handshake:

1. Daemon → core: `Hello {v:1, token, hostname}` — the token travels ONLY here and is
   never logged (`security_log` records the peer IP and the verdict, not the secret).
2. Core → daemon: `HelloAck {v:1, ok, reason?}`.
3. Bad token → close **4401**. Second session while one is active → `ok:false
   "another_session_active"` + close **4400**. Slow/invalid Hello → close **4400**.

Envelopes (both directions after auth):
`Envelope {v, id, type: heartbeat|cmd|result|event, ts, cmd?, args?, status: ok|error?, payload?}`

- `type:"cmd"` — core → daemon; `cmd` ∈ catalog (§2); results correlate by `id`.
- `type:"result"` — daemon → core; `status` mirrors the ExecResult; `payload` IS the
  ExecResult model dump.
- `type:"heartbeat"` — counted by the core; drives the silence watchdog.
- Results for unknown ids are dropped with a WARN — never crash the session.

## 2. Command catalog

| cmd | args | Guard rule | Result |
|---|---|---|---|
| `exec.launch` | `name`, `confirmation_id?`, `audit_code?` | whitelist `auto_approve` OR live `confirmation_id` | ExecResult |
| `exec.open` | `path`, `confirmation_id?`, `audit_code?` | blocked suffix → refuse; UNC / relative traversal → `outside_allowed_roots` | ExecResult |
| `exec.close` | `name`, `confirmation_id?`, `audit_code?` | whitelist `auto_approve` OR live `confirmation_id` (closing is destructive on the live session — same gate as launching; v2.0 pass-1) | ExecResult; `taskkill /IM <image> /F /T` over EVERY image the app runs as (`close_images` UWP alias table — CalculatorApp.exe/Calculator.exe/calc.exe, live defect A 2026-09-05) + psutil-VERIFIED `killed_processes` (poll ≤2 s) |
| `exec.screenshot` | `audit_code?` | read-only capture, no confirmation | ExecResult with `detail` = base64 JPEG (Pillow `ImageGrab`, ≤1600px, quality 70, **entirely in memory — zero disk writes**, v2.0 pass-1) |
| `exec.list_apps` | `audit_code?` | none — read-only running-process report (STT-2, no confirmation gate) | ExecResult; `detail` = the process list (whitelisted exes carry their owner display name, gap-ج) |
| `exec.volume` | `action` (mute/unmute/up/down/set), `level?`, `audit_code?` | none — key-event effect (VK_VOLUME_* via ctypes user32, $0.00) | ExecResult; set-X% = X/2 VOLUME_UP presses (Windows steps 2%) |
| `exec.media_control` | `action` (play_pause/pause/play/next/prev), `audit_code?` | none — key-event effect (VK_MEDIA_*) | ExecResult |
| `exec.screen_ocr` | `audit_code?` | read-only capture + vision extraction | ExecResult; `detail` = verbatim code/text extraction (the OCR prompt forbids conversational filler) |
| `file.upload` | `name`, `payload` (bytes), `audit_code?` | basename-only sanitize (`sanitize_filename`); lands in the FIRST file root (Downloads) | ExecResult; traversal/absolute names reduce to the basename — the root decides location |
| `file.download` | `path`, `audit_code?` | `resolve_in_roots` (traversal/absolute-outside refused); sensitive suffixes blocked | ExecResult; `detail` = base64 of the file bytes |
| `power` | `action`, `confirmation_id` (MANDATORY), `audit_code?` | action in whitelist AND id present — ALWAYS, regardless of any whitelist flag | ExecResult |
| `wol` | `mac`, `ip?=255.255.255.255`, `port?=9` | stateless UDP, one sendto, SO_BROADCAST | ExecResult |
| `telemetry.state` | — | none — read-only snapshot | `LiveState` (`bridge/telemetry.py`); unmeasurable metrics arrive `null`, never a crash |
| `telemetry.app_sessions` | — | none — read-only report | day report: `apps[]` (name/minutes/sessions/first_seen/last_seen), `categories` (Games/Programming/Study/Productivity/Unknown), `total_minutes`, `screen_hours`, `boot_log[]` (v2.0 pass-1 §3-د/3) |

**App-session tracking source**: the daemon samples the foreground window title once
per minute (`user32.GetForegroundWindow`, no new dependency) into
`AppSessionTracker` (`bridge/app_sessions.py`); whitelist `category` fields bucket
apps (Games/Programming/Study/Productivity; uncategorized → Unknown, never a guess).
Locked/idle screens and unreadable titles are gaps, not zero-minute rows. State
persists per local day under `data/app_sessions/` (machine-scoped, gitignored) so a
daemon restart keeps the day's minutes; a new local day starts at zero.

**Force semantics: DROPPED** — no force flag exists on any surface. Anything outside
`config/whitelist.json` — and EVERY power action — needs an owner confirmation on
Telegram (CLAUDE.md rule 4; no exceptions, no bypass). Missing executable → detail
«البرنامج مش موجود عالجهاز». Spawns are detached, `shell=False`,
`CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS`.

## 3. Confirmation ID + audit code lifecycle

- `confirmation_id = uuid4().hex[:12]` — minted core-side at approval time.
- `audit_code = "PC-" + YYYYMMDD + "-" + HHMMSS + "-" + 4hex`
  (`bridge.executor.mint_audit_code`).
- ONE audit code chains the whole event: Confirmations note → command args →
  ExecResult → owner-facing Telegram message (quotable: «رمز التدقيق PC-…»).
- **Note-before-command**: the Confirmations note is persisted to the vault BEFORE the
  command leaves the core — approval without audit is void.
- The daemon refuses unconfirmed non-whitelisted commands even from a compromised core
  (defense in depth: the guard re-checks on the PC side).

## 4. Data-model schemas (vault records)

Confirmations note — `Confirmations/YYYY-MM-DD_<id8>.md`:

```yaml
---
type: pc-confirmation
confirmation_id: <uuid4 hex, 12 chars>
audit_code: <PC-YYYYMMDD-HHMMSS-4hex>
kind: launch|power
target: <app name | power action>
confirmed_at: <ISO-8601 UTC>
---
```

Audit ledger — `04_Archives/Audit/pc-ledger.md`, one line per event, append-only:

```
<ISO-8601 ts> | <audit_code> | <action> | <outcome: executed|refused|error> | <reason>
```

ExecResult (`bridge/executor.py`): `{status: ok|error, detail: str, audit_code: str,
killed_processes: int}` — `killed_processes` carries the psutil-VERIFIED termination count
of `exec.close` (0 on any other action).

## 5. LAN surface (daemon side)

`LanServer` binds loopback/LAN — NEVER 0.0.0.0. Routes:

- `GET /health` → 200 `{"status":"ok"}`.
- `GET /telemetry/live-state` → Bearer `BRIDGE_TOKEN` (401 without/wrong header;
  404 when no provider is wired) → 200 `LiveState` JSON (`psutil` snapshot: cpu,
  ram, C:/D: disks, uptime, top-CPU process; degraded fields `null`).

Telemetry narration contract (core side): `TelemetryClient` (`src/telemetry.py`) —
`fetch_state` rides the tunnel cmd and pydantic-validates; `narrate` makes ONE Tier-1
FAST call with the state JSON as DATA (numbers verbatim, display-only output,
temperature 0) and falls back to a deterministic numeric Arabic line on brain failure;
`report` catches `BridgeOffline`/`TimeoutError`/`ValidationError` →
«الجسر مو متصل هسا» — never raises to the chat layer. The payload carries no secrets
(no token, no hostname, no file paths).

## 6. Owner-intent tool surface (what Sara's tool calls map to)

| Tool | Implementation | Safety chain |
|---|---|---|
| `launch_desktop_app(name)` | `PCActionCoordinator.request_launch(origin="owner_chat")` | origin gate → daemon guard → confirmation prompt → ExecResult |
| power action (shutdown/restart/sleep) | `request_power` / `handle_idle_choice` («نوم»/«اطفاء») | ALWAYS a confirmation id + audit code |
| `save_obsidian_note(...)` | `VaultClient.upsert/upsert_note/append_section/commit_files` (3.1) + `VaultExpander.expand` (3.2) | one auditable vault commit per structural change; PARA backbone is expansion-only |
| `open_path(path)` | daemon `exec.open` | suffix/UNC/traversal checks; executables must go through the whitelist |
| `screenshot` (v2.0 pass-1) | `ToolRegistry._do_screenshot` → tunnel `exec.screenshot` → conversation-lane vision (`image_url` data-URI, m3) | read-only capture; image is DATA (prompt-pinned containment); offline → «الجسر مو متصل هسا», model failure → honest apology |
| `app_sessions` (v2.0 pass-1) | `ToolRegistry._do_app_sessions` → tunnel `telemetry.app_sessions` → short warm narration quoting the report's numbers verbatim | read-only report; numbers are DATA; deterministic numeric report is the fallback when the brain is down |
| close app («سكري…», v2.0 pass-1) | daemon `exec.close` (`taskkill /IM <image> /F`) | SAME gate as launching: whitelist auto_approve OR live confirmation id; audit code every time |
| `schedule` (v2.0 pass-2) | `ScheduledTasksEngine.create_task` — ONE note in `01_Projects/Scheduled_Tasks/` + both Google mirrors | vault-first: the note lands BEFORE any cloud write; `[sara:task:id]` idempotence tag; Google down = parked + ~10-min catch-up loop |
| `knowledge_graph` (v2.0 pass-2) | `build_graph` over a vault snapshot (`VaultClient.list_dir` + reads) — pure local index, zero LLM | read-only; DATA brief (backlinks/neighbors/orphans) quoted verbatim; scan failure = honest degrade line |
| `web_search` (v2.0 pass-4) | `WebIntel.search` — DuckDuckGo HTML endpoint, keyless | real titles/links only; empty-on-failure; results wrapped DATA (untrusted boundary) |
| `weather` (v2.0 pass-4) | `WeatherClient.current` — Open-Meteo (free, keyless; Google Weather API is paid → excluded by $0.00) | static Jordan coords; geocode-once cache; real numbers verbatim |
| `youtube` (v2.0 pass-4) | `YouTubeClient.search` — Data API v3 (10k units/day free) | env-gated `YOUTUBE_API_KEY`; quota failures logged loudly, honest offline line |
| staged §7 surfaces (pass-4) | Instagram sandbox (`InstagramSandbox`), Firecrawl REST (`FirecrawlClient`), Civ6 contract core (`civ6.py`) | live the moment the owner drops credentials in `.env`; sandbox results always labeled `sandbox=True`; Civ6 fog enforcer strips hidden state structurally |
| `close` (2026-09-04 §2) | keyword net close-verbs -> `PCActionCoordinator.request_close` -> daemon `exec.close` | SAME whitelist gate as launch; taskkill /IM /F /T over EVERY UWP image (`close_images` alias table) + psutil-VERIFIED count; the owner line carries the verified numbers; killed=0 keeps its own honest line |
| `volume`/`media`/`screen_ocr`/`file_fetch`/file upload (M2, 2026-09-05 §3) | `ToolRegistry._do_volume/_do_media/_do_screen_ocr/_do_file_fetch` -> daemon `exec.volume`/`exec.media_control`/`exec.screen_ocr`/`file.download`; attachments ride `file.upload` | key-event + read-only capture surfaces (no confirmation gate); file surfaces are root-walled (traversal dies); OCR returns verbatim extraction only |
| external APIs (M4, 2026-09-05 §4) | `ExternalAPIs` — Aladhan `/v1/timings/{DD-MM-YYYY}` (Amman EXACT coords `31.9539,35.9106`, `Asia/Amman`, Awqaf method 23, 24h TTL) · ExchangeRate v6 pair (env key, 1h TTL) · CoinGecko simple/price (JOD, 15m TTL) · Hacker News topstories · ip-api | prayer never sends a city name; currency/crypto/network/HN all degrade to the honest offline line on timeout/HTTP-failure — never a fabricated number |
| `read_page` (live 2026-09-05 D) | Jina Reader `https://r.jina.ai/{target}` — the net captures bare pasted URLs AND verb-led forms («اقراي https://…») | non-URL arg asks for the full link; bounded 1,200-char head; failures degrade honestly |
| demanded voice notes (P0-A, 2026-09-05) | `bot._speak_demanded` — Fish tries once -> LOCAL Edge-TTS lane synthesizes the SAME text -> only a double failure lands the honest apology | a demanded note NEVER lands text-only; ordinary turns keep the Fish-only identity law (no foreign voice) |
| timed reminders (2026-09-04 §5) | `task_orchestrator.Orchestrator` — parse_delay/parse_wallclock (GENERAL shapes) -> asyncio timers | state persists (State/task_reminders.json, restart re-arms); firing dispatches proactively via bot.send_message; dispatch failure retries in a minute — never silent |
| `create_folder` (2026-09-04 §6) | `ToolRegistry._do_create_folder` — ONE `_index.md` commit (contents API creates the dir) | name sanitized by the vault's `_sanitize_component` (traversal dies); idempotent; PARA backbone additive-only |
| Google 41-API suite (2026-09-04 §7) | `google_cloud_suite` — 41 typed adapters (Gemini EXCLUDED) behind CacheEngine + QuotaGuard | cache-first: weather 6h/4-day, places 7d, custom search 24h + HARD 80/day, fitness 08:00/22:00 + 1h, YT analytics daily; >90% free-tier = breaker open (cache-only); spent budgets = honest no-call |

Origin gate: `RefusedOrigin` for any origin ≠ `owner_chat` — untrusted content (email
bodies, web pages, vault parses) is DATA and never mints PC intent (CLAUDE.md rule 7).
