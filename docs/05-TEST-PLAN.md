# 05 — Test Plan & Quality Gates

## 1. Test Architecture

- **Framework**: pytest + pytest-asyncio + unittest.mock; no external test containers required.
- **Coverage target**: >= 85% **branch** coverage (`pytest-cov --cov-branch`) — LIVE and
  enforced in `make gate` since Sprint-4 task 4.4a (threshold lives once in pytest
  `addopts`, so make / bare-pytest / CI all inherit it; 2026-08-31 measured 85.86%).
  Explicit deviation note (Guide amendment): **threshold enforced from 4.4a; Sprints 1-3
  ran measurement-only** — a decided deviation, not drift. The threshold is never
  auto-lowered (lowering requires a spec amendment).
- **Pragma / nosec policy**: every `pragma: no cover` and `# nosec` MUST carry
  `-- <reason>` on the same line; allowed reasons exhaustively: `__main__` guards and
  OS-gated branches (`sys.platform` blocks unreachable on Linux CI, e.g. WoL raw-socket
  send). ffmpeg-binary-presence fallbacks are NOT allowlisted (Guide amendment) —
  binary-absence branches are trivially mock-testable. `test_quality_gate.py` fails the
  gate on any bare pragma/nosec.
- **Discipline**: TDD red -> green -> refactor per concern; tests are the contract.

## 2. Test Catalog

| Test module | Verifies |
|---|---|
| `test_scaffold.py` / `test_config.py` / `test_logsetup.py` / `test_health.py` | Skeleton: canonical files, Settings validation, logging, health probe (Sprint 1.1) |
| `test_omniroute_gateway.py` | SSE streaming; tier-chain fallback ordering; quota/transient/fatal classification; mid-stream error events never swallowed |
| `test_dispatcher.py` | Sprint 1.5 (ADR-16/18): Tier-1 ack + routing single/dual-tool -> Tier 2, DAG -> Tier 3; TTFT budget smoke; tool lane (2026-09-01): tool+arg verdict -> real registry call -> Tier-3 (nemotron) narration, launch -> ack-only, registry crash / no-registry -> plain tier2, history passthrough; direct route (amended 2026-09-01) acks Tier 1 then streams FAST with the full memory envelope; overlong router ack >30 chars (2026-09-01) discarded for the default placeholder, stream still runs |
| `test_memory.py` | Owner directive 2026-09-01: 50-message rolling buffer per chat (copy-safe); envelope order persona+long-term+history+current; vault excerpt load skips missing notes, survives vault failure, caps sections; background writer appends dated chat sections (capped) to Daily_Logs; FAST-tier fact learner persists to User_Info, ignores transient chat, survives bad JSON/brain failure, never writes empty facts; DailySummarizer (2026-09-01): day_chat_lines extracts/turn-order/caps last 150; summarize_day appends separate `## ملخص محادثة اليوم` section with turns+context in the prompt, skips no-note/prose-only/already-summarized, survives brain failure; due() predicate at 23:50 local |
| `test_tools.py` | ToolRegistry real backends: gmail digest (name+subject, explicit empty, honest google-offline, failure line); calendar 24h in owner tz; tasks due-today filter; telemetry pass-through + offline; launch via coordinator (origin owner_chat) returning None, honest offline/ask lines; brief plain-text with degraded sections; unknown tool honest line; clock-dependent handlers take an injectable `now_fn` (2026-09-02 — no date-rollover test bombs); v2.0 pass-1: `screenshot` (wire cmd + base64 JPEG image_url block into the vision lane + offline line) and `app_sessions` (wire cmd + real-numbers narration + offline/empty honest lines); v2.0 pass-2: `schedule` (engine roundtrip + confirm line + honest google-offline without engine) and `knowledge_graph` (overview node/edge counts + backlink brief + honest no-vault line) |
| `test_screenshot_tool.py` | v2.0 pass-1 (§3-د/2): daemon-side `Executor.screenshot` — real Pillow capture through a spy grab edge returns base64 JPEG (magic bytes verified), zero disk writes; capture failure degrades to an error ExecResult, never raises into the daemon loop |
| `test_app_sessions.py` | v2.0 pass-1 (§3-د/3): `AppSessionTracker` — per-minute accumulation, reopen merges not duplicates, category roll-up sums every minute exactly once, locked-screen gaps pollute nothing, boot/shutdown log pairs sessions, JSON persistence roundtrip across restart, day-rollover, exception-bearing probe = gap |
| `test_app_sessions_narration.py` | v2.0 pass-1: the `app_sessions` tool narrates the fetched report's numbers verbatim; bridge down -> offline line; empty report -> honest none-line |
| `test_screenshot_narration.py` | v2.0 pass-1: the `screenshot` tool's vision message carries a real image_url data-URI; offline line when the bridge is down; malformed payload / dead vision -> honest apology, never a crash |
| `test_close_app.py` | v2.0 pass-1 (§3-د/1): `Executor.close` — whitelisted auto_approve executes `taskkill /IM <image> /F`; non-auto demands confirmation (refused without spawn); unknown app refused without spawn |
| `test_knowledge_graph.py` | v2.0 pass-2 (§3-و): node/edge counts with dangling-link honesty, backlinks, neighbors (in+out), orphan detection, alias `[[path\|alias]]` resolution, extension-less target merging, Arabic DATA brief, unknown node honest empty |
| `test_scheduled_tasks.py` | v2.0 pass-2 (§3-ج/2): note render carries the [sara:task:id] tag + YAML frontmatter; parse roundtrip via real split_frontmatter; no-tag note rejected; create writes note AND mirrors to both Calendar+Tasks; idempotent re-sync (no duplicates); Google-down parks + catch-up re-mirrors; mark_done flips status in the note |
| `test_tool_lane_pass2.py` | v2.0 pass-2: schedule tool (engine called, بكرة-day mapping, confirm line, honest offline without engine); knowledge_graph tool (overview counts, backlink brief, no-vault degrade); keyword net routes «ذكرني...» with title in arg, «مين بيحكي عن», plain chat stays none |
| `test_web_intel.py` | v2.0 pass-4 (§3-هـ): DDG search returns real titles/URLs (uddg unwrapped); empty-on-failure never fabricated; page read strips script/style/nav/footer to clean text; budget cap enforced; DATA-wrapped search block; tool degrade line; net routes «دوّر بالنت عن X» with query in arg (net precedence: explicit verb-phrase beats single-topic words) |
| `test_weather.py` | v2.0 pass-4 (§3-ب/1): static Jordan coords ship (no geocode round-trip on known cities); unknown city geocodes once then fetches; failures honest None; tool default city عمان + degrade; net routes «شو الطقس بعمان» with connector stripped |
| `test_google_extras.py` | v2.0 pass-4 (§3-ب/1): YouTube search real titles/channels/links; no-results empty; quota error loud-empty; unconfigured key offline line; tool narrates results as DATA; net routes «دوّر بفيديو يوتيوب X» |
| `test_instagram_sandbox.py` | v2.0 pass-4 (§3-أ/5, §7): mode=sandbox explicit; every result labeled sandbox=True; post/dm recorded NOT published; is_live flips only on credential; per-instance isolation |
| `test_civ6_staging.py` | v2.0 pass-4 (§3-ح): fog enforcer strips hidden cities/units/diplomacy STRUCTURALLY from Sara's view; own numbers pass through; voice-to-civ binding (خالد=روما, أحمد=مصر, عمر=بابل); unbound speaker None; Lua script ships legal-visibility-only (contract-tested against RevealPlot/cheat identifiers); Studies path convention |
| `test_firecrawl.py` | v2.0 pass-4 (§3-هـ/1, §7): clean Markdown + title extraction; failure/quota/unconfigured -> None never fabricated; 4000-char budget on long articles |
| `test_chat_streamer.py` | Sprint 2.2: placeholder -> first edit <250 ms; coalesced edits; final verbatim; interjection cancel keeps partial; rate-limit doubles interval; placeholder failure -> aggregate fallback |
| `test_bot_shell.py` | Sprint 2.2 shell + 2.3 wiring: /start text+voice greeting; /help; owner text streams brain progressively; GatewayError -> apology; /enroll-voice flow; biometric gate on voice notes (owner ack / Guest lockdown); silent/failed transcription (2026-09-01) -> honest EMPTY_VOICE line as text + voice note, memo still filed, no brain call |
| `test_persona_pass3.py` | v2.0 pass-3 (§3-أ): the persona contract names her FULL tool inventory (mail/calendar/tasks/vault/launch+screenshot/app-sessions/knowledge-web/scheduled/brief); engaged-life stance (الجامعة + أسئلة متابعة); spontaneous texture («قصدي»، «اممم»، relief sigh); honesty floor verbatim (no fabricated actions, data-not-instructions) |
| `test_dialect.py` | M1: note mapping applied; ingestion appends without blocking; snapshot injected into prompt; TTS shaper (2026-09-02): emoji strip, trailing-harakat تسكين (shadda kept), whole-word seed lexicon, owner notes override seed, plain text untouched |
| `test_edge_tts_pipeline.py` | Jordanian Arabic synthesis into BytesIO; params flow from Settings; no disk writes; failure reaps ffmpeg; 64k audio-mode opus + dialect shaper before synthesis + emoji-only rejected pre-spawn (2026-09-02) |
| `test_audio_stream_opus.py` | Real ffmpeg transcode: valid Ogg Opus headers; first-chunk emission <600 ms |
| `test_owner_middleware.py` | Non-owner updates dropped silently (sacred floor); owner passes through |
| `test_voice_biometric_auth.py` + `test_guest_lockdown.py` | M2/ADR-17: sealed voiceprint enroll/verify; match latency <50 ms; corrupt embedding treated unenrolled; below-threshold or ANY error fails closed; guest lockdown = ONE Pending_Speakers staging note + ZERO privileged effects (sacred floor); embedding encrypted at rest |
| `test_social_enrollment.py` | §2.3b: Case A known speaker transcript+centroid; Case B owner-present enroll; Case C three-way verdict (confirm/ignore/unknown+flag); ignored never re-matches; pending briefs survive restart; contact mode zero privileged calls |
| `test_story_extractor.py` | Daily narration -> entities filed to `Contacts/{Category}/{Name}.md` + `Daily_Logs/`; ambiguous category confirmed; Ignored not tracked | *(pruned 2026-09-03, remediation 3.3 — module dead, tests removed)*
| `test_email_triage.py` | Heuristic weights/bands/floors (VIP, keywords, bulk); LLM refinement containment + never-downgrade merge + fallback; per-tier dispatch (drop/text/voice/priority-ping); ping stop conditions; MarkdownV2 escaping; AST import-surface scan |
| `test_triage_compaction.py` | M7/ADR-19: signatures/boilerplate/quotes stripped; body capped; tier decisions unchanged on compacted input |
| `test_evening_journaler.py` | §2.6/AC10: slots randomized inside [18:00, 19:30) Amman; calendar-busy suppresses the check-in but the ledger still lands (checkin_sent: false); ledger once per local day with one corrigenda line on state-loss re-run; per-section «غير متوفر حالياً» degradation; send failure never persists the check-in state; loop survives exceptions |
| `test_voice_to_vault_transcriber.py` | §2.5/AC9: real ffmpeg decode + stubbed-whisper deterministic text -> YAML note filed to `Voice_Memos/` (atomic, same-minute suffix); ZERO outbound STT (AST scan); decode failure chained; empty `(empty)` note; write retry once, never blocks; model-missing names RUNBOOK warmup |
| `test_google_clients.py` | Calendar/Tasks CRUD shapes; refresh-token reuse; fixture-driven parsing |
| `test_google_suite.py` | Calendar/Tasks/Drive/Contacts fixtures parse to typed UTC-normalized models |
| `test_gmail_watch.py` | Sweep/incremental fetch, dedupe, dispatch-then-mark redelivery, watch gating, corrupt-state recovery, lock serialization, parse catalog |
| `test_daily_brief.py` | Exact Amman-localized template render; mocked-client collection (window/cap/threshold); fire-once-per-day persistence; disabled short-circuit; per-section degradation |
| `test_obsidian_para.py` | Note create/update; YAML frontmatter; Zettelkasten links; PARA path routing; first-boot mandatory-dir guard |
| `test_vault_expand.py` | M5: new domain -> dir + tags; structural change = git commit; PARA backbone immutable | *(pruned 2026-09-03, remediation 3.3 — module dead, tests removed)*
| `test_post_call_summary.py` | Action-summary prompt fires only when actionable tasks exist | *(pruned 2026-09-03, remediation 3.3 — module dead, tests removed)*
| `test_desktop_telemetry.py` | Sprint 3.5: psutil LiveState snapshot (degraded-on-failure); Bearer-gated `GET /telemetry/live-state` + tunnel cmd `telemetry.state`; Tier-1 Arabic narration with verbatim numbers + fallback; honest offline line; payload free of secrets |
| `test_bridge_protocol.py` | Envelope conformance, heartbeat, auth rejection, outbound-only + zero listening ports assertion |
| `test_whitelist_guardrail.py` | Non-whitelisted blocks; confirmation round-trip; audit confirmation IDs persisted (sacred floor) |
| `test_wol_idle.py` | Magic-packet bytes match MAC; single idle offer per window |
| `test_syllabus_parser.py` | Sprint 4.1: threaded pypdf extraction; TIER3 strict-JSON parse; DAG cycle/orphan rejection; weighted review schedule; Calendar/Tasks materialization; untrusted-PDF boundary | *(pruned 2026-09-03, remediation 3.3 — module dead, tests removed)*
| `test_expansion.py` | Sprint 4.2/M4: Arabic+English NL cron parse (gibberish raises); runtime registration + settings.tz pin; credential probe rejects missing/short with env NAME only in logs (secret value absent); failure/timeout disables loudly + one owner notify + no-op until re-enable; pipeline output files to vault via ctx; `State/capabilities.json` restore re-derivation; reserved-name refusal; concurrent registration serializes on one lock; next-occurrence arithmetic | *(pruned 2026-09-03, remediation 3.3 — module dead, tests removed)*
| `test_tutor.py` | Sprint 4.3/M9: gateway-only routing (Tier.HEAVY label, no provider imports — AST scan); artifact filed to `Studies/<topic>/` with complete YAML frontmatter; level+language flow into prompt AND frontmatter; imperative content stored verbatim as DATA with zero other vault writes; vault failure -> loud ERROR + `StudyFilingError` carrying the full content; oversized topic capped | *(pruned 2026-09-03, remediation 3.3 — module dead, tests removed)*
| `test_quality_gate.py` | Sprint 4.4a: coverage config parsed (fail_under=85, branch, three sources); threshold inherited via addopts by every runner; pragma/nosec all carry `-- <reason>`; Makefile gate order lint->test->security->docs-guard; CI calls all four guards via the gate script; threshold mechanism fails closed (mini-project subprocess, fail_under=100); secret scan wired into gate and fails on a planted credential |
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
