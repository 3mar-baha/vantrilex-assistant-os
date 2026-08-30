# 05 — Test Plan & Quality Gates

## 1. Test Architecture

- **Framework**: pytest + pytest-asyncio + unittest.mock; no external test containers required.
- **Coverage target**: >= 85% **branch** coverage (`pytest-cov --cov-branch`) enforced in
  `make gate` from Sprint-4 task 4.4a; Sprints 1-3 ran measurement-only — explicit decided
  deviation, not drift. Threshold never auto-lowered (spec amendment required).
- **Discipline**: TDD red -> green -> refactor per concern; tests are the contract.

## 2. Test Catalog

| Test module | Verifies |
|---|---|
| `test_scaffold.py` / `test_config.py` / `test_logsetup.py` / `test_health.py` | Skeleton: canonical files, Settings validation, logging, health probe (Sprint 1.1) |
| `test_omniroute_gateway.py` | SSE streaming; tier-chain fallback ordering; quota/transient/fatal classification; mid-stream error events never swallowed |
| `test_dispatcher.py` | Sprint 1.5 (ADR-16/18): Tier-1 ack + routing single/dual-tool -> Tier 2, DAG -> Tier 3; TTFT budget smoke |
| `test_chat_streamer.py` | Sprint 2.2: placeholder -> first edit <250 ms; coalesced edits; final verbatim; interjection cancel keeps partial; rate-limit doubles interval; placeholder failure -> aggregate fallback |
| `test_bot_shell.py` | Sprint 2.2 (old-1.4 shell): /start text+voice greeting; /help; owner text streams brain progressively; GatewayError -> apology; voice ack zero gateway calls |
| `test_dialect.py` | M1: note mapping applied; ingestion appends without blocking; snapshot injected into prompt |
| `test_edge_tts_pipeline.py` | Jordanian Arabic synthesis into BytesIO; params flow from Settings; no disk writes; failure reaps ffmpeg |
| `test_audio_stream_opus.py` | Real ffmpeg transcode: valid Ogg Opus headers; first-chunk emission <600 ms |
| `test_owner_middleware.py` | Non-owner updates dropped silently (sacred floor); owner passes through |
| `test_biometrics.py` | M2/ADR-17: owner voice passes threshold; guest lockdown blocks all tools (sacred floor); message taken + filed; embedding encrypted at rest |
| `test_social_enrollment.py` | Social graph (§6b): Case A transcript+centroid; Case B owner-present enroll; Case C three-way verdict (adopt/ignore/unknown+flag); ignored never re-matches |
| `test_story_extractor.py` | Daily narration -> entities filed to `Contacts/{Category}/{Name}.md` + `Daily_Logs/`; ambiguous category confirmed; Ignored not tracked |
| `test_email_triage.py` | Correct dispatch per tier (drop/text/voice-note/priority-ping); untrusted-body containment |
| `test_triage_compaction.py` | M7/ADR-19: signatures/boilerplate/quotes stripped; body capped; tier decisions unchanged on compacted input |
| `test_journal.py` | M3: chronological ledger; randomized once-daily evening trigger; calendar conflict suppresses; thin ledger prompts |
| `test_voice_transcribe.py` | Inbound voice note -> local Whisper transcription -> YAML-tagged note filed to `Voice_Memos/` |
| `test_google_clients.py` | Calendar/Tasks CRUD shapes; refresh-token reuse; fixture-driven parsing |
| `test_obsidian_para.py` | Note create/update; YAML frontmatter; Zettelkasten links; PARA path routing; first-boot mandatory-dir guard |
| `test_vault_expand.py` | M5: new domain -> dir + tags; structural change = git commit; PARA backbone immutable |
| `test_post_call_summary.py` | Action-summary prompt fires only when actionable tasks exist |
| `test_telemetry.py` | `GET /telemetry/live-state`: foreground window, whitelisted processes, categorized screen time — authed channel only |
| `test_bridge_protocol.py` | Envelope conformance, heartbeat, auth rejection, outbound-only + zero listening ports assertion |
| `test_whitelist_guardrail.py` | Non-whitelisted blocks; confirmation round-trip; audit confirmation IDs persisted (sacred floor) |
| `test_wol_idle.py` | Magic-packet bytes match MAC; single idle offer per window |
| `test_syllabus_parser.py` | Sprint 4.1: threaded pypdf extraction; TIER3 strict-JSON parse; DAG cycle/orphan rejection; weighted review schedule; Calendar/Tasks materialization; untrusted-PDF boundary |
| `test_expansion.py` | M4: Arabic NL cron parses; task registers without redeploy; invalid credential rejected loudly; failure disables task |
| `test_tutor.py` | Sprint 4.3: routing via gateway only; artifact filed to `Studies/` with YAML; study content never triggers actions |
| `test_quality_gate.py` | Sprint 4.4a: coverage threshold config; pragma justification; gate order; fails closed; secret scan in gate |
| `test_packaging.py` / `test_deploy_smoke.py` | Sprint 4.4b: Dockerfile/Space contract; dockerignore; supervision; durable-state audit; keep-alive cron; redacted smoke failures |
| `test_release_metadata.py` | Sprint 4.4c: version==CHANGELOG; scope lock (no pytgcalls/telethon/pyrogram/mem0/firestore); release script refusals |

## 3. Quality Gate Checklist (every change)

- [ ] **Clean Code Guard**: `ruff check .` && `ruff format --check .` — zero findings (ADR-12).
- [ ] **Test Guard**: `pytest -v --cov=src` all green at threshold.
- [ ] **Security Scan**: `bandit -r src/` — zero high/critical issues; pre-commit secret
  scanning (vendored `.githooks`) mirrored inside `make gate` from Sprint-4 task 4.4a.
- [ ] **Docs Guard**: canonical docs updated in the same commit as behavior they describe.
- [ ] Second-pass guards (Clean Code / Test / Docs) re-run as independent review passes at Phase 4.

## 4. Integration & E2E

- Live smoke (manual, gated on credentials): owner message -> brain reply -> voice note
  playback; triage fixture run against sandbox Gmail; whitelist confirmation round-trip
  against the real bridge.
- v1.1 additions: PyTgCalls call lifecycle suite lands with the calling engine.

## 5. Exit Criteria per Sprint

Sprint done = backlog AC checked + gate checklist green + docs synced + CHANGELOG entry.
