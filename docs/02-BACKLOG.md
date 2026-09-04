# 02 — Backlog & Task Breakdown

Acceptance criteria are written per task before implementation starts (Phase 2
specification pass refines each into testable criteria). One concern per worktree;
every task lands red->green->refactor with tests and docs in the same commit.

**Re-mapped 2026-08-29 per MASTER DIRECTIVE (second, 3-tier + skill rotation)**: sprint
specs carry the binding AC→pytest contracts; new capabilities specced in
`docs/specs/master-directive-2026-08-29.md` (M1-M9) + ADR-16..21.

**Status matrix (2026-08-31)**: Sprint 1 complete ✅ (teardown in `docs/10-CHECKPOINT.md`).
Sprint 2 complete ✅: 2.1 · 2.2 · 2.3 · 2.3b · 2.4 · 2.5 · 2.6 done — sprint exit
(teardown + Guide review + core-foundation -> main merge).

**Skill rotation**: each sprint ingests upstream skills into `.claude/skills/` for its
duration and applies the **teardown protocol at sprint exit** — wipe `.claude/skills/*`,
keep all code/tests in `src/`+`tests/`, record the sprint entry in `docs/10-CHECKPOINT.md`.
Upstream toolkit inventory: `worldflowai/everything-claude-code`, `mattpocock/skills`,
`dietrichgebert/ponytail`, `amElnagdy/guard-skills`, `3mar-baha/universal-agentic-os`,
`msitarzewski/agency-agents`.

## Sprint 1 — Foundation: Gateway + Voice + Dialect Engine

- [x] **1.1 Project skeleton**: async Python package (`src/`), pydantic-settings config
      loading `.env`, Loguru structured logging, health module.
      *AC*: `make setup && make gate` green from clean clone; config validates all vars in `.env.example`.
- [x] **1.2 OmniRoute client**: OpenAI-compatible client against `OMNIROUTE_BASE_URL`,
      streaming completions, model fallback (`PRIMARY_MODEL` -> `FAST_MODEL` = Gemini dual-brain
      per ADR-16), retry/quota handling.
      *AC*: streaming works against live gateway; unit tests mock fallback ordering. Code+tests
      committed; live-wired 2026-08-29 (SSE-error hardening in); Gemini pools blocked
      upstream by Google (403 project denied — owner-side fix).
- [x] **1.3 Edge-TTS -> Ogg Opus pipeline**: `io.BytesIO` streaming, ffmpeg subprocess
      transcode, first-chunk dispatch. Zero-disk audio invariant.
      *AC*: `test_audio_stream_opus.py` proves Ogg Opus bytes without disk writes; latency budget asserted in integration smoke.
      Done 2026-08-29: AC1-AC8 green (`src/voice.py`); `-probesize 32` amendment keeps the
      first encoded chunk truly streaming (default probesize gates output until EOF).
- [x] **1.4 Adaptive Jordanian dialect engine (foundation)** — M1, Part 2 (Part 1 = the
      2026-08-29 docs overhaul, ✅): `src/dialect.py` normalization before TTS,
      `Dialect_Notes.md` ingestion loop, snapshot injection into prompt.
      *AC*: `tests/test_dialect.py` per master-directive spec M1.
      Done 2026-08-29: 3/3 ACs green; pure sync module, vault wiring lands in 3.1.
- [x] **1.5 3-tier brain + Fast Front-Door Dispatcher** — ADR-16/18: extend
      `src/gateway.py` to the FAST/MEDIUM/HEAVY chain (`google/gemini-3.5-flash-lite` /
      `google/gemini-3.7-flash` / `nvidia/nemotron-3-ultra-550b` + fallbacks), add the
      dispatcher (Tier-1 ack «من عيوني هسا ببدأ...» <250 ms TTFT, route single/dual-tool
      → Tier 2, DAG → Tier 3), migrate `.env` pins to `google/` prefix.
      *AC*: `tests/test_dispatcher.py` routing + fallback ordering; TTFT budget smoke.
      Done 2026-08-29: AC1-AC9 green (9/9; AC10 live smoke pending the Google 403 owner-side
      fix); runtime `.env` migrated to the tier pins; 2-slot chain retired.

## Sprint 2 — Bot Shell + Google Suite + Triage + Biometrics + Evening Ledger

Skills ingested (Sprint 2): `mattpocock/skills` TDD · `guard-skills` clean-code-guard ·
`everything-claude-code` api-integrator. Teardown at sprint exit → `docs/10-CHECKPOINT.md`.

- [x] **2.1 Google OAuth bootstrap + Gmail watch** (foundation for triage): consent flow,
      vault-persisted encrypted token cache (ADR-15 disposable filesystem), Calendar
      read/write, Tasks CRUD, Drive listing, Contacts read; Gmail watch (Pub/Sub or
      polling fallback) parsing to the internal model, dedupe on message ID.
      *AC*: refresh-token reuse proven; fixture emails parse; dedupe test.
      Done 2026-08-30: `src/google_auth.py`/`src/google_suite.py`/`src/gmail.py` green.
- [x] **2.2 `skill-telegram-chat-streamer`**: Aiogram 3.x long polling, owner-ID middleware
      (silent drop), progressive token streaming to chat (placeholder -> ack <250 ms ->
      coalesced edits -> final), voice-note replies via
      `message.answer_voice(BufferedInputFile(...))` wired to `src/voice.py`.
      *AC*: non-owner update produces zero outbound API calls (mocked); owner gets
      streamed brain reply.
- [x] **2.3 `skill-voice-biometric-auth`** — M2 / ADR-17: local voiceprint (ECAPA-TDNN,
      <50 ms CPU), encrypted owner embedding in vault, Guest Mode lockdown + message-taking.
      *AC*: `tests/test_voice_biometric_auth.py` + `tests/test_guest_lockdown.py` (sacred
      floor); done 2026-08-30 — speechbrain pinned, `/enroll-voice` wired, fail-closed.
- [x] **2.3b `skill-social-enrollment`** — multi-speaker voiceprint registry (§2.3b):
      known-contact match → transcript append + centroid stabilize; unknown → owner
      confirm/ignore/unknown three-way verdict; owner-absent events staged in
      `Voice_Memos/Pending_Speakers/` and briefed later; ignored voices never re-match.
      *AC*: `tests/test_social_enrollment.py` per spec §2.3b.
      Done 2026-08-30: `src/skills/social_enrollment.py` + bot contact-mode routing green.
- [x] **2.4 `skill-tiered-email-triage`** — M7 / ADR-19: four tiers; Low=drop,
      Semi=Markdown text, Important=voice note, Critical=priority voice note + repeat ping
      (v1.0); TokenJuice compaction (signatures/boilerplate/quotes stripped, body capped)
      before LLM classification.
      *AC*: `test_email_triage.py` + `tests/test_triage_compaction.py` per spec M7.
      Done 2026-08-30: triage + daily brief + `tokenjuice_compact` (feeds heuristic
      scoring AND the FAST refinement payload) green; settings `TOKENJUICE_MAX_CHARS=4000`.
- [x] **2.5 `skill-voice-to-vault-transcriber`**: inbound voice notes transcribed via LOCAL
      Whisper (STT decision settled — no cloud probe) → YAML-frontmattered Markdown in
      `Voice_Memos/`.
      *AC*: fixture Ogg file produces correctly filed note.
      Done 2026-08-30: `src/skills/voice_to_vault_transcriber.py` (faster-whisper 1.2.1,
      int8 CPU, in-memory ffmpeg decode; atomic same-minute-safe notes) + bot wiring —
      enrolled owner voice → transcribe → file → streamed reply (AC9 + zero-cloud AST scan).
- [x] **2.6 `skill-evening-proactive-journaler`** — M3 + daily brief: `Daily_Logs/`
      ledger, randomized 18:00-19:30 proactive check-in (fires when the day's ledger is
      sparse, calendar-conflict-guarded), morning/daily brief folded in.
      *AC*: `tests/test_evening_journaler.py` per spec §2.6; brief composes from mocked clients.
      Done 2026-08-31: `src/skills/evening_journaler.py` green — randomized
      calendar-guarded check-in, once-per-day ledger with corrigenda on state loss,
      per-section degradation, retry-on-send-failure state semantics.

## Sprint 3 — Obsidian Vault + PC Bridge + Whitelist

Skills ingested (Sprint 3): `mattpocock/skills` TDD + git-guardrails · `guard-skills`
test-guard · `everything-claude-code` systems-architect. Teardown → `docs/10-CHECKPOINT.md`.

- [x] **3.1 `skill-obsidian-vault-architect`** — M6 / ADR-21: git-backed vault client
      (GitHub Contents API), YAML frontmatter writer, PARA path helpers, Zettelkasten
      link builder; first-boot guard test asserts `Contacts/` `Call_Transcripts/` `Studies/`
      `Voice_Memos/` `Daily_Logs/` + profile files exist.
      Done 2026-08-31: `src/vault.py` (Contents API transport + Git Data API structural
      commits + idempotent bootstrap + Studies migration) and `src/skills/social_graph.py`
      (3.1b dossier/extract/file); 31 new tests (181 total), gate green; no plaintext tokens.
      *AC*: `test_obsidian_para.py` + vault-dir guard test; no plaintext tokens.
      PRUNED 2026-09-03 (remediation 3.3, owner-approved): only `social_graph.py` deleted
      — `vault.py` STAYS (the live VaultClient). No production consumer wired the graph.
- [x] **3.2 `skill-dynamic-vault-expander`** — M5: Sara grows directories/tag ontologies as
      domains emerge; every structural change is an auditable git commit; PARA backbone
      expansion-only.
      *AC*: `tests/test_vault_expand.py` per spec M5.
      Done 2026-08-31: `src/vault_expand.py` — `VaultExpander` (one-commit domain growth
      via Git Data API, `_tags.yaml` ontology, backbone immutable pre-flight, idempotent
      vault-state-as-memory); 10 new tests (191 total), gate green.
      PRUNED 2026-09-03 (remediation 3.3, owner-approved): `src/vault_expand.py` +
      `test_vault_expand.py` deleted — no production consumer ever wired it.
- [x] **3.3 `skill-verbal-action-summary-protocol` + conversation capture**: preference
      extraction -> `User_Info.md`, colloquialisms -> `Dialect_Notes.md`; summary protocol
      («هل بتحب ألخص لك شو رح أعمل هسا؟») on task-bearing turns, suppressed for casual ones.
      *AC*: `test_post_call_summary.py` triggers only when actionable tasks exist.
      Done 2026-08-31: `src/summary.py` (TIER-2 extractor, one-pending state machine,
      arbitration + consent binding) + `common/consent.py` (shared grammar for 3.4);
      10 new tests (201 total), gate green.
      PRUNED 2026-09-03 (remediation 3.3, owner-approved): `src/summary.py` +
      `test_post_call_summary.py` deleted — no production consumer ever wired it
      (`common/consent.py` STAYS: pc_actions + bot use it live).
- [x] **3.4 `skill-pc-whitelist-safety-guardrail`**: Windows daemon — outbound-only TLS
      WebSocket to the Space, LAN port 8000, zero public inbound (asserted), WoL magic
      packet UDP:9, 20-min idle -> one offer per window, strict `config/whitelist.json`
      enforcement, unique audit confirmation IDs persisted to vault.
      *AC*: `test_whitelist_guardrail.py` blocks non-whitelisted and records approvals;
      packet bytes match target MAC; 0% unauthorized executions.
      Done 2026-08-31 — `common/protocol.py` (v1 wire, 4401/4400 auth), `bridge/`
      (guard fail-closed + executor + wol + idle + daemon + LanServer + `__main__`),
      `src/pc_actions.py` (origin gate, confirmations-before-command, audit ledger),
      `src/bridge_server.py` (single session, silence watchdog); 13 new tests (216
      total); `docs/06-API-SPECIFICATION.md` formalized (force semantics DROPPED,
      confirmation_id + audit_code documented).
- [x] **3.5 `skill-desktop-telemetry-protocol`**: `GET /telemetry/live-state` over the
      authenticated bridge + tunnel cmd — one psutil LiveState snapshot (cpu/ram/disks/
      uptime/top process), Tier-1 FAST Arabic narration with real numbers, honest offline
      degradation.
      *AC*: `tests/test_desktop_telemetry.py` per spec §3.5.
      Done 2026-08-31: `bridge/telemetry.py` (degraded-on-failure snapshot) + LAN Bearer
      route + `src/telemetry.py` (TelemetryClient: fetch/narrate/report); 12 new tests
      (228 total), gate green.

## Sprint 4 — Dynamic Expansion + Harden + Release (HF Spaces)

Skills ingested (Sprint 4): `guard-skills` docs-guard + test-guard ·
`universal-agentic-os` github-release-packager + circuit-breaker-guard.
Final teardown → `docs/10-CHECKPOINT.md` (v1.0.0 entry).

- [x] **4.1 `module-syllabus-to-dag-parser`**: `pypdf` extraction + Tier-3 heavy model
      (ADR-16) parsing syllabus PDFs into Task DAGs -> Google Calendar / Tasks review
      schedules; artifacts filed to `Studies/`.
      *AC*: fixture syllabus PDF produces a valid DAG + scheduled reviews.
      Done 2026-08-31: `src/syllabus.py` — threaded extraction, TIER3 strict-JSON parse
      (one retry then loud), validated DAG (cycles/orphans named), weighted capped
      schedule with idempotency tags, Studies filing; 9 new tests (237 total), gate
      green. AC10 live smoke (real PDF -> real Calendar sandbox) is owner-side.
      PRUNED 2026-09-03 (remediation 3.3, owner-approved): `src/syllabus.py` + tests
      deleted, pypdf dropped from requirements — no production consumer ever wired it.
- [x] **4.2 `skill-dynamic-capability-expansion`** — M4: owner-supplied credentials -> new
      scheduled async tasks without redeploy; natural-language Arabic cron; loud failure
      disables a task; secrets enter via `.env` only, never chat logs.
      *AC*: `tests/test_expansion.py` per spec M4.
      Done 2026-08-31: `src/expansion.py` — `parse_nl_cron` (Arabic/English phrasing ->
      `ScheduleSpec`, tz pinned to `settings.tz`), `CapabilityScheduler`
      (credential format probe — env NAME only in errors/logs, max-8 cap, reserved-name
      refusal, single `asyncio.Lock`, per-task `wait_for` timeout), failure/timeout
      disables loudly with one owner notify, state record `State/capabilities.json` +
      `restore(pipelines)` re-derivation on restart (ADR-15); 10 new tests (247 total),
      gate green. AC10 live smoke (owner registers a real task on Telegram) is owner-side.
      PRUNED 2026-09-03 (remediation 3.3, owner-approved): `src/expansion.py` + tests
      deleted — no production consumer ever wired it.
- [x] **4.3 `skill-polymath-tutor`**: curriculum compiler — study guides + 10-language
      lessons with YAML frontmatter filed to `Studies/`; first-principles deconstruction;
      no new engine (chat + 3-tier brain + vault).
      *AC*: lesson artifact renders from a fixture topic through mocked brain.
      Done 2026-08-31: `src/tutor.py` — `TUTOR_SYSTEM_PROMPT` (first-principles
      contract, 10 languages, content-as-data clause) + `study_artifact` (ONE
      `Tier.HEAVY` call, topic capped at 120 chars, YAML frontmatter
      type/topic/level/language/links/created/tags, filed to
      `Studies/<topic>/Study Guide.md`); vault failure raises `StudyFilingError`
      carrying the FULL content (loud ERROR + Arabic apology — never lost); AST-scanned
      zero provider/PC surface; 6 new tests (253 total), gate green. AC6 live smoke
      (one real study session) is owner-side.
      PRUNED 2026-09-03 (remediation 3.3, owner-approved): `src/tutor.py` + tests
      deleted — no production consumer ever wired it.
- [x] **4.4 Production hardening + release (HF Spaces primary, Cloud Run documented
      fallback)**: **>=85% BRANCH coverage** (pytest-cov `--cov-branch`) in `make gate`,
      pre-commit secret scanning, $0.00 verification step, Space Dockerfile (`app_port`,
      OmniRoute+core single-image supervision, HF Secrets, keep-alive ping `/health` every
      10 min), disposable-filesystem audit, Cloud Run alternative documented in RUNBOOK.
      *AC*: clean deploy end-to-end; restart proves state re-derives from vault; coverage
      gate green; version 1.0.0 tagged + CHANGELOG finalized.
      Done 2026-08-31 — three slices:
      **4.4a** coverage gate LIVE (`--cov-branch --cov-fail-under=85` in addopts, 85.86%
      measured), secret scanner in `make gate` (`scripts/secret_scan.py`), CI unified on
      `scripts/security_gate.py`, pragma-reason policy enforced (7 tests);
      **4.4b** `Dockerfile` + `scripts/supervise.py` single-tree supervision,
      `$PORT` health+WSS public port (`start_public_port`), `.dockerignore` with runtime
      negations, keep-alive cron workflow, `scripts/deploy_smoke.py` (5 masked checks),
      durable-state audit test, README Space metadata, RUNBOOK §4/§4b/§4c rewrite (18
      tests, 278 total); **4.4c** `src/__version__='1.0.0'` single source, CHANGELOG
      drained to `## [1.0.0] — 2026-08-31` (Added/Changed/Security/Deferred-to-v1.1),
      `scripts/make_release.py` (consistency/clean-tree/gate verifications, --tag-only,
      NO --force), scope-lock test complete exclusion set (7 tests, 285 total), gate
      green 85.62%. Tag + GitHub Release publish are owner steps (script prints the
      exact `gh` command). AC8 post-tag smoke (container from tag + deploy_smoke) is
      owner-side after tagging.
      *Post-release amendment (2026-08-31)*: v1.0.0 released fully (tag + GitHub
      Release published); HF Space host discovered PAID → **ADR-15 amended to Oracle
      Always Free**; v1.0.1 shipped the Node-24 layer the gateway always needed
      (`docs/09-ORACLE-DEPLOY.md` = the deploy guide). Keep-alive cron = optional
      liveness alarm on the no-sleep VM.

## Deferred Backlog

Authoritative expanded roadmap (owner-finalized 2026-09-01; mirrored in ARCHITECTURE §8 and
HANDOFF §10). Items carry skill-pipeline names where assigned; each enters via the standard
spec pipeline (acceptance criteria first, TDD).

### Milestone v1.1 — Live Voice Calling & Advanced Acoustic Intelligence
- [ ] PyTgCalls WebRTC live bidirectional calling engine + private-session group.
- [ ] VAD + barge-in on calls (M8): owner speech cancels Sara's playback mid-stream.
- [ ] Critical-triage escalation to immediate outbound voice call (critical VIP emails).
- [ ] Post-call transcript persistence + selective verbal action-summary protocol.
- [ ] Universal multi-speaker diarization & separation (`skill-universal-speaker-diarization`):
      multi-voice separation across any audio context (Discord, single-mic room speakerphone,
      multi-party group calls, ambient voice notes) — `SpeechBrain SepFormer` /
      `PyAnnote.audio 3.1` separation -> `ECAPA-TDNN` speaker ID against `Contacts/` ->
      parallel `faster-whisper` transcripts with timestamps + speaker tags.
- [ ] Universal context-aware affect & emotion engine (`skill-affective-context-engine`):
      prosody/pitch/energy/semantics + `User_Info.md` baseline; banter/sarcasm/mock-frustration
      distinguished from genuine anger, sadness, fatigue, excitement, deep focus. STRICT
      invariant: Sara's authentic female Jordanian persona and warm tone preserved 100%.
- [ ] Human conversational paralinguistics & self-repair in live calls
      (`skill-human-paralinguistics-and-self-repair`): disfluencies and self-corrections
      («رح أفتح البرنامـ... قصدي اللعبة»), micro-breaths, relief sighs, light laughs before
      jokes, Jordanian fillers («اممم شوف...», «يعني هسا...»).
- [ ] Engaged life conversational partner: active listening, empathetic curiosity, natural
      follow-up questions on the owner's daily situations and reflections.
- [ ] tech-hardware-scout (GPU/CPU pricing, AI news, tracked sites, voice summaries).
- [ ] career-project-incubator (micro-SaaS ideas, CV-boosting portfolio projects).
- [ ] Mem0/Firestore persistent memory layer evaluation.

### Milestone 1-Month Post-Stabilization — Automation & Content Engine
- [ ] Personal weekly audio story/podcast (`skill-weekly-audio-digest`): Saturday evening
      2-3 minute motivating narrative voice note over the week's 7 `Daily_Logs/`, Sara's voice.
- [ ] Shared history & inside-jokes graph (`skill-shared-history-graph`): milestones,
      development struggles, inside jokes, journey narratives persisted in Obsidian.
- [ ] ~~Clipping bounty automation & anti-shadowban pipeline~~ **DEFERRED BY OWNER
      (2026-09-04, v2.0 pass-4)**: «تأجيلها كلياً الى المستقبل فقط في ملفات التوثيق
      سوف نعمل عليه عندما ينضج المشروع الحالي» — no code, no staging, no scaffolds
      until the owner re-activates it. The full design (Whop/Drive clip ingestion ->
      FFmpeg anti-duplicate mutation (1% micro-zoom, 1.01x speed, AI hook/caption
      generation) -> Playwright-Stealth human-behavior warm-up (random FYP 5-25s
      watches, 15% likes, 5% follows, niche search warming) -> staggered multi-account
      publishing (TikTok/Reels/Shorts) -> bounty submission + daily earnings to
      `Daily_Logs/`) stays HERE as the future spec; owner-gated at every publish
      step; platform-ToS/ban risk recorded in ARCHITECTURE §8 when activated.
- [ ] Private VoIP / softphone — SIP over Wi-Fi (v1.5): inbound/outbound calls to virtual
      internal extensions via Linphone / Zoiper, no cellular SIM.

### Milestone v2.0 & Beyond — Gaming, Persona & Multi-Agent Squad
- [ ] Distributed Civilization VI LAN gaming module: Discord voice integration, secret
      in-game alliance coordination via Telegram, post-match tactical learning in
      `Studies/Gaming/Civ6/`.
- [ ] Autonomous social media virtual persona (AI influencer): Instagram/TikTok persona with
      consistent LoRA face generation and Jordanian captions.
- [ ] Multi-agent squad (post-v2.0): six specialized agents — Sara (Chief of Staff),
      Captain Sakhr (Fitness), Prof. Nour (Academic), Tarek (Dev), Rami (Gaming),
      Karim (Finance) — in a shared Telegram group with private Obsidian memory silos.

### Formally Excluded / Deferred (owner decision 2026-09-01)
- [x] Complex PC-based ambient situational awareness — deferred (inference-error risk).
- [x] Cognitive load / burnout guard — deferred.

Reference contracts for tool surfaces: draft `docs/06-API-SPECIFICATION.md.docx`
(`launch_desktop_app`, `save_obsidian_note`, `initiate_telegram_call`) — formalized during Phase 2.
