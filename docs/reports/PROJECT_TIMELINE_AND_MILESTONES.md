---
tags: [decision]
---

# Project Timeline & Milestones (2026-08-26 → 2026-09-16)

> Executive summary: 22 days from scaffold to a hardened, fully-tested
> sovereign assistant. Four sprints, three releases, two host pivots, one
> voice-engine purge — every step committed to `main` with a green suite.
> Appendix: tag and origin ledger.

## Milestone table

| Date | Milestone | Evidence |
|---|---|---|
| 2026-08-26 | Scaffold + Phase-2 sprint specs (Guide-reviewed) | `ff2542b`, `6fa22f7`; suite 45 green |
| 2026-08-29 | Sprint 1: gateway, voice, dialect, 3-tier brain + dispatcher | `fe4e5ca`; 45 tests; teardown executed |
| 2026-08-30 | Sprint 2: Telegram shell, Google suite, triage, brief, biometrics | 150 tests; branch merged to `main` |
| 2026-08-31 | Sprint 3 (vault + PC bridge + whitelist) + Sprint 4 (tutor, hardening) | 285 tests, 85.6% branch |
| 2026-08-31 | **v1.0.0 tagged** + Oracle Cloud pivot (HF Spaces went paid) | tag `v1.0.0`; ADR-15 amendment |
| 2026-08-31 | **v1.0.1** (Node 24 gateway layer) | tag `v1.0.1` |
| 2026-09-01 | **v1.0.2** (app indexer + auto-logon) + two-strong-model refactor + memory lanes | tag `v1.0.2`; 334 tests |
| 2026-09-02/03 | Forensic audit (43 agents) → 9-step Phase-1 remediation | `docs/AUDIT_REPORT.md`; 417 tests |
| 2026-09-03 | Fish-only voice ruling; biometric threshold 0.60; reply-modality | 447–468 tests |
| 2026-09-05 | Live-defect wave (aliases, UWP images, basename guard) | `test_live_defects_2026_09_05.py` |
| 2026-09-12 | Edge-TTS purge from chain; Stage-2 simulation hardening | voice modules |
| 2026-09-14 | RAG durability (mirror, vault scaffolding), roadmap decoupling | `08-ROADMAP.md` as sole future-home |
| 2026-09-16 | Benchmark 6/6 + invariants; graph MOCs; archive; 16-WORKFLOWS; API/tool audits | 1,460 tests, ruff clean |

## Suite-size evolution

45 → 66 → 108 → 150 → 228 → 285 → 334 → 417 → 474 → 1,457 → 1,460 (today).

## Appendix — tags and HEAD

- Tags: `v1.0.0` (2026-08-31) · `v1.0.1` (2026-08-31) · `v1.0.2` (2026-09-01)
- HEAD: `main`, branch-directive (all commits direct, push immediately) since 2026-08-31
- Full per-commit history: `git log --oneline`

## See also (graph links)

- [Project journey](../PROJECT-JOURNEY.md) · [Timeline](../TIMELINE.md)
- [10 — Checkpoint](../10-CHECKPOINT.md) · [Objectives Ledger](./OBJECTIVES_LEDGER_MET_VS_PENDING.md)
- [Map of Architecture](../00-MAP-OF-ARCHITECTURE.md)
