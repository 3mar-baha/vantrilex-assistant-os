---
tags: [architecture]
---

# 04 — System Architecture

> Canonical topology. Migrated 2026-09-14 from `docs/01-ARCHITECTURE.md`
> (mission record §1 preserved verbatim below; stale tier pins corrected to
> live config; future roadmap moved to `docs/08-ROADMAP.md`).

## 1. Confirmed Mission Record (Discovery, 2026-08-26)

- **Project**: Vantrilex Assistant OS — persona **Sara (سارة)**.
- **Rulings**: Sara naming (Q1) · owner-only access (Q3) · v1.0 = exec core
  minus live calls (Q4) · $0.00 absolute + Telegram confirmation fallback
  for whitelist misses (Q5) · credential manifest filled progressively (Q6).
  (Q2 VPS topology superseded by ADR-15: Oracle VM.)
- **OmniRoute gateway**: `http://localhost:20128/v1`, co-located with the
  core; aggregates free provider pools with quota-aware auto-fallback.
  Adapter: `src/gateway.py` (`OmniRouteClient`) — the only module speaking
  LLM wire format; SSE streaming, 3-tier chain (ADR-16),
  quota/transient/fatal classification (mid-stream SSE errors classified,
  never swallowed). **Fast Front-Door Dispatcher** (ADR-18): Tier-1 ack,
  tiered execution/narration.
- **Telegram voice/chat**: Aiogram 3.x long polling; progressive delivery
  (placeholder → ack → coalesced edits → verbatim final; newer message
  cancels in-flight streams); long replies re-split into 2–3 bubbles.
  **Voice = Fish Audio** (`s2.1-pro-free:free`, «سمسم» ref, via OpenRouter
  speech; NO Microsoft fallback — failures land honest text), in-memory synth
  → ffmpeg → Ogg Opus. Router `voice_reply` verdict picks voice-vs-text per
  turn; explicit owner request always wins.
- **Validated deployment (ADR-15 as amended 2026-08-31)**: **Oracle Cloud
  Always-Free VM**, ONE Docker container (core + OmniRoute), single public
  port behind Caddy TLS (WSS bridge + `/health`), env file on VM,
  `restart: unless-stopped`; durable state ONLY in the git-backed vault.
  **Windows PC Bridge daemon** dials outbound-only (TLS WSS, zero inbound),
  executing whitelist-guarded automation. PC may sleep; Sara stays up.

## 2. Component Topology

```mermaid
graph TD
    User([Owner]) <-->|Chat / Voice Notes| TG[Telegram]
    TG <--> Core[Oracle VM: Aiogram 3.x Core + Orchestrator]
    subgraph VM [Oracle Always-Free Docker - 24/7, Caddy TLS, restart unless-stopped]
        Core <--> Disp[Fast Front-Door Dispatcher ADR-18]
        Disp <--> Omni[OmniRoute :20128 - 3-tier ADR-16]
        Omni <--> T1[Tier1 FAST: groq/gpt-oss-120b - talker | fb gemma, 4s guillotine]
        Omni <--> T2[Tier2 MEDIUM: nex-mini - depth | fb groq]
        Omni <--> T3[Tier3 HEAVY: nex-pro - tool lane | fb nemotron+groq]
        Core <--> TTS[Fish Audio (سمسم) -> ffmpeg -> Ogg Opus | NO fallback]
        Core <--> Bio[Voice biometrics ECAPA-TDNN + Guest Mode]
        Core <--> G[Google Suite: Calendar / Gmail / Drive / Contacts / Tasks]
        Core <--> Vault[(Git-backed Obsidian Vault via GitHub API)]
        Core --> WSS[Public port via Caddy: WSS bridge endpoint + /health]
    end
    WSS <-->|outbound-only link| Bridge[Windows PC Bridge Daemon]
    subgraph PC [Windows PC - may sleep]
        Bridge --> Guard[Whitelist guard + confirmation IDs + audit ledger]
        Bridge --> Exec[Executor: launch/close/open/volume/media/screenshot/OCR/files]
        Bridge --> Claw[OpenClaw controller: breaker + inspect/fetch/browse/actuate]
        Bridge --> Tele[Telemetry snapshot - psutil LiveState]
        Bridge --> WoL[Wake-on-LAN sender UDP:9]
        Bridge --> Idle[Idle monitor 20 min]
    end
```

Background loops (one stitch point `start_background_loops`, all cancelled
on shutdown): 07:30 brief, 18:00–19:30 check-in, ~45-min proactive outreach
(HEAVY-judged, 08:00–22:30, max 3/day, calendar-guarded), Gmail watch,
23:50 summarizer, bridge-reconnect watcher (30-min debounce, quiet hours
08:00–23:30 Amman).

## 3. Data flows

- **Chat turn**: allowlist → biometrics → persona+memory+affect+RAG envelope
  → dispatcher verdict → tool lane or plain tiers → HEAVY narration (≤2
  lines) → background persist (ledger + learn + write-back check).
- **Tool lane**: registry executes the REAL backend first; narration second
  (launch/close notify directly, audit code inside; multi_task streams as-is).
- **RAG**: Tier-1 digest + top-3 on advisory turns; routine device turns
  inject `""` (zero tokens). Boot mirror `04_Resources/` → vault (strict
  copy-if-missing; divergence logged, never overwritten).
- **Write-back**: weight ≥ 4 or explicit intent → async milestone append
  (nested ledger) + capped digest refresh; never blocks TTFT.
- **OpenClaw**: core plans (Single-Brain) → typed `openclaw.*` verbs →
  daemon breaker re-verifies (wire claim ignored) → mechanical act →
  transcript + audit codes. Commits PARK for «نعم»; shell shapes are
  unrepresentable (`ActionForbiddenError`).

## 4. Component registry

Core: `bot.py` (shell/loops), `dispatcher.py` (ADR-18), `gateway.py`
(OmniRoute client), `tools.py` (46 handlers), `decision_loop.py` (ReAct +
PARK), `memory.py` + `memory_ledger.py`, `associative.py` (VaultIndex),
`vault.py` (GitHub client + resolvers), `cognition.py` + `cognitive_dag.py`,
`skills/*` (guides, triage, journaler, outreach, biometrics), `openclaw/`
(intents/plans/protocol). Bridge: `daemon.py`, `executor.py`, `guard.py`,
`server.py` (LAN :8000), `app_sessions.py`, `awareness.py`, `wol.py`,
`openclaw/` (protocol/breaker/controller/inspect/fetch/web/actuator/
hotkeys/perception).

## 5. Knowledge vault layout (PARA + Zettelkasten)

`01_Projects/ 03_Resources/ 04_Archives/ 02_Areas/Profile/{User_Info.md,
Dialect_Notes.md,Omar_Master_Digest.md} Contacts/{Family,Friends,Colleagues,
Ignored,Unknown}/ Call_Transcripts/ Studies/ Voice_Memos/
Daily_Logs/YYYY/MM/YYYY-MM-DD.md` (flat legacy read-fallback) `State/`
(skipped by index). Transport: GitHub Contents API (`Bearer
VAULT_GITHUB_TOKEN`, `?ref=VAULT_BRANCH`); local mirror is disposable.

## 6. Master transformation deltas (P0–P6, 2026-09-17)

- **JODA speech-act bank (P1)**: 500 mined Ammani patterns (5 acts × 80 +
  100 wildcards) in `04_Resources/Dialect_Encyclopedia/JODA_Pattern_Bank.md`,
  consumed by direct section read; unconditional cues ride `load_long_term`
  (capped 300, deterministic sections).
- **Fused FAST router (P3)**: `rag_domains` verdict field (+0ms, closed
  vocabulary) + non-throwing `repair_verdict()` (fence/trailing-comma/schema);
  RAG budget slicing (60/40, 50/30/20, floor-400) with quarantine-halved
  ceiling, sentence chunks, per-hit path citations.
- **Atomic turn counter (P2)**: `<vault>/State/turn_counter.txt`
  (`src/turn_counter.py`) — `.tmp` + fsync + `os.replace`, corrupt-rename→0,
  never raises; bumped only at the transport boundary (`on_text`/`on_voice`),
  ReAct internals banned by test; pytest hermeticity via
  `SARA_TURN_COUNTER_OFF`.
- **Cadence refresh (P2)**: 10-turn memory trigger (`src/cadence.py`) with
  starvation guard + situational conditioning (`MOBILE` concise vs `FOCUS`
  technical lane, humor/grace suppressed).
- **Single-pass synthesis (P4)**: direct turn = exactly 2 model touches (one
  verdict call + one answer stream); placeholder/ack transient, never in
  memory. `confirmation_id` is server-minted post-affirmation
  (`src/pc_actions.py`), persisted pre-execution, machine-to-machine only —
  never in prose or model I/O.

## See also (graph links)

- [01 — Product Requirements](./01-PRODUCT-REQUIREMENTS.md)
- [03 — Technical Specification](./03-TECHNICAL-SPECIFICATION.md)
- [05 — Data Model](./05-DATA-MODEL.md)
- [06 — API Specification](./06-API-SPECIFICATION.md)
- [09 — Decision Records](./09-DECISIONS.md)
- [Map of Architecture](./00-MAP-OF-ARCHITECTURE.md)
