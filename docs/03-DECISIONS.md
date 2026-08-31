# 03 — Architecture Decision Records

Status legend: Accepted · Superseded · Deferred.

## ADR-01: OmniRoute as the Central AI Gateway — **Accepted**
- **Context**: High-quality LLM reasoning without recurring monthly bills.
- **Decision**: Route all LLM calls through OmniRoute (`http://localhost:20128/v1`)
  aggregating 90+ free provider pools with quota-aware auto-fallback.
- **Consequences**: $0 inference cost; resilience to provider outages; dependency on
  gateway uptime (mitigated: co-located on VPS, health-checked).

## ADR-02: Telegram as Primary Transport (voice notes now, live calls v1.1) — **Accepted**
- **Context**: PSTN/SIP trunks carry per-minute fees; Telegram voice is free.
- **Decision**: Aiogram 3.x chat + Ogg Opus voice notes in v1.0; PyTgCalls WebRTC
  live calls in v1.1; cloud SIP telephony deferred to v1.5.
- **Consequences**: 100% free voice; live-call fragility isolated out of first release.

## ADR-03: Whitelist Verification Loop for PC Control — **Accepted**
- **Context**: Unrestricted remote OS execution is unsafe.
- **Decision**: `config/whitelist.json` gates all actions; non-whitelisted requests
  require explicit owner confirmation before execution (Telegram prompt in v1.0;
  live verbal call from v1.1); approvals recorded with confirmation IDs.
- **Consequences**: Convenience cost on first use of any app; hard safety floor.

## ADR-04: Persona Named Sara (سارة) — **Accepted** (2026-08-26)
- **Context**: Mission brief said Sara; the prepared docx drafts used a different draft
  persona name, retired per the zero-tolerance naming rule.
- **Decision**: Sara is canonical; all draft material renamed during scaffold.
- **Consequences**: Drafts remain source-of-record with the old name until superseded.

## ADR-05: VPS-Primary Topology with Outbound-Only PC Bridge — **Accepted**
Supersedes draft preference for Google Cloud Run deployment.
- **Context**: The brain (OmniRoute) ran on localhost; Cloud Run could not reach it
  without tunnels; true 24/7 must survive PC sleep.
- **Decision**: Free-tier VPS hosts core + OmniRoute + Edge-TTS pipeline; Windows PC
  runs a bridge daemon that dials OUT over TLS WebSocket (zero inbound ports,
  token-authenticated). WoL magic packets are sent LAN-locally by the daemon.
- **Consequences**: Core survives PC sleep/shutdown; waking the PC requires an external
  LAN-side sender — the on-PC daemon cannot self-wake its host (see runbook §5).

## ADR-06: Owner-Only Access Model — **Accepted**
- **Decision**: Hard Telegram user-ID allowlist (`AUTHORIZED_USER_ID`); all other
  accounts silently dropped at middleware before any processing.
- **Consequences**: Smallest attack surface; no multi-user capability until demand exists.

## ADR-07: v1.0 Scope = Executive Core minus Live Calls — **Accepted**
- **Decision**: v1.0 ships text chat, Ogg Opus voice notes, Google Workspace suite,
  tiered email triage, Obsidian vault, PC control. Deferred to v1.1: PyTgCalls live
  calling, scout skills (tech-hardware-scout, career-project-incubator),
  Mem0/Firestore memory layer. Critical-triage falls back to priority voice note +
  repeat ping until live calls land.
- **Consequences**: Most fragile dependency (WebRTC/MTProto session) excluded from
  first green release.

## ADR-08: Zero-Cost Invariant Absolute — **Accepted**
- **Decision**: Strictly $0.00/month, no exceptions. Whitelist misses confirm via
  Telegram prompt until live calls exist.
- **Consequences**: Provider choice constrained to free tiers/pools forever.

## ADR-09: Credential Manifest with Progressive Gating — **Accepted**
- **Decision**: `.env.example` documents every secret and where to obtain it; each
  phase gate verifies exactly the credentials that phase needs.
- **Consequences**: No upfront credential blockade; explicit readiness checks per phase.

## ADR-10: Python 3.12 Pin — **Accepted**
- **Context**: Machine default is 3.14 (wheel gaps in aiogram/pytgcalls ecosystem);
  3.12 also installed.
- **Decision**: All environments target Python 3.12 via `py -3.12`.
- **Consequences**: Predictable wheels; revisit when ecosystem supports 3.14.

## ADR-11: Docx Drafts Retained as Source-of-Record — **Superseded** by ADR-14
- **Decision**: The 22 `.docx` planning drafts stay committed untouched until their
  content is superseded by markdown specifications (Phase 2); extraction cache
  `.ingest/` is gitignored.

## ADR-14: Docx Source Drafts Retired from Working Tree — **Accepted** (2026-08-26)
- **Context**: Owner-directed consolidation. The smart-documentation audit confirmed the
  markdown suite is the single most-current state (Sara naming, VPS-primary, Phase-2 specs);
  no unique content existed in the drafts beyond what `.ingest/` text extracts preserve.
- **Decision**: Remove all 22 docx from the working tree. The 21 tracked files remain
  recoverable verbatim from git history; the root `.env.example.docx` (never tracked —
  swallowed by the `.env.*` ignore rule) survives as text only via `.ingest/.env.example.md`.
- **Consequences**: Single-source documentation; draft archaeology via
  `git checkout ff2542b -- '*.docx'`; docs guard unaffected (docx never in canonical list).

## ADR-12: Single Formatter (Ruff) — **Accepted**
- **Decision**: Ruff handles lint + format checking; no Black/isort duplication.
  Supersedes the draft gate's "ruff + black" pairing.
- **Consequences**: One tool, one config, same guarantees.

## ADR-13: uos CLI Anchoring & Native Pattern Adoption — **Accepted** (2026-08-26)
- **Context**: `uos.sh` hardwires `REPO_ROOT` to the universal-agentic-os repo itself
  (script_dir/..); its project commands (`status/ingest/plan/dispatch/merge/graph/ship`)
  operate on that repo, not on consumer projects.
- **Decision**: Use `uos doctor` globally for environment diagnostics; apply the OS's
  workflow patterns natively inside this repository — plain git worktrees per stream +
  our `make gate` (functional equivalent of `uos ship`). Revisit a cwd-anchored fork of
  the CLI only if multi-stream dispatch overhead ever justifies it.
- **Consequences**: No dependency on OS-repo internals for daily flow; upstream pulls
  still deliver diagnostics/tooling improvements via `uos doctor` + toolkit sync.

## ADR-15: HF Spaces as the v1.0 Runtime Host — **Accepted** (2026-08-29, MASTER DIRECTIVE; **amended 2026-08-31: Oracle Always Free**)
- **Context**: Master directive ordered cloud deployment over free tiers. Candidate hosts
  evaluated: Hugging Face Spaces (2 vCPU / 16 GB RAM / 50 GB, Docker, no card),
  Koyeb Nano (0.1 vCPU / 512 MB), Render free (512 MB + 15-min sleep). ADR-05's
  VPS-primary ruling is superseded by this owner directive.
- **Decision**: **Hugging Face Spaces** hosts the v1.0 runtime as ONE Docker Space running
  OmniRoute (`localhost:20128`) + the core co-located — preserving the gateway co-location
  architecture verbatim; the Space's single public port serves the WSS bridge endpoint and
  `/health`. Secrets load from HF Secrets (never git). Keep-alive: cron ping on `/health`
  every 10 min. Rejected: Koyeb/Render — 512 MB cannot host whisper.cpp + speaker
  verification (<50 ms CPU KPI) + OmniRoute + core; Render adds a cron life-support
  dependency on top of resource starvation.
- **Consequences (new hard invariants)**: (1) **Disposable-filesystem rule** — the Space's
  disk is ephemeral: ALL durable state MUST live in the git-backed vault or be re-derivable;
  the Google OAuth token cache is vault-persisted (encrypted) or re-consented after restarts.
  (2) Free Spaces may idle-sleep after prolonged inbound silence — the keep-alive ping is
  mandatory config, documented in RUNBOOK. (3) Sprint-4 packaging = Space Dockerfile with
  `app_port`, single-image OmniRoute+core supervision.
- **AMENDMENT (owner, 2026-08-31, `التالي`)**: **Oracle Cloud Always Free replaces HF
  Spaces as the production host.** Discovered at deploy time: HF made Docker/Gradio Spaces
  a paid PRO feature ($9/month — breaks the $0.00 invariant); Render/Koyeb free tiers
  (512 MB / 0.1 vCPU, scale-to-zero) cannot carry the full stack (whisper + biometrics +
  OmniRoute + core), and Cloud Run's free grant caps at the same 512 MB for an always-on
  service. Oracle's always-free Ampere A1 VM (2 OCPU / 12 GB provisioned, expandable to
  4 OCPU / 24 GB) is truly always-on — no keep-alive pinger, no sleep. The container design
  is unchanged and host-agnostic ($PORT, supervised single tree, health+WSS on one port);
  the disposable-filesystem rule STAYS as a design principle (vault remains the only
  durable store — redeploys are trivial), but the OAuth client JSON may now live on the VM
  (never in git), which RESOLVES the Space-era Google gap (03: Google features fully work
  on the VM). Owner deploy guide: `docs/09-ORACLE-DEPLOY.md`. v1.0.1 ships the Node-24
  layer the gateway always needed.

## ADR-16: Three-Tier Brain via OmniRoute (Gemini retired) — **Accepted** (2026-08-29, MASTER DIRECTIVE; amended 2026-08-30)
- **Context**: Gemini is dead for this project: Google denies the key at API level
  (403 "project denied access" even with Generative Language API enabled) and the free
  GenAI tier is gated behind a billing card the owner's bank rejects. OmniRoute probes
  (read-only SQLite, keys redacted) confirmed the key sits under provider `gemini` and
  only `gemini/...` slugs route there. Meanwhile live catalogs: Groq serves ONLY
  `gpt-oss-120b`/`gpt-oss-20b` (llama-3.3-70b-versatile, llama-4-scout, qwen3-32b are
  404-retired — OmniRoute's BUILT-IN groq list is stale; use Import-from-/models);
  OpenRouter `:free` pool imports 400+ models (~2.2s first-byte queue, 50 req/day/account).
- **Decision**: 3-tier chains pinned in .env.example (2026-08-30 bake-off, 7 candidates,
  same Sara persona prompt, TTFT + Jordanian-dialect quality measured):
  - **FAST** (talker — the only model that speaks to the owner):
    `groq/openai/gpt-oss-20b` (0.5s TTFT, clean Jordanian) → fb `openrouter/minimax/minimax-m2.7:free`
  - **MEDIUM** (worker — Obsidian librarian + task executor; never user-facing prose):
    `groq/openai/gpt-oss-20b` → fb minimax → `groq/openai/gpt-oss-120b`
  - **HEAVY** (deep tasks): `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free` → fb `groq/openai/gpt-oss-120b`
- **Rejected on evidence**: gemma-4 (owner: «لغته ركيكة كعربية» — weak Arabic prose);
  nemotron-3-super + ling-3.0-flash (role inversion — addressed the owner as Sara);
  glm-5.2/gemma-26b/inkling (reasoning burned the whole budget → empty replies).
- **Consequences**: gpt-oss-120b is the designated task worker, never writes user-facing
  prose (pins at task 2.3). OpenRouter free = 50 req/day/account; owner adds 6 keys across
  6 accounts — OmniRoute multi-key rotation is native. Gemini never re-pins. Landed task 1.5:
  `src/gateway.py` walks the 3-tier chains + `src/dispatcher.py` routes behind the ADR-18
  front door; the runtime `.env` carries the tier pins. Harness (Claude Code) remains
  GLM-only per the 2026-08-28 owner rule — two distinct layers, never conflated.

## ADR-17: Voice Biometrics & Guest Mode — **Accepted** (2026-08-29, MASTER DIRECTIVE)
- **Context**: The Telegram-ID allowlist cannot tell WHO is speaking inside the owner's
  account (shared device, stolen session).
- **Decision**: Local speaker verification (SpeechBrain ECAPA-TDNN; Resemblyzer fallback)
  scores inbound voice on CPU (<50 ms KPI) against the owner's encrypted voiceprint
  (one-time 5-10 s enrollment, vault-persisted). Composes with the Telegram-ID allowlist:
  matching voice = full access; non-matching voice inside the owner's account = **Guest
  Mode** — warm greeting («يا هلا، الصوت مش صوت عمر... مين بيحكي معي؟»), zero-trust
  lockdown of PC control, Gmail, Calendar and private vault, message-taking filed to
  `Voice_Memos/` or `Contacts/`. The guest-lockdown test joins the sacred floor.
- **Consequences**: $0 preserved (local inference, no cloud biometrics); false-reject risk
  accepted (re-prompt, never fail-open). Landed sprint-2 2.3 (`src/skills/voice_biometric_auth.py`,
  speechbrain ECAPA pinned; Resemblyzer fallback not needed — wheel-verified on py3.12) and
  extended to the multi-speaker registry in 2.3b (`src/skills/social_enrollment.py`):
  per-contact encrypted vectors + three-way pending verdicts (confirm/ignore/unknown-flag),
  guest containment preserved for every non-owner verdict.

## ADR-18: Fast Front-Door Dispatcher — **Accepted** (2026-08-29, MASTER DIRECTIVE)
- **Context**: One model for everything either lags simple replies or under-thinks hard
  planning; free pools make large-model latency worse.
- **Decision**: Tier 1 always answers first (<250 ms TTFT) with an instant acknowledgment
  («من عيوني هسا ببدأ...») while classifying intent: single/dual-tool requests route to
  Tier 2; multi-step chained DAGs (tutoring, syllabus builds, deep coding) route to
  Tier 3. Fire-and-forget from the owner's perspective — Sara always speaks immediately.
- **Consequences**: Landed as `src/dispatcher.py` + the 3-tier config pins (Sprint-1 task
  1.5, 2026-08-29); perceived latency collapses to Tier-1 TTFT even for heavy jobs.

## ADR-19: TokenJuice-Style Compaction Before LLM Triage — **Accepted** (2026-08-29, MASTER DIRECTIVE)
- **Decision**: Email bodies are compacted BEFORE any LLM classification: signatures,
  disclaimers, tracking boilerplate and quoted reply chains are stripped deterministically
  and the remainder capped to the classification budget.
- **Consequences**: Free-pool token burn drops sharply without changing tier decisions;
  classification runs on clean signal.

## ADR-20: Fully In-Memory Ogg Opus Voice Pipeline — **Accepted** (2026-08-29; verified Sprint 1.3)
- **Decision**: Edge-TTS MP3 streams straight into an ffmpeg child (`io.BytesIO`, asyncio
  subprocess, `-probesize 32`); the first encoded Ogg Opus chunk surfaces in ~30 ms and is
  handed to the Telegram sender immediately — zero disk writes anywhere in the path.
- **Consequences**: Binding Q1 (<600 ms first audio chunk) is met by construction; the HF
  Spaces disposable filesystem never sees audio temp files.

## ADR-21: Obsidian 5-Directory Vault Contract — **Accepted** (2026-08-29, MASTER DIRECTIVE)- **Decision**: The vault carries five mandatory top-level directories — `Contacts/`,
  `Call_Transcripts/` (written from v1.1), `Studies/`, `Voice_Memos/`, `Daily_Logs/` —
  plus `02_Areas/Profile/User_Info.md` and `02_Areas/Profile/Dialect_Notes.md`; a
  first-boot guard test asserts every one exists. Taxonomy expansion is dynamic (Sara
  grows dirs/tags as domains emerge, each change an auditable git commit); the PARA
  backbone is expansion-only. `02_Areas/Studies/` migrates to top-level `Studies/`.
- **Consequences**: ADR-15's disposable-filesystem rule has a single durable home for all
  state; the guard test blocks regressions.

> Numbering note: the directive's draft ADR-04..07 (TokenJuice, In-Memory Opus, 5-Dir
> Vault, Owner-only Drop) collide with settled ledger entries (ADR-04 Persona, ADR-05
> VPS — superseded by ADR-15, ADR-06 Owner-only, ADR-07 v1.0 scope). They are recorded
> here as ADR-19/20/21; owner-only drop remains ADR-06.

## ADR-22: Local Whisper STT — Never Cloud — **Accepted** (2026-08-30, settled owner ruling)
- **Context**: Inbound voice notes need transcription. Cloud STT (Google/Whisper API)
  would break the $0.00 invariant and leak the owner's speech to third parties; the
  "no cloud STT probe" ruling is settled — no evaluation pass needed.
- **Decision**: LOCAL `faster-whisper` (MIT) on the CPU executor (`int8` compute),
  model pinned by `WHISPER_MODEL_SIZE` (default `small`), decoded in-memory by ffmpeg
  to 16 kHz mono s16le; first-run model download is a documented RUNBOOK warmup step.
  Runs only after the ADR-17 biometric gate passes — guest voice never reaches the
  transcriber. Landed sprint-2 2.5 (`src/skills/voice_to_vault_transcriber.py`,
  faster-whisper 1.2.1 / ctranslate2 4.8 wheel-verified on py3.12 Windows).
- **Consequences**: $0.00 preserved end-to-end (no STT API ever); the module's import
  surface carries no network libraries (AST-scan tested); first-run model download is
  the documented RUNBOOK warmup, offline afterwards.
