# 02 — Backlog & Task Breakdown

Acceptance criteria are written per task before implementation starts (Phase 2
specification pass refines each into testable criteria). One concern per worktree;
every task lands red->green->refactor with tests and docs in the same commit.

**Re-mapped 2026-08-29 per MASTER DIRECTIVE (second, 3-tier + skill rotation)**: sprint
specs carry the binding AC→pytest contracts; new capabilities specced in
`docs/specs/master-directive-2026-08-29.md` (M1-M9) + ADR-16..21.

**Status matrix (2026-08-29)**: Completed ✅ 1.1 · 1.2 · 1.3 · 1.4 Part 1 (docs
overhaul) — In Progress 🔄 1.4 Part 2 (dialect engine) — queued: 1.5 dispatcher.

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
- [ ] **1.4 Adaptive Jordanian dialect engine (foundation)** — M1, Part 2 (Part 1 = the
      2026-08-29 docs overhaul, ✅): `src/dialect.py` normalization before TTS,
      `Dialect_Notes.md` ingestion loop, snapshot injection into prompt.
      *AC*: `tests/test_dialect.py` per master-directive spec M1.
- [ ] **1.5 3-tier brain + Fast Front-Door Dispatcher** — ADR-16/18: extend
      `src/gateway.py` to the FAST/MEDIUM/HEAVY chain (`google/gemini-3.5-flash-lite` /
      `google/gemini-3.7-flash` / `nvidia/nemotron-3-ultra-550b` + fallbacks), add the
      dispatcher (Tier-1 ack «من عيوني هسا ببدأ...» <250 ms TTFT, route single/dual-tool
      → Tier 2, DAG → Tier 3), migrate `.env` pins to `google/` prefix.
      *AC*: `tests/test_dispatcher.py` routing + fallback ordering; TTFT budget smoke.

## Sprint 2 — Bot Shell + Google Suite + Triage + Biometrics + Evening Ledger

Skills ingested (Sprint 2): `mattpocock/skills` TDD · `guard-skills` clean-code-guard ·
`everything-claude-code` api-integrator. Teardown at sprint exit → `docs/10-CHECKPOINT.md`.

- [ ] **2.1 Google OAuth bootstrap + Gmail watch** (foundation for triage): consent flow,
      vault-persisted encrypted token cache (ADR-15 disposable filesystem), Calendar
      read/write, Tasks CRUD, Drive listing, Contacts read; Gmail watch (Pub/Sub or
      polling fallback) parsing to the internal model, dedupe on message ID.
      *AC*: refresh-token reuse proven; fixture emails parse; dedupe test.
- [ ] **2.2 `skill-telegram-chat-streamer`**: Aiogram 3.x long polling, owner-ID middleware
      (silent drop), live token streaming to chat, voice-note replies via
      `message.answer_voice(BufferedInputFile(...))` wired to `src/voice.py`.
      *AC*: non-owner update produces zero outbound API calls (mocked); owner gets
      streamed brain reply.
- [ ] **2.3 `skill-voice-biometric-auth`** — M2 / ADR-17: local voiceprint (ECAPA-TDNN,
      <50 ms CPU), encrypted owner embedding in vault, Guest Mode lockdown + message-taking.
      *AC*: `tests/test_biometrics.py` per spec M2; guest-lockdown test joins the sacred floor.
- [ ] **2.4 `skill-tiered-email-triage`** — M7 / ADR-19: four tiers; Low=drop,
      Semi=Markdown text, Important=voice note, Critical=priority voice note + repeat ping
      (v1.0); TokenJuice compaction (signatures/boilerplate/quotes stripped, body capped)
      before LLM classification.
      *AC*: `test_email_triage.py` + `tests/test_triage_compaction.py` per spec M7.
- [ ] **2.5 `skill-voice-to-vault-transcriber`**: inbound voice notes transcribed via LOCAL
      Whisper (STT decision settled — no cloud probe) → YAML-frontmattered Markdown in
      `Voice_Memos/`.
      *AC*: fixture Ogg file produces correctly filed note.
- [ ] **2.6 `skill-evening-proactive-journaler`** — M3 + daily brief: `Daily_Logs/`
      ledger, randomized 18:00-19:30 proactive check-in (fires when the day's ledger is
      sparse, calendar-conflict-guarded), morning/daily brief folded in.
      *AC*: `tests/test_journal.py` per spec M3; brief composes from mocked clients.

## Sprint 3 — Obsidian Vault + PC Bridge + Whitelist

Skills ingested (Sprint 3): `mattpocock/skills` TDD + git-guardrails · `guard-skills`
test-guard · `everything-claude-code` systems-architect. Teardown → `docs/10-CHECKPOINT.md`.

- [ ] **3.1 `skill-obsidian-vault-architect`** — M6 / ADR-21: git-backed vault client
      (GitHub API / local clone), YAML frontmatter writer, PARA path helpers, Zettelkasten
      link builder; first-boot guard test asserts `Contacts/` `Call_Transcripts/` `Studies/`
      `Voice_Memos/` `Daily_Logs/` + profile files exist.
      *AC*: `test_obsidian_para.py` + vault-dir guard test; no plaintext tokens.
- [ ] **3.2 `skill-dynamic-vault-expander`** — M5: Sara grows directories/tag ontologies as
      domains emerge; every structural change is an auditable git commit; PARA backbone
      expansion-only.
      *AC*: `tests/test_vault_expand.py` per spec M5.
- [ ] **3.3 `skill-verbal-action-summary-protocol` + conversation capture**: preference
      extraction -> `User_Info.md`, colloquialisms -> `Dialect_Notes.md`; summary protocol
      («هل بتحب ألخص لك شو رح أعمل هسا؟») on task-bearing turns, suppressed for casual ones.
      *AC*: `test_post_call_summary.py` triggers only when actionable tasks exist.
- [ ] **3.4 `skill-pc-whitelist-safety-guardrail`**: Windows daemon — outbound-only TLS
      WebSocket to the Space, LAN port 8000, zero public inbound (asserted), WoL magic
      packet UDP:9, 20-min idle -> one offer per window, strict `config/whitelist.json`
      enforcement, unique audit confirmation IDs persisted to vault.
      *AC*: `test_whitelist_guardrail.py` blocks non-whitelisted and records approvals;
      packet bytes match target MAC; 0% unauthorized executions.
- [ ] **3.5 `skill-desktop-telemetry-protocol`**: `GET /telemetry/live-state` over the
      authenticated bridge — foreground window, whitelisted processes, daily categorized
      screen time.
      *AC*: endpoint returns all three datasets; served only over the authed channel.

## Sprint 4 — Dynamic Expansion + Harden + Release (HF Spaces)

Skills ingested (Sprint 4): `guard-skills` docs-guard + test-guard ·
`universal-agentic-os` github-release-packager + circuit-breaker-guard.
Final teardown → `docs/10-CHECKPOINT.md` (v1.0.0 entry).

- [ ] **4.1 `module-syllabus-to-dag-parser`**: `pypdf` extraction + Tier-3 heavy model
      (ADR-16) parsing syllabus PDFs into Task DAGs -> Google Calendar / Tasks review
      schedules; artifacts filed to `Studies/`.
      *AC*: fixture syllabus PDF produces a valid DAG + scheduled reviews.
- [ ] **4.2 `skill-dynamic-capability-expansion`** — M4: owner-supplied credentials -> new
      scheduled async tasks without redeploy; natural-language Arabic cron; loud failure
      disables a task; secrets enter via `.env` only, never chat logs.
      *AC*: `tests/test_expansion.py` per spec M4.
- [ ] **4.3 `skill-polymath-tutor`**: curriculum compiler — study guides + 10-language
      lessons with YAML frontmatter filed to `Studies/`; first-principles deconstruction;
      no new engine (chat + 3-tier brain + vault).
      *AC*: lesson artifact renders from a fixture topic through mocked brain.
- [ ] **4.4 Production hardening + release (HF Spaces primary, Cloud Run documented
      fallback)**: **>=85% BRANCH coverage** (pytest-cov `--cov-branch`) in `make gate`,
      pre-commit secret scanning, $0.00 verification step, Space Dockerfile (`app_port`,
      OmniRoute+core single-image supervision, HF Secrets, keep-alive ping `/health` every
      10 min), disposable-filesystem audit, Cloud Run alternative documented in RUNBOOK.
      *AC*: clean deploy end-to-end; restart proves state re-derives from vault; coverage
      gate green; version 1.0.0 tagged + CHANGELOG finalized.

## Deferred Backlog

### v1.1
- [ ] PyTgCalls WebRTC live bidirectional calling engine + private-session group.
- [ ] VAD + barge-in on calls (M8): owner speech cancels Sara's playback mid-stream.
- [ ] Critical-triage escalation to immediate outbound voice call.
- [ ] Post-call transcript persistence + selective verbal action-summary protocol.
- [ ] tech-hardware-scout (GPU/CPU pricing, AI news, tracked sites, voice summaries).
- [ ] career-project-incubator (micro-SaaS ideas, CV-boosting portfolio projects).
- [ ] Mem0/Firestore persistent memory layer evaluation.

### v1.5 / v2.0
- [ ] Virtual cloud SIP telephony (landline calling).
- [ ] Social media agent (GitHub, LinkedIn, Instagram).

Reference contracts for tool surfaces: draft `docs/06-API-SPECIFICATION.md.docx`
(`launch_desktop_app`, `save_obsidian_note`, `initiate_telegram_call`) — formalized during Phase 2.
