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
