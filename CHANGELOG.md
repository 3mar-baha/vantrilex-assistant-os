# Changelog

All notable changes to this project are documented in this file.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
versioning targets [Semantic Versioning](https://semver.org/) starting at v1.0.0.
("v1.1.0" in project branding names the Universal Agentic OS framework Sara is built on;
product release tags start independently at v1.0.0.)

## [Unreleased]

### Added
- Socratic discovery record and confirmed mission statement (persona: Sara سارة).
- Canonical documentation scaffold: CLAUDE.md, README, LICENSE, CONTRIBUTING,
  CHANGELOG, SECURITY, Makefile, CI workflow, and docs/00–05.
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
