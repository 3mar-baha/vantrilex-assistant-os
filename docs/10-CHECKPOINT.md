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

## Sprint 4 — Syllabus parser, expansion, tutor, hardening & release — QUEUED

- **Skills to ingest**: `guard-skills/docs-guard` · `guard-skills/test-guard` ·
  `universal-agentic-os/skills/github-release-packager.md` ·
  `universal-agentic-os/skills/circuit-breaker-guard.md`
- **Teardown**: final production release packaging (v1.0.0) — recorded here at release.
