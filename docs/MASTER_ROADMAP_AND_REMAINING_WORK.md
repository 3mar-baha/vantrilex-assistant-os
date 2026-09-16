---
tags: [decision]
---

# Master Roadmap & Remaining Work — Vantrilex Assistant OS (Sara)

> Synthesis audit 2026-09-16 · baseline `main @ a163b03` · suite 1,457/7/0 · ruff clean.
> Charter note: per the decoupling rule, `docs/08-ROADMAP.md` remains the SOLE
> authority for planned/deferred/unbuilt scope. This document sequences the
> operationalization of already-built capability; it mints no new scope.
> Premise corrections applied during audit: the suite is
> `docs/01-PRODUCT-REQUIREMENTS.md`…`docs/16-WORKFLOWS.md` (there is no
> `01-SYSTEM_OVERVIEW.md`); voice is Fish-only (Edge-TTS purged 2026-09-03,
> chain removed 2026-09-12); conversation memory persists to the Obsidian
> vault + `vault/State/*.json`, not SQLite; tags `v1.0.0`/`v1.0.1`/`v1.0.2`
> already exist.

## Phase 1 — Operationalization & Live Interactive Validation (Day 1, owner-led)

Goal: Sara running for real, not hermetically. All pieces exist; the gates are
physical credentials and hosts.

1. Start OmniRoute (`http://localhost:20128/v1`) with free provider keys, then
   `sara.ps1` / `sara.bat` local cycle; re-run
   `scripts/live_interactive_benchmark.py` expecting 6/6 in **LIVE** mode.
2. Voice loop: text → ack → answer; voice note → single Fish voice note
   (`fish-audio/s2.1-pro-free:free`, speed 0.9); latency bars — TTFT < 1.2 s,
   voice first chunk < 600 ms.
3. `/enroll-voice` (≥5 s note; threshold 0.60) + one-time Google OAuth consent
   on the VM (`config/google_oauth_client.json` via scp; watch the known
   Google 403 on project `vantrilex-assistant-2008`).
4. Confirm cross-session memory: `vault/Daily_Logs/`, `User_Info.md`, and the
   23:50 `DailySummarizer` entry after a real dialog day.
5. Oracle path (if local-first is done): `docs/15-ORACLE-DEPLOY.md` → DuckDNS →
   `sara.env` (21 vars) → `BRIDGE_SERVER_URL=wss://<domain>/bridge` on the PC.

## Phase 2 — Knowledge Ingestion & Personal Context Priming

Goal: RAG recall at bar (13/14 top-1, 14/14 top-3, p95 ≤ 5 ms) on live data.

1. Keep `04_Resources/` as the tracked seed (mirror source — pinned by
   `test_rag_vault_sync.py`); never relocate it.
2. Prime `02_Areas/Profile/User_Info.md` + `Dialect_Notes.md` via live use and
   `«تعلمي:»` pairs; verify pronunciations reach the TTS lexicon and the
   Whisper prompt without reboot.
3. Spot-check `VaultIndex` scoring (alias+10, title×3, tags×2, body×1) and the
   ≤600-char injection block on real queries; enrich thin areas per the
   orphan-wiring backlog in `docs/08-ROADMAP.md`.

## Phase 3 — Multi-Channel Expansion & Remote Accessibility

Shipped: aiogram bot (owner-ID silent drop), `/start` + WoL, voice pipeline,
quiet-hours gate. Remaining:

1. Point the PC bridge at the public WSS endpoint; verify telemetry
   (`«شو وضع الجهاز؟»`) and confirm-gated launches over the tunnel.
2. Harden secrets: rotate the exposed OpenRouter key in untracked
   `opencode.json`, the GitHub PAT, and Telegram `API_HASH` (see
   `docs/OWNER-NEXT-STEPS.md`); keep `sara.env` parity with local `.env`.
3. Webhook/long-poll posture: long polling stays default (outbound-only);
   any webhook move needs token validation + allowlist review first.

## Phase 4 — Hardware Bridge & IoT Integration (OpenClaw Layer)

Shipped substrate: `bridge/` daemon (guard, executor, breaker, telemetry, WoL,
idle, app_sessions, awareness) + OpenClaw arms (inspect, fetch, browse, hotkeys,
actuator, controller) bench-proven 12/12 with zero unconfirmed executions.
Gates before widening:

1. Real-profile browser control stays opt-in (isolated Sara profile default).
2. UIA tree enumeration feeding `snapshot()` and the vision re-plan loop are
   unbuilt (`docs/08-ROADMAP.md` OpenClaw section) — no sensor/automation
   protocol lands without breaker coverage + chaos-bench green.
3. Whitelist alias targets (Spotify/Telegram/WhatsApp paths) confirmed on the
   owner host per the orphan-wiring backlog.

## Phase 5 — Production Hardening, Release & Lifecycle Governance

1. Release: tags `v1.0.0`–`v1.0.2` exist; next patch runs
   `scripts/make_release.py` (dry-run → tag → push → GitHub Release), then the
   post-tag container rebuild + `deploy_smoke` re-run (AC8, manual).
2. Backup: `vault/State/*.enc`, `google_token.json.enc`, owner voiceprint —
   encrypted blobs whose only copies live in the vault working copy; define
   the owner-side encrypted backup cadence (Silent Vault Backup is parked in
   `docs/08-ROADMAP.md`).
3. Lifecycle: `make gate` per change; sacred floor
   (`test_owner_middleware.py`, `test_whitelist_guardrail.py`,
   `test_guest_lockdown.py`) blocks every merge; skill rotation
   teardown each sprint exit; evening-ledger + checkpoint discipline per
   `docs/16-WORKFLOWS.md` (`/plan` default, `/code`, `/audit`, `/sync`).

## Deferred scope (authority: `docs/08-ROADMAP.md` — not this document)

v1.1 live voice calls (mock-complete, needs call-budget rules) · Instagram
sandbox → live · Civ6 promotion/retirement · diarization runtime trigger ·
Firecrawl key + quota · v1.5 SIP · v2.0 social agent · Mem0/Firestore
evaluation · PC Health Monitor · Emotional Context Memory.

## See also (graph links)

- [08 — Roadmap](./08-ROADMAP.md)
- [10 — Sprint Checkpoint Ledger](./10-CHECKPOINT.md)
- [15 — Oracle Deploy](./15-ORACLE-DEPLOY.md)
- [16 — Operational Workflows](./16-WORKFLOWS.md)
- [Map of Architecture](./00-MAP-OF-ARCHITECTURE.md)
