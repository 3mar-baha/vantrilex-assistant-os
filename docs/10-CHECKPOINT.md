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

## Sprint 1 — Foundation (gateway + voice + dialect + dispatcher) — IN PROGRESS

- **Skills ingested**: `mattpocock-skills/skills/tdd` · `mattpocock-skills/skills/diagnosing-bugs`
  · `ponytail/skills/*` · `guard-skills/clean-code-guard` · `everything-claude-code/agents/python-specialist`
- **Deliverables so far**: task 1.1 skeleton (merged to main, `221c650`) · task 1.2 gateway
  + SSE hardening (`3e44f1c`, live-wired) · task 1.3 voice pipeline (`4d0aefa`) · docs
  overhaul commits (`71a17ca`, `fef6246`, `0e796fd`) · task 1.4 dialect engine M1
  (`src/dialect.py`, 3/3 ACs)
- **Remaining**: 1.5 (3-tier brain + front-door dispatcher)
- **Teardown**: pending sprint exit — wipe `.claude/skills/*`, verify sacred floor green,
  record outcome here.

## Sprint 2 — Telegram suite, biometrics, triage, logs — QUEUED

- **Skills to ingest**: `mattpocock-skills/skills/tdd` · `guard-skills/clean-code-guard` ·
  `everything-claude-code/agents/api-integrator`
- **Teardown**: clean session skills, update checkpoint.

## Sprint 3 — Vault, PC bridge, whitelist — QUEUED

- **Skills to ingest**: `mattpocock-skills/skills/tdd` · `mattpocock-skills/skills/git-guardrails` ·
  `guard-skills/test-guard` · `everything-claude-code/agents/systems-architect`
- **Teardown**: clean session skills, update checkpoint.

## Sprint 4 — Syllabus parser, expansion, tutor, hardening & release — QUEUED

- **Skills to ingest**: `guard-skills/docs-guard` · `guard-skills/test-guard` ·
  `universal-agentic-os/skills/github-release-packager.md` ·
  `universal-agentic-os/skills/circuit-breaker-guard.md`
- **Teardown**: final production release packaging (v1.0.0) — recorded here at release.
