---
tags: [testing]
---

# 10 — Sprint Checkpoint Ledger

Per-sprint record of the MASTER DIRECTIVE skill rotation + teardown protocol. Each sprint
entry: skills ingested into `.claude/skills/` at entry, code/tests produced (which STAY in
`src/` + `tests/`), teardown verification at sprint exit, and the sprint outcome. The sacred
floor (`test_owner_middleware.py`, `test_whitelist_guardrail.py`, sprint-2 guest-lockdown)
must run green after every teardown.

Upstream toolkit inventory: `worldflowai/everything-claude-code` · `mattpocock/skills` ·
`dietrichgebert/ponytail` · `amElnagdy/guard-skills` · `3mar-baha/universal-agentic-os` ·
`msitarzewski/agency-agents`.

---

## Sprint 1 — Foundation (gateway + voice + dialect + dispatcher) — COMPLETE (2026-08-29)

- **Skills ingested**: `mattpocock-skills/skills/tdd` · `ponytail/skills/*` ·
  `guard-skills/clean-code-guard` (tdd + clean-code-guard SKILL.md read in full and applied;
  diagnosed-bugs and python-specialist never needed — tasks landed without them)
- **Deliverables**: task 1.1 skeleton (merged to main, `221c650`) · task 1.2 gateway
  + SSE hardening (`3e44f1c`, live-wired) · task 1.3 voice pipeline (`4d0aefa`) · docs
  overhaul commits (`71a17ca`, `fef6246`, `0e796fd`) · task 1.4 dialect engine M1
  (`aa64644`) · task 1.5 3-tier brain + Fast Front-Door Dispatcher (`fe4e5ca`; runtime
  `.env` migrated, 2-slot chain retired) · social-graph + sprint re-map commits
  (`79b9563`, `5519a6c`, `53d8d71`)
- **Teardown (executed 2026-08-29)**: `.claude/skills/*` wiped; full suite green after
  teardown (45 passed). Sacred-floor note: `test_owner_middleware.py` +
  `test_whitelist_guardrail.py` are born with Sprint-2 task 2.2 / Sprint-3 task 3.4 —
  until then the full suite IS the floor.
- **Carry-over**: AC10 live smoke (task 1.2 gateway + 1.5 dispatcher TTFT) blocked on the
  Google 403 "project denied access" owner-side fix in Google Cloud.

## Sprint 2 — Telegram suite, biometrics, triage, logs — COMPLETE (2026-08-31)

- **Skills ingested**: `mattpocock/skills` TDD · `guard-skills/clean-code-guard` ·
  `everything-claude-code` api-integrator (session aids, never committed; diagnosing-bugs
  ingested but unused — no sprint-2 bug required its loop)
- **Deliverables** (all on `core-foundation`): task 2.1 Google OAuth + suite clients
  (`11c733f`) + Gmail watch/poll (`ae48aea`) · task 2.2 progressive chat streamer + bot
  shell (`0a5ae11`) · task 2.3 voice biometrics + Guest Mode (`e0fd30e`→`08470db`,
  PCM decode fix `112eba5`) · 2.3b social enrollment registry + verdicts (`583e3c9`,
  `ff5d92e`) · task 2.4 triage classifier + dispatcher (`438bfb3`) + daily brief
  (`98a9617`..`62c1174`) + TokenJuice (`67c9d7a`, `b8f2c5c`) · task 2.5 local-whisper
  voice-to-vault (`ed03b03`, `afc8975`) · task 2.6 evening journaler (`c619e12`,
  `0959333`) — docs rides along each task (`a928dc0`, `4ba0183`, `ba55d76`, `2570400`,
  `e45e5ee`, `a70a7a5`, `aa2885f`, `52f9e12`, `30381d9`)
- **Teardown (executed 2026-08-31)**: `.claude/skills/*` wiped (untracked session aids);
  full suite green after teardown — **150 passed**; sacred floor green
  (`test_owner_middleware.py` + `test_guest_lockdown.py`, 7 passed;
  `test_whitelist_guardrail.py` is born with Sprint-3 task 3.4).
- **Sprint-exit verification (Guide pass)**: full gate green (lint + 150 tests +
  security gate + docs guard 16 canonical files); AC→pytest contracts all mapped
  (AC1-AC12, M2/M3/M7, ADR-17/19/22); spec §2.1-§2.6 delivered; docs synced per task.
- **Carry-over to owner**: OAuth bootstrap + live smokes; Google 403 owner-side fix
  (blocks AC10 live smoke); Whisper warmup one-liner (RUNBOOK §6).
- **Outcome**: core-foundation merged to `main` mid-sprint (`e7e0f2f`) and re-merged at
  sprint close per owner directive; 150 tests green; sprint-level HALT.

## Sprint 3 — Vault, PC bridge, whitelist — COMPLETE (2026-08-31)

- **Skills ingested**: `mattpocock-skills/skills/tdd` · `mattpocock-skills/skills/git-guardrails` ·
  `guard-skills/test-guard` · `everything-claude-code/agents/systems-architect` ·
  `ponytail/*` (session aids, never committed; TDD + guardrail discipline governed the
  whole sprint — red suite first on every task)
- **Deliverables** (all directly on `main`, per the 2026-08-31 branch directive): task 3.1
  vault client + social graph + first-boot bootstrap (`38f1e4c`..) · task 3.2 VaultExpander
  (`fe2493d` red, `e1c9714` green, docs `de916d4`/`1e87463`/`82d87cd`) · task 3.3 verbal
  action-summary protocol + shared consent grammar (`b0a50ee`, `c19119d`, docs
  `81e95cb`/`3d9f09e`) · task 3.4 PC control plane — wire protocol (`dcfac95`), guardrail
  executor + WoL + idle (`c6fdfd0`), owner-side coordinator (`9097c31`), tunnel acceptor +
  outbound daemon + LAN surface (`ad29956`), bridge settings (`154d1fd`), API spec docs
  (`db6c20b`) · task 3.5 desktop telemetry — red suite (`d49a05c`), LiveState + Bearer LAN
  route + TelemetryClient narration (`ab81144`), docs (`5282baf`)
- **Teardown (executed 2026-08-31)**: `.claude/skills/*` wiped (untracked session aids);
  full suite green after teardown — **228 passed**; sacred floor green
  (`test_owner_middleware.py` + `test_guest_lockdown.py` + `test_whitelist_guardrail.py`).
- **Sprint-exit verification**: full gate green (lint + 228 tests + security gate +
  docs guard 16 canonical files); AC→pytest contracts all mapped (spec §3.1-§3.5:
  3.1 M6/ADR-21, 3.2 M5, 3.3 summary protocol, 3.4 AC1-AC12 + AST outbound-only scan,
  3.5 AC1-AC8 + psutil degradation); docs synced per task (ARCHITECTURE, RUNBOOK,
  06-API-SPECIFICATION, CHANGELOG, BACKLOG ticks).
- **Carry-over to owner**: live smokes on a real PC bridge run (daemon auto-start task +
  WoL external sender reality check — RUNBOOK §5); Google 403 owner-side fix still blocks
  AC10 dispatcher live smoke.
- **Outcome**: 228 tests green; 5/5 tasks delivered; sprint-level HALT — owner decides
  Sprint 4 start (syllabus parser, dynamic expansion, tutor, hardening & v1.0.0 release).

## Sprint 4 — Syllabus parser, expansion, tutor, hardening & release — COMPLETE (2026-08-31) · v1.0.0

- **Skills ingested**: `guard-skills/docs-guard` · `guard-skills/test-guard` ·
  `universal-agentic-os/skills/github-release-packager.md` ·
  `universal-agentic-os/skills/circuit-breaker-guard.md` (SKILL.md files read in full at
  sprint entry; docs-guard + test-guard governed every task slice; release-packager shaped
  `scripts/make_release.py` — verify-then-tag with NO force flag; circuit-breaker-guard
  informed the loud-disable failure semantics of 4.2's scheduler)
- **Deliverables** (all directly on `main`, closed loop, red-tests-first per task):
  task 4.1 `src/syllabus.py` syllabus->DAG (`d9a5076` red, `16173eb` green; 9 tests) ·
  task 4.2 `src/expansion.py` dynamic capability expansion M4 (`c0fc115` red,
  `36f2b54` green; 10 tests) ·
  task 4.3 `src/tutor.py` polymath tutor M9 (`dade4bc` red, `71964d1` green; 6 tests) ·
  task 4.4a gate hardening: coverage LIVE 85% branch, `scripts/secret_scan.py` in gate,
  CI unified on `scripts/security_gate.py`, pragma-reason policy (7 tests; `6206cd4`) ·
  task 4.4b HF Spaces packaging: `Dockerfile` + `scripts/supervise.py` single-tree
  supervisor, `$PORT` health+WSS (`start_public_port`), `.dockerignore` runtime
  negations, keep-alive cron workflow, `scripts/deploy_smoke.py` (5 checks + secret
  masker), durable-state audit test, README Space metadata, RUNBOOK §4 rewrite
  (18 tests; `49399e2` red, `ef9e695` green, `52dc37b` docs) ·
  task 4.4c release: `src/__version__='1.0.0'`, CHANGELOG drained to
  `## [1.0.0] — 2026-08-31` (Added/Changed/Security/Deferred-to-v1.1), scope-lock test
  (complete exclusion set: pytgcalls/telethon/pyrogram/mem0/firestore),
  `scripts/make_release.py` (consistency/clean-tree/gate verifications, --tag-only,
  tag-collision policy = bump 1.0.1; `ac37ca0` red, `2f8d800` green, `266b2c8` docs;
  7 tests, 285 total)
- **Teardown (executed 2026-08-31)**: `.claude/skills/*` wiped (all four sprint-4
  skills removed; code/tests untouched); post-teardown sacred floor green —
  `test_owner_middleware.py` + `test_whitelist_guardrail.py` + `test_guest_lockdown.py`
  = 16 passed. Full gate green after teardown: 285 passed / 1 skipped (docker build —
  dev machine lacks docker + OmniRoute clone), coverage 85.62% branch.
- **Release sequence executed**: dry-run verifications green -> `--tag` created
  annotated tag `v1.0.0` on the validated HEAD -> `git push origin v1.0.0` -> owner
  publishes the GitHub Release with the script-printed `gh release create v1.0.0
  --verify-tag ...` command. Publishing + post-tag container-from-tag smoke (AC8)
  are owner steps.
- **Outcome**: 285 tests green; **v1.0.0 shipped — the sprint-level HALT lands with the
  owner** (Release publish, AC8 post-tag smoke, then v1.1 decisions: PyTgCalls live
  calls, tech-hardware-scout + career-project-incubator, Mem0/Firestore evaluation).

## Post-release addendum — 2026-08-31: v1.0.1 + Oracle pivot (no sprint, no skills)

Skill rotation: **none ingested** (closed-loop patch + docs only). Commits directly on
`main`: `83a61f7` red (Dockerfile must carry Node >=22 — OmniRoute npm engines) ·
`9545753` green (NodeSource 24 layer + global gateway install + `OMNIROUTE_CMD`
default) · `5f07db9` docs (ADR-15 amendment → Oracle Always Free; `docs/09-ORACLE-DEPLOY.md`
Arabic owner guide; RUNBOOK/HANDOFF/OWNER-NEXT-STEPS re-anchored) · `7e49f85` release
(version 1.0.1 + CHANGELOG `[1.0.1]`; scope-deferral test pinned to v1.0.0). Tag
`v1.0.1` pushed; GitHub Release published. Full gate green throughout (285 passed).
Owner deploy blocked at Oracle card verification — bank contact 2026-09-01, recovery
checklist in `docs/09-ORACLE-DEPLOY.md` §1. Record: `docs/PROJECT-JOURNEY.md` §14.

## Post-release addendum — 2026-09-01: v1.0.2 (owner-directed runtime enhancements)

Skill rotation: **none ingested** (closed-loop patch + docs only). Commits directly on
`main`: `3cfdc43` red (tests/test_app_indexer.py — 9 tests: clean name extraction from
`.lnk` stems, .lnk-only recursive discovery, cross-root casefold dedupe, System32 filter,
preserve-restricted_actions merge, idempotency, Guard end-to-end acceptance, dry-run
writes nothing) · `1203cde` green (`src/app_indexer.py`: both Start Menu roots scanned;
targets resolved via PowerShell WScript.Shell COM in 80-path `-EncodedCommand` batches —
no shell, no quoting hazards; `C:\Windows` targets incl. System32 dropped; categorized
Coding/Gaming/Study/Productivity; idempotent casefold merge; durable-state audit
allowlist justified) · `ee70660` docs+live (RUNBOOK §5b headless remote boot — Sysinternals
Autologon LSA secret preferred / netplwiz alt + Windows Hello caveat; bridge daemon
Task Scheduler ONLOGON preferred with ONSTART alt; end-to-end headless proof; LIVE
whitelist merge on owner machine: 223 discovered / 154 added / 63 system-skipped /
156 total) · `82afb03` release (version 1.0.2 single-source + CHANGELOG [1.0.2] +
HANDOFF component row + README badge). Release sequence: full gate green (294 passed /
1 skipped / 85.73% branch) → dry-run green → annotated tag `v1.0.2` pushed → GitHub
Release published (temp-file notes pattern). Record: `docs/PROJECT-JOURNEY.md` §14.

## Remediation arc — 2026-09-02→03: forensic audit + phases 1–2 (+3.1)

Skill rotation: **none ingested** (owner-directed remediation run, closed loop on `main`).
Forensic audit (6 axes × 43 agents + adversarial verify) → `docs/AUDIT_REPORT.md` (10
CONFIRMED findings C-1..C-10) → owner-approved `docs/REMEDIATION_PLAN.md` (3 phases).
**Phase 1** (voice/persona/consent, steps 1.1–1.9, commits `ad042dd`…`9e5a63e` class):
transient ack, single-modality voice, string purity + AST contract, task.cancel zombie
kill, standalone-affirmative consent, Fish Audio primary voice. **Phase 2** (2.1–2.7,
CLOSED 2026-09-03): keyword net `aac5e41` (C-1) · Arabic app aliases + honest unknown
line `5d939b1` (C-7) · voice-confirmation consumption `4ebefcd` (C-2, sacred floor) ·
confirmation memory + orphan yes/no guard `3e41560` (C-8) · live dialect learning loop
`b903921` («تعلمي:» → vault + live lexicon) · Whisper pinned to Jordanian Arabic
`d2e2bcf` · envelope tail-slice `91b5531`. **Phase 3 opened same day**: 3.1 absent
loops live `9bdb3a4` (brief 07:30 + journaler 18:00–19:30 + gmail watch + daily
summary through one testable `start_background_loops` stitch). Gate at Phase-2 close:
**478 passed / 1 skipped / 86.47% branch / security + docs green**; sacred floors
(owner-middleware, whitelist-guardrail, guest-lockdown, consent-grammar) **43/43**.
Records: `docs/REMEDIATION_PLAN.md` per-step ✅ blocks · `.claude/PHASE-STATE.md` ·
`docs/PROJECT-JOURNEY.md` (audit + remediation sections).

## Live-defect round — 2026-09-05→06: defects A–G sealed (commit `4bb212c`)

Skill rotation: **none ingested** (owner-directed live-defect remediation + unattended
deep audit, closed loop on `main`). The owner's 2026-09-05 Telegram session surfaced seven
production defects; each fix carries its regression pins in the NEW floor
`tests/test_live_defects_2026_09_05.py` (39 collected items — A: UWP close images ·
B: prayer coords/method/tz/date · C: weather geocode + loguru mixed-format ban ·
D: dispatcher priority net · E: demanded-voice Edge failover · F: OAuth single scope ·
G: create_folder honest failure). Commit `4bb212c` (8 files, +591/−24) pushed to
`origin/main`; unattended audit run 2026-09-06: full gate GREEN (Ruff clean · **851 passed /
1 skipped / 85.31% branch** · security + docs green · sacred floors + defect floor 83/83).
Exhaustive audit artifact `AUDIT_AND_PLAN_40_FEATURES.md` (78 features: 53 ✅ / 24 ⏳ /
0 broken). Docs synced: CHANGELOG · 06-API-SPECIFICATION · Sara's capabilities manifest.
Record: `EXECUTIVE_PROGRESS_REPORT_2026_09_06.md`.

## Phase B — 2026-09-06: Tool Wiring & Operational Surface Completion

Skill rotation: **none ingested** (owner-directed Phase B wiring, closed loop on `main`).
The B1-B8 backlog from `AUDIT_AND_PLAN_40_FEATURES.md` was shipped end-to-end:
B1 `drive` · B2 `contacts` · B3 `create_event`/`create_task` · B4 `places` ·
B5 `deep_search` · B6 `fitness` · B7 `cloud_backup`/`analytics` ·
B8 `quota_safety`. New backend `src/google_cloud_client.py::GoogleCloudClient`
wraps the §7 adapters + CacheEngine + QuotaGuard; bound in `bot.py`. Settings
gains `GOOGLE_PLACES_KEY`/`CUSTOM_SEARCH_CX`/`CUSTOM_SEARCH_KEY`. 10 new
routing patterns (inserted before calendar/tasks so WRITE verbs beat READ
tools) + `_VALID_TOOLS` entries + 10 per-tool skill guides. 44 new
tests across `test_tools_expansion.py` + `test_google_cloud_client.py`. Gate:
**902 passed / 1 skipped / 85.01% branch / Security + Docs green /
sacred floors 44/44**. Record: `CHANGELOG.md` · `docs/06-API-SPECIFICATION.md`
· `.claude/PHASE-STATE.md`.

## Phase C — 2026-09-14: Groq FAST Pivot + Fail-Fast Doctrine + Tier3 Response Coach

Diagnosis first (commits `95a6f62`, `14c108e`): the ~3 min Telegram greeting
stall was the OmniRoute hop holding Gemma's SSE stream ~107 s before
surfacing a 429 (direct-OpenRouter same-429 lands in ~300 ms; zero reasoning
deltas at all budgets — starvation ruled out). Shipped: FAST-only 4 s
first-token guillotine, 15 min quarantine on ANY 429/empty/stall with
turn-zero skip, `(reset after Xs)` window parsing. Then the strategic pivot:
`FAST_MODEL=groq/openai/gpt-oss-120b` primary (measured cold TTFT ~0.6–0.9 s
at budgets >=128), Gemma secondary fallback (`.env` + `.env.example` +
contract tests flipped; live core needs a restart to bite). Tier3 gained a
Groq response coach (`tests/suite/tier3_shadow_tracer/response_coach.py`:
dialect/immersion/concision graders + 9 hermetic contracts + live
`scripts/groq_persona_probe.py` calibration runner). Recorded: ADR-23,
this entry, CLAUDE.md brain matrix, `01-ARCHITECTURE.md` Tier1 label.
OPEN: Groq per-key TPD throttle observed midday — multi-key rotation is an
OmniRoute provider-layer decision (no client bypass per hard rule 1);
RESOLVED 2026-09-14: owner selected OmniRoute-side rotation (zero repo code;
client keeps the single bearer + quarantine doctrine);
`docs/ai/PROJECT-CONTEXT.md` referenced by tasking but absent from the tree.

## Phase C sign-off — 2026-09-14: transition COMPLETE
Polish commit: excised the stray ~60-line "Active Components" harness
appendix from CLAUDE.md (uncommitted residue of a prior session, bundled by
accident in `eb25935`); persona carries the owner-ordered hygiene cap
(٦ إيموجي كحد أقصى بالرد الواحد — free choice of WHICH emoji stands),
response-coach ceiling aligned to 6, persona hash re-pinned
4782/ec6acc69. Acceptance: MATRIX 6/6 green, FAST cold TTFT <1.2 s measured
live, Tier3 calibrated (11/12 live checks; single emoji-pileup deviation now
governed by the cap). Core restart still required for the `.env` flip to
bite on the live bot.

## Phase D — 2026-09-14: Forensic Audit, 45/44 Census, Roadmap Decoupling

Three-track forensic sweep (subagents, lead-verified; two agent errors
struck) at baseline `1116de6`/1,385 green. Census re-measured: 45 handlers /
44 valid+net / 41 capabilities / 44 guides / 6 irreversible. Forgotten-feature
shortlist ranked in `docs/reports/EXHAUSTIVE_SYSTEM_AUDIT_REPORT.md` §Track 1
(strongest: orphaned `exec.open` verb, tunnel `wol` verb, `stream_heavy`).
Decoupling: future-only content moved to `docs/02-FUTURE-ROADMAP.md`; live
docs synced (CLAUDE decoupling rule, 01-ARCHITECTURE tier pins, README Fish
voice + shipped-scope). Frozen history untouched per owner ruling
(08-OWNER-NEXT-STEPS, NIGHT_RUN, compendium, PHASE-STATE keep legacy pins).

## Anchor — 2026-09-14 · Commit `3fe6703` · Tests 1,457 passed (0 failures) · STABLE / PRODUCTION CORE SEALED

Living-cognition mission complete (12/12 steps): MAC-bound WoL, copy-if-missing
mirror + master-digest plant, nested `Daily_Logs/YYYY/MM/` archive, intent-gated
RAG, inspect net hoist, `openclaw.browse` verb + browser bind, planner adapter,
dynamic PARK warnings, reconnect hook + quiet hours, whitelist 5+1 with
confirm-gated cmd.exe, scoped `exec.open` caller, `stream_heavy` MoE reroutes,
async write-back engine. Canonical 16-doc suite cutover ships in this same
change (`docs/08-ROADMAP.md` replaces `docs/02-FUTURE-ROADMAP.md`; legacy
`00–05` numbers retired to unprefixed frozen names).

---

## Phase 1 — 2026-09-15: Docs Synchronization to Commit 3fe6703 — COMPLETE (commit `4a3a1fd`)

Skill rotation: **none ingested** (closed-loop docs sync, no code change to logic).
Synchronized 16 canonical files to the `3fe6703` anchor: `CONTRIBUTING.md` →
`09-DECISIONS.md`/`14-RUNBOOK.md`; `CLAUDE.md` → `15-ORACLE-DEPLOY.md`/`08-ROADMAP.md`/
`04-ARCHITECTURE.md`; `docs/ai/AI-INSTRUCTIONS.md` → `04-ARCHITECTURE.md`/
`09-DECISIONS.md`/`01-PRODUCT-REQUIREMENTS.md`+`08-ROADMAP.md`. Rewrote
`scripts/docs_guard.py` as a 16-file suite (`README.md`, `.env.example`, `CLAUDE.md`,
`docs/01-13`) + `docs/ai/` — now asserts **all 16 canonical files present** (was 8).
Fixed `tests/test_bot_shell.py:114` `test_owner_text_streams_brain_progressively`:
import `DIGEST_HEADER_AR` from `src.associative`; assert roles `[system,user]`, user
`حدّد موعد بكره`, `system.startswith(SYSTEM_PROMPT_AR)`, envelope `""` or contains digest
header; `build_persona([])` len 4782 identical to baseline. `ruff check` + `format --check`
clean (351 files); `security_gate.py` OK (bandit + secret scan). Full `pytest -q -p no:cacheprovider --no-cov`:
**1,462 passed, 2 skipped**. Committed `4a3a1fd` ("docs: synchronize 16-file architecture
suite to commit 3fe6703 (1,462 tests passed)", 34 files), pushed `3fe6703..4a3a1fd main->main`.

**Verification**: `scripts/docs_guard.py` → `Docs Guard OK — 16 canonical files present`.
`src/tests` dangling-ref scan: empty. All 45 tools catalogued in `tools.py` (handlers),
44 `_VALID_TOOLS` entries, 44 `_TOOL_NET` entries, 41 capabilities, 44 skill guides,
6 irreversible. Census cross-matrix (handler × valid × net × capability × prompt × guide)
verified per `docs/reports/EXHAUSTIVE_SYSTEM_AUDIT_REPORT.md`.

---

## Phase 2 — LIVE INTERACTIVE BENCHMARK (Tests A–F) — READY TO EXECUTE

**Status**: `scripts/live_interactive_benchmark.py` has been **created** covering Tests A–F
with live-attempt + graceful DEGRADED fallback. The script is written and saved. It has
NOT yet been executed in the current session (was interrupted before completion).

**Objective**: Run the benchmark, capture all transcripts + latencies, then generate Phase 3 report.

### Test Matrix

| Test | Name | Live Target | DEGRADED Fallback |
|------|------|------------|-------------------|
| **A** | Persona & Masculine Arabic | `FAST_MODEL=groq/openai/gpt-oss-120b` via gateway; verify `build_persona([])` len 4782, Jordanian `ar-JO` dialect, masculine addressing | Verify `src/persona.py:SARA_PERSONA_AR` contains "سارة" + "عمان"; `build_persona([])` returns len 4782; `DIGEST_HEADER_AR` present |
| **B** | Screen inspection ("افحصي عناصر الشاشة") | `openclaw.perceive` via bridge; `_do_openclaw_inspect` | `tests/suite/openclaw_bench/mock_desktop.py` — `notepad_desktop()` + `ScreenInspector` with `mock_grab_factory`/`mock_ocr_factory`; assert foreground == "Notepad - report.txt", ocr contains "Error 404" |
| **C** | Destructive gating & whitelist guardrails | `executor.launch("cmd.exe", confirmation_id=None)` → refused; `executor.launch("cmd.exe", confirmation_id="cid-123")` → allowed | Create temp `Guard` + `Executor`; assert `cmd.exe` without `confirmation_id` returns error; `gate(dag, coordinator=None) == "park"` |
| **D** | Two-tier associative memory | `src/associative.py` — Routine→`""` digest injection; Tier-1+Tier-2 write-back vault; `DIGEST_HEADER_AR=[الموجز الحي — سياق أساسي]` | `intent_for("حدّد موعد بكره")` returns `calendar` (advisory, not routine); `calendar` not in `ROUTINE_INTENTS`; `load_digest_block(vault)` returns `""` or digest header |
| **E** | Hardware bridge & Amman quiet hours | `bridge/daemon.py` quiet-hours gate; `in_active_window(now, "Asia/Amman", start="08:00", end="23:30")` end-INCLUSIVE (matches `src/bot.py`; `test_bridge_online.py` pins 23:30 → True); 30m debounce | Inline `in_active_window()` + `_amman()` helpers; assert 08:00/14:00/23:30 in-window, 03:00/07:59/23:31 out-of-window, overnight 22:00→02:00 wraps |
| **F** | 4-task swarm via `stream_heavy()` | `src/gateway.py:313` `stream_heavy()` on `http://localhost:20128/v1`; HEAVY chain = `nex-agi/nex-n2.5-pro:free` (Nemotron-550B); 4-task DAG | `settings.omniroute_base_url`; `OmniRouteClient.heavy_chain_for(n_tasks=4, is_dag_swarm=True)` returns escalated chain; `stream_heavy()` method verified present at `src/gateway.py:313` |

### Fallback Logic (strict)
- If gateway `http://localhost:20128/v1` responds with HTTP 200 within 2 s → **LIVE** path executes.
- If gateway unreachable/timeout/non-200 → **DEGRADED** path executes hermetic doubles.
- Both paths write identical `ScenarioResult` rows; the report marks each as `LIVE` or `DEGRADED`.
- No test crashes the runner; every exception is captured as a row with `status: DEGRADED-ERROR`.

### Invariants to Verify (5)
1. **Immersion**: All Sara responses use Arabic (Jordanian `ar-JO` dialect).
2. **Masculine addressing**: Persona uses masculine verb forms (هو/يعمل/يقول), no feminine.
3. **Zero Edge-TTS**: `VOICE_NAME` = `fish-audio/s2.1-pro-free:free`; no `ar-EG-SalmaNeural` reference anywhere.
4. **Zero unconfirmed cmd**: `executor.launch("cmd.exe", confirmation_id=None)` returns error; no process spawned.
5. **$0.00 cost**: All LLM calls route through OmniRoute free pools; no paid API key hardcoded.

### How to Run (new session)
```bash
cd C:\Projects\Git-hub\Vantrilex Assistant OS\Vantrilex Assistant OS - Architecture & Docs
.venv/Scripts/python.exe scripts/live_interactive_benchmark.py 2>&1
```
This prints the Executive Summary Scorecard to stdout and writes `benchmarks/LIVE_BENCHMARK_TRANSCRIPT.json`.

---

## Phase 3 — FULL SYSTEM AUDIT & LIVE BENCHMARK REPORT — PENDING

**Deliverable**: `docs/reports/SARA_FULL_SYSTEM_AUDIT_AND_LIVE_BENCHMARK_REPORT.md`

**Status**: NOT YET GENERATED. Must be compiled after Phase 2 completes.

### Required Contents

1. **Complete 45-tool catalog** — every handler from `src/tools.py` listed individually:
   - Tools 1–45 enumerated with trigger pattern, handler name, subsystem, reversibility, test seam.
   - NO ellipses (`...`), NO truncation, NO "etc." — every single tool name appears in full.

2. **Test transcripts and latencies** — A–F scenario results with timestamps, wall-clock ms,
   pass/fail status, and DEGRADED fallback marker.

3. **5-invariant verification** — each invariant stated, tested, and result (PASS/FAIL):
   - Immersion: Arabic Jordanian `ar-JO` dialect confirmed.
   - Masculine addressing: masculine verb forms confirmed.
   - Zero Edge-TTS: `VOICE_NAME` = `fish-audio/s2.1-pro-free:free` confirmed; Edge-TTS purged.
   - Zero unconfirmed cmd: whitelist + `confirmation_id` + `PC-` audit gate confirmed.
   - $0.00 cost: OmniRoute free pools + `FAST_MODEL`/`MEDIUM_MODEL`/`HEAVY_MODEL` all free-tier.

4. **Executive Summary Scorecard** printed to stdout on completion.

### How to Generate (new session)
1. Run Phase 2 benchmark script to get results.
2. Read `benchmarks/LIVE_BENCHMARK_TRANSCRIPT.json` for transcripts + latencies.
3. Write `docs/reports/SARA_FULL_SYSTEM_AUDIT_AND_LIVE_BENCHMARK_REPORT.md`.
4. Print Executive Summary Scorecard to stdout.
5. Commit `scripts/` + `docs/reports/` on `main`; push.

---

## Key Configuration (for Phase 2 & 3)

- **Gateway**: `http://localhost:20128/v1` (OmniRoute, co-located with core)
- **Models**: FAST `groq/openai/gpt-oss-120b` fb `google/gemma-4-31b-it:free`;
  MEDIUM `nex-agi/nex-n2.5-mini:free`; HEAVY `nex-agi/nex-n2.5-pro:free` fb
  `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free,groq/openai/gpt-oss-120b`
- **Voice**: Fish-only `fish-audio/s2.1-pro-free:free` (ref `56c2f0c23924449781863ff20aceb5fa`);
  Edge-TTS `ar-EG-SalmaNeural` purged; zero-edge gate enforced.
- **Guardrails**: `PaidModelBlockedError`, whitelist + `confirmation_id` + `PC-` audit,
  `ActionForbiddenError`, `$0.00`, owner-only, async-only, secrets env-only.
- **Locale**: `Asia/Amman`, quiet hours 08:00–23:30, 30m debounce.
- **Branch**: `main` (all commits direct, push immediately).
- **Testing**: `pytest + pytest-asyncio + unittest.mock`; TDD mandatory.
- **Lint**: `ruff check` + `ruff format --check`.

---

## Exact Next Moves (for the NEW session)

1. **Execute** `scripts/live_interactive_benchmark.py` (Tests A–F). Capture stdout scorecard.
2. **Read** `benchmarks/LIVE_BENCHMARK_TRANSCRIPT.json` for all transcripts + latencies.
3. **Write** `docs/reports/SARA_FULL_SYSTEM_AUDIT_AND_LIVE_BENCHMARK_REPORT.md` with:
   - Complete 45-tool catalog (no ellipsis/truncation).
   - Test transcripts and latencies from the JSON transcript.
   - Verification of the 5 invariants (Immersion, Masculine, Zero Edge-TTS, Zero unconfirmed, $0.00).
4. **Print** Executive Summary Scorecard to stdout.
5. **Commit** `scripts/live_interactive_benchmark.py` + `docs/reports/SARA_FULL_SYSTEM_AUDIT_AND_LIVE_BENCHMARK_REPORT.md` + `benchmarks/LIVE_BENCHMARK_TRANSCRIPT.json` on `main`.
6. **Push** to `origin/main`.

## Relevant Files

- `tests/test_bot_shell.py`: fixed assertion for living envelope (line 114).
- `scripts/live_interactive_benchmark.py`: **CREATED** — Test A–F runner with DEGRADED fallback.
- `scripts/benchmark_openclaw.py`: existing hermetic-benchmark pattern (reference).
- `scripts/docs_guard.py`: 16-file canonical suite (reference).
- `scripts/security_gate.py`: bandit + secret scan (reference).
- `tests/suite/openclaw_bench/scenarios.py`: A1–E4 hermetic scenarios (reference for DEGRADED doubles).
- `tests/suite/openclaw_bench/mock_desktop.py`: `notepad_desktop()`, `mock_grab_factory`, `mock_ocr_factory`.
- `tests/test_whitelist_guardrail.py`: AC3 confirmation-gated verdict; `test_confirm_gated_verdict_keeps_executable`.
- `tests/conftest.py`: `make_settings` builds `Settings(_env_file=None)`; `make_shell`.
- `src/tools.py`: all 45 handlers (line 90–1284).
- `src/gateway.py:313`: `stream_heavy()` method.
- `src/associative.py`: `DIGEST_HEADER_AR`, `INJECT_HEADER_AR`, `ROUTINE_INTENTS`, `intent_for`, `load_digest_block`, `DIGEST_REL_PATH`.
- `src/persona.py`: `SARA_PERSONA_AR`, `build_persona` (len 4782).
- `src/bot.py`: `SYSTEM_PROMPT_AR` (alias of `SARA_PERSONA_AR`).
- `bridge/executor.py`: `Executor(guard)` requires `Guard`; `launch`, `close`, `power`, `open_path` with `confirmation_id` gate.
- `bridge/guard.py`: `Guard` class for whitelist checking.
- `bridge/openclaw/breaker.py`: `SafetyCircuitBreaker`, `ActionForbiddenError`, `authorize(op, confirmation_id)`.
- `src/openclaw/plans.py`: `build_dag`, `gate`, `needs_confirmation`.
- `src/openclaw/protocol.py`: `Op`, `OpKind`.
- `src/config.py`: `Settings` — `omniroute_base_url` (not `gateway_url`), `tz="Asia/Amman"`, `voice_name` defaults to `ar-EG-SalmaNeural` but `.env` overrides to `fish-audio/s2.1-pro-free:free`, `fast_model`/`medium_model`/`heavy_model` chains.
- `docs/reports/TOOLS_AND_API_COMPENDIUM.md`: tool census + API rollup (consolidated 2026-09-16; supersedes the pruned exhaustive audit).
- `docs/01-PRODUCT-REQUIREMENTS.md`, `docs/04-ARCHITECTURE.md`, `docs/09-DECISIONS.md`,
  `docs/14-RUNBOOK.md`, `docs/15-ORACLE-DEPLOY.md`, `docs/08-ROADMAP.md`, `docs/ai/AI-INSTRUCTIONS.md`.
- `vault/02_Areas/Profile/Omar_Master_Digest.md`: two-tier memory anchor.
- `config/whitelist.json`: 5 auto-approved + `cmd.exe` confirm-gated.
- `benchmarks/LIVE_BENCHMARK_TRANSCRIPT.json`: **OUTPUT** of Phase 2 benchmark run.
- `.env.example`: `OMNIROUTE_BASE_URL=http://localhost:20128/v1`, `OMNIROUTE_API_KEY=sk-omniroute-local-key`.

## See also (graph links)

## P0 — Shape contracts (master transformation plan, 2026-09-17)

AST enumeration: 23 Arabic-literal equality asserts (13 streamer plumbing echoes
excluded with rationale — fixture-in/out mechanics, not presentation).
8 additive `_shape` twins in `tests/test_shape_contracts_p0.py` (dispatcher ack
clean/drift, shell ack replacement, voice-fallback frozen shape, triage card +
voice slots, brief + journaler sections). Denylist byte-identical, persona
4,782, suite 1,469/7/0. Commits: `1b7c368`. HALT before P1.

## P1 — Pattern bank (master transformation plan, 2026-09-17)

Miner `scripts/mine_joda_bank.py` (dev-layer, openpyxl read-only over local
gitignored `data/joda/*.xlsx`): 5 acts × 80 floors + 100 rarity wildcards =
500 patterns, first-act-wins dedupe, generic cap 5, into
`04_Resources/Dialect_Encyclopedia/JODA_Pattern_Bank.md` (raw xlsx never in
git). Deviation on record: competitive top-1 recall hits only 287/500
(shared dialect vocabulary) — bank is consumed by DIRECT section read instead
(gated by `tests/test_joda_bank_p1.py`: quotas, dedupe, shape, section parse).
Suite 1,474/7/0. Commits: `f519bc3` (+ `0c8af40` cue integration). HALT before P2.

## P2 — Counter, cadence, cues (master transformation plan, 2026-09-17)

P2.1 `src/turn_counter.py` (atomic tmp+fsync+replace, corrupt-rename→0,
human-turn-only via transport hooks + ReAct-import ban, pytest hermeticity
fence); P2.2 `src/cadence.py` (10-turn trigger, starvation guard, MOBILE
derivation, posture-conditioned wheel); P2.3 JODA cues in `load_long_term`
(capped 300, deterministic sections). P2.4 audit: 5 invariants clean (no
prose/voice/PC/network/secrets surface). Suite 1,496/7/0, ruff clean,
security OK. Commits: `d2a1633` (counter), `a28025c` (cadence), `0c8af40`
(cues). HALT before P3.

## P3 — Fused router + sliced RAG (master transformation plan, 2026-09-17)

P3.1 `rag_domains` fused verdict field (+0ms) + `repair_verdict()` non-throwing
layer (fence/trailing-comma/schema); `_parse_router` 5-tuple frozen (zero
collateral); `front.rag_domains` observed state. P3.2 closed budget slicing
(60/40, 50/30/20, floor-400) + sentence chunks + quarantine-halved ceiling +
per-hit path citations + legacy header preserved; wired via deterministic
intent→domain map (model verdict stays observed pending verdict-first
reorder). Regression caught and fixed: phase-6 citation/header test.
Suite 1,514/7/0. Commits: `5e4da96` (fused router), `6a4d8f5` (slicing).
HALT before P4.

## P4 — Token/prose split + single-pass synthesis (master plan, 2026-09-17)

Forensic result: confirmation_id is minted server-side post-affirmation,
persisted pre-execution, machine-to-machine only — never in prose or model
I/O. P4.1 pins: challenges carry no auth token (audit receipt stays),
execution target comes from pending state (reply naming another app still
fires the original), refusal clears clean, park warning single-pass shaped
with static floor. P4.2 pins: direct turn = exactly 2 model touches,
placeholder/ack never reach memory (full-turn variant). Suite 1,521/7/0,
ruff clean, security OK. Commits: `98d2180` (token/prose), `805fc3b`
(single-pass). HALT before P5.

## P5 — Fault matrix, overlay, live harnesses (master plan, 2026-09-17)

P5.1 audited the 30-seam registry: 27 covered, 3 genuine gaps pinned
(MEDIUM 429 cascade, dead-coordinator park, missing-binary Arabic line).
P5.2 `tests/live_harness/overlay.py` OverlayVault (shadow writes, fallback
reads, diary pristine). P5.3 ten live harnesses (skip-soft, pacing, diary
fence; 6 pass hermetic legs, 7 skip without backends). Suite 1,536/14/0.
Commits: `c1c07e2`/`43311c3` (matrix), `07a5a1c` (overlay), `572f278`
(harnesses). HALT before P6.

## P6 — Tiered coverage 98/90 (master plan, 2026-09-17) — COMPLETE

- **Batches**: 1–5 + 3a/3b/3c + 4a/4b + 5 + 6a + 7a–7g (`test_coverage_gaps_p6*.py`,
  `p64*.py`, `p65*.py`, `p66a`, `p67a–p67g`); `scripts/check_tiered_coverage.py`
  (22 core modules ≥98 + TOTAL ≥90, live files included).
- **Commit range**: `94d53da` (batch 1) … `3e52802` (checkpoint) — batches
  `94d53da`, `0ff7c91`, `726902c`, `621bc81`, `9e88b79`, `aa06c7e`,
  `03ea7d5`, `73f8b60`, `b03d7f8`, `c5f68ec`, `918ae84`, `d48496d`,
  `98c97c2`, `b92cd8f`, `5e5f86f`, `decd87c`, `c82f6b7`, `32ba3d6`,
  `d48041d`, `162b4ac`, `843f825` (+ lint/format fixes interleaved).
- **Verdict**: TIERED COVERAGE GATE PASSED — 22/22 core OK (3 at 100, lows 98.2
  associative / 98.5 executor), TOTAL 91.8%; full suite 1,798 passed, 7 skipped.
- **Production fixes found by pins (2)**: `VaultClient._migrate_studies` guard
  reorder (non-list payload crashed with AttributeError); `VoiceprintRegistry.match`
  missing `await` on `match_vector` (returned an unawaited coroutine).
- **Known environmental**: `h04 TTFT` + `h06 JODA dialogues` fail only while the
  free pools are rate-limited (groq cooldown + gemma first-token timeout —
  fail-fast quarantines working as designed); both pass on recovered pools.
- HALT — master transformation plan P0–P6 complete.

## sara.ps1 full-stack hardening (ops, 2026-09-17)

10-item audit + auto-launch OmniRoute (1-click launcher): port-true teardown
(`Stop-PortOwner` for `$Port` + `:20128` stale nodes), reactive `Wait-PortFree`
(200 ms), `.venv`/`.env` preflight + in-repo `--health` JSON gate, real HTTP
probes (`/v1/models`, `/health` — never bare TCP), titled windows (`[SARA Core
:PORT]` / `[SARA PC Bridge]` / `[SARA OmniRoute Gateway :20128]`),
ESTABLISHED-dial bridge proof (`Test-BridgeDial`), stale-variable fix
(`$stillAlive` in final gate) + `TryParse` port validation, `logs/` transcripts
(gitignored), pwsh-or-powershell parity + quote-safe paths + occupied-port
fail-fast. Gateway path: reuse-healthy → clear-squatter → `omniroute` (fallback
`npx omniroute`) → 20 s `/v1/models` wait → `-Force` override. Verified:
parser 0 errors, `Get-Command` resolves, `-Port abc` fail-fast pre-teardown.

## sara.ps1 handshake-collision fix (ops, 2026-09-17 live)

False-negative boot verdict on a HEALTHY stack (bridge session online, Telegram
live): plain-HTTP `Invoke-RestMethod /health` never reaches `process_request`
on the websockets handshake server — it dies as InvalidMessage/EOFError spam
in the core window, cascading to a missed dial check. Fix: `Test-CoreHealth`
sends a complete Upgrade-handshake request to /health over raw TcpClient (200
`{"status":"ok"}` + abort-after-response, zero log spam; proven 45 ms live).
Deeper finding: ESTABLISHED bridge<->core pair (49512<->8443) exists, but both
endpoint PIDs are blank-CLI worker children — so `Test-BridgeDial` is now
TUPLE-anchored (any ESTABLISHED loopback tuple touching :8443, 30 s/250 ms;
proven live), and `Stop-PortOwner` also clears Established holders (PID-0
guarded). Plus: `--health` JSON now parsed for the Google row with the
`src.google_auth` renewal hint (HTTP 400 expired-grant lesson).

## Windows logon auto-start (ops, 2026-09-17)

`scripts/setup_autostart.ps1` (idempotent, `.\sara.bat -InstallAutoStart` entry):
Task Scheduler primary (AtLogOn + 30 s delay, working dir = root, calls
`sara.ps1` directly to dodge the `.bat pause`, Interactive/Highest with
`-RunLevel` toggle) + minimized Startup-shortcut fallback (`-Mode Shortcut`);
`-Remove` cleans both modes. Self-elevates only when a task op truly needs it
(shortcut-only removal stays UAC-free). Silent-boot rule: the Google grant
must pre-exist (`vault/State/google_token.json.enc` roll call at install;
interactive `src.google_auth` once). Tested: task objects construct valid
(`OMAR\OMAR`, PT30S); shortcut install->remove cycle clean, no residue. Live
Task registration needs one elevated owner run (UAC).

## Live shadow tracer console (telemetry, 2026-09-18)

`feat(telemetry)`: opt-in serialized JSONL sink in `src/logsetup.py`
(`SARA_SHADOW_JSONL`, default-ON from `sara.ps1` into
`vault/State/SARA_SHADOW_COGNITION_LOG.jsonl`; unset = historical behavior) +
`scripts/live_shadow_tracer.py` (rich console: vitals CORE_HEALTH/BRIDGE_DIAL/
gateway/turn-counter + rotation-safe 7-domain classified feed, `--once` mode;
missing fields render `--`, never fabricated) + `sara.bat -Trace` launcher.
Tests `tests/test_shadow_sink.py` + `tests/test_shadow_tracer.py` (16 new).
Gates: suite 1,813 passed / 2 pre-existing fails proven unrelated via
`git stash` (p63b summarizer + h06 free-pool live); tiered coverage PASSED
(91.7% total); ruff clean; security gate OK; live benchmark 6/6 LIVE + 5/5
invariants. Launch: `.\sara.bat -Trace` (full cognition stream after next
core boot). Pre-existing fails carried, not fixed: p63b run_forever +
h06 joda live.

## Incident 2026-09-18 14:54–14:57 + hardening (telemetry/triage, 2026-09-18)

Live session wall of «خلل تقني»: free-pool storm (nex-agi 404 no provider
credentials + groq/gemma 429 quarantines ~900 s + nemotron empty) overlaid on
a Gmail per-minute quota 403. Forensics: the core did NOT die — the pasted
traceback is `tools:call`'s own ERROR log; `_tool_lane` survival boundary
(`dispatcher.py:945-958`, tested by `test_registry_failure_degrades_to_plain_tier2`)
held. Landed: (a) tracer hotfix — loguru time-dict unwrap, rule reorder
(memory/tools before router/generation), bare-`router` keyword dropped for
dispatcher-anchored signals (openrouter-slug collision), `exhausted`/`tool '`
keywords, wait-notice once; (b) Gmail quota diet — `PEEK_DEFAULT_MAX=10`
(was 25), `FETCH_BURST_CAP=25` with cursor hold-back so overflow redelivers
(`_do_gmail` needs only sender/subject; triage keeps full bodies); (c) pool
audit — MEDIUM/HEAVY primaries are nex-agi slugs, dead-weight 404s until the
OmniRoute credential is restored (owner console action; `auto/*` combos now
served). Gates: suite 1,819 passed (3 live storm fails re-passed post-recovery;
p63b carried pre-existing); tiered coverage PASSED (91.8%); ruff clean;
security gate OK; docs guard 16/16.

## Sovereign rewrite of docs/16-WORKFLOWS.md (2026-09-18)

Wholesale replacement from deep scan of
`O:\Claude Code\vantrilex\vantrilex-registry\` (1,486 skills / 283 agents /
903 MCPs / 13 plugins / 19 hooks; catalog 2,743 lines, 18 ✅ defaults
retained). Curated provisioning matrix with rejection causes (rag-blueprint,
cloud-vision, fetch/time, local-weight MCPs); Skill Lock codified §0.1; five
consensus pillars operationalized (ephemeral cache, scratchpad healing,
memory_upsert, hybrid RAG, ROI vision); live floors (1,819 passed, Gmail
10/25, guides 45). Registry gaps recorded: no pytest entry (local-only),
git-guardrails file named `git-guardrails-claude-code.md`, docs-guard file
named `docs-guard.md`.

## CI triage + P1 quick-wins (2026-09-18)

CI root-caused via `gh run view` (21 fails, all environmental): Linux runner
vs Windows-native suite (windll/DETACHED_PROCESS/tmp paths/Win32 disks),
4 missing Settings vars in `test_fish_audio_pipeline` (vault_github_repo/
token, bridge_token/server_url — local `.env` masked it), missing ffmpeg,
plus genuine date-rot in p63b (`run_forever` used real today vs 2026-09-17
fixture). Landed: `ci.yml` → windows-latest + choco ffmpeg; hermetic fish
`_settings` (`_env_file=None` + dummies); `run_forever(now_fn=)` seam
(SelfEvolutionWorker precedent) + frozen clocks. P1 primitives (wiring P2):
ReflectiveTrace.render_ledger_block, stdlib BM25 rank/score, memory
upsert_fact/resolve_current_facts (row-scoped supersede), HealingBudget +
normalize_tool_arg, CompositionCache (explicit read-only gate). Suite 1,838
passed, only h04/h06 live-pool fails; coverage 91.8% PASSED; ruff + security
+ quality gates green. Guards: clean/test-guard clean.

## P2 wiring + evolution loop (2026-09-18)

Dispatcher: arg healing at lane entry (quotes/Indic digits), single retry
iff transient-shaped (stall/429/5xx — quota/auth never retried) via
HealingBudget, outcomes recorded into the friction ledger, verdict cache
for read-only tools (router call skipped; هسا/هسه/الحين bypass; launch-class
never cached). Adjacent fix disclosed: unparsable router replies crashed on
unbound `voice_hint` — scoped into the parsed branch + regression test.
Envelope: superseded rows filtered from User_Info reads (vault keeps audit).
Nightly: DailySummarizer(trace=) appends the friction block as a second
section. Evolution: src/evolution.py distill (≥3 repeats) + AST gate
(allowlisted stdlib, no eval/exec/open/socket) + owner-proposal markdown —
no self-registration, ever. Suite 1,855 passed (h04/h06 live only);
coverage 91.9% PASSED; ruff/security/quality green. Guards: clean/test-guard
clean. P3 next: sandbox execution, promotion gates, cache TTL/invalidation.

## CI closure — last Windows failure (2026-09-18)

Triage run fell 21 → 1: `test_owner_account_never_gusted_across_devices`
read a sealed Arabic JSON note with bare `read_text()` → cp1252
UnicodeDecodeError on the Windows runner. One-line fix
(`encoding="utf-8"`); sibling sweep: only ASCII marker reads remain
(cp1252-safe); production `src/` fully pinned (15/15 reads explicit).
Expected state: main 100% green in CI.

## Model probe Phase 1 — FAST (2026-09-18)

`scripts/probe_candidate_models.py` (`--phase fast`; tabulate present,
storm etiquette: sequential, 6 s gaps, fail-soft). Live: baseline
`google/gemma-4-31b-it:free` TTFT 29.3 s / 51.7 s @1.5–2.2 tok/s;
mission slug `google/gemma-4-26b-a4b:free` is HTTP 404 (does not exist —
real slug carries `-it`); `openrouter/google/gemma-4-26b-a4b-it:free`
TTFT 23.5 s @3.1 tok/s with cleaner masculine markers (طمني، أهلا),
zero feminine hits both. Pool-wide TTFTs ~30–50× SLA during the window —
comparative verdict only. Report:
`benchmarks/CANDIDATE_MODELS_PROBE_REPORT.md` (+ JSONL records).

## Model probe Phase 2 — MEDIUM (2026-09-18)

Mission slug `nex-agi/nex-n2.5-mini:free` is HTTP 404 ×3 (same provider-credential
gap as the 14:54 storm). `openrouter/`-prefixed slug works first try:
TTFT 4.9 s, strict `{"tool":"calendar","arg":"…"}` with zero hallucinated keys
(`valid_json` + `schema_ok` true). Throughput ~4 tok/s — nowhere near the
>100 t/s dashboard claim; that target is rejected as pool-fiction. JSON
discipline itself is sound; the slug prefix is the entire problem.

## Model probe Phase 3 — HEAVY (2026-09-18)

Bare `nex-agi`/`nvidia` slugs dead; all HEAVY rows are `openrouter/` forms:
pro → empty stream ([DONE], zero deltas); Ultra-550b → empty in 869 ms
(incident signature); Lightning → ok 24.3 s but English chain-of-thought
prose, ignoring the JSON-only instruction (steps=0 — needs the house
`repair_verdict` post-pass). Verdict: neither displaces pro; Lightning is
the only breathing fallback candidate, format-repair required; Ultra out
until it streams content. Dashboard latency claims (869 ms) rejected —
measured 24 s. Table slug ambiguity fixed via two-segment display.

## Model probe Phase 4 — ASR (2026-09-18, final)

Fish-synthesized ar-JO fixture («مرحبا سارة، شوفيلي شو في مواعيد اليوم»,
temp-only, deleted after run) vs `groq/whisper-large-v3-turbo` (557 ms,
WER 0.714), `groq/whisper-large-v3` (643 ms, WER 0.571), local
faster-whisper-small/int8 baseline (3.6 s, WER 0.714). All three normalize
colloquial toward MSA (شوفيلي→شوفيني، مواعيد→مواعد/موايد); v3 edges turbo
by one word; Groq is ~6× faster than local at equal-or-better accuracy.
Pipeline switch NOT proposed here — needs its own plan (privacy/latency
trade, §2.5 local-first doctrine). Mission verdicts Q1–Q4 complete in the
report; no production config changes made.

## Pool re-probe — key rotation verdict (2026-09-18 13:25)

Re-ran fast/medium/heavy on the current pool. Degraded → now: FAST 31b
29/52 s → 53/102 s TTFT (WORSE); 26b 23.5 s → 47 s (worse); bare nex-agi
slugs still 404; pro still empty; Ultra empty → OK (3.6 s TTFT, valid
3-step gmail/calendar/telemetry DAG); Lightning ok → empty (84 s).
Models flap ok↔empty between runs minutes apart. Rotation unverifiable
from here: OmniRoute exposes no admin API (only a Next.js /status
dashboard), and `.env` holds single GROQ/OPENROUTER keys — the 5+5 pool
is server-side. VERDICT: pool NOT stable enough to pin; keep all
baselines; owner action = OmniRoute /status inspection + provider
credential audit. Ultra validated capable-when-streaming (fallback with
repair, never primary).

## Arsenal sanitization (governance, 2026-09-17)

## Compliance enforcement (governance, 2026-09-17)

`docs/16-WORKFLOWS.md` verified byte-identical (untouched). MCP surgery:
`fetch` + `time` removed (npm 404, re-probed), `sqlite` fixed dormant,
`filesystem` gained the project-root arg, `instructions[]` repointed off
quarantined skills (all 7 targets exist). `tdd` + `test-guard` invoked via
skill loader (visible transcript); test-guard self-review of P0/P1 test files:
no violations. Agents (8, incl. the 4 mandated), plugins manifest (4
official), key hooks — all present on disk. HALT before P2.

Bloat premise falsified (none of the 16 alleged skills on disk); 9 unlisted
residual dirs quarantined restorable; MCP `fetch`/`time` removed as dead
(404/unresolvable), `sqlite` fixed dormant; sequential-thinking launch-proven;
`16-WORKFLOWS.md` §0 realigned + Mandatory Invocation Rule bound from P2.

- [07 — Implementation Plan](./07-IMPLEMENTATION-PLAN.md)
- [11 — Testing](./11-TESTING.md)
- [Objectives Ledger](./reports/OBJECTIVES_LEDGER_MET_VS_PENDING.md)
- [Master Transformation Plan](./MASTER_SYSTEM_TRANSFORMATION_AND_EXECUTION_PLAN.md)
- [System & Codebase Encyclopedia](./reports/SARA_EXHAUSTIVE_SYSTEM_AND_CODEBASE_ENCYCLOPEDIA.md)
- [Map of Testing & Audits](./00-MAP-OF-TESTING-AND-AUDITS.md)
