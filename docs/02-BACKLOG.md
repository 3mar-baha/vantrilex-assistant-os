# 02 — Backlog & Task Breakdown

Acceptance criteria are written per task before implementation starts (Phase 2
specification pass refines each into testable criteria). One concern per worktree;
every task lands red->green->refactor with tests and docs in the same commit.

## Sprint 1 — Foundation: Gateway + Voice Pipeline + Bot Shell

- [x] **1.1 Project skeleton**: async Python package (`src/`), pydantic-settings config
      loading `.env`, Loguru structured logging, health module.
      *AC*: `make setup && make gate` green from clean clone; config validates all vars in `.env.example`.
- [ ] **1.2 OmniRoute client**: OpenAI-compatible client against `OMNIROUTE_BASE_URL`,
      streaming completions, model fallback (`PRIMARY_MODEL` -> `FAST_MODEL`), retry/quota handling.
      *AC*: streaming works against live gateway; unit tests mock fallback ordering.
- [ ] **1.3 Edge-TTS -> Ogg Opus pipeline**: `io.BytesIO` streaming, ffmpeg subprocess
      transcode, first-chunk dispatch.
      *AC*: `test_audio_stream_opus.py` proves Ogg Opus bytes without disk writes; latency budget asserted in integration smoke.
- [ ] **1.4 Aiogram 3.x shell**: long polling, owner-ID middleware (silent drop),
      `/start`, `/help`, text echo-through-brain handler.
      *AC*: non-owner update produces zero outbound API calls (mocked); owner gets brain reply.

## Sprint 2 — Google Suite + Tiered Email Triage

- [ ] **2.1 Google OAuth bootstrap**: consent flow, token cache, Calendar read/write,
      Tasks CRUD, Drive listing, Contacts read.
      *AC*: integration test against sandbox project; refresh-token reuse proven.
- [ ] **2.2 Gmail watch + fetch**: Pub/Sub push or polling fallback; parse to internal model.
      *AC*: fixture emails parse; dedupe on message ID.
- [ ] **2.3 Triage classifier + dispatcher**: four tiers per `docs/01-ARCHITECTURE.md` §4;
      Low=drop, Semi=Markdown text, Important=voice note, Critical=priority voice note + repeat ping (v1.0).
      *AC*: `test_email_triage.py` asserts correct dispatch per urgency class incl. untrusted-body containment.
- [ ] **2.4 Daily brief**: calendar + triage digest at configured time.
      *AC*: brief composes from mocked calendar/gmail clients.

## Sprint 3 — Obsidian Vault + PC Bridge + Whitelist

- [ ] **3.1 Git-backed vault client**: GitHub API (or local clone) read/write, YAML
      frontmatter writer, PARA path helpers, Zettelkasten link builder.
      *AC*: `test_obsidian_para.py` covers note create/update, frontmatter, links; no plaintext tokens.
- [ ] **3.2 Voice memo ingestion**: inbound Telegram voice note -> transcription ->
      YAML-tagged note into `Voice_Memos/`.
      *AC*: fixture Ogg file produces correctly filed note.
- [ ] **3.3 Conversation capture**: preference extraction -> `User_Info.md`,
      colloquialism capture -> `Dialect_Notes.md`; action-summary protocol
      ("هل بتحب ألخص لك شو رح أعمل هسا؟") on task-bearing turns.
      *AC*: `test_post_call_summary.py` triggers only when actionable tasks exist.
- [ ] **3.4 Bridge protocol**: TLS WebSocket server (core) + outbound daemon (PC);
      command/response envelope, heartbeat, auth via `BRIDGE_TOKEN`.
      *AC*: protocol conformance suite both sides; daemon holds zero listening ports (asserted).
- [ ] **3.5 Windows-MCP executor + whitelist guard**: launch apps/files, drive access C:/D:;
      `config/whitelist.json` enforcement, confirmation round-trip, confirmation IDs persisted.
      *AC*: `test_whitelist_guardrail.py` blocks non-whitelisted, records approvals; 0% unauthorized executions.
- [ ] **3.6 Wake-on-LAN + idle monitor**: magic packet from daemon NIC; 20-min idle ->
      shutdown/sleep offer by message.
      *AC*: packet bytes match target MAC; idle timer fires offer exactly once per window.

## Sprint 4 — Harden & Release

- [ ] **4.1 Full quality gate**: lint, tests, bandit, docs guard green.
- [ ] **4.2 Packaging**: Dockerfile (core), systemd unit notes, VPS deploy runbook validated end-to-end.
- [ ] **4.3 Release**: version 1.0.0, CHANGELOG finalization, git tag, artifacts.

## Deferred Backlog

### v1.1
- [ ] PyTgCalls WebRTC live bidirectional calling engine + private-session group.
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
