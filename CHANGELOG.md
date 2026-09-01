# Changelog

All notable changes to this project are documented in this file.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning targets [Semantic Versioning](https://semver.org/) starting at v1.0.0.
("v1.1.0" in project branding names the Universal Agentic OS framework Sara is built on;
product release tags start independently at v1.0.0.)

## [Unreleased]

### Added
- **Two-strong-model brain (owner directive 2026-09-01)**: conversation lane FAST `minimax-m2.7:free` (fb `gpt-oss-120b`) + MEDIUM `gpt-oss-120b`; tool lane HEAVY `nemotron-3-ultra-550b` as the exclusive Gmail/Calendar/Tasks/bridge executor.
- **Dual-tier memory** (`src/memory.py`): 50-message rolling buffer per chat (owner directive — widened from 15), Obsidian long-term envelope (User_Info + Dialect_Notes + today's Daily_Logs) injected every turn, background writers persist each exchange to Daily_Logs and learn durable facts into User_Info.
- **Memory on every chat path (live-debug fix 2026-09-01)**: the ADR-18 `direct` route no longer answers from the history-less router call — simple chat acks at Tier 1 then streams the FAST conversation lane with the full envelope; the router only classifies.
- **Real tool execution loop** (`src/tools.py` ToolRegistry): gmail/calendar/tasks/telemetry/launch/brief with honest offline lines; launch notifies the owner directly with its audit code (no narration).
- **One-command local cycle** (`sara.bat`/`sara.ps1`): full stop->start — kills stale core/bridge processes, gateway preflight check, relaunches both windows (`-StopOnly` / `-Port` supported).
- **Daily conversation summary** (`DailySummarizer`): at 23:50 local the day's last 150 chat turns + Obsidian owner context go to the conversation lane; the detailed Arabic summary lands as a separate `## ملخص محادثة اليوم` section in the day's Daily_Logs note (idempotent, tick-loop like the brief/journaler).
- **Voice-out replies**: owner voice notes now get an ar-JO Ogg Opus voice note of Sara's streamed reply; pending PC-launch confirmations are consumed by the coordinator before the brain sees them.
- **Overlong router ack guard (live-debug fix 2026-09-01)**: minimax sometimes writes a mini-ANSWER into the router's `ack` field, so the owner saw a wrong reply followed seconds later by the real one in the same bubble. Acks over 30 chars are now discarded for the default «من عيوني هسا ببدأ...», and the router prompt forbids answering inside the ack.
- **Honest voice reply on silent/failed transcription (live-debug fix 2026-09-01)**: a 6-second silent voice note transcribed empty and left the owner with two static acks. Empty transcript or transcription failure now answers with the honest line «ما سمعت شي واضح بالملاحظة...» as text AND an ar-JO voice note; the memo is still filed.

## [1.0.2] — 2026-09-01

Owner-directed runtime enhancements ahead of the first cloud deploy (local test phase).

### Added
- **Start Menu app indexer** (`src/app_indexer.py`, `python -m src.app_indexer [--dry-run]`):
  discovers installed applications from both Windows Start Menu shortcut roots
  (`C:\ProgramData\...` + `%APPDATA%\...`), resolves each `.lnk` target through
  PowerShell WScript.Shell COM (batched EncodedCommand — no shell, no quoting hazards),
  categorizes apps (Coding / Gaming / Study / Productivity) and merges them into
  `config/whitelist.json` so the owner never hand-writes executable paths. Safety
  contract: only Start-Menu-installed desktop shortcuts enter the whitelist — anything
  resolving under `C:\Windows` (System32 included) is dropped; existing entries and
  `restricted_actions` are preserved verbatim; merging is idempotent (casefold dedupe);
  the whitelist Guard keeps re-reading the file per check. First live run: 223
  shortcuts discovered, 154 apps merged, 63 system binaries skipped.
- **Headless remote boot documentation** (RUNBOOK §5b): Windows Auto-Logon via
  Sysinternals Autologon (LSA secret, preferred) or netplwiz, so a Wake-on-LAN magic
  packet boots straight into the owner's desktop session; bridge daemon auto-start via
  Task Scheduler (ONLOGON preferred — runs in the user session after auto-logon;
  ONSTART alternative documented); end-to-end headless proof checklist.

## [1.0.1] — 2026-08-31

Patch release closing the two gaps discovered while preparing the first cloud deploy.

### Fixed
- **Container could never start the gateway**: OmniRoute is a Node/npm application
  (engines `node >=22.22`) while the image was `python:3.12-slim` — no Node runtime.
  The Dockerfile now installs Node 24 via NodeSource and installs the vendored
  OmniRoute clone globally (`npm install -g /app/scripts/omniroute` — the clone pins
  the gateway version), with `ENV OMNIROUTE_CMD="omniroute run"` as the zero-config
  default. Asserted by `tests/test_packaging.py::test_dockerfile_contract`.

### Changed
- **ADR-15 amended: Oracle Cloud Always Free replaces the HF Space as production host**
  (owner ruling 2026-08-31). HF made Docker/Gradio Spaces a paid PRO feature ($9/mo —
  breaks the $0.00 invariant); Render/Koyeb/Cloud-Run free tiers (512 MB) cannot carry
  the full stack. The container design is unchanged and host-agnostic; the
  disposable-filesystem rule stays as a design principle, and the OAuth client JSON may
  live on the VM (never git), resolving the Space-era Google gap. Owner deploy guide:
  `docs/09-ORACLE-DEPLOY.md`; RUNBOOK §4 re-anchored; keep-alive cron now optional
  (the VM never sleeps).

## [1.0.0] — 2026-08-31

First tagged release: **Sara (سارة)** — an owner-only, strictly-zero-cost executive
assistant speaking warm Jordanian Arabic over Telegram, reasoning through a 3-tier
multi-model brain behind a fast front-door dispatcher, running 24/7 in one free
Hugging Face Space with all durable state in a git-backed Obsidian vault.

### Added
- **Sprint 4 / task 4.4c — release v1.0.0**: single version source
  (`src/__version__`) with a consistency guard, and `scripts/make_release.py` —
  verifications (version == newest CHANGELOG heading naming both on mismatch; clean
  `git status --porcelain`; green `make gate`) then the annotated tag on the validated
  HEAD (`--tag` only; an existing tag means bump to 1.0.1, and there is deliberately
  NO --force flag — its absence is the safety feature). Publishing stays an owner step
  with the exact `gh release create` command printed by the dry run. Scope-lock test
  freezes the full settled v1.0 exclusion set (pytgcalls/telethon/pyrogram/mem0/
  firestore absent from artifacts and runtime imports).
- **Sprint 4 / task 4.4b — HF Spaces packaging (the ONE container, ADR-15)**:
  `Dockerfile` (python:3.12-slim, ffmpeg, non-root `sara` user, TZ=Asia/Amman) whose
  entrypoint is the new single-tree supervisor `scripts/supervise.py` — OmniRoute
  gateway child + core child (commands via `OMNIROUTE_CMD`/`CORE_CMD`; first child to
  exit tears down the tree and becomes the container exit, so the Space restarts whole,
  never half-alive). The core reads `$PORT` and serves `GET /health` + the authenticated
  bridge WSS on the single public port (`src.main.start_public_port`). `.dockerignore`
  keeps secrets/tests/docs/OAuth client/sessions out of the build context while
  re-including the two runtime needs. `.github/workflows/keepalive.yml` pings the Space
  `/health` every 10 minutes and fails loudly on any non-200 (shipped contract, not an
  ops footnote). `scripts/deploy_smoke.py` turns "is Sara alive?" into an exit code —
  five checks (gateway/telegram/vault/google_token_cache/space_health), per-check
  timeout bounds, all checks run even after one fails, and a Settings-aware masker
  screens EVERY failure detail (httpx errors embed full URLs carrying the bot token —
  nothing secret survives into logs; host + path class remain). Durable-state audit
  test locks every disk write in runtime code to ADR-15-justified stores; README gains
  Space metadata (sdk: docker, app_port) + HF Secrets policy; RUNBOOK §4 rewritten
  (Space deploy / keep-alive / Cloud Run fallback) with troubleshooting rows and a
  dated validation checklist ending in deploy_smoke exit 0.
- **Sprint 4 / task 4.4a — quality-gate hardening**: the >=85% branch coverage threshold
  is LIVE — `--cov=src --cov=bridge --cov=common --cov-branch --cov-fail-under=85` lives
  once in pytest `addopts` (85.86% measured at activation; Sprints 1-3 ran
  measurement-only, per Guide amendment note in TEST-PLAN §1). The vendored
  `.githooks/pre-commit` secret scanner now runs inside `make gate`
  (`scripts/secret_scan.py` — the hook's pattern battery over tracked files, placeholder
  allowlist intact) and a finding fails the gate exactly like a bandit high; CI's bandit
  step is unified onto `scripts/security_gate.py` (one gate implementation everywhere).
  Pragma policy enforced by test: every `pragma: no cover` / `# nosec` carries
  `-- <reason>` (`__main__` guards and OS-gated branches only; ffmpeg-binary fallbacks
  NOT allowlisted). The threshold mechanism is proven to fail closed (mini-project
  subprocess at fail_under=100).
- **Sprint 4 / task 4.3 — skill-polymath-tutor (M9)**: `src/tutor.py` — first-principles
  tutoring as a persona behavior of the existing chat+brain+vault loop, NO new engine:
  `study_artifact(topic, level, language, gateway, vault)` drives ONE `Tier.HEAVY`
  conversation (temperature 0.4, 4096-token budget) under `TUTOR_SYSTEM_PROMPT` —
  first-principles deconstruction (concept/why/how it's built), a graded learning
  path, 5 drills with answers, bilingual key terms, in the requested language
  verbatim (10 languages, Arabic-first). Artifacts file to
  `Studies/<topic>/Study Guide.md` with complete YAML frontmatter
  (type/topic/level/language/links/created/tags) and wikilinks; oversized topics cap
  at 120 chars. Boundaries: no provider or PC surface in the module (AST-scanned);
  generated content is DATA — imperative strings store verbatim and trigger nothing;
  vault failure logs ERROR + raises `StudyFilingError` carrying the FULL content with
  an Arabic apology so the reply never loses the guide.
- **Sprint 4 / task 4.2 — skill-dynamic-capability-expansion (M4)**:
  `src/expansion.py` — Sara gains capabilities at runtime, no redeploy (ADR-15 state
  re-derivation): the owner hands a credential env NAME in chat; `CapabilityScheduler`
  probes presence/format (>= 16 chars, no whitespace) with ONLY the NAME in errors and
  logs (the value never leaves `.env`), parses Arabic/English natural-language
  scheduling («كل صباح 7» → daily 07:00, «كل اثنين 9» → weekly, «كل ساعة» → hourly,
  gibberish → `ExpansionError`) with the clock zone pinned to `settings.tz`, and
  registers a background asyncio job (`register_capability` — reserved-name refusal,
  max-8 cap, single-lock serialization). Any failure or `wait_for` timeout DISABLES the
  task loudly (ERROR log with the task name + one owner notify, no silent retry loops);
  re-enable is an explicit owner action. Registry persists to `State/capabilities.json`;
  `restore(pipelines)` re-derives enabled tasks after a restart. Pipelines receive one
  ctx dict (`name`/`credential_env`/`vault`) — the secret VALUE never travels.
- **Sprint 4 / task 4.1 — module-syllabus-to-dag-parser**: `src/syllabus.py` turns a
  course syllabus PDF into an executable study plan — threaded `pypdf` extraction
  (length-capped untrusted input), ONE TIER3 `HEAVY_MODEL` call with strict-JSON output
  (one malformed retry, then loud `SyllabusError`; temperature 0, max_tokens 4096
  budget), nx-free DAG validation (cycles and orphan prereqs rejected with named
  offenders, deadlines parsed), weighted capped review schedule (60-min sessions
  backward from each deadline, daily cap, `[sara:syllabus:...]` idempotency tags on
  every Calendar event and Tasks entry), and the compiled plan filed to
  `Studies/<course>/` with YAML frontmatter. PDF text is DATA never instructions —
  the module has no PC-action surface (AST-scanned by AC7). New dep `pypdf>=5` (BSD-3).
- **Sprint 3 / task 3.5 — skill-desktop-telemetry-protocol**: one psutil snapshot
  (`bridge/telemetry.live_state()` — cpu, ram, C:/D: disks, uptime, top-CPU process,
  <2 s) that degrades unmeasurable metrics to None instead of crashing; served two
  ways: `GET /telemetry/live-state` on the LAN surface (Bearer BRIDGE_TOKEN — 401
  without it, 404 when unwired) and the tunnel cmd `telemetry.state` executed by the
  daemon. Core-side `TelemetryClient` (`src/telemetry.py`): pydantic-validated fetch,
  ONE Tier-1 FAST Arabic narration with the state numbers as verbatim DATA
  («شو وضع الجهاز؟»), deterministic numeric fallback when the brain is unreachable,
  honest «الجسر مو متصل هسا» when the bridge is offline. Payload carries no secrets.
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
  brain failure never breaks the reply; bounded filing retries.
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
  confirmation; `Ignored/` never appends).
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
  PRIMARY/FAST chain retired.
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
- **Branch directive (owner, 2026-08-31, binding)**: ALL commits land directly on
  `main` and push immediately; the per-stream worktree/branch merge pattern retired
  (the `core-foundation` worktree is a reference checkout only).
- **Quality gate hardened (4.4a)**: >=85% branch coverage enforced from 4.4a onward
  (Sprints 1-3 ran measurement-only — decided deviation, documented in TEST-PLAN §1);
  CI unified onto one gate script.

### Security
- **Owner-only access surface**: non-owner Telegram accounts dropped silently at
  middleware level; two-layer owner auth composes the allowlist with local voice
  biometrics (ECAPA-TDNN, fail-closed) — any verification error or below-threshold
  voice lands in Guest Mode: warm lockdown reply, message-taking only, ZERO
  privileged effects.
- **Secrets never travel**: all credentials load strictly from environment/HF
  Secrets; vault token redacted on every log/exception path (`redact_secret`);
  capability registration handles credential env NAMES only (the value never leaves
  the environment, never reaches ctx, never reaches logs); the bridge token travels
  only inside the first Hello frame and is never logged; deploy-smoke failures are
  screened through a Settings-aware masker (httpx errors embed full URLs carrying
  the bot token — nothing secret survives into logs).
- **Whitelist guardrail**: any PC action outside `config/whitelist.json` requires an
  explicit owner confirmation with the confirmation ID persisted to the vault BEFORE
  the command leaves the core; power actions always require it; the whitelist guard
  fails CLOSED on a corrupt file (CRITICAL); force semantics were dropped from the
  API specification entirely.
- **Untrusted content boundary**: email bodies, PDF text, web pages and generated
  study content are DATA never instructions — triage containment, syllabus/tutor
  AST-scanned zero PC-action surfaces, LLM output strict-JSON validated with loud
  garbage collapse.
- **Build/deploy hygiene**: `.dockerignore` keeps `.env`, OAuth client JSON, session
  files and local state out of the build context; the vendored secret scanner runs
  inside `make gate` (known API key formats, credential-assignment heuristic with
  placeholder allowlist, committed-.env detection); container runs non-root; durable
  state confined to the vault by an enforced audit test.

### Deferred-to-v1.1
- Live bidirectional Telegram voice calls (PyTgCalls WebRTC engine) — v1.0 ships
  ZERO live-call code, locked by test.
- tech-hardware-scout and career-project-incubator proactive skills.
- Mem0/Firestore persistent memory layer (evaluation deferred).
