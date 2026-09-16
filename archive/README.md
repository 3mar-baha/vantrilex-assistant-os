---
tags: [testing]
---

# Archive Manifest — non-destructive consolidation (2026-09-16)

> Every file below was **moved with history preserved** (`git mv` → rename
> status `R`), never deleted. To restore any file: run its reversibility
> command, then `git commit`. Nothing here is imported, executed, or gated:
> `supervise.py` stays in `scripts/` (`test_packaging.py` imports it),
> `tests/reports/` stays (the shadow-tracer harness writes there at runtime).

| Original Path | Relocated Path | Date Archived | Rationale | Reversibility Command |
|---|---|---|---|---|
| `EXECUTIVE_PROGRESS_REPORT_2026_09_06.md` | `archive/reports/EXECUTIVE_PROGRESS_REPORT_2026_09_06.md` | 2026-09-16 | One-off progress snapshot; root stays entry-point-only | `git mv archive/reports/EXECUTIVE_PROGRESS_REPORT_2026_09_06.md ./` |
| `NIGHT_RUN_REPORT.md` | `archive/reports/NIGHT_RUN_REPORT.md` | 2026-09-16 | One-off night-run notes | `git mv archive/reports/NIGHT_RUN_REPORT.md ./` |
| `MANUAL_TEST_CHECKLIST_2026_09_06.md` | `archive/reports/MANUAL_TEST_CHECKLIST_2026_09_06.md` | 2026-09-16 | Dated manual checklist, superseded by suite | `git mv archive/reports/MANUAL_TEST_CHECKLIST_2026_09_06.md ./` |
| `AUDIT_AND_PLAN_40_FEATURES.md` | `archive/reports/AUDIT_AND_PLAN_40_FEATURES.md` | 2026-09-16 | 78-feature audit; B1–B8 backlog fully wired since | `git mv archive/reports/AUDIT_AND_PLAN_40_FEATURES.md ./` |
| `PROJECT_IDEAS_COMPENDIUM.md` | `archive/reports/PROJECT_IDEAS_COMPENDIUM.md` | 2026-09-16 | Idea backlog; planned work lives in `docs/08-ROADMAP.md` | `git mv archive/reports/PROJECT_IDEAS_COMPENDIUM.md ./` |
| `run_live_probe.py` | `archive/scratch_scripts/run_live_probe.py` | 2026-09-16 | Root-level probe entry; no importers | `git mv archive/scratch_scripts/run_live_probe.py ./` |
| `scripts/joda_distill.py` | `archive/scratch_scripts/joda_distill.py` | 2026-09-16 | One-off distill spike; zero importers | `git mv archive/scratch_scripts/joda_distill.py scripts/` |
| `scripts/groq_persona_probe.py` | `archive/scratch_scripts/groq_persona_probe.py` | 2026-09-16 | Bake-off probe; referenced in comments only | `git mv archive/scratch_scripts/groq_persona_probe.py scripts/` |
| `scripts/fish_calibration_spike.py` | `archive/scratch_scripts/fish_calibration_spike.py` | 2026-09-16 | Calibration spike; findings live in `tests/reports/` | `git mv archive/scratch_scripts/fish_calibration_spike.py scripts/` |
| `scripts/cognitive_shadow_observer.py` | `archive/scratch_scripts/cognitive_shadow_observer.py` | 2026-09-16 | Observer spike; zero importers | `git mv archive/scratch_scripts/cognitive_shadow_observer.py scripts/` |
| `scripts/joda_schema_probe.py` | `archive/scratch_scripts/joda_schema_probe.py` | 2026-09-16 | Schema probe; zero importers | `git mv archive/scratch_scripts/joda_schema_probe.py scripts/` |
| `versions/release-v1.1-pass1/CHANGELOG.md` … `versions/release-v2.0-pass5/CHANGELOG.md` (×10) | `archive/legacy_versions/versions/…` (same tree) | 2026-09-16 | Generated snapshots; root `CHANGELOG.md` + tags are canonical | `git mv archive/legacy_versions/versions ./` |
| `compile.txt`, `ruff_out.txt` | `archive/ephemera/` (untracked, gitignored) | 2026-09-16 | Ephemeral tool dumps; never committed | `mv archive/ephemera/<f> ./` (stays ignored) |

## Deliberately NOT archived (load-bearing — do not move without a new audit)

- `scripts/supervise.py` — imported by `tests/test_packaging.py`; Dockerfile CMD + `.dockerignore` assertions pin its path.
- `tests/reports/*` — `tests/suite/tier3_shadow_tracer/audit_harness.py` writes `FULL_SYSTEM_EXHAUSTIVE_AUDIT.md` + `audit_records.jsonl` there at runtime.
- `scripts/benchmark_*.py`, `scripts/live_*.py` — imported by tier-1 resilience tests / mission tooling.
