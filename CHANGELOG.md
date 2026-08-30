# Changelog

All notable changes to this project are documented in this file.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning targets [Semantic Versioning](https://semver.org/) starting at v1.0.0.
("v1.1.0" in project branding names the Universal Agentic OS framework Sara is built on;
product release tags start independently at v1.0.0.)

## [Unreleased]

### Added
- **Sprint 2 / task 2.3b — skill-social-enrollment (multi-speaker registry, §2.3b)**:
  `src/skills/social_enrollment.py` — `VoiceprintRegistry` extends ADR-17 beyond the
  owner: per-contact Fernet-sealed vectors under `State/voiceprints/` with dossier
  frontmatter (`voiceprint_ref`), owner-first `match` (<50 ms cosine), running-centroid
  stability, transcript appends, and the three-way pending lifecycle — known contact ->
  warm `CONTACT_MODE_AR` message-taking reply (zero privileged calls, bot-wired through
  `verify_or_lockdown`); unknown owner-absent -> `Voice_Memos/Pending_Speakers/` staging;
  verdicts `confirm:{Category}` -> dossier+voiceprint, `ignore` -> `Contacts/Ignored/`
  (never matches again), `unknown` -> `Contacts/Unknown/` + security flag (re-matchable).
- **Sprint 2 / task 2.3 — skill-voice-biometric-auth + Guest Mode (ADR-17)**:
  `src/skills/voice_biometric_auth.py` — sealed single-owner ECAPA-TDNN voiceprint
  (speechbrain pinned, py3.12 wheel-verified; lazy model load, CPU executor, ffmpeg
  in-memory decode): `/enroll-voice` + one owner voice note Fernet-seals
  `{vault}/State/owner_voiceprint.enc`; every voice note then verifies — unenrolled
  -> middleware-only trust (info log), match >= VOICEPRINT_THRESHOLD -> owner path,
  below-threshold or ANY verification error -> Guest Mode (fail-closed): warm
  Jordanian lockdown reply + exactly ONE `Voice_Memos/Pending_Speakers/` staging
  note (transcript placeholder + encrypted embedding, ADR-15-durable, same-minute
  collisions never overwritten) and ZERO privileged effects — spy-proven no
  gateway/whitelist/subprocess/extra-vault calls. `tests/test_guest_lockdown.py`
  JOINS the sacred floor. Settings: VOICEPRINT_THRESHOLD=0.75,
  VOICEPRINT_MODEL=speechbrain/spkrec-ecapa-voxceleb.
- **Sprint 2 — Google integration + tiered email triage (tasks 2.1-2.4)**:
  `src/google_auth.py` (OAuth consent + Fernet-sealed token cache, proactive/401
  single-flight refresh), `src/google_suite.py` (Calendar/Tasks/Drive/Contacts typed
  clients, UTC-normalized), `src/gmail.py` (sweep/incremental fetch with dedupe and
  sweep fallback, dispatch-then-mark redelivery, watch registration, read-only
  peek_unread), `src/email_triage.py` (heuristic tiers + one FAST_MODEL refinement
  with untrusted-data containment and never-downgrade merge; dispatch matrix
  drop/text/voice/critical-ping with ack + owner-activity stops), `src/daily_brief.py`
  (fire-once-per-local-day Jordanian digest — events, due tasks, mail picture —
  deterministic template, per-section degradation). Settings: GOOGLE_VIP_SENDERS,
  TRIAGE_KEYWORDS_*, CRITICAL_PING_*, BRIEF_ENABLED, BRIEF_LOCAL_TIME.
- **Sprint 2 / task 2.4 remainder — TokenJuice compaction (ADR-19)**: pure
  `tokenjuice_compact` (quoted reply chains, signature blocks, legal footers and
  tracking boilerplate stripped; whitespace collapsed; body capped with a truncation
  marker) now feeds BOTH the heuristic body-keyword scan and the FAST refinement
  payload — less free-pool token burn, identical tier decisions. Settings:
  TOKENJUICE_MAX_CHARS=4000.

### Changed
- **Second master-directive alignment (2026-08-29)**: ADR-16 amended in place to the
  3-tier multi-model brain (FAST/MEDIUM/HEAVY via OmniRoute) + ADR-17..21 appended
  (voice biometrics/Guest Mode, front-door dispatcher, TokenJuice, in-memory Opus,
  5-directory vault); Fast Front-Door Dispatcher specced as Sprint-1 task 1.5;
  per-sprint skill rotation with the teardown protocol (`docs/10-CHECKPOINT.md`);
  sprint specs 2-4 exhaustively re-mapped; `.env.example`/`agents_config.json`
  re-pinned to the tier models; `config/whitelist.json` seeded; KPIs add
  Tier-1 TTFT < 250 ms and biometric < 50 ms.
- Documentation consolidation (ADR-14): 22 docx drafts retired from the working tree
  (21 recoverable via git history; 1 via .ingest text); zero-tolerance persona naming
  enforced across all records; Future Scope parked without version numbers (PC Health
  Monitor, Voice Read-It-Later, Emotional Context Memory, Silent Vault Backup,
  on-demand YouTube/Weather/Maps APIs — per-request, free-tier, $0 preserved).

### Added
- **Sprint 2 / task 2.2 — skill-telegram-chat-streamer + bot shell**: progressive delivery
  replaces the one-shot aggregated reply — `src/skills/telegram_chat_streamer.py`
  (`ChatStreamer.stream_reply`) sends the placeholder instantly, fires the first edit on the
  first delta (<250 ms Audio-TTFT), coalesces further deltas at `STREAM_EDIT_INTERVAL_MS`
  (750 ms), lands the final text verbatim, and honors a cancel event (owner interjection
  keeps the partial in the bubble). Error modes: edit rate-limit doubles the interval;
  placeholder failure falls back to the Sprint-1 aggregate send; mid-stream failure -> shell
  apology with delivered text preserved. Bot shell (`src/bot.py` + `src/middleware.py`,
  carried from old-1.4): owner-ID silent-drop middleware on `dp.update.outer_middleware`,
  /start welcome + Ogg voice greeting, /help, voice-note static ack (zero gateway calls),
  typing indicator, global `dp.errors` handler; `FrontDoorDispatcher.handle` now carries the
  persona system prompt into the tier stream. Settings: `STREAM_EDIT_INTERVAL_MS=750` in
  `.env.example`.
- **Sprint 1 / task 1.5 — 3-tier brain + Fast Front-Door Dispatcher** (`src/dispatcher.py`,
  `src/gateway.py` chains): per ADR-16/18 — `Tier` FAST/MEDIUM/HEAVY chains walked per
  request (quota -> immediate advance, transient -> capped retries, fatal -> loud stop,
  unchanged per-tier), one Tier-1 router call classifies (tiny JSON verdict) and yields the
  instant Jordanian ack («من عيوني هسا ببدأ...») as the first delta (<250 ms TTFT budget);
  simple chat answered fully at Tier 1, single/dual-tool intents stream Tier 2, multi-step
  DAGs stream Tier 3; unparsable/failed routing degrades safely to Tier 2 with a loud log.
  Settings carries the tier pins + comma-separated fallback lists (boot fails fast on gaps);
  `.env.example` and the runtime `.env` migrated to the `google/`-prefixed pins; the 2-slot
  PRIMARY/FAST chain retired. AC10 live smoke pending the upstream Google 403 owner-side fix.
- **Sprint 1 / task 1.4 — adaptive Jordanian dialect engine** (`src/dialect.py`): M1
  notes-driven pronunciation normalization before Edge-TTS (longest-term-first),
  never-blocking ingestion of owner teach-lines («تعلمي: term -> phonetic (context)»)
  into `Dialect_Notes.md` YAML entries (term/phonetic/context/date), and the compact
  system-prompt dialect snapshot; pure sync transforms, vault persistence wired at 3.1.
- **Sprint 1 / task 1.3 — voice pipeline** (`src/voice.py`): Edge-TTS -> ffmpeg -> Ogg Opus
  fully in memory as an async byte-chunk iterator; first encoded chunk surfaces immediately
  (time-to-first-encoded-chunk, <600 ms budget — binding Q1; tiny `-probesize 32` keeps the
  stream flowing from the first frames); blank/oversized text rejected pre-spawn; missing
  ffmpeg raises an actionable error; every failure path reaps the ffmpeg child; Edge-TTS
  metadata events never forwarded.
- **Sprint 1 / task 1.2 — OmniRoute client** (`src/gateway.py`): OpenAI-compatible SSE
  streaming as async text-delta iterator; PRIMARY->FAST model fallback; free-pool survival
  (quota -> immediate fallback, transient -> capped-backoff retries, fatal -> loud stop);
  mid-stream failures never restart a partially-yielded reply; missing-[DONE] guard; mid-stream SSE error events classified (never swallowed).
- **Sprint 1 / task 1.1 — project skeleton**: async `src/` package with pydantic v2
  `Settings` validating `.env` (fail-fast on the six critical vars, empty-string→unset
  normalization), one-sink loguru setup, ops health probe (`python -m src.main --health`),
  and the async entrypoint behind `make run-core`.
- Socratic discovery record and confirmed mission statement (persona: Sara سارة).
- Canonical documentation scaffold: CLAUDE.md, README, LICENSE, CONTRIBUTING,
  CHANGELOG, SECURITY, Makefile, CI workflow, and docs/00–05.
- **Phase 2 implementation specifications** (`docs/specs/sprint-{1..4}.md`): per-task
  interfaces, behaviors, testable acceptance criteria mapped to pytest targets,
  error modes, zero-cost checks — drafted by parallel agents and adversarially
  verified (Guide pass); every finding integrated with disposition appendix.
- Session-resume protocol baked into CLAUDE.md + checkpoint file.
- Native stage-gate hooks (`.claude/hooks/`) and resumable phase state
  (`.claude/PHASE-STATE.md`).
- Credential manifest (`.env.example`) covering core (VPS) and bridge (PC) processes.
- Source-of-record planning drafts preserved as `docs/*.docx` (to be superseded by
  markdown specifications during Phase 2).

### Deferred to v1.1
- Live bidirectional Telegram voice calls (PyTgCalls WebRTC engine).
- tech-hardware-scout and career-project-incubator proactive skills.
- Mem0/Firestore persistent memory layer.

## [1.0.0] — Planned
First tagged release: Telegram chat + Ogg Opus voice notes, OmniRoute free-pool
reasoning, Google Workspace integration with tiered email triage, git-backed
Obsidian knowledge vault, whitelisted PC control over an outbound-only bridge.
