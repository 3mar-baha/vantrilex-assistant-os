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

## Where the analysis lives, and where the decisions live (2026-10-01)

A full analysis report of this codebase drives the current programme. It has two
homes, and conflating them is the mistake:

| Artifact | Location | Content |
|---|---|---|
| **The analysis** | [Drive folder](https://drive.google.com/drive/folders/1_iQ-w8ekzDW3xsIfnZ1VS83SMqocMtpd) — `INDEX.md` map, `part-a`…`part-h` sections, `REPORT.md` assembly | the reasoning, `file:line` evidence, patch drafts |
| **The decisions** | this ledger + `docs/architecture/CROSS_FRAMEWORK_ANALYSIS_AND_SELF_EVOLUTION.md` | what was decided, what shipped, what is still RED |

**The report is PINNED to `a817efa`; the tree has moved past it.** Treat every
`file:line` in it as a claim to re-verify before building on it, not a location
to trust. P3-D already landed under that rule, and it contradicted the report's
own patch draft: §41's F-1 draft assumed `ToolRegistry.call` takes a `context`
dict, and it does not — the signature is `call(self, tool: str, arg: str = "")`.
The report invited that check explicitly ("adapt to reality"); the reality
differed, and the owner approved a different signature.

A local copy is vendored at `Sara Agent - Full Analysis Report/` as a **reading
copy only**. It is deliberately **gitignored** and deliberately **not** committed:
it is pinned to a commit this repository has since left, so tracking it would
freeze a dead snapshot that a future agent reads as current documentation.
`docs_guard.py` does not police it, so nothing would catch that drift. It also
duplicates nothing — every conclusion that matters is recorded in the tracked
artifacts above, re-derived from the tree at each milestone. Nothing is deleted;
the directory stays on disk as the reading copy.

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
default) · `5f07db9` docs (ADR-15 amendment → Oracle Always Free; `docs/15-ORACLE-DEPLOY.md`
Arabic owner guide; RUNBOOK/HANDOFF/OWNER-NEXT-STEPS re-anchored) · `7e49f85` release
(version 1.0.1 + CHANGELOG `[1.0.1]`; scope-deferral test pinned to v1.0.0). Tag
`v1.0.1` pushed; GitHub Release published. Full gate green throughout (285 passed).
Owner deploy blocked at Oracle card verification — bank contact 2026-09-01, recovery
checklist in `docs/15-ORACLE-DEPLOY.md` §1. Record: `docs/PROJECT-JOURNEY.md` §14.

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

## P3 sandbox + promotion gates + cache TTL (2026-09-18)

CI closure: triage run fell 21 → 1; last failure was a bare
`read_text()` on a sealed Arabic note (cp1252 on the Windows runner) —
one-line utf-8 pin; sibling sweep + production audit (15/15 pinned):
test-only bug class. Evolution: src/evolution.py gains evaluate_proposal
(chain/tools/AST/vault-notes structural checks against OverlayVault —
no code executes), PromotionReport, promotion_decision (report + owner
word + green suite, all three), PROMOTABLE_TOOLS pinned disjoint from
IRREVERSIBLE_TOOLS by test. Cache TTL: CompositionCache ttl_s with
expiry sweep on lookup; dispatcher verdicts TTL 1800 s (relative-date
staleness bound). Suite 1,864 passed (h06 live only); coverage 91.9%
PASSED; ruff/security/quality/docs guards green. Guards: clean (evaluate
split) / test-guard clean.

## CI closure — last Windows failure (2026-09-18)

Triage run fell 21 → 1: `test_owner_account_never_gusted_across_devices`
read a sealed Arabic JSON note with bare `read_text()` → cp1252
UnicodeDecodeError on the Windows runner. One-line fix
(`encoding="utf-8"`); sibling sweep: only ASCII marker reads remain
(cp1252-safe); production `src/` fully pinned (15/15 reads explicit).
Expected state: main 100% green in CI.

## P3-A shipped — EvolutionTask and the append-only backlog (2026-09-30)

`src/evolution.py` gains the gap-detection stage: `is_valid_task_name`,
`EvolutionTask`, `BACKLOG_RELPATH`, `append_task`, `read_backlog`, `classify_gap`,
`OWNER_NOTICE_TEMPLATE`, `owner_notice`. 192 RED → green, plus 4 registry-precondition
guards that were green from the start.

**The barrier proved itself before any code existed.** The qa-agent built a throwaway
reference implementation **in temp** and mutation-tested it: 19 mutants, each verified
to have landed and to have collected 196 tests — **19/19 caught**. Green-ability was
checked too, so the guards are satisfiable rather than over-constrained. That harness
found a real defect in its own reference: a crash-torn last line has **no trailing
newline**, and a plain append concatenates onto it — destroying both the torn residue
and the new record, which is exactly the corruption JSONL exists to prevent. Pinned in
`test_append_never_rewrites_and_never_drops_the_garbage_line_before_it`, and the
implementer's break-run #1 disabled the repair and confirmed exactly that test reds.

### The four-name leak — measured, not asserted

| Set | Size |
|---|---|
| `TOOL_CAPABILITIES` | **42** (not 46) |
| `_VALID_TOOLS` | **46** |
| union | 46 |
| capabilities − valid | **empty** |
| **valid − capabilities** | **`analytics`, `cloud_backup`, `none`, `quota_safety`** |

A collision guard reading only `TOOL_CAPABILITIES` provably leaks exactly those four —
the same four-point registration trap the master plan warns about. Break-run #2 dropped
the `_VALID_TOOLS` surface and failed on precisely those four names × 3 tests and on
nothing else, which is what bounds the leak rather than hand-waving it.

### Two ratified deviations

1. **`EvolutionTask` gains `kind`.** Blueprint §3.1's snippet omits it, but §3.5.2
   requires the backlog to record *which* gap was chosen. A dataclass with no
   discriminator cannot satisfy that.
2. **The forced safety tier is a token scan over `intent` + `evidence`.** A
   *paraphrased* irreversible request («سكّر البرنامج اللي مقفول») names no tool and
   will not trip it. Stated in the module docstring, not hidden. Structural backstop:
   `IRREVERSIBLE_TOOLS ⊆ TOOL_CAPABILITIES`, so a task *named* after one is rejected
   outright, and that subset relation is pinned by a test.

### Refuted premise, carried forward

The blueprint said the backlog is `State/evolution_backlog.json` while describing JSONL.
A `.json` name holding JSONL is a lie in the filename. Corrected to `.jsonl` in the same
commit (blueprint `:185`); it was the only other reference anywhere.

### OPEN ITEM — `State/` is not gitignored, and one existing justification says it is

`append_task` is a genuine new durable-state write site, so it joined the AC6 allowlist
rather than evading the detector: the implementer used `path.open("a", …)`, which is the
form the guard *catches*, and declined the builtin-`open` spelling that would have
slipped past the `\.open\(` regex. Evasion would have defeated the guard's whole purpose.

The justification I wrote does **not** repeat a claim I could not verify:

> **`.gitignore` covers `data/` and `vault/` under its "state lives in the vault" comment
> and does NOT cover `State/`.** One existing entry, `tests/test_packaging.py:219`
> (`src/task_orchestrator.py`), asserts `gitignored` and is **false as written**.

**Correction to my own first pass.** I initially recorded *two* stale `gitignored`
claims. Checking each one individually rather than pattern-matching the word showed the
second is **true**: `bridge/app_sessions.py:218` writes under `data/app_sessions/`, and
`data/` **is** ignored at `.gitignore:37`, so "gitignored like vault/" is accurate. One
stale claim, not two. An audit that greps for a keyword and counts hits gets the wrong
answer; one that checks each claim gets the right one.

Nothing is tracked under `State/` today, so a rule is safe — but once `append_task`
ships, a `State/evolution_backlog.jsonl` will exist at runtime and `git add -A` would
stage it. Not fixed here: it is a different item, and bundling it would break
one-item-one-commit. **Owner approved: add `State/` to `.gitignore` and correct the one
stale justification, in an isolated commit.**

### Measured

`src/evolution.py` coverage 88% → **93%**. The +69 statements and +14 branches added
contribute **zero new misses**; every remaining miss is pre-existing P2 code. Two of the
implementer's own gaps were closed honestly rather than by evasion — a blank-line guard
that was dead code (`json.loads("")` already raises `ValueError`) and a zero-byte check
that merged into the absent-file check. The file was **not** added to the tiered-coverage
core list; that is a separate item.

## Dual console shipped — Terminal 1, the drill, and the 6th HUD marker (2026-09-30)

Plan items A–D from `MASTER_OPERATIONAL_PLAN_AND_DUAL_CONSOLE.md` §1, each its own
commit, Test-First Barrier honoured: `b6b0a67` landed the RED suite (26 red / 18
green) before a line of implementation existed. Then `7ab3d0d` (A), `bbe3cf7` (B),
`7b3db69` (C), `ea79a3b` (D).

**Terminal 2 was already delivered.** `sara.bat -Trace` has existed all along
(`sara.bat:11-14`) and the tracer already carried 5 of the 6 HUD markers. The delta
was one classifier group, not a subsystem. The directive's `sara.bat --tracer` is
now an accepted alias.

**Terminal 1 is new: `src/bot_shell.py`** (190 lines). `build_shell(gateway,
settings) -> Shell`; `Shell.turn(text)` is an async generator yielding the
dispatcher's deltas **verbatim**. It imports none of `src.persona`,
`src.gender_pipeline`, `src.voice_policy`, `src.tools`, `src.pc_actions`,
`bridge.executor` — a guard parses the module with `ast` and asserts it. The
invariant guarantee is therefore structural: no second code path exists.

### ~~OWNER DECISION~~ — SUPERSEDED 2026-10-01 — Terminal 1 answers in ar-JO

> **This section is retained as the record of the question, not as its answer.** The
> decision landed the same day: `src/bot_shell.py` now binds **exactly one** symbol from
> `src.persona` — `build_persona_joda`, the builder — so resolution **2** was taken over
> resolution **1**, and Terminal 1 speaks ar-JO. Nothing about a second dialect path was
> reopened: the builder composes the byte-locked identity core with the JODA few-shot
> exemplars, so the terminal and Telegram share **one** dialect contract. The CHANGELOG
> entry that announced this as a live limitation was corrected in the same milestone
> (`tests/test_changelog_dialect_claims.py` now re-derives the binding and fails if the
> changelog re-announces it). See *Phase 0 — analysis-report catalogue (2026-10-01)* below.

The directive asked Terminal 1 for "authentic Amman dialect (ar-JO)". **At the time it
could not have that without importing `src.persona`, which the safety rule forbade.** Live
proof: asked about programming, the shell replied MSA. The gap was stated in the
module docstring, not papered over. Two honest resolutions:

1. **Persona-free shell** (current) — ar-JO arrives only where the full pipeline
   runs (Telegram). Terminal 1 is an engineering surface, not Sara.
2. **Let the shell compose the persona** — gives ar-JO in Terminal 1, and reopens
   a second path for the gender and dialect invariants to leak through.

Not mine to decide. Until it is decided, Terminal 1 is a dispatcher front, not
Sara.

### Refuted premise — the CRLF incident was not real

The implementer reported that the committed `sara.bat` was LF-only, that `cmd.exe`
skipped every `if … (` block, and that it had restored CRLF — a pre-existing repo
defect that "would have shipped a `-Chat` flag that does the opposite of what it
says". I read the committed blob directly: `HEAD:sara.bat` has CR=16 LF=16. **It
was already CRLF.** The mixed endings were that agent's own intermediate write,
misdiagnosed. The end state is correct — the content diff is 14 added / 0 removed —
but the narrative was fabricated and would have put a non-existent incident into
the permanent record. Recorded here so nobody goes hunting for a CRLF bug that was
never in a commit.

### Accepted finding — a docstring that recommended dead batch

`tests/test_launcher_flags.py` documented
`if /i "%~1"=="-Trace" if /i "%~1"=="--tracer" (` as yielding two flags off one
block. Chained `if`s are a **conjunction** in cmd. Verified on this machine with a
probe batch file: with that spelling **neither** `-Trace` nor `--tracer` enters the
block. The docstring would have shipped a dead launcher behind a green guard. It is
corrected, `sara.bat` carries a `rem` at the alias site, and the alias is two
blocks with byte-identical bodies.

### Measured limits — stated in-tree, not in a report

- **The per-tool counters count the tool lane's failure path only.** Successful
  calls log nothing; 1 of 229 real records carries a tool marker. Exactness needs
  a success-path log in `src/tools.py` — outside the write-set, not claimed.
- **The drill adds ~101 s to the suite** (33.4 s per run), dominated by the
  gateway's retry-and-backoff at 30 s/turn against a closed port. Intrinsic to
  drilling the real gateway; not hacked around, because doing so would have
  violated the retry doctrine.

### Decision 6 proven, not asserted

The drill's live launch row records **REFUSED (whitelisted but requires
confirmation)** in 146 ms. A PID diff across a full run: **73 Chrome processes
before, 73 after, zero new.** Two structural reasons, both commented at the call
site: the drill carries its *own* fail-closed whitelist rather than
`config/whitelist.json`, and it calls the dispatcher with `tools=None`.

### Director's own errors in this milestone — three, all corrected

1. `--amend` swept the whole index and batched the 10 agent roles into the contract
   commit.
2. Item A's commit **silently failed** on PowerShell quoting and its files were
   absorbed into item B's commit — verified by `git show --stat`, undone with
   `reset --soft`, re-committed separately.
3. A heredoc for item C's message split into a string array, so `git commit` took
   the trailing lines as *file paths*.

Directive 1 exists to prevent exactly this, and it happened three times in one
milestone. What caught all three was verifying `git show --stat` after every commit
rather than trusting the exit output. Message files (`git commit -F`) are the fix.

## 10-agent agency swarm + Precision Workflow binding (2026-09-30)

Leader directive: provision a 10-agent swarm, then finalize a dual-console
plan. **Scope actually landed: swarm provisioning + governing contract.**
The dual-console surface is specified but NOT built — refuted premises
below, and the stop condition was not met.

### Contract: Vantrilex-Precision-Workflow is now binding

`Vantrilex-Precision-Workflow` loaded and demonstrably applied this
session. **Material finding: it was not repo-resident.** It existed only
at `~/.config/opencode/skills/` — a user-level path, so it loads for
this machine and for nobody else, and no sub-agent in a fresh checkout
would have it. Vendored byte-identical (hash-verified) to
`.claude/skills/vantrilex-precision-workflow/SKILL.md` and bound as
`CLAUDE.md` §5.1, naming all 7 directives with their one-line tests.
Anti-pattern recorded in-tree: a binding that points outside the repo is
a dangling reference.

`CLAUDE.md:164-165` ("One implementer thread per task — no agent
swarms during implementation", owner-approved) left intact for
*implementation*. §5.1 adds a scope clarification (owner,
2026-09-30): concurrent read-only reconnaissance and review sub-agents
ARE authorized; parallel *writers* are not. That is what was actually
run.

### Swarm provisioned

`msitarzewski/agency-agents` (MIT, pinned `765be423`) fetched by clone.
**9 of 10 roles map to a real upstream persona**, vendored verbatim into
`.claude/agents/agency/` (10 files + LICENSE). `github-ecosystem-miner`
has **no upstream counterpart** — authored locally, says so on its face
rather than borrowing an unrelated persona. 10 Sara-bound role files in
`.claude/agents/`; the 8 pre-existing unrelated agent files left
untouched and untracked.

### Scout runner — and two defects peer review caught

`scripts/launch_parallel_scouts.py` (874 lines) + 41 tests, stdlib-only.
A Python process cannot spawn harness sub-agents, so Group A (the two
internal scouts) are real in-process AST detectors run concurrently on a
`ThreadPoolExecutor`; Group B (web/GitHub) return `deferred_to_harness`
with a dispatch manifest and **zero findings** — a deferred scout never
claims to have scanned anything.

Directive 7 review found two correctness defects in the tool itself:
the tool reported things that were not true.

1. **False positive.** `src/agent_manager.py:247` reported "fans out
   with no obvious bound", but `_trim_lines` at `:152-155` caps the
   iterable at `MAX_LINES` one call upstream. Now `bounded-fanout`, with
   the bound resolved and cited (`:156` → helper at `:246`).
2. **A documented signal that could never fire.** `_is_justified` read
   the handler comment via `ast.unparse(handler)`, and `ast.unparse`
   strips comments — proven: it returns `'except Exception:'`. The
   docstring claimed a handler's own comment marks it deliberate. Now
   reads real source lines via a `tokenize`-based comment map, with
   suppression pragmas stripped. Consequence fixed: `associative.py:194`
   and `:459` are structurally identical handlers and were getting
   opposite verdicts; both now quote their own reason.

Both fixes carry break-runs with injection proof. The second break-run's
first attempt **printed no confirmation line** — the injection had never
landed (PowerShell `\"` is not an escape) — and was re-run with a
pre-flight match assertion. That is Directive 2 catching its own class.

The sub-agent then found **one of its own guards was defective**: the
twin-consistency invariant test passed with the D2 mechanism still
broken, because a non-empty-but-wrong rationale also read "deliberate".
Strengthened to assert each row quotes *its own* comment and not the
twin's; both injection variants now go red.

### Refuted premises — measured, not assumed

- **"Unjustified silent loss" 15 → 0.** All 16 broad `except` handlers
  with a bare `pass`/`return` body in `src/`+`tests/` carry an inline
  rationale that survives pragma-stripping. The 15 were an artifact of
  reading a comment that could never be read. Zero here is a true
  statement, not a broken detector.
- **"46 cataloged capabilities"** → `TOOL_CAPABILITIES` holds **42**.
- **"Laya sub-10ms"** → upstream states **33 ms**, and a checkpoint
  violates `$0.00`. Not adopted as a dependency.
- **"Fish Audio SIP outbound calling"** → `src/skills/live_calls.py` is
  PyTgCalls over Telegram; SIP is a recorded v1.5 deferral, no SIP
  library in any requirements file.
- **`@explore-codebase` / `@explore-architecture`** → the harness
  exposes exactly `explore` and `general`. Roles 7-8 map onto `explore`.
- **"Meter sub-agent queries across the 5+5 Groq/OpenRouter key pools"**
  → harness sub-agents do not route through OmniRoute at all; the pool
  is server-side and invisible from the repo.
- **"CMD REPL HUD"** → a case-insensitive search for `HUD` returns zero
  hits across the whole tree.

### Gate-record defects found (queued, NOT fixed — Directive 1 scope)

- **`check_tiered_coverage.py` is not in `make gate`.** `Makefile:40` is
  `gate: lint test security docs-guard`. `docs/11-TESTING.md:37-42`
  lists coverage inside a checklist headed "every change — `make gate`".
  Documented gate and real gate differ by one step. *Fix the document,
  not the script* — but which side is wrong is the Leader's call.
- **The nine `.claude/hooks/*.json` guards are unarmed.**
  `.claude/settings.json` registers an `Edit|Write` ruff hook and no
  `PreToolUse`; those JSON files are reference configs.
- **`opencode.json` holds a live `sk-or-v1-…` key.** Verified NOT
  tracked, gitignored at `.gitignore:50`, zero commits in history. Not
  leaked. Rotating it is an owner action.
- `pyproject.toml:7` excludes `.claude` from ruff, so no agent
  definition is linted.

## Cross-framework analysis + self-evolution blueprint (2026-09-30)

Leader directive: exhaustive mapping of 24 external resources + a hardened
"Mojito"-pattern self-evolution engine. Deliverable:
`docs/architecture/CROSS_FRAMEWORK_ANALYSIS_AND_SELF_EVOLUTION.md` (~610
lines, docs-only — zero runtime change, zero new packages).

Upstreams fetched and quoted directly: mojito (README, self-rebuild-loop,
SECURITY, CLAUDE), laya, JevRouter, qualixar/jev-decision-layer, HyperAgents,
ScaleMCP (arXiv 2505.06416), ReasoningBank (arXiv 2509.25140 / ICLR 2026).

Central engineering finding — **registering a tool is four edits, not one.**
`ToolRegistry.call` resolves `_do_<tool>` by `getattr` (runtime-bindable) and
`TOOL_CAPABILITIES` is a mutable dict, but `_VALID_TOOLS` (dispatcher) and
`_TOOL_GOALS` (cognition) are `Final` literals. A tool missing from either is
silently unreachable: an unknown name is rewritten to `"none"`
(`dispatcher.py:730`) and `deduce` can never propose it. No exception is
raised. Therefore the roadmap ships an overlay refactor with an EMPTY overlay
(P3-C) before any dynamic tool is enabled (P3-D).

Comparative result: mojito's own `SECURITY.md` admits *"the auto/ask gate is
not enforced in code"* and its `CLAUDE.md` forbids test files — the release
gate is type-check + build. Sara's four gates (own tests, full baseline,
per-module 98% coverage, lint+security) plus a bool-returning
`promotion_decision` with no override path are the whole difference.

Dossier corrections recorded in §8 of the blueprint: (1) laya is a 33 ms
non-autoregressive decision model, not a sub-10 ms ModernBERT classifier —
and a checkpoint is ruled out by $0.00 anyway; (2) Jev's 193.6×/444.6× and
$0.042/M are TypeSafe's published claims, not repo measurements; (3)
`TOOL_CAPABILITIES` holds **42** capabilities, not 46.

Gates: pytest **1,864 passed** / 2 failed / 6 skipped — the 2 are the known
live-pool class (h04 TTFT, h06 dialect), failing on gateway
`empty reply` + `first-token timeout` against a throttled free pool, zero code
regressions. Coverage 91.9% TIERED GATE PASSED. security_gate OK. quality
7/7. docs_guard 16/16. ruff check + format clean (418 files). Also: MOC entry
added to `00-MAP-OF-ARCHITECTURE.md`, CHANGELOG entry added.

Pending owner word, unchanged: MEDIUM/HEAVY `openrouter/`-prefix slug switch
(production file, not applied). Also flagged: 12 tracked docs are deleted in
the working tree, unstaged — `docs/00-MAP-OF-ARCHITECTURE.md` still links to
them. Not restored, not staged; owner's call.

## Pool re-probe under round-robin (2026-09-18, Step 3)

Owner set round-robin + sticky-5 on both providers. Re-probe: FAST 31b
1.6 s TTFT (first sub-SLA sample ever) then 25 s; 26b 44 s — floor
improved, tails persist (high variance across accounts). Bare nex-agi
slugs still 404 (slug form, not pool). Pro streams first time via
`openrouter/` fallback: 6 s, quality Arabic 3-step DAG. Ultra empty;
Lightning ok-but-prose again. VERDICT: improved but not pinnable —
variance too high for FAST pin changes; MEDIUM/HEAVY primaries should
move to `openrouter/`-prefixed slugs (explicit approval requested, NOT
applied). Baselines hold.

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

## nex-agi slug-form re-pin (owner decision 2026-09-30) — supersedes the 2026-09-13 "pool audit"

The 2026-09-13 pool audit above recorded MEDIUM/HEAVY primaries as dead-weight
404s "until the OmniRoute credential is restored". **That premise is refuted and
this entry supersedes it.** The live gateway's `/models` (1,409 models) lists both
`nex-n2.5-mini:free` and `nex-n2.5-pro:free` under the `openrouter/` provider: the
pool was never down and the credential never needed restoring — the BARE
`nex-agi/...` slug form is the wrong *form* and 404s, while `openrouter/nex-agi/...`
routes. Pins re-written in `.env.example` and the live `.env` to
`openrouter/nex-agi/nex-n2.5-mini:free` / `openrouter/nex-agi/nex-n2.5-pro:free`.
Scope: those TWO variables only — fallback chains, escalation model, concurrency
threshold and Tier 1 held still, asserted by `tests/test_env_model_slugs.py`.
The earlier dated entries (incl. the bare-slug 404 observations at :962) are left
intact as the record of what was believed and measured at the time.
`tests/test_omniroute_gateway.py::test_nexagi_404_canary_regression` keeps the bare
slug on purpose — it is this decision's regression witness.

## Radical truth documentation pass (2026-10-01)

A read-only audit swept every markdown file in the repo, verifying each claim against
source by running the tools rather than reading a brief. **47 STALE, 9 UNVERIFIED,
0 confirmed roadmap-marked-as-live.** Zero files were changed by the auditor itself; the
findings were applied by hand and each one is listed below with its evidence.

### The single worst claim, and it was in the README's architecture diagram

`README.md:54` said **`Tier1 fast (reflex, <250ms)`**. It was refuted three times over
by this repository's own artifacts:
- the live probe records **23.5 s – 51.7 s** TTFT on the FAST pool
  (`benchmarks/CANDIDATE_MODELS_PROBE_REPORT.md`)
- the 500-turn benchmark records **2,453.5 ms mean / 3,078.3 ms p95**, with **277 of
  500 turns throttled to no reply at all**
- `docs/AUDIT_REPORT.md:132` is *titled* "the `<250ms` ack target is unreachable"

It was the only sub-second claim in the README, it sat in the diagram a new reader sees
first, and it was the number most likely to make someone believe Sara answers instantly.
Replaced with a measured table: **1.6 s best, 102.1 s worst on the same model on the
same free pool**, drawn from 14 probe samples in the JSONL records.

### Rules that instructed agents to do the wrong thing — the more dangerous class

Stale *numbers* mislead. Stale *instructions* cause damage, because an agent obeys them.

1. **`CLAUDE.md:147` named Edge-TTS `ar-EG-SalmaNeural` as the voice stack**, and
   `:108-110` granted "unconfigured deployments" an Edge carve-out — while
   `src/voice_policy.py:12` **bans `edge_tts` outright** and Edge was purged 2026-09-12.
   That row instructed an agent to wire a module the codebase treats as a banned
   footprint, and the invariant contradicted its own next clause. Both fixed.
2. **`CLAUDE.md:13` and `:36` and `CONTRIBUTING.md:31` demanded "all green".** With the
   P3-D RED barrier committed, an agent obeying those would try to turn 109
   intentionally-failing tests green — precisely the Directive-5 violation, pinning the
   barrier's own bug as correct behaviour. **The RULE was wrong, not just the count.**
   All three now say *no unexplained failure*, and name the RED barrier as legitimate
   and must-not-be-fixed.
3. **`CONTRIBUTING.md:13` mandated the per-stream worktree merge pattern**, which
   `CLAUDE.md:175-177` **retired** as of owner directive 2026-08-31, binding. It
   instructed a retired pattern.
4. **`CLAUDE.md:223-264`** carried a pasted session artifact listing "Agents (1)" and
   "Skills (11)" — contradicting the 10-agent roster documented elsewhere and the ~55
   skills actually available. Left in place pending the owner's call on whether the
   block is still wanted; **flagged, not deleted unilaterally.**

### The owner deploy guide was unreachable by the name 15 files cite

`docs/15-ORACLE-DEPLOY.md` exists. **Seven documents cited `docs/09-ORACLE-DEPLOY.md`** —
a file that does not exist — across `09-DECISIONS`, `10-CHECKPOINT`, `14-RUNBOOK`,
`AUDIT_REPORT`, `HANDOFF`, `OWNER-NEXT-STEPS` and `PROJECT-JOURNEY`. The same class:
`docs/08-OWNER-NEXT-STEPS.md` in four files. **Both renames applied.** A doc the owner is
told to follow during a deploy was not reachable.

### Count corrections, re-derived by script

The audit's numbers disagreed with the brief that commissioned it, and **the tree won on
both**: 2,500 collected (not 2,379), and 109 deliberate-RED (not 107). The brief's 91.9%
was also stale — measured 91.8%. A **fourth** number was surfaced that nothing uses
correctly: **42 catalogued / 46 routed / 46 `_do_*` handlers / 45 claimed**. These are
four different sets; `docs/04-ARCHITECTURE.md` and `PROJECT-CONTEXT.md` say "45 handlers"
and the tool compendium says "46 tools" while naming tools from neither set exactly.

### What the audit found CLEAN — and why that matters more than the rot

- **Zero broken relative markdown links** across 48 in-scope files; all 5 `[[wikilinks]]`
  are legitimate (4 quote the rule, 1 is inside an acceptance criterion).
- **`SECURITY.md` and `docs/00-MAP-OF-TESTING-AND-AUDITS.md`: fully clean.**
- **The dangerous class — roadmap presented as live — is genuinely empty.** No document
  claims SIP telephony, a Laya runtime, or a working self-evolution engine. The SIP
  deferral, the Laya-is-a-pattern verdict, and "P3-C ships empty" are all recorded
  correctly and consistently across five documents.
- **One near-miss worth naming:** `src/skills/self_evolution.py:45 SelfEvolutionWorker`
  IS live and wired (`src/bot.py`, nightly 23:40) — but it proposes **dialect notation**
  into `Dialect_Notes.md` for owner approval. It does **not** synthesize or register tools.
  Writing "self-evolution is operational" without that distinction would have been
  exactly the lie this audit existed to catch. The README now names both explicitly.

**Owner-approved, applied:** the pasted session artifact at the foot of `CLAUDE.md`
("Active Components", `runner=opencode model=inclusionai/ling-3.0-flash-vl:free`, listing
"Agents (1)", "Skills (11)", "Plugins (7)", "Hooks (5)", "MCP Servers (6)") is
**deleted**. It was a snapshot of one session sitting inside the governing contract, and
"Agents (1)" directly contradicted the 10-agent roster in
`docs/architecture/AGENCY_SWARM_WORKFLOW.md`. All five contract sections — Operating
Protocol, System Identity, Invariants, Stack Pins, Commands, Engineering Line — verified
intact after removal. `CLAUDE.md` 238 → 202 lines.

**Deferred by owner:** the remaining ~40 of the 47 STALE findings are count corrections
across `03-TECH-SPEC`, `11-TESTING`, `01-PRD` and four `docs/reports/` files. Deferred to
a dedicated measured cleanup pass rather than rushed here.

**Structural note:** `docs_guard.py` checks *presence only* for 16 canonical files. It
does not police `SECURITY.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, `docs/14-16`,
`docs/00-*`, `docs/architecture/` or `docs/reports/`. **The documentation rot was
concentrated exactly where the gate cannot see it** — which is why this audit was
necessary and why `docs_guard` passing is not evidence of accuracy.

## P3-B shipped — AST gate hardened to 5 rules (2026-09-30)

`verify_proposal_code` no longer early-returns on the first violation. It collects
all violations and joins them with `"; "`, so `open(".env")` yields BOTH
`forbidden call: open` AND `ambient authority: .env` — and a test pins that the
dual reason appears, which is what makes the M6 first-violation-only mutant
catchable.

The two new rules, both genuinely RED before this commit (28 failed / 29 passed /
1 xpassed on the barrier):
- **Ambient authority** — `confirmation_id`, `.env`, `_secrets`, `getattr`,
  `setattr`, `__dict__`, `globals`, `locals` rejected as names, attributes, AND
  string literals, each with `ambient authority: <token>`. A bare `# noqa` is
  not a reason.
- **`importlib` denylist** — `forbidden import: importlib`, checked before the
  allow-list. `from importlib import import_module` + `import_module("os")`
  defeated the `__import__` ban before this commit; the highest-value single
  test in the set proves it no longer does.

**Explicitly not built, by owner-ratified non-goal:** bare `id()` is excluded —
rejecting it would ban an innocent builtin. And non-secret `pathlib` reads
(`Path("notes.txt").read_text()`) are unspecified by design; inventing a
filesystem policy would be a claim nobody measured. The xfail hole-demonstration
(`Path(".env").read_text()` passes structurally) stays demonstrating on both
sides of the fix.

Break-runs, each with printed injection proof and hash-verified restore:
ambient-name dropped → 8 red; ambient-string dropped → 10 red (the xfail
hole-demo passes again, proving the string rule is what closes it);
importlib denylist dropped → 3 red; reason weakened to generic → 8 red.

Coverage: `src/evolution.py` 146 → 169 statements at steady **96%** — +23
statements, zero new misses in the gate code; every new enforcement line is hit
by the 28 gate tests. Residual misses are pre-existing/out-of-scope.

Two doc corrections in the same commit (Directive 7): the §3.3 ambient row went
PROPOSED → three Implemented rows (the old row wrongly listed bare `id`), and
the §6 P3-B "three new rules" count now reconciles with the table. Leftover
staleness outside the write-set, flagged for follow-up: the §3.3 intro "extends
it to five" against a 7-row table, the "honest limits" paragraph still claiming
the `importlib` bypass, and the header "Nothing in §3–§6 is implemented."

Suite: 2,379 passed / 2 failed / 6 skipped / 1 xfailed. The 2 failures are the
live-pool family (h06 + the omniroute live probe, both `GatewayError: all models
exhausted… streamed zero deltas in 4s`); h04 passed this run. Zero code
regressions. Tiered coverage PASSED, security OK, quality 7/7, docs 16/16,
ruff clean.

---

## P3-D shipped — live tool registration, and it still ships EMPTY (2026-10-01)

The RED barrier (`b506315`) went **107 red / 5 green → 115 green / 0 red**, and the
barrier's own claims were correct on every point I could check. Read the numbers as
they were measured, not as the brief stated them: the barrier is **112 tests** across
the two files (29 + 83), **not 112 with 107 red** — measured **107 failed / 5 passed**,
so the brief's "25 red / 4 green" and "82 red / 1 green" were both off by the same
single test in the same direction. The target "107 red → green" is exact; the split
between the two files was not.

**What shipped.** `register_tool(name, markers, handler, *, goals, needs, reversible,
chains_with)` and `unregister_tool(name)` on `src/tool_overlay.py`, writing **SIX**
surfaces or NONE. The brief said five; measurement found a sixth that the four-point
table does not name — the `sara_tool_skills._SKILLS` narration guide, without which a
capability record turns the green guard `test_skill_standard.py:50` red in *whatever
test runs next*, not in the test that registered the tool. That is the sixth point,
and it is the one an implementer working from the four-point table alone would miss.

**The overlay still ships EMPTY, and nothing registers at runtime.** No tool is
registered at import; **no production code path in this repository calls
`register_tool`.** Sara does not autonomously synthesize tools. What shipped is the
all-or-nothing entry point and the guards that hold it honest. Both the
`src/tool_overlay.py` module docstring and §7 of the cross-framework doc were
corrected in the same commit — the old sentence "SHIPS EMPTY. This phase registers
nothing" was true of P3-C and false of P3-D.

**Three seams, closed by measurement, not by assertion:**

- **Seam 1** — the prompt sent at `src/dispatcher.py:868` is now `router_prompt()`, composed
  live. Empty overlay ⇒ **byte-identical** to the `Final` literal (measured `==` against
  the module attribute, not "equivalent"); a registered name is in the prompt the gateway
  actually receives; releasing one tool removes exactly that one line. **Composition, not
  surgery on the literal** — splicing the overlay into `_ROUTER_PROMPT_AR` would move a
  string three other guards pin, and a live read is what makes the release observable at
  all. `src/decision_loop.py:322` sends the same prompt and is on the same seam; it was
  **not** touched and is flagged below.
- **Seam 2** — `ToolRegistry.call(<registered>, arg)` returns the handler's exact reply
  including the echoed argument. `staticmethod(handler)` is load-bearing and was proved it:
  the bound-method mutant returns `TOOL_FAIL_AR` — a tool that is registered and does
  nothing, with no exception anywhere along the way.
- **Seam 3** — `evolution.is_valid_task_name` unions the live overlay **inside** the
  predicate and reads the module global at call time. `_COLLIDING_TOOL_NAMES` comes out
  **byte-identical**; the registration tests assert that surface is unmoved. Ten modules
  read the base registries, and rewriting the snapshot would change their meaning
  mid-suite.

**Owner condition #1, enforced in this commit, not deferred.** `IRREVERSIBLE_TOOLS` is a
`Final` frozenset built at import, so a dynamic tool declaring `reversible=False` would
enter `TOOL_CAPABILITIES` and NOT the deny-list, and every downstream confirmation gate
would miss it — blueprint §3.6's "closed by construction" was a sentence in a document.
Both halves shipped: **R4** refuses `reversible=False` outright, and a **post-condition**
re-checks the whole live registry after the capability write and rolls the registration
back if any non-deny-listed key carries the irreversible flag. The second half is what
makes the claim structural rather than a promise about one function's argument list, and
it has its own guard file (`tests/test_p3d_irreversible_backstop.py`, written RED first).

**Two guards inverted, in `tests/test_tool_overlay.py`, and why.** Both asserted the
router/capability surfaces were *blind to the overlay* — which is the defect, not the law.
`test_router_prompt_constraint_holds_today_and_blind_to_the_overlay` became
`test_router_prompt_constraint_holds_and_now_tracks_the_overlay`, and
`test_capability_constraint_holds_today_and_blind_to_the_overlay` became
`test_capability_constraint_holds_for_every_registered_tool`. Each keeps its intent and
inverts its claim; neither was deleted, and each docstring records what changed and why.
The first did **not** mechanically go red under this implementation — the static literal
is still blind, deliberately — which is stated in the guard rather than left for the next
reader to discover. **Reported, not hidden:** the brief predicted both would go red.

**Measured results** (all re-derived by running the commands, none typed from memory):

| Measurement | Value |
|---|---|
| P3-D barrier files | **115 passed**, 0 failed |
| `tests/test_tool_overlay.py` | **119 passed**, 0 failed |
| Suite excluding the 3 P3-D files | **2,378 passed** / 2 failed / 7 skipped / 1 xfailed |
| Full suite | **2,493 passed** / 2 failed / 7 skipped / 1 xfailed |
| `src/tool_overlay.py` branch coverage | **98.4%** (CORE list, threshold 98.0%) |
| TOTAL branch coverage | **91.9%** (was 91.8%) |
| ruff check / format | clean / clean |
| `security_gate.py` / `docs_guard.py` | OK / 16/16 OK |
| Mutation run | **12 mutants, 12 RED** |

The 2 failures are `tests/live_harness/test_h04_ttft_monitor` and
`test_h06_joda_dialogues` — the pre-existing free-provider-pool flake
(`GatewayError: all models exhausted… streamed zero deltas in 4s`), reproduced on the
baseline before this work started. **Not weakened, not skipped, not touched.**

**Mutation run — every guard proved non-vacuous** (Directive 5; each mutant applied,
run, and reverted from a byte-copy backup):

| Mutant | Guard that went RED |
|---|---|
| M1 drop the R4 refusal | `test_registration_never_makes_a_tool_irreversible` |
| M2 drop the P5 narration guide | `test_registration_keeps_every_capability_covered_by_a_narration_guide` |
| M3 memoise the seam-1 composition | `test_router_prompt_with_an_empty_overlay_is_the_static_base_byte_for_byte` + **3 more**, incl. both per-tool release guards |
| M4 bind the handler as a plain class attribute | `test_registration_point_1_is_reachable_through_tool_registry_call` |
| M5 collision check before the idempotency check | `test_registering_the_same_name_twice_is_a_no_op` |
| M6 collision reads only the capabilities half | `test_registration_refuses_a_name_that_collides_with_a_live_tool[analytics]` |
| M7 drop the irreversible post-condition | `test_an_undenied_irreversible_entry_makes_the_registration_refuse_and_roll_back` |
| M8 `is_valid_task_name` reads only the snapshot | `test_a_registered_name_is_no_longer_a_valid_task_name` |
| M9 write the overlay before the capability record | `test_registration_refuses_and_names_the_point_it_cannot_reach` |
| M10 `reset_overlay` keeps the registrations | `test_router_prompt_sent_to_the_gateway_names_a_registered_overlay_tool` |
| M11 `unregister_tool` clears the whole overlay | `test_two_registered_tools_are_both_named_and_release_one_by_one` |
| M12 R1 accepts a non-snake_case name | `test_a_refused_registration_leaves_no_registration_point_half_populated[R1-bad-shape]` |

M3 was run twice: with `-x` (byte-identity guard first) and without, which is how the
**per-tool** guards were confirmed to catch memoisation independently — four guards red,
not one.

**Holes found, NOT fixed (out of scope, gated on the next item):**

1. **`src/decision_loop.py:322` sends `_ROUTER_PROMPT_AR` directly** — the same seam-1 call
   site, one layer over. A registered tool is unemittable from the decision loop exactly as
   it was from the dispatcher before this commit. **F-1's territory**: the decision loop's
   tool lane, not the router catalog, is the real gate. Not touched.
2. **`register_tool` is the only thing in the tree that can `setattr` `ToolRegistry`,** and
   the P3-B AST gate's `AMBIENT_AUTHORITY_NAMES` does not police it. A registered handler
   could rewrite a *shipped* `_do_*` and hijack the tool lane. The asymmetry is recorded
   in the module docstring rather than fixed.
3. **R3 is unobservable at this boundary, by construction** — the deny-list is a subset of
   both live registries, so R2 refuses all six names first. Kept as an explicit law so a
   future reordering that weakened R2 cannot reopen the tier; the enforceable form is R4.
   Recorded in the barrier's own docstring before this commit, and confirmed here.

---

## Phase 0 — analysis-report programme: catalogue + docs (2026-10-01)

Owner-approved Phase 0. Three work orders, three commits, each RED-first. **F-1's soundness
depends on the outcome of QW-7** — see the explicit statement at the end of this section.

### QW-1 — the MSA "known limitation" was stale

`CHANGELOG.md` announced *"Known limitation — Terminal 1 answers in MSA, not ar-JO"*, naming
the cause as importing `src.persona` being forbidden. Both halves were false: the safety rule
has since been narrowed, and `src/bot_shell.py` binds **exactly one** symbol from
`src.persona` — `build_persona_joda`, the builder — composing it into
`TERMINAL_SYSTEM_PROMPT` at import and into the `system` default of `_live_shell`.
`tests/test_bot_shell_dialect.py` asserts that binding with `ast`, so the entry named as the
cause of a limitation the suite forbids. There is also **no second dialect path**: the builder
composes the byte-locked identity core with the JODA ar-JO few-shot exemplars, so the
terminal and Telegram share one dialect and one masculine-address contract.

Corrected in place — CHANGELOG history is not rewritten, so a reader who remembers the entry
can find where it went. New guard `tests/test_changelog_dialect_claims.py` (4 tests) re-derives
the binding from source and fails only on a *contradiction*: it matches an announced
limitation heading naming the terminal that also makes an MSA claim, never the bare token, so
the two truthful "MSA" entries (G2P tanween, prompt bias) are untouched. Break-verified
in-process against the exact removed entry.

The superseded **OWNER DECISION** section above is struck through and annotated rather than
deleted — it is the record of the question, and its resolution is the mirror of it.

### QW-3 — `src/vault.py`'s docstring contradicted its own loop

The docstring claimed *"409 after one GET->PUT retry"*; the shipped loop is
`for attempt in (1, 2, 3)` — **three** attempts, each a full re-merge (re-read sha, re-run the
caller's `merge`, re-PUT), which the inline comment on that line already stated correctly.
Docstring only; **no behaviour change, retry logic untouched** — the code is the authority
(Directive 6). The corrected text also adds the claim the old one omitted: a 429/403 on a
*read* is retried at most once (`_get_with_rate_limit`), which is the one-retry rule that
actually exists and was presumably what the stale sentence was a garbled memory of.

New guard `tests/test_vault_docstring_conflicts.py` (4 tests) reads the attempt count from the
loop's own integer-tuple literal via `ast`, located by structure — it cannot be satisfied by
rewording, and a refactor makes the guard say so instead of letting the docstring drift. The
re-merge half is checked separately (and derived from the code) because a count-only check
would pass a docstring claiming three attempts of a *stale* re-PUT, a different and wrong law.

### QW-7 — the four routed-but-uncatalogued tools (load-bearing)

**Why Phase 0 and not P2.** `IRREVERSIBLE_TOOLS` is derived from `TOOL_CAPABILITIES`
(`src/skills/capabilities.py`). An uncatalogued tool is therefore not "absent from the
deny-list" — it is **structurally incapable of being in it**. Three of the four had live
`_do_<name>` handlers. `cloud_backup` uploads a Fernet-sealed vault snapshot to Cloud Storage,
and F-1's upcoming irreversible gate would have waved it through unconfirmed because it reads
a set those names are not in.

**Reversibility decisions, with evidence.**

| Tool | Decision | Evidence |
|---|---|---|
| `cloud_backup` | **IRREVERSIBLE** (owner decision) | `_do_cloud_backup` → `GoogleCloudClient.cloud_backup` → an `objects.insert` upload to `b/state-backups/o`. Nothing in the tree deletes the object; an uploaded snapshot cannot be recalled. Honest degradation (unconfigured session → `False`) is not reversal. |
| `analytics` | REVERSIBLE (a read) | `_do_analytics` → `sqlite_life_analytics` over **local** SQLite. No write, no network. Honest limit recorded in the catalog: that function does not exist yet, so the tool degrades to `None` — a read that cannot yet answer is still a read. |
| `quota_safety` | REVERSIBLE (a read) | `_do_quota_safety` → `QuotaGuard.allow` → `free_tier_usage_percent`, a Service Usage API **read**. The breaker only decides whether to proceed. |
| `none` | **Not a tool** | The dispatcher's rewrite target for "no tool selected" and for an unknown router verdict (`src/dispatcher.py:763-765`); no handler. |

`none` gets an explicit machine-visible `INTERNAL_ONLY_TOOLS` marker rather than a capability
record: a record would assert a handler that does not exist and drag a narration guide and an
audit-matrix prompt into existence for a non-tool. The guard resolves the marker lazily by name
so its absence **fails** rather than aborting collection — a bare `ImportError` would mean no
guard in the file is ever seen failing (Directive 2).

**What `test_audit_safety.py:31-32` forced.** The guard asserts
`not (IRREVERSIBLE_TOOLS & LIVE_TOOLS)` — an irreversible tool must not be marked
`LIVE_EXEC`, because that tier fires real backends. **Measured before writing the record:
`cloud_backup` was not in `LIVE_TOOLS`, so nothing was forced.** It was added to `PROMPTS`
only, which places it at the `CONSTRUCT+DEGRADE` tier — a bare-registry call that must answer
honestly and never upload. The guard was **not** weakened; the new audit rows keep the matrix
equal to the catalog (zero exclusions) and the irreversible/LIVE intersection empty.

**Directive 4, unreachability stated in-tree.** None of the three new tools is in
`cognition._TOOL_GOALS`, so `deduce` — which iterates `tool_goals()`, not the catalog — never
scores them, and their new markers do not reach deduction today. They are read by
`markers_for`, which `src/cognition.py:393` unions into `_goal_markers` for any tool that *is*
selectable. Adding `_TOOL_GOALS` entries is a **routing behaviour change** and is deliberately
**not** done here — this phase is catalog + docs. The missing producer is named in the catalog
comment itself, not in a report.

**One guard rewritten, loudly.** `tests/test_tool_overlay.py::
test_capability_registry_is_a_strict_subset_of_valid_tools` asserted the routed-but-
uncatalogued set was exactly `{analytics, cloud_backup, none, quota_safety}`. Read its **name**
against its **assertion**: the name states the law — the registry is a *strict subset* of the
routed set — while the assertion pinned one week's measurement of the gap. It therefore encoded
a snapshot as a law, and enforcing it made the defect permanent (Directive 5: a test that pins
a bug is worse than no test). What survives is the law, now **derived**: the gap must equal
`INTERNAL_ONLY_TOOLS`, and it must stay non-empty. Both neighbouring guards that lean on the
asymmetry (`test_evolution_task.py:264`, `test_p3d_seams.py:693`) still pass. The four-name
literal is gone so that a **fifth** uncatalogued tool fails the completeness guard instead of
being absorbed here.

**Measured, re-derived by script — nothing typed from memory.**

| Measurement | Before | After |
|---|---|---|
| `TOOL_CAPABILITIES` | 42 | **45** |
| `INTERNAL_ONLY_TOOLS` | (absent) | **1** (`none`) |
| `valid_tools()` (routed) | 46 | 46 |
| `IRREVERSIBLE_TOOLS` | 6 | **7** |
| `PROMOTABLE_TOOLS` | 8 | 8 (∩ irreversible = ∅) |
| Routed, uncatalogued, unaccounted | **4** | **0** |
| Executable routed tools outside the catalog | **3** | **0** |
| `PROMPTS` == `TOOL_CAPABILITIES` | 42 == 42 | 45 == 45 |
| Catalogued without a handler / without a guide | 0 / 0 | 0 / 0 |
| tier1_resilience suite | 458 passed | **459 passed** |
| Suite excluding `tests/live_harness` | 2,485 passed / 0 failed | **2,548 passed / 0 failed** |
| TOTAL branch coverage | 91.9% | **91.9%** (gate ≥ 90.0%) |
| ruff check / format | clean / 1 pre-existing | clean / 1 pre-existing |
| `security_gate.py` / `docs_guard.py` | OK / 16/16 | OK / 16/16 |

`ruff format --check` still reports `scripts/attribute_p3d_guards.py` unformatted. That file is
committed and untouched at `d4e4420` — a **pre-existing baseline failure**, outside all three
work orders, reported rather than silently folded into an unrelated commit.

**Mutation run — 4 mutants, 4 RED** (Directive 5; each applied, run, reverted from a
byte-copy backup, and the tree re-verified green after each revert):

| Mutant | Guard(s) that went RED |
|---|---|
| A `cloud_backup` → `reversible: True` | `test_every_external_state_writer_is_deny_listed` |
| B remove the `analytics.md` narration guide | `test_every_catalogued_tool_carries_real_markers_and_a_guide[analytics]` |
| C de-catalogue `analytics` again | `test_every_routed_tool_is_either_catalogued_or_explicitly_internal_only` **+** `test_the_accounting_holds_for_the_EXECUTABLE_routed_names_specifically` |
| D *(extra)* empty `INTERNAL_ONLY_TOOLS` | `test_every_routed_tool_is_either_catalogued_or_explicitly_internal_only` **+** `test_the_internal_only_marker_matches_what_the_dispatcher_rewrites_to` |

A first attempt at mutant B deleted only the tuple's `"analytics.md",` line rather than the
whole entry, which broke the literal and reddened **45** tests. Reported because it is the
honest reading order: the *narrow* mutant is the informative one (1 test, named
`[analytics]`), and the broad one only proves the file fails to import.

### F-1's entry gate now depends on this catalog being complete

**This is the load-bearing statement of the milestone.** F-1's irreversible-action gate reads
`IRREVERSIBLE_TOOLS`, and that set is *derived* from `TOOL_CAPABILITIES`. Before this commit an
executable routed tool could sit outside the catalog entirely and be invisible to the gate by
construction — which is what `cloud_backup` did, uploading a vault snapshot with nothing asked.
The invariant now established and guarded is:

> `IRREVERSIBLE_TOOLS ⊇ {every routed tool whose handler changes external state}`

Today it holds structurally: **zero executable routed tools outside the catalog**, and every
external-state writer is deny-listed. **F-1 may proceed on the basis that the catalog is
complete — and that basis is now an enforced, mutation-tested invariant rather than a claim.**
A future routed tool that omits its capability record will fail
`tests/test_tool_catalog_completeness.py` before it can reach F-1's gate.

### Not started, by instruction

*(As of the QW-7 commit above: F-1, F-2, F-3, F-5, F-6, F-8, 33B and Part E were untouched, and
no file in `src/decision_loop.py`, `src/pc_actions.py`, `src/bot.py`, `src/dispatcher.py`,
`src/tools.py` or `bridge/` was modified — Phase 0 was catalog + docs. F-5 has since landed and
does touch `bridge/`; see the section below.)*

## F-5 — the bridge acceptor's two auth gaps + QW-4 + QW-6

Owner-approved P0 phase 1. Two commits: a RED barrier (`tests/test_bridge_auth_hardening.py`
alone) then the implementation. 18 guards, **14 mutants, 14 RED, 0 survived**, every injection
confirmed landed before its verdict was read.

#### The path gate — `src/bridge_server.py:152-187`

**Measured before writing anything:** `BridgeServer._handler` never read `request.path`, so
`ws://host:PORT/`, `/admin` and `/bridge2` all reached a live tunnel. That is the audit's finding
at `docs/AUDIT_REPORT.md:169`. The gate lives in a `process_request` wrapper that `start()`
installs, **after** the caller's responder — `src/main.py:25-28`'s `/health` returns a Response
and never reaches the gate, which is why a shared port keeps its keep-alive. It cannot live in
the handler: by then the 101 is on the wire and only a close code remains.

**Why 404 and not 403.** A wrong path is not a resource, and a 403 would confirm to a
port-scanner that something *is* mounted on that port. `bridge/server.py:42` already answers 404
for an unknown route, so this is the house answer. It is also the only status that can be
returned at all here — a close code would already be a completed upgrade.

**Owner-approved write-set exception** (recorded per CLAUDE.md §5.1 Directive 7): enforcing one
path cannot coexist with the ten root-dial sites in `tests/test_coverage_gaps_p66a.py` (7),
`tests/test_bridge_protocol.py` (3) and `tests/test_desktop_telemetry.py` (1). All eleven were
retargeted to `/bridge` — **dial URLs only, not one assertion changed**. A permissive default
would have been a fake guard. Production risk is zero and was verified, not assumed: the daemon
dials `BRIDGE_SERVER_URL` verbatim (`bridge/__main__.py:64`) and `.env.example:169` ships
`wss://your-space-host/bridge`. The accepted path is logged at startup *and* on every refusal, so
a deployment whose URL disagrees fails loudly instead of silently.

**No config surface changed.** `bridge_path` is a constructor argument, not an env var or a
settings field, and `src/config.py` was not touched. Stated in the code: nothing in `src/` reads
`BRIDGE_SERVER_URL` — it is a PC-side value this process never receives.

#### The backoff — `src/bridge_server.py:191-247`

Dependency-free, in-memory, bounded. Thresholds, and why they are generous: the regression this
risks is the **owner's** bridge, not the attacker's rate. The daemon redials with capped
exponential backoff, and a rotated `BRIDGE_TOKEN` on the PC produces a steady drip of 4401s that
a tight limit would convert into a self-inflicted outage.

| Threshold | Value | Reasoning |
|---|---|---|
| `AUTH_FAIL_LIMIT` | 20 bad tokens | 20 from one host in 5 minutes is a probe, not a flaky dial |
| `AUTH_FAIL_WINDOW_S` | 300 s | wide enough to span a slow retry loop |
| `AUTH_LOCKOUT_S` | 900 s | outlives the daemon's own backoff, so a transient fault is not re-attempted into a second lock |
| window ≤ lockout | invariant | guarantees the owner's slate is already clean the instant a cooldown lifts, instead of re-locking on the next typo |

Two properties the guards pin rather than assert in prose: a cooldown refuses the **correct**
token too (that is what makes it a cooldown and not a guess-throttle), and a *successful* auth
clears the peer's record so the owner is never one typo from a fresh lockout.

**Bounded, and the bound is asserted on the accounting.** `_peer_auth` is keyed by an
attacker-chosen peer, so it is capped at `AUTH_PEER_CAP = 256` with eviction that forgets the
entry *closest to expiry* — a full dict degrades to dropping stale peers, never new ones, and
eviction can only ever release a cooldown. The refusal sample is separately capped
(`AUTH_LOG_CAP = 64`, bad-token entries at 5, the pre-existing cap). Every refusal is written to
the loguru stream, which is the complete record; the list is the bounded sample. Without that
split, "log every refusal" would itself have been the leak.

**Directive 4, the measured detail that makes the backoff real.** `connection.remote_address` is a
`(host, port)` tuple with an **ephemeral** port (measured, websockets 15.0.1). Keying on the whole
tuple would hand every attempt its own bucket — the counter could never reach its threshold and
the cooldown would be dead code that still reads as a guard. `_peer_key` keys on the host alone,
and mutant `i` re-keys on the tuple to prove the guard notices.

#### QW-6 — the LAN token compare — `bridge/server.py:7,27-33`

`auth != f"Bearer {self.lan_token}"` → `hmac.compare_digest`. **Measured trap:** the `str` overload
of `compare_digest` raises `TypeError` on non-ASCII, and `http.server` decodes headers as
iso-8859-1, so any LAN client can put a non-ASCII byte in `Authorization` and turn a 401 into a
dead request thread. The compare is therefore over **bytes**; mutant `c2` applies the `str`
overload and the 401 guard goes RED.

#### QW-4 — the colliding comment ids

`docs/AUDIT_REPORT.md` owns the numbering: `S-1` executor `open_path`, `S-2` executor
`confirmation_id`, `S-3` the any-path upgrade, `S-6` the app-indexer whitelist. The comments in
`src/bridge_server.py:39,89,91` and `bridge/daemon.py:57` reused those tokens for unrelated
findings, so a grep for a finding landed on the wrong file. They now carry property tags
(`AUTHZ-const-time`, `AUTHZ-log-bounded`, `AUTHZ-plaintext-warn`, `AUTHZ-peer-backoff`,
`PATH`); the new docstring cites `docs/AUDIT_REPORT.md:169` by line anchor instead. Verified by
the work order's own command: `git grep -n "S-2\|S-3" src/bridge_server.py bridge/daemon.py`
→ zero hits, and zero `S-<digit>` anywhere in either file.

#### Two guards that were NOT red before the fix — stated, not hidden

* `test_the_configured_bridge_path_upgrades_and_authenticates` was green precisely *because* any
  path upgraded. It is the guard the fix could break; mutants `a`/`a2` prove it is real.
* `test_the_lan_surface_answers_401_on_a_non_ascii_authorization_header` — `!=` cannot raise, so
  it is green pre-fix by construction. It guards the hazard the fix **introduces**, and mutant
  `c2` is what makes it real.

#### Two of my own defects, found by existing guards and fixed in production, not in the tests

`tests/test_coverage_gaps_p66a.py` went red twice and both times **the test was right**:

1. `len(server.security_log) == 5` became 12 — I had appended each bad token twice, once through
   the legacy cap and once through the new refusal logger. Fixed by giving the logger the call
   site's own sampling decision (`sample=`/`cap=`) instead of double-appending.
2. `any("auth rejected" in line ...)` became false — I had renamed the log vocabulary. Reverted to
   the original entry strings; **no existing assertion was touched anywhere in this item.**

Also found and repaired in my own instrument: the mutation driver used `Path.write_text`, which
applies Windows newline translation, so its *restore* rewrote `bridge/server.py` whole (a 9-line
diff reported as 168). The driver now reads and writes **bytes** and detects the file's own line
ending. It also caught its own stale anchor and refused to report a mutant rather than measuring
nothing.

#### Measured, re-derived by script

| Measurement | Before (HEAD `aba16e7`) | After |
|---|---|---|
| `tests/test_bridge_auth_hardening.py` | absent | **18 guards, all green** |
| Suite excluding `tests/live_harness` | 2,547 passed / 5 skipped | **2,566 passed / 4 skipped / 1 xfailed / 0 failed** |
| Collected (same suite) | 2,552 | **2,570** (= +18, the new guards) |
| `src/bridge_server.py` coverage | 92% | **95%** |
| TOTAL branch coverage | 91.9% | **91.9%** (gate ≥ 90.0%) |
| `TOOL_CAPABILITIES` / `IRREVERSIBLE_TOOLS` / routed / unaccounted | 45 / 7 / 46 / 0 | **45 / 7 / 46 / 0** |
| ruff check / format | clean / clean | **clean / clean** |
| `security_gate.py` / `docs_guard.py` | OK / 16/16 | **OK / 16/16** |

The pass/skip difference against the work order's stated 2,548/4 baseline is **not** a code
difference: my own pre-change run measured 2,547/5, and 2,548 + 18 = 2,566 exactly. The one test
that differed is network-dependent (`tier2_live_probes/test_omniroute.py` free-provider pool, or
`live_probe/test_bridge_live.py` against an offline core). The 2 `live_harness` failures
(`test_h04_ttft_monitor`, `test_h06_joda_dialogues`) are the pre-existing free-provider flakes;
they were not weakened, skipped or re-scoped.

#### Mutation run — 14 mutants, 14 RED

| Mutant | Guard that went RED |
|---|---|
| a remove the path gate | `test_upgrade_on_the_root_path_is_refused_with_404` |
| a2 path gate loosened to a prefix match | `test_upgrade_on_an_arbitrary_path_is_refused_with_404` |
| b remove the cooldown refusal | `test_the_lockout_refuses_even_the_correct_token` |
| b2 never record a failure (counter inert) | `test_a_burst_of_bad_tokens_locks_the_peer_out` |
| c revert the LAN compare to `!=` | `test_the_lan_token_compare_is_constant_time` |
| c2 LAN compare over `str` (the TypeError trap) | `test_the_lan_surface_answers_401_on_a_non_ascii_authorization_header` |
| d unbounded peer tracking dict | `test_peer_auth_state_is_bounded_however_many_distinct_peers_appear` |
| d2 unbounded refusal sample | `test_cooldown_refusals_cannot_grow_the_security_log_without_bound` |
| e a successful auth does not clear the record | `test_a_successful_auth_clears_the_peer_backoff_record` |
| f renumber the S-comments back | `test_audit_finding_ids_do_not_collide_with_the_comments_in_the_auth_paths` |
| g tighten the thresholds into a lockout footgun | `test_shipped_auth_thresholds_are_generous_enough_not_to_lock_out_a_flaky_owner` |
| h the gate swallows the shared `/health` surface | `test_a_caller_supplied_health_responder_still_answers_before_the_gate` |
| i key the peer bucket on the whole address tuple | `test_the_peer_bucket_key_is_the_host_alone` |
| j drop the 4400 non-Hello refusal arm | `test_a_valid_non_hello_first_frame_is_refused_and_logged` |

#### Still open, deliberately not folded in

`docs/AUDIT_REPORT.md:159` (V-9) has a second half — the in-memory `security_log` is still
**unbounded for the non-bad-token paths** (`/health` responder aborts, session teardown). F-5 caps
every path it *added*; capping the pre-existing ones is a separate item and would move assertions
in tests outside this write-set. Also open: the `ws://` plaintext-dial warning on the daemon side
is informational only, and TLS remains Caddy's job per `docs/09-DECISIONS.md` §7.

## F-3 — the `open_path` holes (S-1): containment, the double-click set, the discarded id

Owner-approved P0 phase 2. Two commits: a RED barrier (`tests/test_open_path_containment_f3.py`
plus the AC6 extension) then the implementation. **42 guards, 19 mutants, 19 RED, 0 survived.**

Report §43 is at `Sara Agent - Full Analysis Report/part-f-errors.md:152` (a gitignored reading
copy, not committed). Every `file:line` it gives was re-measured against the tree; the file wins
where they disagree, and two of them did (below).

#### The report's containment draft was a NO-OP — re-scoped, not built as written

§43 step 2 says to "reuse the `_require_roots` semantics from `:357`". Measured, `_require_roots`
(`bridge/executor.py:355-357` pre-change) is:

```python
if not self._file_roots:
    return ExecResult(status="error", detail="file roots not configured", ...)
```

It asserts that roots are **CONFIGURED**. It never inspects the path, and it returns `None` —
which reads as *admitted* — so the draft taken literally leaves the hole exactly as wide while a
comment claims it closed. Re-scoped per Directive 3: the real mechanism is component-wise
containment, and the shipped version is `_under()` + an explicit per-path check, not
`resolve_in_roots`.

**`resolve_in_roots` was measured and was not sufficient on its own.** It is where the containment
lives for `file_download`, so fixing it fixed that path too, and the same fix is what makes
`open_path` sound. Its predicate was `str(resolved).startswith(str(base_resolved))` — a **string**
prefix, so `Downloads-evil` passed as "inside" `Downloads`. It is now `Path.relative_to`
(`bridge/executor.py:_under`), which is component-wise and still case-insensitive on Windows.
The prefix hole was a live hole in `file_download`, not a theoretical one.

#### The suffix set failed to match its own comment

The comment above `OPEN_BLOCKED_SUFFIXES` already said the rule — *"double-click equivalents:
opening one of these IS launching it"* — and the set did not implement it. Added: `.lnk` (runs its
target), `.url` (navigates to an attacker-chosen page), `.jar` (executes), `.hta`/`.html`/`.htm`
(run script), `.wsf`/`.wsh` (Windows Script Host). `.htm` is a byte-for-byte alias of `.html`;
omitting it would re-open the same hole through the other spelling. The original nine are still
there, and `test_blocked_set_is_a_superset_of_the_pre_f3_set` holds the pre-F-3 nine as a
**literal in the test file**, so a future edit cannot drop one silently.

**The refusal is not a dead end, per the report's regression risk (a).** The owner legitimately
opens `.url` shortcuts and jars. The message now names the suffix, the reason (*"IS launching
it"*), and the route that works (*"launch the app by name (or add it to `config/whitelist.json`)
instead"*). `src/tools.py:_do_open_path` returns the executor's `detail` to the owner verbatim, so
this text is what they actually read. A guard asserts the containment wall and the suffix wall do
**not** share copy — the first draft of that guard was blind, because grepping one keyword could
not tell which wall fired (measured; see the mutation table `f3`).

#### `confirmation_id`: stopped being discarded, honestly

`del confirmation_id` is gone. The id is kept for wire symmetry with launch/close/power and is
**not** a bypass — no id value moves a path past any wall, and two guards pin both directions: an
id neither helps (`is_not_a_bypass`) nor gates a legitimate open
(`does_not_gate_a_legitimate_open`; mutant `e2` demands an id for every open and turns it RED).

**The situation is made honest, not papered over:** `open_path` does not *require* a
confirmation, and the docstring says so plainly. Whether an id is *valid* is F-2's work (the
executor-wide verifier); implementing it here would duplicate and then collide with F-2. The
pre-F-3 comment (`open_path is never auto-approved past these checks`) was true but was attached
to a `del`, which is the one thing that made it read as a dropped confirmation.

#### The roots design — a constructor argument, and a new knob the owner should know about

**`open_roots=` on the `Executor` constructor is a new configuration surface.** Following F-5's
`bridge_path` precedent it is a constructor argument, **not** an env var and not a settings field,
and `src/config.py` was not touched. The seed (`default_open_roots()`) is home + the repo this
bridge ships from + the process CWD — the last because `data/inbox` is itself CWD-relative. It is
never the home's **parent**: `C:/Users` would "reach the home" while admitting every other profile
on the box, which is a containment failure dressed as convenience. `DEFAULT_FILE_ROOTS` is
**not** reused — it is Downloads-only, so reusing it would confine every open to Downloads and
break the verb for the whole project (mutant `c6`).

Semantics of the knob: omit it → the seed applies. Pass `()` → **nothing opens** (fail-closed, never
"the wall is off"). `bridge/__main__.py:68` does not pass it today, so the shipped daemon runs on
the seed; wiring an explicit set there is a one-line change the owner may want.

#### `file:line` audit against §43's claims

| §43 claim | Tree | Verdict |
|---|---|---|
| `OPEN_BLOCKED_SUFFIXES` at `:98` | `:98` | matches |
| `del confirmation_id` at `:315-317` | `:317` | matches |
| UNC/traversal/suffix walls at `:320-357` | `:319-337` | matches |
| `_require_roots` at `:357` | `:355-357` | matches — and is the no-op, as measured above |
| `resolve_in_roots` used by `file_download` at `:391` | `:391` | matches |
| AC6 at `tests/test_whitelist_guardrail.py:183-196` | **`:182-197`, and the file is `tests/test_whitelist_guardrail.py` — NOT `tests/suite/tier1_resilience/`** | **moved + path wrong** |
| `src/tools.py:592-611` sends `exec.open` | `:592-611` | matches |
| `bridge/daemon.py:178-182` routes it | `:178-183` | matches (+1 line, F-5 drift) |

The work order and the report both place the AC6 test under `tests/suite/tier1_resilience/`. There
is no such file; the test is `tests/test_whitelist_guardrail.py`. The report is otherwise accurate
about the executor.

**Not done here, and it is not a silent skip:** §43 step 4 asks for the
`src/tools.py:596-597` comment (*"this lane adds no checks of its own"*) to be updated to describe
the post-fix contract. `src/tools.py` is outside this write-set. The comment is now **stale in
substance but not false** — the lane still adds no checks of its own, and the daemon's walls are
still authoritative; it simply no longer enumerates them exhaustively. F-2 or a docs pass should
name the containment wall there.

#### Directive 5 — one test repaired, and the write-set exceeded on purpose

`tests/test_coverage_gaps_p63c.py::test_open_path_walls_and_open` asserted **the hole**: it built an
`Executor` with no roots and then *required* `C:\Users\note.txt` to open. Name and assertion
disagree, so the test is what moved (Directive 5) — **the fix was not reverted to keep it green**.
This exceeds the stated write-set, recorded per Directive 7; the AC6 test in
`tests/test_whitelist_guardrail.py` was extended, never weakened, and no other file outside the
sanctioned set is touched.

#### Mutation run — 19 mutants, 19 RED, 0 survived

| Mutant | Guard that went RED |
|---|---|
| a containment reverted to a config-only check | `test_absolute_path_outside_every_root_is_refused` |
| a2 restore the string-prefix predicate (`Downloads-evil` hole) | `test_sibling_directory_sharing_the_root_name_is_refused` |
| b remove all eight added suffixes | `test_double_click_equivalents_never_open` |
| b2 drop only `.url` (the owner's own regression risk) | `test_double_click_equivalents_never_open` |
| c drop the empty-roots refusal (wall off when unconfigured) | `test_no_open_roots_configured_fails_closed` |
| c2 the report's draft: substitute `_require_roots` semantics | `test_absolute_path_outside_every_root_is_refused` |
| c3 reuse `DEFAULT_FILE_ROOTS` (the over-blocking bug) | `test_executor_seed_reaches_the_owner_home_and_the_project` |
| c4 re-home a bare relative name into the FIRST root (decoy swap) | `test_relative_bare_name_resolves_against_the_process_cwd` |
| c5 seed the roots with the home's PARENT | `test_default_open_roots_are_deduplicated_and_dont_include_user_profile` |
| c6 seed the roots with Downloads only (draft, over-blocking) | `test_executor_seed_reaches_the_owner_home_and_the_project` |
| d restore `del confirmation_id` | `test_open_path_never_deletes_its_confirmation_id` |
| e let a `confirmation_id` bypass the suffix wall | `test_confirmation_id_is_not_a_bypass` |
| e2 **demand** a `confirmation_id` for every open | `test_confirmation_id_does_not_gate_a_legitimate_open` |
| f bare `error:` suffix refusal (dead end) | `test_suffix_refusal_names_the_reason_and_the_working_route` |
| f2 name the whitelist but not the file | `test_suffix_refusal_names_the_reason_and_the_working_route` |
| f3 reuse the suffix copy for the containment wall | `test_containment_refusal_is_distinguishable_from_the_suffix_refusal` |
| g2 drop the relative-branch `OSError` arm in `resolve_in_roots` | `test_resolve_in_roots_refuses_when_the_relative_resolve_raises` |
| g let an unresolvable path reach `os.startfile` unvalidated | `test_unresolvable_path_fails_closed_without_raising` |
| h accept an empty path | `test_empty_path_is_refused_by_the_empty_wall_not_by_containment` |

**Six of these 18 guards were BLIND on the first mutation pass and were repaired — the guards, not
the production code.** Named, because a guard that has never been seen to fail is not a guard:

1. `test_no_open_roots_configured_fails_closed` passed a mutant that removed the empty-roots branch
   entirely, because the per-path `any()` over an empty tuple refuses anyway. Now asserts the
   message (`not configured`), which is what the core maps to Arabic.
2. `test_default_open_roots_reach_the_owner_home_and_the_project` asserted the *helper*;
   `c3` swapped the constructor's default and left the helper correct. Added
   `test_executor_seed_reaches_the_owner_home_and_the_project`, which reads the Executor's own
   roots and then exercises the verb.
3. `test_relative_bare_name_resolves_against_the_process_cwd` had no decoy, so "resolve against
   CWD" and "resolve against `root[0]`" were indistinguishable. A decoy of the same name now sits
   in the first root.
4. `test_confirmation_id_is_not_a_bypass` put the `.exe` **outside** the roots, where containment
   refuses it either way. The payload moved inside so the suffix wall is the only thing that can
   be speaking.
5. `test_suffix_refusal_names_the_reason_and_the_working_route` grepped `whitelist` in `detail` —
   which the containment message also contains, so a mangled suffix message sailed through. Each
   clause is now pinned to an exact phrase.
6. `test_empty_path_is_refused` passed a mutant that dropped the empty check, because `Path("")`
   resolves to the CWD and containment refused it. Now asserts the empty-wall message.

The mutation driver honours the F-5 lesson: it reads and writes **bytes** (never
`Path.write_text`, so Windows newline translation cannot rewrite the file on restore), verifies
every restore by sha256, and **refuses to report a mutant whose anchor is not unique** rather than
measuring nothing. All 18 restores verified byte-exact.

#### Not red before the fix — stated plainly

* `test_absolute_path_inside_a_root_is_admitted`,
  `test_every_configured_root_is_reachable` and
  `test_open_roots_constructor_argument_overrides_the_seed` assert the fix does **not** over-block.
  They were green pre-fix (nothing was contained) and go RED if containment is built wrongly.
  That is their job: they are the guards a containment fix breaks first.
* `test_open_path_documents_the_confirmation_contract` is green pre-fix by construction — it pins a
  policy that the pre-fix code did not state. `d` is what makes it real.
* `test_confirmation_id_does_not_gate_a_legitimate_open` guards the hazard the fix **introduces**
  (a well-meaning "require confirmation" fix), same shape as F-5's QW-6 guard.

#### Measured, re-derived by script

| Measurement | Before (HEAD `61b9228`) | After |
|---|---|---|
| `tests/test_open_path_containment_f3.py` | absent | **42 guards, all green** |
| `OPEN_BLOCKED_SUFFIXES` | 9 | **17** |
| Suite excluding `live_harness`/`live_probe` | 2,560 passed / 2 skipped / 1 xfailed | **2,601 passed / 2–3 skipped / 1 xfailed / 0 failed** |
| `bridge/executor.py` coverage | 98.5% | **98.7%** (gate ≥ 98.0%) |
| TOTAL branch coverage | 91.9% | **92.0%** (gate ≥ 90.0%) |
| ruff check / format | clean / clean | **clean / clean** |

`IRREVERSIBLE_TOOLS` 7 · `TOOL_CAPABILITIES` 45 · routed 46 · `INTERNAL_ONLY_TOOLS {"none"}` —
all unchanged, verified by `scripts/security_gate.py`. F-3 touches no tool registry, no dispatcher
and no capability entry, which is why the census is identical.

The count wobbles by one between runs because a **network-dependent** test is sometimes skipped
(`tier2_live_probes/test_omniroute.py` free-provider pool, `live_probe/test_bridge_live.py`
against an offline core) — it is reported separately from passes and was never skipped or weakened
to make a number look right. Both exclusion shapes, re-derived from the tree:

| Command | Result |
|---|---|
| `--ignore=tests/live_harness` (the work order's exact command) | **2,607 passed / 5 skipped / 1 xfailed / 0 failed** |
| `--ignore=tests/live_harness --ignore=tests/live_probe` | **2,601 passed / 2–3 skipped / 1 xfailed / 0 failed** |

Against the work order's stated 2,566 baseline the first row is **+41** (2,566 + 42 new guards
− the repairs) and the second **+35**: the 2,566 figure was measured with `live_probe` **included**,
so the two rows are not directly comparable and only the first is. The 2 `live_harness` failures
seen in the coverage run remain the pre-existing free-provider flakes.

#### Still open, deliberately not folded in

The `src/tools.py:596-597` comment (above). V-9 (`security_log` unbounded on non-bad-token
paths) is out of scope per the work order. F-2 — the executor-wide confirmation verifier — is the
next work order and is **gated on the owner's review of this entry**; `open_path` deliberately does
not pre-empt it.

- [07 — Implementation Plan](./07-IMPLEMENTATION-PLAN.md)
- [11 — Testing](./11-TESTING.md)
- [Objectives Ledger](./reports/OBJECTIVES_LEDGER_MET_VS_PENDING.md)
- [Master Transformation Plan](./MASTER_SYSTEM_TRANSFORMATION_AND_EXECUTION_PLAN.md)
- [System & Codebase Encyclopedia](./reports/SARA_EXHAUSTIVE_SYSTEM_AND_CODEBASE_ENCYCLOPEDIA.md)
- [Map of Testing & Audits](./00-MAP-OF-TESTING-AND-AUDITS.md)
