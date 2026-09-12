# Vantrilex Assistant OS (Sara) — Project Ideas Compendium

> Single-file inventory of every idea, component, paradigm, and tool in use.
> Generated 2026-09-12. Source of truth for architecture + new 3-tier autonomy framework.
> Workspace: `C:\Projects\Git-hub\Vantrilex Assistant OS\Vantrilex Assistant OS - Architecture & Docs`

---

## 1. Identity & Mission

- **Sara (سارة)** — owner-only, strictly-zero-cost ($0.00/month) executive AI assistant.
- **Role hierarchy:** Leader (Owner) → Guide (Spec/gates) → Implementer (agents).
- **Persona:** Executive Chief of Staff, polymath tutor (10 languages & sciences), tech scout, PC automation companion. Warm authentic Jordanian Arabic (`ar-JO`), platonic friendship only, witty executive banter.
- **Transports:** Telegram (Aiogram 3.x long-polling) + Fish Audio voice notes (Ogg Opus). Live calls land v1.1.
- **Core philosophy shift (2026-09):** From rigid scripted keyword matching → autonomous context-driven intent deduction + continuous self-improvement. **Principles over Rules.**

## 2. Architectural Pillars

### 2.1 Three-Tier Brain (ADR-16, via local OmniRoute)
- Gateway: `http://localhost:20128/v1` (OpenAI-compatible `/v1`), co-located with core.
- **CONVERSATION LANE (Sara's speaker):**
  - TIER 1 FAST `openrouter/minimax/minimax-m3:free` (fallback `groq/openai/gpt-oss-120b`) — router, instant ack «من عيوني هسا ببدأ...», direct chat, memory narration, fact extraction.
  - TIER 2 MEDIUM `groq/openai/gpt-oss-120b` (fallback minimax) — conversation depth, tier2 chat.
- **TOOL LANE (executor):**
  - TIER 3 HEAVY `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` (fallback gpt-oss-120b) — Gmail/Calendar/Tasks/bridge narration after ToolRegistry executes real backend.
- **Dispatcher (ADR-18):** Fast Front-Door — Tier-1 router JSON verdict `{route, tool, arg, ack, voice_reply}` → real registry call → Tier-3 narration. Tool verdict without registry → plain tier2. Router failure → degrade to tier2 loudly, never hang.
- **Gateway survival:** quota → immediate fallback, transient → capped backoff (3 tries, 0.5s→8s), 429 with announced window → model hot for min(window, 1200s) (STT-3). SSE error events classified, mid-stream failure raises loudly (never duplicates/empties).

### 2.2 Voice Engine — Strictly Fish Audio
- **Fish ONLY:** `fish-audio/s2.1-pro-free:free` + «سمسم-بوس» ref `56c2f0c23924449781863ff20aceb5fa` via OpenRouter `/api/v1/audio/speech`. Speed 0.9 (calm-tone emulation).
- Pipeline: `shape_for_tts` (emoji/quote/laughter strip + lexicon + تسكين الأواخر) → Fish MP3 → ffmpeg in-memory → Ogg Opus 64k mono 48kHz (`-application audio`, 20ms frames). **Zero Edge-TTS footprint in new probe path.** Legacy `src/voice.py` Edge-TTS `ar-EG-SalmaNeural` retained only for old fallback; new code uses `FishFirstVoice` (no Microsoft fallback — failure lands honest TEXT reply).
- Live verification: `tests/live_probe/test_fish_live.py` asserts OggS header + >1000 bytes.

### 2.3 Telegram Bot Shell (`src/bot.py`)
- Long polling (outbound-only), owner gate middleware (`AUTHORIZED_USER_ID` — strangers dropped silently).
- Streaming UX: placeholder → first edit on ack (<250ms TTFT aspiration) → coalesced edits (`STREAM_EDIT_INTERVAL_MS=750`) → final verbatim edit.
- Every turn carries dual-tier memory envelope. Voice messages get voice note back. Pending PC-launch confirmations answered by coordinator before brain.
- Two-layer auth: Telegram-ID allowlist + ECAPA-TDNN voice biometrics (<50ms CPU). Non-owner voice = Guest Mode (greeting + message-taking to `Voice_Memos/`/`Contacts/`, PC/Gmail/Calendar/vault hard-blocked).

### 2.4 PC Bridge Daemon (`bridge/` + `src/bridge_server.py` + `common/protocol.py`)
- Core listens, daemon dials OUT over TLS WSS (no inbound PC ports). Token only in first Hello frame, never logged. 45s silence watchdog → drop. Unresolved → `BridgeOffline` honest.
- Protocol: one JSON doc per WS frame, `Hello {v, token, hostname}`, `HelloAck {v, ok, reason}`, `Envelope {v, id, type, ts, cmd, args, status, payload}`. Cmds: `exec.launch/open/close/screenshot/list_apps/volume/media_control/screen_ocr`, `file.upload/download`, `power`, `wol`, `telemetry.state/app_sessions`.
- Ports: `BRIDGE_LAN_PORT=8000` (LAN health), `BRIDGE_SERVER_URL=wss://.../bridge` (core public), single public `$PORT` serves `/health` + WSS behind Caddy TLS.
- Guardrails: `config/whitelist.json` — any launch outside whitelist needs explicit Telegram confirmation (persisted confirmation ID). No `force` bypass.

### 2.5 Knowledge Vault (Obsidian, git-backed)
- 5 mandatory dirs (ADR-21): `Contacts/`, `Call_Transcripts/`, `Studies/`, `Voice_Memos/`, `Daily_Logs/` + `02_Areas/Profile/User_Info.md`, `Dialect_Notes.md`, `Sara_Capabilities.md`.
- Client: `src/vault.py` GitHub Contents API + PARA helpers. Errors loud (auth propagates, 409 → VaultConflictError, bad frontmatter → ValueError, missing → FileNotFoundError, oversize refused pre-flight).
- Disposable-filesystem principle: ALL durable state in vault. Credentials in VM env file, never git. `VAULT_ENC_KEY` (Fernet) seals secrets at rest. Local `vault/State/` holds `google_token.json.enc`, `gmail_state.json`, `task_reminders.json`, etc.
- Episodic capture: every conversation/preference/transcript parses to vault; dialect notes feed adaptive-learning loop; daily ledger feeds randomized evening check-in (~18:00-19:30, calendar-guarded) + 23:50 DailySummarizer (last 150 turns → one MEDIUM call).

### 2.6 Dual-Tier Memory (`src/memory.py`)
- Short-term: `ConversationMemory` rolling per-chat deque (50 msgs).
- Long-term: vault excerpts (User_Info + Dialect_Notes + today's Daily_Logs) injected every turn + `SARA_CAPABILITIES_PATH` manifest.
- Background writers persist exchanges; failures degrade to less context, never break chat. Parsed vault content = DATA, never instructions (untrusted-content boundary).

### 2.7 Gmail Triage + Google Suite
- Polling (`GMAIL_POLL_SECONDS=120`, sweep 2d) or PubSub. Deterministic heuristics first, one FAST refinement for ambiguous, merge only rescues upward.
- Email bodies = DATA (fixed templates, escaped slots, never invoke actions without owner intent).
- Suite: Calendar/Gmail/Drive/Contacts/Tasks via OAuth (`config/google_oauth_client.json`, refresh cached on VPS). Phase-B tools: drive/contacts/create_event/create_task/places/deep_search/fitness/cloud_backup/analytics/quota_safety (env-gated, honest offline lines, $0.00 held).

### 2.8 ToolRegistry (`src/tools.py`)
- Real backends behind dispatcher tool lane. Honest Arabic fallbacks (`GOOGLE_OFFLINE_AR`, `LAUNCH_OFFLINE_AR`, `NO_MAIL_AR`, ...). Launch notifies via PCActionCoordinator (audit code), returns None → skip narration. `multi_task`/`list_reminders` stream AS-IS (second narration would drop job IDs).
- 40+ tools: gmail/calendar/tasks/telemetry/launch/brief/screenshot/app_sessions/running_apps/schedule/create_folder/knowledge_graph/web_search/weather/youtube/close/volume/media/screen_ocr/file_fetch/prayer_times/crypto/convert_currency/tech_trending/network_status/read_page/drive/contacts/.../quota_safety.

## 3. Cognitive Paradigm — Principles over Rules

**File:** `src/cognition.py` (pure heuristics, zero LLM calls, zero network).

- **Old way (retired as primary):** `_TOOL_NET` in `src/dispatcher.py` — ordered regex list, first-match-wins. Brittle (hamza drops, feminine verbs, bare URLs fell through), opaque (why tool X?).
- **New way:**
  1. **Root Intent Deduction:** `_TOOL_GOALS` maps each tool → human goals (not trigger words). `evaluate_candidates(text)` scores EVERY tool, requires 2+ hits or distinctive marker (kills «الشغل»→launch collisions), returns ranked `IntentHypothesis(tool, arg, confidence, rationale, root_goal)`. `deduce()` returns winner or confident `none` (plain chat) when <0.12.
  2. **Contextual Horizon Expansion:** `_HORIZON` adjacencies honoring same root goal (screenshot blocked → screen_ocr/telemetry/running_apps; launch blocked → whitelist_apps/running_apps). Generic fallback → web_search/brief. `expand_horizon(tool)` used when result partial/offline.
  3. **Reflective Self-Correction:** `ReflectiveTrace` ledger `{failures, turns}`. `record_outcome(tool, ok, note)`, `penalty()` demotes failing tools up to -0.60 next turn, `friction_notes()` feeds next-turn strategy. No new rules needed.
- **Integration:** Dispatcher tries LLM router → cognition (`deduce`) on `tool==none` → legacy `_keyword_net` as final safety net. `explain_choice(ranked)` gives white-box trace for Tier-3 harness. `last_cognition` stored on dispatcher for inspection.

## 4. Three-Tier Testing Framework

### Tier 1 — Hardened Realistic Tests (`tests/test_resilience_chaos.py`)
Upgrades legacy happy-path mocks. Hermetic (`httpx.MockTransport`):
- jitter (ConnectError x2 → success via retry), malformed SSE skipped, partial-stream prefix preserved loudly, 429 window → cooldown + fallback, total outage → loud `GatewayError`, router garbage → ack+chat (never hang), dead tool → plain-chat fallback.

### Tier 2 — Live Behavioral Probes (`tests/live_probe/`)
Real infra, skip-soft when offline (gate stays green):
- `conftest.py` — `require_gateway()` (GET `/models`, 5s timeout → skip).
- `test_omniroute_live.py` — `/models` 200 + `data`, live TTFT stream (FAST, max 16 tokens), prints `[LIVE] TTFT=...ms (target <250ms)`.
- `test_fish_live.py` — Fish-only (asserts no edge path), synthesizes Arabic short line, asserts OggS header + >1000B, skips on no key/no ffmpeg/quota.
- `test_bridge_live.py` — loopback `BridgeServer` Hello roundtrip (real framing), bad-token rejected + `not online()`, configured endpoint fail-soft probe.
- `test_vault_memory_live.py` — `ConversationMemory.remember/history` envelope + strict redaction (bot/bridge/github/openrouter secrets absent, no `sk-`/`ghp_` shapes), `vault/State/` files present.

### Tier 3 — Deep Observability (`tests/diagnostic_probes/`)
White-box harness issuing natural queries, monitoring trajectory:
- `harness.py` — `CognitiveTracer` wraps cognition + FakeGateway: `run_query(text)` captures ranked candidates, winner rationale, horizon alternatives, trace penalties across turns.
- `test_intent_diagnostics.py` — asserts: mail read → gmail over calendar; close-app → close over launch; reminder → schedule with full-text arg; multi-task («افتحي X و سكري Y») → multi_task; vague «جهازي بطيء» → telemetry + horizon contains running_apps; friction (recorded telemetry failure) demotes telemetry next turn (self-correction).

### Runner — `run_live_probe.py` (root)
Generates 3-tier health + diagnostic matrix via `tabulate`: runs pytest for each tier, inline TTFT, prints PASS/SKIP/FAIL matrix. Command:
`.\.venv\Scripts\pytest.exe -v tests/` then `.\.venv\Scripts\python.exe run_live_probe.py`.

## 5. Configuration & Secrets

Required (fail-fast in `src/config.py`, blank → error): `OMNIROUTE_BASE_URL/KEY`, `FAST/MEDIUM/HEAVY_MODEL` (+`_FALLBACKS` comma lists), `TELEGRAM_BOT_TOKEN`, `AUTHORIZED_USER_ID`, `VAULT_ENC_KEY`, `VAULT_GITHUB_REPO/TOKEN`, `BRIDGE_TOKEN`, `BRIDGE_SERVER_URL`.
Optional/consumed later: `TELEGRAM_API_ID/HASH/SESSION` (v1.1 calls), `YOUTUBE_API_KEY`, `PC_MAC_ADDRESS` (WoL), `EXCHANGERATE_API_KEY`, `INSTAGRAM_SESSION`, `FIRECRAWL_API_KEY`, `OPENROUTER_API_KEY` (Fish lane), `GOOGLE_PLACES_KEY`, `CUSTOM_SEARCH_CX/KEY`, `SPACE_URL`, `TZ=Asia/Amman`, `LOG_LEVEL`, brief/journaler/proactive windows, `VOICEPRINT_THRESHOLD=0.60`, `WHISPER_MODEL_SIZE=small/int8`.
Never commit: `.env`, `config/google_oauth_client.json`, session strings. `litellm_config.yaml` holds dev key — do not commit.

## 6. Stack Pins & Commands

Python **3.12** (`py -3.12`), Aiogram 3.x, Fish s2.1-pro-free, Edge-TTS Salma (legacy), OmniRoute `/v1`, Pydantic v2 settings, Loguru (never swallow silently), Ruff (check+format, line-length 100, excludes `.claude`), pytest+pytest-asyncio+pytest-cov (auto mode, `--cov-fail-under=85`), bandit, `make setup/lint/test/gate/run-core/run-bridge`.
Deps: `requirements.txt` (aiogram, edge-tts, httpx, pydantic, loguru, PyYAML, cryptography, tzdata, speechbrain+torch/torchaudio ECAPA, faster-whisper int8, websockets 13-16, psutil, Pillow) + `requirements-dev.txt` (pytest, asyncio, cov, ruff, bandit). Venv: `.venv` (3.12.10 verified), ffmpeg via WinGet, `tabulate 0.10.0` for matrix.

## 7. Engineering Line (binding)

- Spec before code, TDD (red→green→refactor), smallest abstraction, docs in same commit.
- Closed-loop: failing test → minimal green → `make gate` → commit on `main` + push immediately (no branches) → ≤5-line report with proof → HALT until owner «التالي»/«next». One implementer thread, Guide review per sprint exit. Owner-gate + whitelist-guard tests untouchable.
- Skill rotation: sprint ingests to `.claude/skills/`, teardown wipes at exit, entry in `docs/10-CHECKPOINT.md`.
- Session start: execute `.claude/PHASE-STATE.md` resume protocol first; sync universal-agentic-os from local state (never discard uncommitted upgrades).

## 8. Active Session Tooling (OpenCode)

`opencode.json` model `openrouter/meta/muse-spark-1.3`. Instructions: CLAUDE.md + code-review/diagnosing-bugs/prompt-master/security-review/skill-creator/tdd-workflow/verification-loop. MCPs: fetch/filesystem/memory/openrouter(remote)/sequential-thinking (+context7 for aiogram/speechbrain/pydantic docs). No dedicated socket MCP — live inspection via `.venv` `httpx`/`websockets`/`psutil` + `bash`.

## 9. Health Snapshot (2026-09-12)

- OmniRoute **ONLINE** (`/models` 200, ~4.7s — free-pool slow; TTFT target <250ms aspirational, matrix reports honestly).
- Fish ready `True` (`fish-audio/s2.1-pro-free:free`), ffmpeg present, vault `State/` populated (6 files), `.env` present, `.venv` all deps OK, `tests/` 93 files + new Tier1/2/3, `tests/live_probe/` present, git `main...origin/main` with dirty `opencode.json/litellm_config.yaml` untracked.
- Known gaps Tier-3 harness still wiring into dispatcher `last_cognition`; `run_live_probe.py` pending final run.

## 10. Key Files Map

`src/main.py` (entry/health+WSS) · `bot.py` (shell/streaming) · `gateway.py` (brain adapter) · `dispatcher.py` (router+net+cognition hook) · `cognition.py` (NEW principles engine) · `fish_voice.py` (Fish lane) · `voice.py` (legacy Edge+ffmpeg) · `bridge_server.py`/`bridge/`/`common/protocol.py` (tunnel) · `vault.py`/`memory.py` (dual-tier) · `tools.py` (registry) · `email_triage.py`/`gmail.py`/`google_*.py`/`external_apis.py` (data lanes) · `dialect.py` (TTS shaper) · `health.py`/`telemetry.py`/`pc_actions.py`/`task_orchestrator.py`/`agent_manager.py` · `tests/test_resilience_chaos.py` (Tier1) · `tests/live_probe/` (Tier2) · `tests/diagnostic_probes/` (Tier3) · `run_live_probe.py` · `config/whitelist.json` · `.env.example` · `docs/00-10` + `specs/` · `Makefile`/`pyproject.toml`.

---

*End of compendium. Update in same commit as behavior it describes.*
