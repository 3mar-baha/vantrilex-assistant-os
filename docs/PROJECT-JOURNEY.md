# Project Journey — Complete Record (Vantrilex Assistant OS)

Full documentation of everything accomplished, decided, discovered, and deferred —
written at the close of the founding session (2026-08-26). For the authoritative mission
statement see `docs/01-ARCHITECTURE.md` §1; for decisions see `docs/03-DECISIONS.md`;
for live lifecycle state see `.claude/PHASE-STATE.md`.

---

## 1. What This Project Is

**Vantrilex Assistant OS v1.1.0 "Sara (سارة)"** — an owner-only, strictly $0.00/month
executive AI assistant living 24/7 on a free-tier host (founding ruling: VPS — superseded
2026-08-29 by HF Spaces, ADR-15; §10 addendum): Telegram chat + Ogg Opus voice notes
in warm Jordanian Arabic (`ar-JO-SanaNeural`), reasoning through OmniRoute free provider pools,
Google Workspace integration with tiered email triage, a git-backed PARA+Zettelkasten Obsidian
vault, and whitelisted PC control over an outbound-only Windows bridge daemon.
Live PyTgCalls calling → v1.1 · SIP telephony → v1.5 · social-media agent → v2.0.

## 2. Session Timeline (all on 2026-08-26)

| Step | Outcome |
|---|---|
| Preflight | 13-point environment audit: 11 PASS, 2 blocking FAILs (FFmpeg missing, OmniRoute down) — risk accepted by owner, both fixed same-day |
| Socratic Discovery | 6 questions, 6 binding rulings (below); mission confirmed verbatim |
| Scaffold | 22 legacy `.docx` drafts ingested; 16 canonical files authored; native hooks + resumable state; initial commit `ff2542b` |
| Guide Audit #1 | Independent adversarial review of scaffold: 3 BLOCKERs + 5 MINORs found and fixed before commit (credential-filename gap, bare-pytest CI failure, branch naming, honest self-WoL limitation, sleep-needs-confirmation) |
| Preflight re-check | Owner installed FFmpeg 9.0.1; started OmniRoute; brain VERIFIED with real streamed completion (`gemini-3.1-flash-lite`, free pool) |
| Phase 2 Orchestration | 8-agent workflow (4 spec drafters → 4 adversarial Guide verifiers, ~490k tokens, 122 tool calls) produced four sprint specifications |
| Guide Audit #2 | All four verdicts FIX; 1 BLOCKER + 12 MAJOR + ~20 MINOR findings — every one integrated into the specs with disposition appendices |
| Credentials | Bot token stored + verified via `getMe`; vault repo created & PARA-seeded; `.env` manifest filled (15 values) |
| Resilience | Safety-classifier outage mid-session: all remaining deliverables completed through file-tools + web-fetch workarounds; nothing blocked permanently |

## 2b. Session Timeline (2026-08-28 → 2026-08-29)

| Step | Outcome |
|---|---|
| Sprint 1.1 (08-28) | Async skeleton merged to `main` (`221c650`) — owner-directed; gate green, live `--health` proof |
| Closed-loop protocol | Owner-approved binding execution loop (per-task: red→green→`make gate`→commit→report→HALT until "التالي"); sacred floor + circuit breaker pinned |
| Model pin (08-28/29) | Two-layer ruling: harness GLM-only (`z-ai/glm-5.3-flash`); Sara's brain via OmniRoute |
| Sprint 1.2 (08-29) | OmniRoute client (`3e44f1c`): SSE streaming + fallback; live-wired against the real gateway; mid-stream SSE error events classified (silent-empty defect found & fixed); Gemini pools blocked upstream (Google 403 — owner-side fix pending) |
| Sprint 1.3 (08-29) | Voice pipeline (`4d0aefa` + `0e796fd`): in-memory Edge-TTS → Ogg Opus, first encoded chunk ~30 ms (probesize amendment documented); AC1-AC8 green |
| First directive (08-29) | MASTER-DIRECTIVE overhaul (`71a17ca` + `fef6246`): ADR-15 (HF Spaces host) + ADR-16 (brain routing); backlog re-map; M1-M9 spec; docs/config sync |
| Second directive (08-29) | MASTER ARCHITECTURAL DIRECTIVE: 3-tier brain + dispatcher (ADR-16 amended, ADR-17..21 appended), 6 upstream toolkits, per-sprint skill rotation + teardown, sprint specs 1-4 rewritten, full doc/config overhaul |
| Atomic commits (08-29) | Owner-ordered split: voice feature, gateway fix, runbook docs, checkpoint — pushed; working tree clean for shutdown |

## 3. Binding Discovery Rulings

| Q | Ruling |
|---|---|
| 1 | Persona = **Sara (سارة)** — retired draft persona name replaced everywhere canonical |
| 2 | **VPS-primary** topology + outbound-only PC bridge (supersedes draft Cloud Run) |
| 3 | **Owner-only** hard allowlist; silent drop of all other accounts |
| 4 | v1.0 = exec core minus live calls (chat, voice notes, Google suite, triage, vault, PC control) |
| 5 | **$0.00 absolute**; whitelist miss → Telegram confirmation prompt (v1.0) |
| 6 | Credential manifest `.env.example`; progressive per-phase gating |

## 4. Infrastructure Provisioned During the Session

- FFmpeg 9.0.1 full build (winget) — voice-pipeline dependency
- OmniRoute gateway running on :20128 with free pools proven end-to-end
- Telegram bot **@Sara_Vantrilex_bot** created; token `getMe`-verified; owner ID bound
- GitHub vault **3mar-baha/vantrilex-vault** (private) seeded with PARA skeleton +
  `User_Info.md` / `Dialect_Notes.md`
- Local `.env` filled from manifest (secrets gitignored); quality gate green
  (ruff · format · pytest · security · docs-guard 16/16)

## 5. Security Findings Caught Before Any Code Existed

Worth their own section — this is what the adversarial process bought us:

1. 🔴 **`open_path` whitelist bypass** (Sprint-3 draft): file-opening path launched arbitrary
   executables without confirmation — rewritten guard-first with executable-as-app-launch rule.
2. 🟠 **Bot-token log leak**: deploy-smoke failure details would have printed the token inside
   httpx exception URLs — masked redaction layer specified + dedicated test.
3. 🟠 **Crash-window email loss**: seen-state persisted before dispatch could permanently skip
   critical mail — inverted to dispatch-then-mark with re-delivery test.
4. 🟠 **Self-Wake-on-LAN impossibility**: daemon cannot wake its own suspended host — canonically
   ruled and documented (ADR-05, ARCHITECTURE §2, RUNBOOK) instead of silently broken.
5. Confirmation-flow hardening: 10-min TTL, consent binding to explicit prompts, deterministic
   arbitration between pending summaries and confirmations, fail-closed corrupt-whitelist mode.

## 6. Deliverable Map

```
docs/specs/sprint-{1..4}.md   Phase-2 implementation contracts (AC→pytest mapped)
docs/00–05                    Vision, architecture, backlog, ADRs, runbook, test plan
CLAUDE.md                     Agent directives + mandatory session-resume protocol
.claude/PHASE-STATE.md        Resumable lifecycle state (fresh sessions prime from here)
.claude/hooks/                Native stage-gate hooks
Makefile / ci.yml             make gate ≡ CI (ruff, pytest, bandit, docs-guard)
docs/03-DECISIONS.md          ADR-01…13
docs/*.docx                   Original planning drafts (preserved source-of-record)
```

## 7. Commits (this repo)

| Hash | Content |
|---|---|
| `ff2542b` | Canonical scaffold suite (Phase 1) — 47 files |
| `c9f6c62` | Session-resume protocol baked into CLAUDE.md + checkpoint |
| `6fa22f7` | Phase-2 sprint specifications with integrated Guide fixes — 7 files / 1439 insertions |
| *(this commit)* | Project-journey documentation + workflow-repo protection ruling |

## 8. Open Items (owner side, none blocking Phase 3 start)

1. Google Cloud project + OAuth client JSON — needed before Sprint 2 (~20 min, walkthrough in `.env.example`)
2. Free-tier VPS provisioning — needed before Sprint 4 (~30 min; Oracle Always Free / GCP e2-micro)
3. Universal-agentic-os workflow upgrade — owner finalizing locally; will hand over the finished
   repo explicitly; until then that repo is untouched-by-design (protocol step 2)
4. Bridge TLS style (self-signed + SPKI pin vs Let's Encrypt) — decided at Sprint-3 implementation

## 9. Next Steps

Phase 3 — Implement & Verify opens with stream `core-foundation`: Sprint-1 task 1.1
(config/logging/health skeleton) in its own git worktree, strict TDD per
`docs/specs/sprint-1.md`. Every session resumes via the ⚡ SESSION RESUME PROTOCOL at the top
of `.claude/PHASE-STATE.md`.

## 10. Addendum — 2026-08-29: Two Master Directives + Phase 3 under way

**Phase 3 progress (closed-loop, one task per gate):** task 1.1 skeleton merged to main
(`221c650`); task 1.2 OmniRoute client + live-wiring with SSE-error hardening (`3e44f1c`);
task 1.3 Edge-TTS → Ogg Opus in-memory pipeline (`4d0aefa`) — AC1-AC8 green, with the
measured `-probesize 32` amendment that keeps the first encoded chunk truly streaming
(default probesize gates all ffmpeg output until EOF). Merge to main awaits owner review.

**Master directive #1 (2026-08-29, morning):** ADR-15 (HF Spaces runtime host — supersedes
the founding VPS ruling) + ADR-16 (brain via OmniRoute); backlog re-mapped to the new sprint
DAG; M1-M9 capability spec (`docs/specs/master-directive-2026-08-29.md`); canonical docs +
configs synchronized.

**Master directive #2 (2026-08-29):** the brain upgraded to a **3-tier multi-model routing**
system (ADR-16 amended in place: Tier 1 fast reflex TTFT<250 ms · Tier 2 tool executor ·
Tier 3 heavy DAG/tutoring) behind the **Fast Front-Door Dispatcher** (ADR-18) — new Sprint-1
task 1.5. New ADRs: 17 (voice biometrics + Guest Mode lockdown), 19 (TokenJuice compaction),
20 (in-memory Opus pipeline), 21 (5-directory vault contract). **Per-sprint skill rotation**
into `.claude/skills/` with a binding sprint-exit **teardown protocol**, ledgered in
`docs/10-CHECKPOINT.md` (new). Sprint specs 2-4 exhaustively re-mapped (AC1-AC10 each);
`config/whitelist.json` seeded; `.env.example` carries the FAST/MEDIUM/HEAVY tier pins.
Numbering note: the directive's draft ADR-04..07 collide with settled ledger entries and are
recorded as ADR-19/20/21 (see ledger note).

## 11. Addendum — 2026-08-30/31: Sprint 2 complete (Telegram suite → evening journaler)

### 11.1 Outcome snapshot

| Measure | Value |
|---|---|
| Tasks delivered | 2.1 · 2.2 · 2.3 · 2.3b · 2.4 · 2.5 · 2.6 — all green, TDD (red→green→refactor) |
| Test suite | **150 passed** (was 45 at sprint-1 close) · Security Gate OK · Docs Guard 16/16 |
| Sacred floor | `test_owner_middleware.py` + `test_guest_lockdown.py` green post-teardown (`test_whitelist_guardrail.py` is born with sprint-3 task 3.4) |
| Branch | worked on `core-foundation` (worktree), merged to `main` mid-sprint (`e7e0f2f`) and re-merged at close (`13a2d01`, sync `9840bda`) — **from 2026-08-31 all commits go directly to `main` (owner directive, §11.4)** |
| Teardown | executed 2026-08-31 per master-directive protocol — ledgered in `docs/10-CHECKPOINT.md` |

### 11.2 Task-by-task record

**2.1 — Google OAuth + Suite clients + Gmail watch** (`11c733f`, `ae48aea`)
`src/google_auth.py` consent flow + Fernet-sealed token cache (`{vault}/State/google_token.json.enc`,
ADR-15) with single-flight proactive/401 refresh; `src/google_suite.py` typed Calendar/Tasks/
Drive/Contacts clients (UTC-normalized models); `src/gmail.py` watch registration (optional
Pub/Sub topic) + polled incremental fetch (historyId with query-sweep fallback), message-ID
dedupe, **dispatch-then-mark** redelivery (no crash-window email loss), read-only `peek_unread`.

**2.2 — Progressive chat streamer + bot shell** (`0a5ae11`)
`src/skills/telegram_chat_streamer.py`: placeholder bubble → first edit <250 ms (Audio-TTFT
KPI) → edits coalesced at `STREAM_EDIT_INTERVAL_MS=750` → final text verbatim; cancel event
(owner interjection keeps the partial). Error modes: edit rate-limit doubles the interval,
placeholder failure → aggregate send fallback, mid-stream failure → apology preserving
delivered text. `src/bot.py` + `src/middleware.py`: owner-ID silent-drop middleware,
`/start` welcome + Ogg voice greeting, `/help`, voice static ack (zero gateway calls),
typing indicator, global error handler.

**2.3 — Voice biometrics + Guest Mode (ADR-17)** (`e0fd30e`, `01678b4`, `08470db`, `112eba5`)
`src/skills/voice_biometric_auth.py`: ECAPA-TDNN owner voiceprint (speechbrain pinned,
wheel-verified on py3.12/Windows), Fernet-sealed to `{vault}/State/owner_voiceprint.enc`,
`/enroll-voice` command, <50 ms CPU cosine verify, **fail-closed**: below-threshold or ANY
verification error → Guest Mode (warm ar-JO lockdown reply + exactly ONE
`Voice_Memos/Pending_Speakers/` staging note with encrypted embedding + placeholder
transcript; ZERO privileged effects — spy-proven no gateway/whitelist/subprocess calls).
`tests/test_guest_lockdown.py` joins the sacred floor. PCM decode return bug fixed with a
real-ffmpeg contract test.

**2.3b — Social enrollment / multi-speaker registry (§2.3b)** (`583e3c9`, `ff5d92e`)
`src/skills/social_enrollment.py`: `VoiceprintRegistry` extends ADR-17 beyond the owner —
per-contact sealed vectors + dossier frontmatter, owner-first match, running-centroid
stability, transcript appends; unknown owner-absent events staged and briefed later;
three-way verdicts `confirm:{Category}` → dossier+voiceprint, `ignore` → `Contacts/Ignored/`
(never re-matches), `unknown` → `Contacts/Unknown/` + security flag (re-matchable).

**2.4 — Tiered email triage + daily brief + TokenJuice (M7/ADR-19)** (`438bfb3`, brief series
`98a9617`..`62c1174`, TokenJuice `67c9d7a`/`b8f2c5c`)
`src/email_triage.py`: heuristic tiers (VIP/keywords/bulk) + ONE `FAST_MODEL` refinement on
the ambiguous remainder (untrusted-data containment markers, temperature 0, never-downgrade
merge — model can rescue upward only), dispatch matrix drop/text/voice/critical-ping with
repeat pings and owner-activity stop; `tokenjuice_compact` strips quoted chains/signature
blocks/legal footers and caps the body (feeds BOTH heuristic scoring and the LLM payload —
less free-pool burn, identical tiers). `src/daily_brief.py`: fire-once-per-local-day
Jordanian digest (events, due tasks, mail picture), per-section «غير متوفر حالياً»
degradation, persist-on-send-success. Settings: `GOOGLE_VIP_SENDERS`, `TRIAGE_KEYWORDS_AR/EN`,
`CRITICAL_PING_INTERVAL_MIN/MAX`, `TOKENJUICE_MAX_CHARS=4000`, `BRIEF_ENABLED`,
`BRIEF_LOCAL_TIME`.

**2.5 — Voice-to-vault transcriber (ADR-22)** (`5df9f80`, `ed03b03`, `8d1e385`, `afc8975`)
`src/skills/voice_to_vault_transcriber.py`: enrolled owner voice notes decode in-memory
(ffmpeg → 16 kHz mono s16le) and transcribe via **LOCAL faster-whisper** (MIT, CPU int8;
cloud STT settled to NEVER — ADR-22; network-free import surface AST-tested) on a dedicated
executor; atomic `Voice_Memos/YYYY-MM-DD-HHMM.md` YAML notes (same-minute numeric suffixes,
`(empty)` fallback, write retried once, never blocks the reply). Bot wiring: biometric gate →
transcribe → file → transcript enters the standard streamed text pipeline; guest voice never
reaches the transcriber. Deps wheel-verified before implementation: faster-whisper 1.2.1 +
ctranslate2 4.8.

**2.6 — Evening proactive journaler (§2.6)** (`c619e12`, `0959333`)
`src/skills/evening_journaler.py`: once per local day writes the ledger
`Daily_Logs/YYYY-MM-DD.md` (YAML frontmatter `date`+`checkin_sent`; Calendar / Mail /
Voice memos / Notes sections, each degrading independently) and sends ONE Jordanian
check-in at a `random.uniform` slot inside `[JOURNALER_WINDOW_START, JOURNALER_WINDOW_END)`
(Amman): calendar-guarded (busy → no message, ledger still lands), send failure never
persists the check-in date (30 s retry tick), state-loss same-day re-run appends one
corrigenda line instead of duplicating, `run_forever` loop survives any exception.
Zero LLM in the hot path. Settings: `JOURNALER_ENABLED`, `JOURNALER_WINDOW_START/END`
(loud HH:MM validators), `DAILY_LOGS_DIR`; state `{vault}/State/journaler.json`.

### 11.3 Docs, ADRs & config synchronized this sprint

ADR-22 appended (local Whisper — never cloud) · ADR-17 amended (multi-speaker registry) ·
ARCHITECTURE §6 voice-to-vault + evening-journaler legs, §6b social graph · RUNBOOK: Google
OAuth walkthrough, email-triage tuning, Whisper warmup one-liner, daily-brief + evening-
journaler schedules, voice enrollment + social registry · TEST-PLAN rows for every new suite ·
BACKLOG status matrix + task records · CHANGELOG entries per task · `.env.example` extended
(triage, brief, biometrics, whisper, journaler blocks) · `config/whitelist.json` seeded
(sprint-1 directive carry-over).

### 11.4 Sprint exit + branch directive

- **Teardown (2026-08-31)**: `.claude/skills/*` wiped (untracked session aids — re-ingested
  per sprint from the upstream toolkits); post-teardown full suite 150 passed; sacred floor
  green; `docs/10-CHECKPOINT.md` records the sprint-2 COMPLETE entry with the Guide
  verification pass (gate + AC→pytest coverage + docs sync).
- **Owner directive (2026-08-31, binding): ALL commits land directly on `main` and push
  immediately** — the per-stream worktree/branch merge pattern is retired. `main` is the
  implementation branch; the `core-foundation` worktree becomes a reference checkout only
  (kept ff-synced to `main`). Recorded in `.claude/PHASE-STATE.md` so every future session
  complies.

### 11.5 Owner-side pending (live enablement — none block Sprint 3 start)

1. Google OAuth bootstrap (RUNBOOK §6 walkthrough) — unlocks live Calendar/Gmail.
2. Google 403 "project denied access" fix — unlocks the Gemini pools (blocks AC10 live
   smoke from sprint 1).
3. Whisper warmup one-liner (RUNBOOK §6) — one-time model download before first live memo.
4. VAULT_ENC_KEY set in `.env`; 6 OpenRouter keys connected to OmniRoute pools (3-tier).
5. Live smokes: streamed text reply, voice round-trip, daily brief, triage dispatch.

### 11.6 Next

**Sprint 3 — vault + PC bridge + whitelist (tasks 3.1-3.5)**: git-backed vault client
(PARA/frontmatter/first-boot guard), dynamic vault expander, verbal action-summary protocol,
whitelist safety guardrail daemon (sacred floor `test_whitelist_guardrail.py`), desktop
telemetry protocol. Skills to ingest at entry: mattpocock TDD + git-guardrails,
guard-skills test-guard, everything-claude-code systems-architect. Opens on the owner's
«التالي».

## 12. Addendum — 2026-08-31: Sprint 3 complete (vault → PC bridge → telemetry)

Full-sprint record per convention. All five tasks landed **directly on `main`** under the
binding branch directive (owner, 2026-08-31) with immediate pushes; red→green→refactor on
every task (the AC→pytest contracts in `docs/specs/sprint-3.md` were the test design, never
re-invented).

### 12.1 Task 3.1 — skill-obsidian-vault-architect (M6 / ADR-21)

`src/vault.py`: `VaultClient` over the GitHub Contents API (Bearer + versioned headers,
`?ref=VAULT_BRANCH`; upsert = sha lookup → 404 create / 200 update; one 409 GET→PUT retry
then `VaultConflictError`; auth errors loud with zero retries; >1 MB payloads refused
pre-flight), Git Data API `commit_files` (ONE-commit structural changes incl. the legacy
`02_Areas/Studies/` → top-level `Studies/` migration), `append_section`, deterministic
title sanitizer (Arabic verbatim), YAML frontmatter writer/splitter, PARA helpers +
Zettelkasten wikilinks, `redact_secret` screening every log/exception path, idempotent
first-boot `ensure_mandatory_dirs()` (mandatory dirs + contacts taxonomy + both profile
files; re-run = zero writes). Plus **3.1b** `src/skills/social_graph.py` (`SocialGraph`:
dossier / FAST-tier entity extraction (strict JSON, LLM output is DATA) / dated file_action
into dossier AND daily log; ambiguous holds for owner confirmation; `Ignored/` never
appends). Settings: VAULT_GITHUB_REPO/VAULT_GITHUB_TOKEN required, VAULT_BRANCH, PyYAML.
31 new tests (181 total).

### 12.2 Task 3.2 — skill-dynamic-vault-expander (M5)

`src/vault_expand.py`: `VaultExpander.expand(domain, dirs, tags)` grows `01_Projects/<domain>`
trees as domains emerge — sanitized sub-dirs, `_index.md` per directory (wikilinked), tag
ontology `<domain>/_tags.yaml`; every expansion ONE auditable commit (`sara: expand vault —
<domain>`) via the Git Data API; PARA backbone expansion-only (`BackboneImmutableError`
pre-flight, zero API calls; no delete/move code path exists); idempotent (vault state IS
the memory); token never in logs/exceptions. 10 new tests (191 total).

### 12.3 Task 3.3 — skill-verbal-action-summary-protocol

`src/summary.py` + `common/consent.py`: task-bearing turns close with the exact prompt
«هل بتحب ألخص لك شو رح أعمل هسا؟»; `TaskExtractor` rides ONE TIER 2 MEDIUM call per turn
(strict JSON, garbage collapses to `[]` loudly); one pending per turn (newer supersedes,
casual turns capture nothing); consent grammar shared with 3.4 (`is_affirmative` first-token
Jordanian match) with the structural binding rule — only an affirmative FOLLOWING the live
prompt mints consent; approvals file `04_Archives/Conversations/YYYY-MM-DD-HHMMSS-summary.md`;
arbitration defers to 3.4's confirmation consumer and re-asks once after; brain failure never
breaks the reply. 10 new tests (201 total).

### 12.4 Task 3.4 — skill-pc-whitelist-safety-guardrail (the PC control plane)

- `common/protocol.py` — v1 wire (JSON-per-frame; PROTOCOL_VERSION/heartbeats/1 MiB cap;
  Hello/HelloAck token handshake: bad token closed 4401 with token never logged, second
  session 4400; results correlate by envelope id; unknown-id results WARN+drop).
- `bridge/guard.py` — whitelist re-read per check, fail-CLOSED on corrupt file (CRITICAL),
  power ALWAYS requires a confirmation id regardless of any whitelist flag.
- `bridge/executor.py` — detached `shell=False` spawns, audit codes
  `PC-YYYYMMDD-HHMMSS-4hex`, traversal/UNC refusal, missing exe «البرنامج مش موجود عالجهاز».
- `bridge/wol.py` + `bridge/idle.py` — exact 102-byte magic packet (one UDP:9 sendto,
  SO_BROADCAST) and the latched idle monitor (one offer per window «صرت مدة طويلة...»,
  sustained-activity re-arm so a momentary blip never re-arms).
- `src/pc_actions.py` — owner-origin gate (`RefusedOrigin`; untrusted content is DATA and
  never mints PC intent), confirmations-note-BEFORE-command (approval without audit is
  void), one audit code chaining note → cmd → ExecResult → Telegram «رمز التدقيق»,
  append-only `04_Archives/Audit/pc-ledger.md`.
- `src/bridge_server.py` + `bridge/daemon.py` + `bridge/server.py` + `bridge/__main__.py` —
  single-session acceptor with silence watchdog and honest `BridgeOffline`; outbound-only
  dialer (AST-scanned: never binds) with heartbeats + capped backoff; LAN HTTP surface
  loopback-bound; settings wired (BRIDGE_TOKEN/BRIDGE_SERVER_URL/BRIDGE_LAN_PORT).
- `docs/06-API-SPECIFICATION.md` formalizes wire + command catalog (force semantics
  DROPPED) + confirmation/audit lifecycle + data models + LAN surface.
13 new tests (216 total).

### 12.5 Task 3.5 — skill-desktop-telemetry-protocol

`bridge/telemetry.py`: one psutil snapshot `live_state()` (<2 s) — cpu, ram, C:/D: disks,
uptime, top-CPU process (primed counters, single settle window) — degrades unmeasurable
metrics to None/`"unknown"` instead of crashing (OSError-safe: psutil 7 removed
`DiskNotFoundError`). Served two ways: `GET /telemetry/live-state` on the LAN surface
(Bearer BRIDGE_TOKEN — 401 without it, 404 when no provider wired) and the tunnel cmd
`telemetry.state` (daemon executes `live_state()`, returns `ok` + model dump).
`src/telemetry.py`: `TelemetryClient` — pydantic-validated fetch; `narrate` makes ONE
Tier-1 FAST call with the state JSON as DATA (numbers verbatim, display-only, temperature 0)
with a deterministic numeric Arabic fallback on brain failure; `report` catches
BridgeOffline/Timeout/ValidationError → honest «الجسر مو متصل هسا», never raises to the
chat layer. Payload carries no secrets (no token/hostname/paths — exact-schema `extra=forbid`).
12 new tests (228 total).

### 12.6 Sprint exit + teardown

- **Teardown (2026-08-31)**: `.claude/skills/*` wiped (untracked session aids); post-teardown
  suite 228 passed; sacred floor green (`test_owner_middleware.py` + `test_guest_lockdown.py`
  + `test_whitelist_guardrail.py`). Full record: `docs/10-CHECKPOINT.md` (Sprint 3).
- **Verification**: full gate green (lint + 228 tests + security gate + docs guard 16
  canonical files); AC→pytest coverage: spec §3.1-§3.5 complete; docs synced per task
  (ARCHITECTURE §2/§5, RUNBOOK §5, 06-API-SPECIFICATION, CHANGELOG, BACKLOG ticks).
- **Carry-over to owner**: Google 403 fix still blocks the AC10 dispatcher live smoke;
  bridge live run needs the auto-start task + the WoL external-sender reality check
  (RUNBOOK §5 wake reality check).
- **Outcome**: 228 tests green; sprint-level HALT — owner decides Sprint 4 (4.1 syllabus
  parser, 4.2 dynamic capability expansion, 4.3 polymath tutor, 4.4 hardening + v1.0.0
  release on HF Spaces).

## 13. Addendum — 2026-08-31: Sprint 4 complete (syllabus → expansion → tutor → hardening) · **v1.0.0 released**

### 13.1 Outcome snapshot

| Measure | Value |
|---|---|
| Tasks delivered | 4.1 · 4.2 · 4.3 · 4.4a · 4.4b · 4.4c — all green, TDD (red→green→refactor), all directly on `main` |
| Test suite | **285 passed, 1 skipped** (was 228 at sprint-3 close) · coverage **85.62% branch** (85% gate LIVE) · Security Gate OK · Docs Guard 16/16 |
| Sacred floor | `test_owner_middleware.py` + `test_whitelist_guardrail.py` + `test_guest_lockdown.py` = 16 passed post-teardown |
| Branch | every commit direct to `main` + immediate push (binding directive; `core-foundation` reference-only) |
| Release | **tag `v1.0.0` created on the validated HEAD and pushed to origin**; GitHub Release publish = owner step (`gh release create v1.0.0 --verify-tag ...` printed by the script) |
| Teardown | executed 2026-08-31 — `.claude/skills/*` wiped, code/tests kept; ledgered in `docs/10-CHECKPOINT.md` (Sprint 4) |

### 13.2 Task-by-task record

**4.1 — syllabus-to-DAG parser** (`d9a5076` red, `16173eb` green, `8faf485` docs)
`src/syllabus.py`: threaded pypdf extraction (length-capped untrusted input) → ONE TIER3
HEAVY strict-JSON parse (one retry, then loud `SyllabusError`; temperature 0) → nx-free DAG
validation (cycles/orphan prereqs named) → weighted capped review schedule (60-min sessions
backward from deadlines, `[sara:syllabus:...]` idempotency tags on Calendar/Tasks) → plan
filed to `Studies/<course>/` with YAML frontmatter. PDF text is DATA never instructions —
AST-scanned zero PC surface. New dep `pypdf>=5` (BSD-3).

**4.2 — dynamic capability expansion (M4)** (`c0fc115` red, `36f2b54` green, `3363fe6` docs)
`src/expansion.py`: owner hands a credential env NAME in chat; `parse_nl_cron` maps
Arabic/English phrasing («كل صباح 7», «كل اثنين 9», «كل ساعة») to `ScheduleSpec` with tz
pinned to `settings.tz`; `CapabilityScheduler` probes presence/format (errors/log carry the
NAME only), registers background asyncio jobs (reserved-name refusal, max-8, single lock),
persists to `State/capabilities.json` with `restore(pipelines)` re-derivation after restart
(ADR-15). Any failure/timeout DISABLES the task loudly (ERROR + one owner notify; re-enable
is explicit owner action). ctx carries `name`/`credential_env`/`vault` — never the value.

**4.3 — polymath tutor (M9)** (`dade4bc` red, `71964d1` green, `bdf97cc`/`f8ec0f9`/`66f0f32` polish+docs)
`src/tutor.py`: no new engine — `study_artifact` drives ONE `Tier.HEAVY` call under
`TUTOR_SYSTEM_PROMPT` (first-principles deconstruction, graded path, 5 drills, bilingual
terms, requested language verbatim); artifacts file to `Studies/<topic>/Study Guide.md`
with complete YAML frontmatter; vault failure raises `StudyFilingError` carrying the FULL
guide (Arabic apology — never lost); zero provider/PC surface (AST-scanned); generated
content is DATA.

**4.4a — quality-gate hardening** (`6206cd4`)
85% branch coverage LIVE in pytest addopts (85.86% at activation); vendored secret scanner
in `make gate` (`scripts/secret_scan.py` — pattern battery + placeholder allowlist;
committed-`.env` detection); CI unified on `scripts/security_gate.py`; pragma policy
enforced — every `pragma: no cover`/`# nosec` carries `-- <reason>`; fail-closed threshold
proven via subprocess mini-project.

**4.4b — HF Spaces packaging (ADR-15)** (`49399e2` red, `ef9e695` green, `52dc37b` docs)
`Dockerfile` (python:3.12-slim, ffmpeg, non-root `sara`, TZ=Asia/Amman) whose CMD is the
new single-tree supervisor `scripts/supervise.py` (OmniRoute child + core child; first exit
tears down the tree → container exit → Space restarts whole). Core reads `$PORT` and serves
`GET /health` + authenticated bridge WSS on the single public port (`start_public_port`).
`.dockerignore` keeps secrets/sessions/OAuth client out while re-including the two runtime
needs. `.github/workflows/keepalive.yml` pings `/health` every 10 min, fails loudly on
non-200. `scripts/deploy_smoke.py`: five checks (gateway/telegram/vault/google_token_cache/
space_health), per-check timeouts, all run even after one fails, Settings-aware masker
screens every failure detail (httpx errors embed full URLs carrying the bot token —
nothing secret reaches logs). Durable-state audit test locks every runtime disk write to
ADR-15-justified stores. README Space metadata; RUNBOOK §4/§4b/§4c rewritten with
troubleshooting + dated validation checklist.

**4.4c — release v1.0.0** (`ac37ca0` red, `2f8d800` green, `266b2c8` docs)
`src/__version__='1.0.0'` single source; CHANGELOG `[Unreleased]` drained into
`## [1.0.0] — 2026-08-31` (complete Added across Sprints 1-4, Changed, new **Security**
section, **Deferred-to-v1.1**); scope-lock test freezes the complete exclusion set
(pytgcalls/telethon/pyrogram absent from artifacts AND all runtime imports; mem0/firestore
likewise). `scripts/make_release.py`: verify_consistency (version == newest CHANGELOG
heading, both named on mismatch) → verify_clean_tree (porcelain) → verify_gate (subprocess)
→ annotated tag ONLY with `--tag` (no `--force` exists, by design; collision policy =
bump 1.0.1); publishing stays owner-run with the exact `gh` command printed. Release
sequence executed: dry-run green → `--tag` → tag pushed to origin. RUNBOOK gains the
"production deploys pin `git checkout v1.0.0`" line; README version badge; BACKLOG 4.4
ticked; ARCHITECTURE §8 verified accurate for the shipped build.

### 13.3 Carry-over to owner

- **Publish the GitHub Release**: `gh release create v1.0.0 --verify-tag --title
  "Vantrilex Assistant OS v1.0.0" --notes-file <(sed -n '/^## \[1.0.0\]/,$p' CHANGELOG.md)`
  (Git Bash; PowerShell users: extract the section to a temp file first).
- **AC8 post-tag smoke (manual)**: rebuild the Space container from the tag, re-run
  `python scripts/deploy_smoke.py` → exit 0 (closes the tagged-vs-running loop).
- Still open from earlier sprints: Google 403 fix blocking the dispatcher live smoke
  (AC10, task 1.2); live syllabus/tutor smokes (AC10s, tasks 4.1/4.3) need a live brain.

### 13.4 Outcome

**v1.0.0 shipped** — Sara is feature-complete for the v1.0 scope: 3-tier brain behind the
front-door dispatcher, Jordanian voice in/out with biometric Guest lockdown, git-backed
vault with PARA/Zettelkasten capture, Gmail triage + daily brief, PC control plane with
fail-closed whitelist guardrail, telemetry narration, syllabus/tutor/expansion skills, all
packaged as ONE free HF Space container. 285 tests green, 85.62% branch coverage, gate
green end-to-end. Sprint-level HALT: owner publishes the Release and decides the v1.1
agenda (PyTgCalls live calls, hardware-scout/career-incubator, Mem0/Firestore evaluation).

## 14. Addendum — 2026-08-31 (post-release): v1.0.1 + the Oracle pivot

### 14.1 The deploy-time platform discovery

Post-release deploy attempts hit a wall: HF made Docker/Gradio Spaces a **paid PRO
feature ($9/month)** — the owner verified with screenshots ("Gradio and Docker Spaces
require a paid plan"; earlier assistant knowledge that cpu-basic Docker Spaces were free
was outdated, and the assistant acknowledged the error explicitly). An honest host
re-audit followed, owner present:

| Candidate | Verdict |
|---|---|
| Render / Koyeb free | ✗ 512 MB / 0.1 vCPU + scale-to-zero — cannot carry whisper + biometrics + OmniRoute + core; text-only Sara |
| Google Cloud Run free grant | ✗ same 512 MB cap for an always-on service |
| HF PRO | ✗ $9/mo — breaks the absolute $0.00 invariant (owner: «قراري هو اني لن اكسر القاعدة») |
| **Oracle Cloud Always Free** | ✓ **OWNER-CHOSEN** — Ampere A1 VM (2 OCPU/12 GB, expandable 4/24), truly always-on, $0 forever, card for verification only |

ADR-15 amended in place (owner `التالي`): the container design is unchanged and
host-agnostic; the disposable-filesystem rule STAYS as a design principle (vault remains
the only durable store); and the OAuth client JSON may live on the VM (never git) —
**resolving the Space-era Google gap**.

### 14.2 v1.0.1 — the Node gap, closed-loop

While re-verifying the container for a real deploy, the fatal gap surfaced: OmniRoute is
an **npm application** (engines `node >=22.22`), and the image was `python:3.12-slim` —
no Node runtime, the gateway child could never start. Closed loop on `main`:

- `83a61f7` red: `test_dockerfile_contract` extended (NodeSource 24, global install of
  the vendored clone, zero-config `OMNIROUTE_CMD`).
- `9545753` green: Dockerfile gains the Node 24 layer + `npm install -g
  /app/scripts/omniroute` + `ENV OMNIROUTE_CMD="omniroute run"`. Gate 285 passed /
  85.67% branch.
- One test harness fix in the release commit: `test_v100_documents_scope_deferrals`
  was pinned to v1.0.0 — it had been accidentally tracking HEAD's CHANGELOG section,
  which a patch release legitimately does not carry a deferral block.

### 14.3 Documentation wave (`5f07db9`, `7e49f85`)

- **`docs/09-ORACLE-DEPLOY.md`** — the owner's Arabic hand-held guide: account (home
  region PERMANENT) → VM (Ubuntu 24.04, A1.Flex 2/12, ingress 22/80/443) → DuckDNS →
  Docker → build from `v1.0.1` + OmniRoute clone → `~/sara-secrets/sara.env` (21 vars +
  `PORT=8080`) → compose + Caddy TLS → verification → PC bridge → maintenance +
  troubleshooting tables.
- RUNBOOK §4 rewritten Oracle-primary (§4b keep-alive now legacy/optional on the
  no-sleep VM; §4c documents HF-paid/Cloud-Run/Render-Koyeb as rejected alternatives);
  §4-validation checklist re-anchored to VM terms; §1 table + §5 bridge first step +
  troubleshooting rows de-Space'd.
- HANDOFF (07) snapshot → v1.0.1 + Oracle; §9.2 marked FIXED, §9.4 marked RESOLVED-on-VM;
  docs map gains 09. OWNER-NEXT-STEPS (08) rewritten around Oracle with the full
  21-variable `sara.env` template.
- Release commit `7e49f85` (version + CHANGELOG `[1.0.1]` in one commit, per policy) →
  dry-run green → annotated tag `v1.0.1` pushed → **GitHub Release published**
  (notes via temp file — process substitution `<(...)` is broken on Windows Git Bash).

### 14.4 Where the day stopped

The owner's Oracle signup was blocked at card verification ("Your credit card has been
declined") — a bank-side card flag in the overwhelming majority of cases (online/
international transactions disabled, OTP, name/address mismatch). The owner paused work
for 2026-08-31 and will contact the bank on 2026-09-01; the recovery checklist is
documented in `docs/09-ORACLE-DEPLOY.md` §1. All machine-side work is complete and
pushed; only the owner-side Oracle deploy (docs/09) waits on the card. PHASE-STATE
marker: **v1.0.1 shipped — HALT pending Oracle card resolution**.
