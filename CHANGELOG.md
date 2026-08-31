# Changelog

All notable changes to this project are documented in this file.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning targets [Semantic Versioning](https://semver.org/) starting at v1.0.0.
("v1.1.0" in project branding names the Universal Agentic OS framework Sara is built on;
product release tags start independently at v1.0.0.)

## [Unreleased]

### Added
- **Sprint 3 / task 3.5 — skill-desktop-telemetry-protocol**: one psutil snapshot
  (`bridge/telemetry.live_state()` — cpu, ram, C:/D: disks, uptime, top-CPU process,
  <2 s) that degrades unmeasurable metrics to None instead of crashing; served two
  ways: `GET /telemetry/live-state` on the LAN surface (Bearer BRIDGE_TOKEN — 401
  without it, 404 when unwired) and the tunnel cmd `telemetry.state` executed by the
  daemon. Core-side `TelemetryClient` (`src/telemetry.py`): pydantic-validated fetch,
  ONE Tier-1 FAST Arabic narration with the state numbers as verbatim DATA
  («شو وضع الجهاز؟»), deterministic numeric fallback when the brain is unreachable,
  honest «الجسر مو متصل هسا» when the bridge is offline. Payload carries no secrets.
  12 new tests (228 total), gate green.
- **Sprint 3 / task 3.4 — skill-pc-whitelist-safety-guardrail (M5)**:
  the PC control plane. `common/protocol.py` — v1 wire (JSON-per-frame, Hello/HelloAck
  token handshake: bad token closed 4401, second session 4400, token never logged);
  `bridge/guard.py` — whitelist re-read per check, fail-CLOSED on corrupt file
  (CRITICAL), power actions ALWAYS need a confirmation id; `bridge/executor.py` —
  detached `shell=False` spawns, audit codes `PC-YYYYMMDD-HHMMSS-4hex`, traversal/UNC
  refusal (`outside_allowed_roots`), missing exe «البرنامج مش موجود عالجهاز»;
  `bridge/wol.py` + `bridge/idle.py` — exact 102-byte magic packet (one UDP:9 sendto)
  and the latched idle monitor (one offer per window, sustained-activity re-arm);
  `src/bridge_server.py` — single-session acceptor, silence watchdog, honest
  `BridgeOffline`; `bridge/daemon.py` — outbound-only dialer (AST-asserted: never
  binds), heartbeat + capped exponential backoff; `src/pc_actions.py` — owner-origin
  gate (`RefusedOrigin`), confirmations-note-BEFORE-command, one audit code chaining
  note → cmd → ExecResult → Telegram, append-only `04_Archives/Audit/pc-ledger.md`;
  `docs/06-API-SPECIFICATION.md` formalizes the contracts (force semantics DROPPED).
  13 new tests (216 total), gate green.

- **Sprint 3 / task 3.3 — skill-verbal-action-summary-protocol**:
  `src/summary.py` + `common/consent.py` — task-bearing turns close with the exact
  Jordanian prompt «هل بتحب ألخص لك شو رح أعمل هسا؟»; `TaskExtractor` rides ONE TIER 2
  MEDIUM call per turn, strict-JSON validated (LLM output is DATA — garbage collapses to
  `[]` loudly, hashed not logged); one pending per turn (newer supersedes, casual turns
  capture nothing); consent grammar shared with 3.4 (`is_affirmative` first-token
  Jordanian match) with the structural binding rule — only an affirmative FOLLOWING the
  live prompt mints consent; approval files
  `04_Archives/Conversations/YYYY-MM-DD-HHMMSS-summary.md` (frontmatter `id`/`asked_at`/
  `resolved_at`/`task_count`/`tags: [action-summary]`, numbered tasks + daily-log
  wikilink); arbitration defers to 3.4's confirmation consumer and re-asks once after;
  brain failure never breaks the reply; bounded filing retries. 10 new tests (201
  total), gate green.
- **Sprint 3 / task 3.2 — skill-dynamic-vault-expander (M5)**:
  `src/vault_expand.py` — `VaultExpander.expand(domain, dirs, tags)` grows new domain
  trees under `01_Projects/<domain>` as structure emerges in conversation: sanitized
  sub-directories, an `_index.md` per directory (wikilinked to the domain root), and the
  tag ontology `<domain>/_tags.yaml` (`domain` / `created` ISO-UTC / `tags`, Arabic
  intact). Every expansion lands as ONE auditable commit (`sara: expand vault —
  <domain>`) through the Git Data API. PARA backbone (`01_Projects/ 02_Areas/
  03_Resources/ 04_Archives/ Contacts/ Call_Transcripts/ Studies/ Voice_Memos/
  Daily_Logs/`) is expansion-only — backbone-touching requests raise
  `BackboneImmutableError` pre-flight (zero API calls) and the module has no
  delete/move code path. Idempotent (vault state IS the memory — re-run = empty delta,
  no commit); invalid proposals refused pre-flight; token never in logs/exceptions.
  10 new tests (191 total), gate green.
- **Sprint 3 / task 3.1 — skill-obsidian-vault-architect (M6 / ADR-21)**:
  `src/vault.py` — THE read/write surface for Sara's git-backed Obsidian vault:
  `VaultClient` over the GitHub Contents API (Bearer + versioned headers, `?ref=VAULT_BRANCH`;
  upsert = sha lookup -> 404 create / 200 update, one 409 GET->PUT retry then
  `VaultConflictError`, auth errors loud with zero retries, >1,000,000-byte payloads refused
  pre-flight), Git Data API `commit_files` for ONE-commit structural changes (legacy
  `02_Areas/Studies/` -> top-level `Studies/` migration), `append_section` for append-only
  dossiers/logs, deterministic title sanitizer (Arabic preserved verbatim), YAML frontmatter
  writer/splitter (`safe_dump`, leading fences only, malformed -> ValueError naming the path),
  PARA path helpers + Zettelkasten wikilinks + canonical constants (PROFILE_USER_INFO,
  PROFILE_DIALECT, CONVERSATIONS/CONFIRMATIONS/AUDIT dirs), `redact_secret` screening every
  log/exception path, and the idempotent M6 first-boot `ensure_mandatory_dirs()` (index note
  per mandatory dir + contacts taxonomy + both profile files; re-run = zero writes).
  Settings: VAULT_GITHUB_REPO / VAULT_GITHUB_TOKEN (SecretStr) now required, VAULT_BRANCH
  (default main); new dep PyYAML>=6,<7. Plus **3.1b** `src/skills/social_graph.py` —
  `SocialGraph`: `dossier()`/`create_dossier()`, FAST-tier `extract_entities()` (strict JSON,
  LLM output is DATA — garbage -> [] loudly), `file_action()` (dated sections into the
  person's dossier AND `Daily_Logs/YYYY-MM-DD.md`; ambiguous category holds for owner
  confirmation; `Ignored/` never appends). 31 new tests (181 total), gate green.
- **Sprint 2 / task 2.6 — skill-evening-proactive-journaler (§2.6)**:
  `src/skills/evening_journaler.py` — closes the owner's day: one Jordanian check-in at a
  `random.uniform` slot inside [18:00, 19:30) Amman (tasks done, critical mail, memos
  filed + one open question), calendar-guarded (booked -> no message, ledger still
  lands), plus the daily ledger `Daily_Logs/YYYY-MM-DD.md` (YAML frontmatter + Calendar/
  Mail/Voice memos/Notes sections, per-section «غير متوفر حالياً» degradation). Once per
  local day (corrigenda line on state-loss re-run); send failure never persists the
  check-in date (30 s retry tick); zero LLM in the hot path. Settings:
  JOURNALER_ENABLED, JOURNALER_WINDOW_START/END, DAILY_LOGS_DIR; state
  `{vault}/State/journaler.json`.
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
- **Sprint 2 / task 2.5 — skill-voice-to-vault-transcriber (ADR-22)**:
  `src/skills/voice_to_vault_transcriber.py` — owner voice notes (post-biometric-gate
  only) decode in-memory via ffmpeg to 16 kHz mono s16le and transcribe with LOCAL
  faster-whisper (MIT, CPU int8; cloud STT settled to never — ADR-22); notes file
  atomically to `Voice_Memos/YYYY-MM-DD-HHMM.md` (YAML frontmatter date/source/
  duration_s, same-minute numeric suffixes, empty transcripts filed as `(empty)`,
  write retried once and never blocking the reply). Bot wiring: enrolled owner voice →
  transcribe → file → transcript enters the standard streamed text pipeline; guest
  voice never reaches the transcriber. Settings: WHISPER_MODEL_SIZE=small,
  WHISPER_COMPUTE_TYPE=int8, VOICE_MEMOS_DIR=Voice_Memos.

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
