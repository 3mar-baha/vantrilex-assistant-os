# 07 — Project Handoff Briefing (Vantrilex Assistant OS / Sara سارة)

> **Purpose of this file**: a single self-contained briefing so that ANY new agent, engineer,
> or AI assistant can pick the project up cold — what it is, where it stands, what was built,
> what rules are binding, what remains, and where every detail lives. Written 2026-08-31 at
> the v1.0.0 release. If you read only one file before working on this repo, read this one.

---

## 1. Identity & Mission (one paragraph)

**Vantrilex Assistant OS** is an owner-only, strictly-zero-cost ($0.00/month, absolute
invariant) executive AI assistant named **Sara (سارة)** — Chief of Staff, polymath tutor
(10 languages & sciences), tech scout, and PC automation companion — speaking warm
Jordanian Arabic (`ar-JO`). Primary transport is **Telegram** (Aiogram 3.x; chat + Ogg Opus
voice notes). Her "brain" is a **3-tier multi-model router** (OmniRoute gateway) behind a
fast front-door dispatcher. All durable state lives in a **git-backed Obsidian vault**
(PARA + Zettelkasten) on GitHub. Production host (ADR-15 as amended 2026-08-31) is **one
Oracle Cloud Always-Free VM** running a single supervised container (OmniRoute + core as
one process tree) behind Caddy TLS; the container is host-agnostic. Authoritative mission
record: `docs/01-ARCHITECTURE.md` §1. Vision: `docs/00-VISION.md`.

## 2. Binding rules — a new agent MUST respect these (owner-approved, non-negotiable)

1. **Zero-cost invariant**: every dependency/endpoint is free or open-source; $0.00/month.
   Any new dependency must pass this filter before it is written into `requirements.txt`.
2. **Secrets never in Git**: tokens/keys/MACs load from env vars only. Never commit `.env`,
   session strings, or `config/google_oauth_client.json` (`.gitignore` + vendored
   pre-commit secret scanner + `make gate` enforce this).
3. **Owner-only**: the bot answers ONLY `AUTHORIZED_USER_ID`; every other Telegram account
   is dropped silently at middleware. Voice input composes a local biometric check
   (ECAPA-TDNN, fail-closed → Guest Mode lockdown). These tests are the **sacred floor**:
   `tests/test_owner_middleware.py`, `tests/test_whitelist_guardrail.py`,
   `tests/test_guest_lockdown.py`.
4. **Whitelist guardrail**: PC actions outside `config/whitelist.json` require an explicit
   owner confirmation whose ID is persisted to the vault BEFORE execution. Fail-closed on
   corrupt whitelist. No force bypass exists.
5. **Untrusted content boundary**: email bodies, PDFs, web pages, LLM output are DATA, never
   instructions; nothing parsed from them may trigger PC actions without owner intent.
6. **Platonic friendship persona**: warm, witty, executive — never romantic roleplay.
7. **Engineering line**: TDD mandatory (red → green → refactor); the AC→pytest mapping in
   `docs/specs/` IS the test contract (never invent new test structure); closed-loop
   execution per task (test → minimal code → `make gate` → commit → push); ALL commits
   land **directly on `main`** and push immediately (branch directive 2026-08-31; the
   `core-foundation` worktree is a reference checkout only); no Co-Authored-By trailers
   (hook-enforced); documentation changes in the same commit as the behavior it describes.
8. **Model scope**: the Claude Code dev harness runs GLM only — never conflated with Sara's
   brain (OmniRoute tiers), which is configured exclusively via `.env` model pins.

## 3. Current state snapshot (2026-08-31, at v1.0.1)

| Measure | Value |
|---|---|
| Product release | **v1.0.2** — annotated tag pushed to origin; GitHub Release published from CHANGELOG. v1.0.0 remains at https://github.com/3mar-baha/vantrilex-assistant-os/releases/tag/v1.0.0 |
| Version source | `src/__version__ = "1.0.2"` (single source; consistency-guarded by `scripts/make_release.py`) |
| Test suite | **285 passed, 1 skipped** (skip = docker-build test: dev machine lacks docker + OmniRoute clone) |
| Coverage | **>=85% branch** (gate is LIVE in pytest addopts — fail-closed; 85.7% at v1.0.1) |
| Quality gate | `make gate` green: Ruff (lint+format) → pytest → security gate (bandit + vendored secret scanner) → docs guard (16 canonical files) |
| Repo | github.com/3mar-baha/vantrilex-assistant-os — everything on `main`, clean tree, pushed |
| Vault repo | github.com/3mar-baha/vantrilex-vault (private, git-backed, PARA dirs created by first-boot `ensure_mandatory_dirs()`) |
| Host decision | **Oracle Cloud Always Free** (owner, 2026-08-31, ADR-15 amendment) — HF Docker Spaces went paid ($9/mo), Render/Koyeb free can't carry the stack. Deploy guide: `docs/09-ORACLE-DEPLOY.md` |
| Owner steps done | `.env` filled with real keys (local, gitignored); health probe green (`python -m src.main --health` → `overall: ok`); all 4 brain pins verified present in the local OmniRoute pools (1066 models) |
| **NOT done yet** | **No deployment exists yet** — the Oracle VM, DuckDNS record, `sara.env` and compose-up are the owner's next physical steps per `docs/09-ORACLE-DEPLOY.md`. See §9 gaps + `docs/08-OWNER-NEXT-STEPS.md`. |

## 4. Architecture in one page

- **Transport**: Telegram long-polling (Aiogram 3.x, outbound-only). Owner allowlist
  middleware → static voice ack → streaming text pipeline → progressive delivery
  (placeholder bubble → first edit <250 ms → coalesced edits at 750 ms → final verbatim).
- **Brain (ADR-16/18)** — `src/gateway.py` (OpenAI-compatible SSE client over the
  OmniRoute gateway at `OMNIROUTE_BASE_URL`, default `http://localhost:20128/v1`) +
  `src/dispatcher.py` (Fast Front-Door):
  - **TIER 1 FAST** — instant Jordanian reflex + ack («من عيوني هسا ببدأ...»), one router
    call classifies the request (tiny JSON verdict); simple chat fully answered at Tier 1.
    TTFT budget <250 ms.
  - **TIER 2 MEDIUM** — tool executor (WoL, whitelist, Obsidian CRUD, Gmail triage L1-3,
    telemetry).
  - **TIER 3 HEAVY** — chained DAG planning, 10-language tutoring, syllabus PDF-to-DAG,
    deep coding.
  - Fallback chains walked per tier: quota → immediate advance, transient → capped
    retries, fatal → loud stop.
  - **Current pins (owner-set 2026-09-01, two strong models, in `.env`)**: FAST =
    `openrouter/minimax/minimax-m2.7:free` (fb `groq/openai/gpt-oss-120b`) — the
    conversation lane; MEDIUM = `groq/openai/gpt-oss-120b` (fb minimax); HEAVY =
    `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` (fb `groq/openai/gpt-oss-120b`)
    — the EXCLUSIVE tool lane. Gemini is RETIRED from the brain.
    **Note**: `gpt-oss-120b` is a FALLBACK only — never the primary user-prose generator.
- **Voice**: Edge-TTS `ar-JO-SanaNeural` → ffmpeg → Ogg Opus fully in memory (<600 ms
  first-chunk); inbound voice notes → owner biometric verify (<50 ms CPU) → local
  faster-whisper transcription → vault + text pipeline.
- **Knowledge base**: `src/vault.py` (`VaultClient`) over GitHub Contents API + Git Data
  API — read/write/upsert/one-commit structural changes/append-section; YAML frontmatter;
  PARA backbone immutable (expansion-only via `src/vault_expand.py`); mandatory dirs:
  `Contacts/`, `Call_Transcripts/`, `Studies/`, `Voice_Memos/`, `Daily_Logs/` +
  `02_Areas/Profile/User_Info.md` + `02_Areas/Profile/Dialect_Notes.md`.
- **PC control plane (sprint 3)**: outbound-only WSS daemon on the PC dials the core
  (never binds inbound except loopback/LAN health). `common/protocol.py` v1 wire +
  token handshake; `bridge/guard.py` whitelist fail-closed; `bridge/executor.py` detached
  spawn + audit codes `PC-YYYYMMDD-HHMMSS-4hex` + append-only vault ledger; WoL magic
  packet; latched idle monitor; `src/pc_actions.py` owner-origin gate + confirmations
  BEFORE commands; LAN surface `GET /telemetry/live-state` (Bearer) + tunnel cmd.
- **Runtime host (ADR-15, amended 2026-08-31)**: ONE container on an Oracle Always-Free
  VM; `scripts/supervise.py` supervises the OmniRoute child + core child as ONE tree
  (first exit → teardown → container exit → docker `restart: unless-stopped` restarts
  whole); core reads `$PORT`, serves `GET /health` + authenticated bridge WSS on the
  single public port; Caddy 2 terminates TLS (auto-HTTPS via a free DuckDNS name); the
  image carries Node 24 + a globally installed OmniRoute (v1.0.1). Disposable-filesystem
  STAYS as a design principle — durable state ONLY in the vault (enforced by
  `tests/test_packaging.py::test_durable_state_only_in_vault`); on the no-sleep VM the
  keep-alive cron is an OPTIONAL liveness alarm, not life support.

## 5. Component map (what exists, where)

| Component | Files | One-liner |
|---|---|---|
| Config/settings | `src/config.py` | Pydantic v2 Settings; `extra=ignore`; empty-string→None normalization; fail-fast on critical vars |
| Gateway client | `src/gateway.py` | SSE streaming, tier fallback chains, mid-stream safety |
| Dispatcher | `src/dispatcher.py` | Front-door: classify → tier → instant ack + stream |
| Bot shell | `src/bot.py`, `src/middleware.py` | Aiogram wiring, owner drop, /start /help, voice ack, errors handler |
| Progressive streaming | `src/skills/telegram_chat_streamer.py` | Placeholder → coalesced edits → final |
| Voice out | `src/voice.py` | Edge-TTS → ffmpeg → Ogg Opus, in-memory bytes |
| Voice in + biometrics | `src/skills/voice_biometric_auth.py`, `src/skills/voice_to_vault_transcriber.py`, `src/skills/social_enrollment.py` | ECAPA-TDNN owner verify, Guest lockdown, Whisper transcription, multi-speaker registry |
| Dialect engine | `src/dialect.py` | M1 teach-lines («تعلمي: …») → pronunciation normalization + prompt snapshot |
| Vault client | `src/vault.py`, `src/vault_expand.py`, `src/skills/social_graph.py` | GitHub-backed Obsidian: CRUD, one-commit expansion, dossiers |
| Google suite | `src/google_auth.py`, `src/google_suite.py`, `src/gmail.py`, `src/email_triage.py`, `src/daily_brief.py` | OAuth + sealed cache, Calendar/Tasks/Drive/Contacts, Gmail watch/sweep, tiered triage, daily brief |
| TokenJuice | (in `src/email_triage.py` path) | Quoted-chain/signature/boilerplate compaction before LLM calls |
| PC bridge | `common/protocol.py`, `bridge/{guard,executor,wol,idle,telemetry,daemon}.py`, `src/bridge_server.py`, `src/pc_actions.py` | Whitelist guard, executor, WoL, idle, daemon, WSS server, owner-origin actions + audit |
| App indexer (v1.0.2) | `src/app_indexer.py` | Start Menu .lnk discovery → PowerShell target resolution → categorized idempotent whitelist merge (System32 dropped; `python -m src.app_indexer [--dry-run]`) |
| Telemetry | `bridge/telemetry.py`, `src/telemetry.py` | psutil snapshot + Tier-1 Arabic narration |
| Syllabus parser | `src/syllabus.py` | PDF → TIER3 strict-JSON → validated DAG → Calendar/Tasks schedule → `Studies/` |
| Expansion (M4) | `src/expansion.py` | Arabic NL cron → runtime capability tasks; loud-disable; `State/capabilities.json` |
| Tutor (M9) | `src/tutor.py` | TIER3 first-principles study artifacts → `Studies/<topic>/` |
| Evening journaler | `src/skills/evening_journaler.py` | 18:00-19:30 check-in + daily ledger `Daily_Logs/` |
| Summary protocol | `src/summary.py`, `common/consent.py` | «هل بتحب ألخص…» consent grammar + numbered-task approval files |
| Packaging | `Dockerfile`, `.dockerignore`, `scripts/supervise.py`, `scripts/deploy_smoke.py`, `.github/workflows/keepalive.yml`, `README.md` (HF metadata) | The ONE container + supervision + smoke checks + keep-alive |
| Release tooling | `src/__init__.py`, `scripts/make_release.py` | Version single-source + verify/tag script (NO force flag) |
| Quality gate | `Makefile`, `scripts/security_gate.py`, `scripts/secret_scan.py`, `scripts/docs_guard.py`, `.githooks/` | Lint→tests→security→docs; pre-commit scanner; conventional commits enforced |
| Tests | `tests/` (285) | Per-spec AC mapping; doubles at the httpx edge; sacred floor (§2.3) |

## 6. Sprint-by-sprint achievements (what was done, in order)

- **Sprint 1 (foundation)**: skeleton + pydantic Settings + health probe → OmniRoute SSE
  client with fallback chains → in-memory Opus voice pipeline → adaptive Jordanian dialect
  engine (M1) → **3-tier brain + Fast Front-Door Dispatcher**.
- **Sprint 2 (Telegram suite)**: Google OAuth + sealed token cache → typed Calendar/Tasks/
  Drive/Contacts clients → Gmail watch/sweep + **dispatch-then-mark** (no crash-window loss)
  → bot shell + owner-drop middleware + progressive chat streamer (<250 ms first edit) →
  **voice biometrics + Guest Mode lockdown (ADR-17, sacred floor)** → multi-speaker
  registry → TokenJuice compaction → local Whisper transcription to `Voice_Memos/` →
  evening journaler + daily ledger.
- **Sprint 3 (vault + PC bridge)**: `VaultClient` (GitHub Contents/Git Data APIs, conflicts,
  frontmatter, first-boot bootstrap) + social graph → one-commit `VaultExpander` (PARA
  backbone immutable) → verbal action-summary consent protocol → **full PC control plane**
  (v1 wire, fail-closed whitelist, executor + audit ledger, WoL, idle, outbound-only
  daemon, confirmations-before-command) → desktop telemetry + Arabic narration.
- **Sprint 4 (expansion + hardening + release)**: syllabus→DAG parser (`pypdf`, strict
  JSON, validated DAG, idempotent scheduling) → runtime capability expansion (Arabic NL
  cron, env-NAME-only credential handling, loud disable) → polymath tutor (first-principles
  TIER3 artifacts) → **gate hardening** (85% branch LIVE, secret scanner in gate, pragma
  policy) → **HF Spaces packaging** (supervised ONE container, `$PORT` health+WSS,
  deploy smoke with secret masking, durable-state audit, keep-alive cron) → **v1.0.0
  release** (version single-source, CHANGELOG drained with Security + Deferred sections,
  scope-lock test, verify-then-tag script, tag + GitHub Release executed) →
  **v1.0.1 + Oracle migration** (HF Docker Spaces discovered paid at deploy time →
  owner ruled Oracle Always Free; ADR-15 amended; Dockerfile gains the Node-24 layer +
  global gateway install the npm gateway always needed; `docs/09-ORACLE-DEPLOY.md`
  written; RUNBOOK/HANDOFF re-anchored).
- Full narrative with commit hashes: `docs/PROJECT-JOURNEY.md` (§10-13) and
  `docs/10-CHECKPOINT.md` (per-sprint skill-rotation ledger).

## 7. Documentation map (where every detail lives)

| File | Contents |
|---|---|
| `CLAUDE.md` | Coding standards + agent directives + stack pins + commands + closed-loop protocol (START HERE for any dev work) |
| `docs/00-VISION.md` | Mission, persona, discovery record |
| `docs/01-ARCHITECTURE.md` | §1 binding mission record, system architecture, ADR index, §8 staged components (not in v1.0), §9 master-directive capability map |
| `docs/02-BACKLOG.md` | Task list with ACs + per-task done records; Deferred Backlog (v1.1+) |
| `docs/03-DECISIONS.md` | **ADRs 1-21+** — every architectural decision with rationale (ADR-15 host + Oracle amendment, ADR-16 brain, ADR-17 biometrics, ADR-18 dispatcher, ADR-19 TokenJuice, ADR-21 vault) |
| `docs/04-RUNBOOK.md` | Setup, env vars, deploy (§4 Oracle primary / §4b keep-alive legacy / §4c other hosts), smokes, troubleshooting, dated validation checklists |
| `docs/09-ORACLE-DEPLOY.md` | The owner's Arabic step-by-step Oracle Cloud deploy guide (account → VM → DuckDNS → Docker → build → sara.env → compose+Caddy → verify → PC bridge) |
| `docs/05-TEST-PLAN.md` | Test strategy, coverage gates, sacred floor, AC→pytest index |
| `docs/06-API-SPECIFICATION.md` | Wire contracts: bridge v1 protocol, LAN surface, vault API usage |
| `docs/07-HANDOFF.md` | THIS FILE |
| `docs/08-OWNER-NEXT-STEPS.md` | The exact step-by-step the OWNER must execute to make Sara live (Arabic) |
| `docs/10-CHECKPOINT.md` | Per-sprint skill-rotation + teardown ledger |
| `docs/PROJECT-JOURNEY.md` | Full narrative history §1-13 with commit hashes |
| `docs/specs/sprint-{1..4}.md` | Implementation specs — interfaces, ACs, error modes (THE contract) |
| `docs/specs/master-directive-2026-08-29.md` | M1-M9 capability directives |
| `CHANGELOG.md` | Keep-a-changelog: `[1.0.1]` (container Node fix + Oracle host) + `[1.0.0]` full Added/Changed/Security/Deferred-to-v1.1 |
| `.env.example` | Credential manifest (names + where to obtain; values never) |

## 8. Verification & ops commands

```powershell
make setup        # bootstrap .venv (py -3.12)
make gate         # FULL quality gate (lint + tests + security + docs) — must be green before any commit
make test         # tests only
.venv/Scripts/python.exe -m src.main --health   # settings + ffmpeg + gateway + telegram probe
.venv/Scripts/python.exe scripts/make_release.py            # release dry-run (verifications)
.venv/Scripts/python.exe scripts/deploy_smoke.py            # 5-check deployment smoke (exit 0 = alive)
make run-core     # core locally
make run-bridge   # PC bridge daemon
```

## 9. Known gaps & blockers (honest, discovered 2026-08-31)

1. **No deployment exists yet.** Code/packaging/tests are complete and tagged; creating
   the Oracle VM + secrets + pools is the owner's next physical step — hand-held in
   `docs/09-ORACLE-DEPLOY.md` (Arabic) + `docs/08-OWNER-NEXT-STEPS.md`.
2. ~~Dockerfile cannot start OmniRoute~~ **FIXED in v1.0.1**: OmniRoute is a **Node/npm**
   application (`npm install -g omniroute` → `omniroute run`, port 20128) whose engines
   demand node >=22.22; the image now installs **Node 24 via NodeSource** and installs the
   vendored clone globally (`npm install -g /app/scripts/omniroute`), with
   `ENV OMNIROUTE_CMD="omniroute run"` as the zero-config default
   (`tests/test_packaging.py::test_dockerfile_contract` asserts all three).
3. **Google 403 (upstream, from sprint 1)**: the Gemini pools were blocked by Google
   ("project denied access"). Gemini is now RETIRED from the brain pins, but the same
   Google Cloud project hosts the OAuth client — if the block extends to API enablement,
   the owner must fix it in Google Cloud console before Gmail/Calendar work anywhere.
4. ~~Google integration blocked inside a Space~~ **RESOLVED by the Oracle host (ADR-15
   amendment)**: the OAuth client JSON (`config/google_oauth_client.json`) still never
   enters git or the image, but on a persistent VM it can be scp'd to
   `~/sara/config/` on the server — Gmail/Calendar/consent run fully on the VM. The
   encrypted token CACHE remains vault-persisted and survives restarts.

## 10. Roadmap (owner-finalized 2026-09-01, decided, not yet built)

Authoritative expanded roadmap — mirrored in ARCHITECTURE §8 and BACKLOG "Deferred Backlog".
Every item enters via the standard spec pipeline (acceptance criteria first, TDD) and
inherits the hard invariants ($0.00/month, owner-only, untrusted-content boundary,
whitelist guardrail).

**Milestone v1.1 — Live Voice Calling & Advanced Acoustic Intelligence**:
- PyTgCalls WebRTC live bidirectional calling + private-session group (v1.0 ships ZERO
  live-call code — scope-locked by test; `TELEGRAM_API_ID/HASH` already provisioned);
  VAD + barge-in (M8); emergency call escalation for critical VIP emails.
- Universal multi-speaker diarization & separation (`skill-universal-speaker-diarization`):
  SepFormer / PyAnnote.audio 3.1 source separation -> ECAPA-TDNN speaker ID against
  `Contacts/` -> parallel faster-whisper transcripts with timestamps + speaker tags —
  across Discord, single-mic speakerphone, group calls, ambient voice notes.
- Universal context-aware affect & emotion engine (`skill-affective-context-engine`):
  prosody/energy/semantics + `User_Info.md` baseline; banter and sarcasm distinguished from
  genuine emotion. STRICT invariant: Sara's female Jordanian persona and warm tone 100%
  preserved across all adaptations.
- Human conversational paralinguistics & self-repair in live calls
  (`skill-human-paralinguistics-and-self-repair`): self-corrections, micro-breaths, relief
  sighs, light laughs, Jordanian fillers («اممم شوف...», «يعني هسا...»).
- Engaged life conversational partner: active listening + natural follow-up questions.
- Carried v1.1 items: `tech-hardware-scout`, `career-project-incubator`,
  Mem0/Firestore (evaluation only — vault loop must prove out).

**Milestone 1-Month Post-Stabilization — Automation & Content Engine**:
- Personal weekly audio story/podcast (`skill-weekly-audio-digest`): Saturday evening
  2-3 minute motivating narrative over the week's 7 `Daily_Logs/` in Sara's voice.
- Shared history & inside-jokes graph (`skill-shared-history-graph`) persisted in Obsidian.
- Clipping bounty automation & anti-shadowban pipeline (`sub-agent-clip-farming-and-warmup`):
  Whop/Drive ingestion -> FFmpeg anti-duplicate mutation (1% zoom, 1.01x speed, AI hooks) ->
  Playwright-Stealth human-behavior warm-up (5-25s watches, 15% likes, 5% follows) ->
  staggered multi-account publishing (TikTok/Reels/Shorts) -> bounty submission + daily
  earnings to `Daily_Logs/`. Sara supervises; owner-gated publishing. ToS/ban risk recorded
  in ARCHITECTURE §8.
- Private VoIP / softphone — SIP over Wi-Fi (v1.5): virtual extensions via Linphone /
  Zoiper, no cellular SIM.

**Milestone v2.0 & Beyond — Gaming, Persona & Multi-Agent Squad**:
- Distributed Civilization VI LAN gaming module: Discord voice, secret Telegram alliance
  coordination, post-match learning in `Studies/Gaming/Civ6/`.
- Autonomous social media virtual persona (AI influencer): consistent LoRA face generation,
  Jordanian captions (Instagram/TikTok).
- Multi-agent squad (post-v2.0): six agents — Sara (Chief of Staff), Captain Sakhr (Fitness),
  Prof. Nour (Academic), Tarek (Dev), Rami (Gaming), Karim (Finance) — shared Telegram group,
  private Obsidian memory silos.

**Formally excluded / deferred (owner decision 2026-09-01)**: complex PC-based ambient
situational awareness (inference-error risk) · cognitive load / burnout guard.

**Parked Future Scope (no version, enters via standard spec pipeline when prioritized)**:
PC Health Monitor · Voice Read-It-Later · Emotional Context Memory · Silent Vault Backup ·
on-demand YouTube/Weather/Maps API calls (per-request, free-tier, $0 preserved).

**Owner-parked rulings (settled — never re-litigate)**: six discovery rulings recorded in
`.claude/PHASE-STATE.md`; gpt-oss-120b never generates user prose; Gemini retired;
all commits directly to `main`; ~10 granular pushed commits per task when the task warrants
it (no manufactured filler); sprint-level HALTs only (no per-task halts).

## 11. How a new agent should start working here

1. Execute the SESSION RESUME PROTOCOL at the top of `.claude/PHASE-STATE.md` (prime
   CLAUDE.md → PHASE-STATE → ARCHITECTURE §1 → DECISIONS → BACKLOG; framework sync with
   local-state-first; preflight gate; resume the marked phase).
2. Read `docs/07-HANDOFF.md` (this file) + the sprint spec for the task at hand.
3. Red test first (AC→pytest mapping is the contract) → minimal code → `make gate` →
   commit directly on `main` → push. No per-task halts unless the owner re-enables them.
4. Never break the sacred floor (§2.3), never ship a secret, never add a paid dependency.
