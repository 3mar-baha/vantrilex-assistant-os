# Changelog

All notable changes to this project are documented in this file.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning targets [Semantic Versioning](https://semver.org/) starting at v1.0.0.
("v1.1.0" in project branding names the Universal Agentic OS framework Sara is built on;
product release tags start independently at v1.0.0.)

## [Unreleased]

### Changed
- Documentation consolidation (ADR-14): 22 docx drafts retired from the working tree
  (21 recoverable via git history; 1 via .ingest text); zero-tolerance persona naming
  enforced across all records; Future Scope parked without version numbers (PC Health
  Monitor, Voice Read-It-Later, Emotional Context Memory, Silent Vault Backup,
  on-demand YouTube/Weather/Maps APIs — per-request, free-tier, $0 preserved).

### Added
- **Sprint 1 / task 1.2 — OmniRoute client** (`src/gateway.py`): OpenAI-compatible SSE
  streaming as async text-delta iterator; PRIMARY->FAST model fallback; free-pool survival
  (quota -> immediate fallback, transient -> capped-backoff retries, fatal -> loud stop);
  mid-stream failures never restart a partially-yielded reply; missing-[DONE] guard.
- **Sprint 1 / task 1.1 — project skeleton**: async `src/` package with pydantic v2
  `Settings` validating `.env` (fail-fast on the six critical vars, empty-string→unset
  normalization), one-sink loguru setup, ops health probe (`python -m src.main --health`),
  and the async entrypoint behind `make run-core`.
- Socratic discovery record and confirmed mission statement (persona: Sara سارة).
- Canonical documentation scaffold: CLAUDE.md, README, LICENSE, CONTRIBUTING,
  CHANGELOG, SECURITY, Makefile, CI workflow, and docs/00–05.
- **Phase 2 implementation specifications** (`docs/specs/sprint-{1..4}.md`): per-task
  interfaces, behaviors, testable acceptance criteria mapped to pytest targets,
  error modes, zero-cost checks — drafted by parallel agents and adversarially
  verified (Guide pass); every finding integrated with disposition appendix.
- Session-resume protocol baked into CLAUDE.md + checkpoint file.
- Native stage-gate hooks (`.claude/hooks/`) and resumable phase state
  (`.claude/PHASE-STATE.md`).
- Credential manifest (`.env.example`) covering core (VPS) and bridge (PC) processes.
- Source-of-record planning drafts preserved as `docs/*.docx` (to be superseded by
  markdown specifications during Phase 2).

### Deferred to v1.1
- Live bidirectional Telegram voice calls (PyTgCalls WebRTC engine).
- tech-hardware-scout and career-project-incubator proactive skills.
- Mem0/Firestore persistent memory layer.

## [1.0.0] — Planned
First tagged release: Telegram chat + Ogg Opus voice notes, OmniRoute free-pool
reasoning, Google Workspace integration with tiered email triage, git-backed
Obsidian knowledge vault, whitelisted PC control over an outbound-only bridge.
