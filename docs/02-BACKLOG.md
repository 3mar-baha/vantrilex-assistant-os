# 02 — Backlog & Task Breakdown

Acceptance criteria are written per task before implementation starts (Phase 2
specification pass refines each into testable criteria). One concern per worktree;
every task lands red->green->refactor with tests and docs in the same commit.

**Re-mapped 2026-08-29 per MASTER DIRECTIVE**: new capabilities (biometrics/guest mode,
daily ledger + evening check-in, dialect engine, token compaction, vault expansion,
dynamic capability expansion, 85% coverage gate, HF Spaces runtime) are specced in
`docs/specs/master-directive-2026-08-29.md` (M1-M9). Sprint spec files refresh at each
sprint's entry gate from that file + this backlog. Sprint-1 spec is frozen for in-flight 1.2/1.3.

## Sprint 1 — Foundation: Gateway + Voice + Dialect Engine

- [x] **1.1 Project skeleton**: async Python package (`src/`), pydantic-settings config
      loading `.env`, Loguru structured logging, health module.
      *AC*: `make setup && make gate` green from clean clone; config validates all vars in `.env.example`.
- [x] **1.2 OmniRoute client**: OpenAI-compatible client against `OMNIROUTE_BASE_URL`,
      streaming completions, model fallback (`PRIMARY_MODEL` -> `FAST_MODEL` = Gemini dual-brain
      per ADR-16), retry/quota handling.
      *AC*: streaming works against live gateway; unit tests mock fallback ordering. Code+tests
      committed; AC10 live proof pending valid Gemini pool credential (owner-side).
- [ ] **1.3 Edge-TTS -> Ogg Opus pipeline**: `io.BytesIO` streaming, ffmpeg subprocess
      transcode, first-chunk dispatch. Zero-disk audio invariant.
      *AC*: `test_audio_stream_opus.py` proves Ogg Opus bytes without disk writes; latency budget asserted in integration smoke.
- [ ] **1.4 Adaptive Jordanian dialect engine (foundation)** — M1: `src/dialect.py`
      normalization before TTS, `Dialect_Notes.md` ingestion loop, snapshot injection into prompt.
      *AC*: `tests/test_dialect.py` per master-directive spec M1.

## Sprint 2 — Bot Shell + Google Suite + Triage + Biometrics + Evening Ledger

- [ ] **2.1 Aiogram 3.x shell** (moved from old Sprint 1): long polling, owner-ID middleware
      (silent drop), `/start`, `/help`, text echo-through-brain handler.
      *AC*: non-owner update produces zero outbound API calls (mocked); owner gets brain reply.
- [ ] **2.2 Google OAuth bootstrap**: consent flow, token cache (vault-persisted encrypted per
      ADR-15 disposable-filesystem rule), Calendar read/write, Tasks CRUD, Drive listing, Contacts read.
      *AC*: integration test against sandbox project; refresh-token reuse proven.
- [ ] **2.3 Gmail watch + fetch**: Pub/Sub push or polling fallback; parse to internal model.
      *AC*: fixture emails parse; dedupe on message ID.
- [ ] **2.4 Triage classifier + dispatcher + token compaction** — M7: four tiers per
      `docs/01-ARCHITECTURE.md` §4; Low=drop, Semi=Markdown text, Important=voice note,
      Critical=priority voice note + repeat ping (v1.0). Boilerplate/signature/quote stripping
      before LLM classification (TokenJuice pattern).
      *AC*: `test_email_triage.py` + `tests/test_triage_compaction.py` per spec M7.
- [ ] **2.5 Daily brief**: calendar + triage digest at configured time.
      *AC*: brief composes from mocked calendar/gmail clients.
- [ ] **2.6 Speaker verification + Guest Mode** — M2: local voiceprint (ECAPA-TDNN,
      <50 ms CPU), encrypted owner embedding in vault, guest lockdown + message-taking.
      *AC*: `tests/test_biometrics.py` per spec M2; guest-lockdown test joins the sacred floor.
- [ ] **2.7 Daily activity ledger + evening check-in** — M3: `src/journal.py` ->
      `Daily_Logs/YYYY-MM-DD.md`; randomized 18:00-19:30 proactive check-in, calendar-guarded.
      *AC*: `tests/test_journal.py` per spec M3.

## Sprint 3 — Obsidian Vault + PC Bridge + Whitelist

- [ ] **3.1 Git-backed vault client + mandatory directories** — M6: GitHub API (or local
      clone) read/write, YAML frontmatter writer, PARA path helpers, Zettelkasten link builder;
      guard test asserts `Contacts/` `Call_Transcripts/` `Studies/` `Voice_Memos/` `Daily_Logs/`
      exist on first boot.
      *AC*: `test_obsidian_para.py` + vault-dir guard test; no plaintext tokens.
- [ ] **3.2 Voice memo ingestion + STT decision**: inbound voice note -> transcription
      (whisper.cpp via PC bridge vs Groq free tier — decide at task entry with latency/quality
      probe) -> YAML-tagged note into `Voice_Memos/`.
      *AC*: fixture Ogg file produces correctly filed note.
- [ ] **3.3 Conversation capture**: preference extraction -> `User_Info.md`,
      colloquialism capture -> `Dialect_Notes.md`; action-summary protocol
      ("هل بتحب ألخص لك شو رح أعمل هسا؟") on task-bearing turns.
      *AC*: `test_post_call_summary.py` triggers only when actionable tasks exist.
- [ ] **3.4 Vault taxonomy expansion** — M5: Sara grows directories/tag ontologies as domains
      emerge; every structural change is a git commit; PARA backbone expansion-only.
      *AC*: `tests/test_vault_expand.py` per spec M5.
- [ ] **3.5 Bridge protocol**: TLS WebSocket server (core) + outbound daemon (PC);
      command/response envelope, heartbeat, auth via `BRIDGE_TOKEN`; bridge endpoint LAN port 8000,
      zero public inbound (per master directive; HF Space exposes only WSS+/health).
      *AC*: protocol conformance suite both sides; daemon holds zero listening ports (asserted).
- [ ] **3.6 Windows-MCP executor + whitelist guard**: launch apps/files, drive access C:/D:;
      `config/whitelist.json` enforcement, confirmation round-trip, confirmation IDs persisted.
      *AC*: `test_whitelist_guardrail.py` blocks non-whitelisted, records approvals; 0% unauthorized executions.
- [ ] **3.7 Wake-on-LAN + idle monitor**: magic packet UDP:9 from daemon NIC; 20-min idle ->
      shutdown/sleep offer by message.
      *AC*: packet bytes match target MAC; idle timer fires offer exactly once per window.

## Sprint 4 — Dynamic Expansion + Harden + Release (HF Spaces)

- [ ] **4.1 Dynamic capability expansion engine** — M4: owner-supplied credentials -> new
      scheduled async tasks without redeploy; natural-language Arabic cron; loud failure disable.
      *AC*: `tests/test_expansion.py` per spec M4.
- [ ] **4.2 Full quality gate + coverage**: lint, tests, bandit, docs guard green;
      **>=85% test coverage** enforced via pytest-cov in `make gate`.
- [ ] **4.3 HF Spaces packaging**: single Docker Space (OmniRoute + core co-located, `app_port`,
      single-image supervision), HF Secrets wiring, keep-alive cron ping `/health` every 10 min,
      disposable-filesystem audit (all durable state -> vault).
      *AC*: clean deploy end-to-end; restart proves state re-derives from vault.
- [ ] **4.4 Release**: version 1.0.0, CHANGELOG finalization, git tag, artifacts.

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
