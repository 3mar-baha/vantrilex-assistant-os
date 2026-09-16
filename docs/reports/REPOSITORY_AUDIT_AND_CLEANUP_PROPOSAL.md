---
tags: [testing]
---

# Repository Audit & Cleanup Proposal — Vantrilex Assistant OS

> **STRICTLY NON-DESTRUCTIVE.** This document is an audit and proposal only.
> Zero files were deleted, moved, or truncated to produce it. Every
> Deprecate/Relocate row below requires separate human confirmation before
> any action. Baseline: `main @ 883777e`.
>
> Related: `docs/reports/EXHAUSTIVE_SYSTEM_AUDIT_REPORT.md` (system census),
> `docs/08-ROADMAP.md` (sole home of planned/deferred work per decoupling rule).

## 0. Baseline health (Phase 0, 2026-09-16)

| Signal | Result |
|---|---|
| `pytest -q -p no:cacheprovider --no-cov` | **1,457 passed, 7 skipped, 0 failed** (~113 s) |
| Gateway `http://localhost:20128/v1` | **Unreachable** → benchmark target is DEGRADED mode |
| `git status` (pre-mission) | `M CLAUDE.md`, `M benchmarks/LIVE_BENCHMARK_TRANSCRIPT.json`, 12 untracked housekeeping paths (see §2) |
| Python | 3.12.10 (per Stack Pins) |

## 1. Method

Enumerated `src/`, `src/skills/`, `src/openclaw/`, `bridge/`, `bridge/openclaw/`,
`common/`, `tests/` (+ `suite/`, `fixtures/`, `live_probe/`, `reports/`),
`scripts/`, `docs/`, `vault/`, `config/`, `.github/`, `.claude/`, `data/`,
`versions/`, `04_Resources/`, `benchmarks/`, `_reference_repo/`, and root.
For each path: `git ls-files` (tracked?) + `git check-ignore -v` (ignored?)
determined the Keep/Deprecate/Relocate verdict. Sensitive values were never
printed; one live secret exposure is flagged in §3 without quoting it.

## 2. Classification table

| File Path | Current Function | Suggested Status | Rationale | Risk |
|---|---|---|---|---|
| `docs/01–15` + `docs/specs/` + `docs/ai/` | Canonical 16-file suite + sprint specs (presence-gated by `scripts/docs_guard.py`) | **Keep** | Contract surface; teardown/rename breaks gate | High (to touch) |
| `docs/reports/SARA_FULL_SYSTEM_AUDIT_AND_LIVE_BENCHMARK_REPORT.md` | Phase 2–3 audit + benchmark record | **Keep** (+ §4 correction this mission) | Mission record; §§C/E misattribution must be fixed, not removed | Med |
| `docs/reports/EXHAUSTIVE_SYSTEM_AUDIT_REPORT.md` | System census (decoupling rule anchor) | **Keep** | Referenced by CLAUDE.md | Low |
| `docs/reports/{OPENHUMAN-ASSESSMENT,SARA-CAPABILITIES-ROADMAP}.md` | Advisory assessments | **Keep** | Historical input, tiny | Low |
| `docs/00-MAP-OF-ARCHITECTURE.md`, `docs/00-MAP-OF-TESTING-AND-AUDITS.md` | Navigation hubs (MOC) | **Keep** (created this mission) | Committable graph hubs; `docs_guard.py` checks presence-only so additions are safe | Low |
| `src/*.py` (core: `bot/gateway/dispatcher/memory/tools/…`) | Production core | **Keep** | 1,457-test suite pins behavior | High (to touch) |
| `src/persona.py` | `SARA_PERSONA_AR` + `build_persona` (4,782-byte invariant) | **Keep, do not reformat** | `test_a_persona_masculine_arabic` asserts exact length | High (to touch) |
| `src/skills/*`, `src/openclaw/*`, `src/gender_pipeline/*` | Capability skills, planner, pipeline | **Keep** | Active imports across suite | Med |
| `bridge/*.py`, `bridge/openclaw/*` | PC daemon: guard, executor, breaker, arms | **Keep** | Sacred-floor adjacent (`test_whitelist_guardrail.py`) | High (to touch) |
| `common/` | Shared consent/protocol | **Keep** | Imported by core + bridge | Med |
| `tests/test_*.py` (×~100), `tests/conftest.py`, `tests/helpers_*.py` | Regression suite incl. sacred floor (`test_owner_middleware.py`, `test_whitelist_guardrail.py`, `test_guest_lockdown.py`) | **Keep** | The contract; never delete/skip | High (to touch) |
| `tests/suite/{openclaw_bench,tier1_resilience,tier2_live_probes,tier3_shadow_tracer}/` | Bench + resilience + shadow harnesses | **Keep** | Benchmark provenance | Med |
| `tests/fixtures/{canned_voice.mp3,syllabus_sample.pdf}` | Binary fixtures | **Keep** | Referenced by voice/syllabus tests | Med |
| `tests/live_probe/` | Live (gateway-required) probes | **Keep** | Skipped hermetically by design | Low |
| `scripts/live_interactive_benchmark.py` | Tests A–F + 5-invariant benchmark | **Keep** (+ Phase 4 hardening) | Mission deliverable; script-only fixes | Med |
| `scripts/{security_gate,secret_scan,docs_guard,make_release,deploy_smoke,benchmark_500,benchmark_openclaw,live_canary_phase6,live_telegram_tester}.py` | Gates, release, probes | **Keep** | Wired into `make gate`/CI/release | Med |
| `scripts/{joda_distill,groq_persona_probe,fish_calibration_spike,supervise,cognitive_shadow_observer,joda_schema_probe}.py` | One-off spikes/probes | **PARTIAL: 4 spikes in `archive/scratch_scripts/`; `joda_distill.py` RESTORED to `scripts/` 2026-09-16 (owner whitelist); `supervise.py` KEPT (imported by `test_packaging.py`, pinned by Dockerfile CMD)** | Zero importers on the moved four; harmless | Low |
| `config/whitelist.json` | App/power allowlist (re-read live) | **Keep** | Rule-4 guardrail source | High (to touch) |
| `config/google_oauth_client.json` | OAuth client secret (on disk) | **Keep ignored** | `gitignore:6` covers `config/google_*.json` ✓ — verify never staged | High (if staged) |
| `.env.example`, `requirements*.txt`, `Dockerfile`, `Makefile`, `pyproject.toml`, `conftest.py`, `sara.ps1`, `sara.bat` | Env manifest, deps, build, entry | **Keep** | Pins + runbooks | Med |
| `.github/workflows/{ci,keepalive}.yml`, `.githooks/` | CI + commit hooks | **Keep** | Quality enforcement | Med |
| `04_Resources/` (tracked KB seed) vs `vault/04_Resources/` (gitignored local copy) | Dialect/KB/style content in two places | **Keep both; owner ruling needed on canonical source** | Tracked copy is the committable seed; vault copy is owner-data working state. Do NOT dedupe without confirmation | Med |
| `vault/**` (entire tree) | Owner-data working copy of git-backed vault | **Keep ignored** | `gitignore:40` (`vault/`) ✓ — vault edits are local-only, never committed | High (if staged) |
| `benchmarks/LIVE_BENCHMARK_TRANSCRIPT.json`, `benchmarks/records*.jsonl`, `BENCHMARK_*_REPORT.md`, `DISCOVERY_AND_IMPROVEMENTS.md` | Benchmark evidence | **Keep** | Transcript refreshed this mission | Low |
| `EXECUTIVE_PROGRESS_REPORT_2026_09_06.md` (17 KB) | One-off progress snapshot (root) | **[RELOCATED → `archive/reports/` 2026-09-16]** | Root must stay entry-point-only; content preserved verbatim | Low |
| `NIGHT_RUN_REPORT.md` (9 KB) | One-off night-run notes (root) | **[RELOCATED → `archive/reports/` 2026-09-16]** | Same as above | Low |
| `MANUAL_TEST_CHECKLIST_2026_09_06.md` (9 KB) | Manual checklist (root) | **[RELOCATED → `archive/reports/` 2026-09-16]** | Same as above | Low |
| `AUDIT_AND_PLAN_40_FEATURES.md` (58 KB) | Feature audit + plan (root) | **[RELOCATED → `archive/reports/` 2026-09-16]** | Same as above | Low |
| `PROJECT_IDEAS_COMPENDIUM.md` (15 KB) | Idea backlog (root) | **[RELOCATED → `archive/reports/` 2026-09-16]** | Decoupling rule: planned work lives in `08-ROADMAP.md` | Low |
| `run_live_probe.py` (4 KB, root) | Live probe entry (root) | **[RELOCATED → `archive/scratch_scripts/` 2026-09-16]** | Zero importers; scripts belong out of root | Low |
| `tests/reports/*` (`FISH_TAG_CALIBRATION.md`, `FULL_SYSTEM_EXHAUSTIVE_AUDIT.md`, `JODA_SCHEMA_NOTE.md`, `audit_records.jsonl`) | Calibration/audit notes under tests | **KEPT 2026-09-16 (relocation vetoed): `audit_harness.py` writes `FULL_SYSTEM_EXHAUSTIVE_AUDIT.md` + `audit_records.jsonl` there at runtime** | Test tree should hold code + fixtures, not reports | Low |
| `versions/release-v*/CHANGELOG.md` (×10 dirs, tracked) | Generated release snapshots | **[RELOCATED → `archive/legacy_versions/versions/` 2026-09-16]** | Superseded by root `CHANGELOG.md` + tags `v1.0.x`; history preserved in git even if removed | Med |
| `compile.txt` (untracked) | Compiler dump | **[PRUNED / DELETED 2026-09-16]** (owner-authorized; 15 B; zero references) | Ephemera; never committed | Low |
| `ruff_out.txt` (untracked) | Linter dump | **[PRUNED / DELETED 2026-09-16]** (owner-authorized; 34 B; zero references) | Same as above | Low |
| `litellm_config.yaml` (untracked) | Gateway config (?) | **Review → `config/` or `.gitignore`** | Untracked + not ignored; owner decides committable vs local | Low |
| `opencode.json` (untracked) | Harness config **containing a live OpenRouter API key** | **NEVER commit; add to `.gitignore`; rotate the key** | Secret would enter git history on commit. Relative `instructions[]` paths are clean; the `provider.openrouter.options.apiKey` value is the exposure | **High** |
| `.claude/hooks/*.json`, `.claude/agents/`, `.claude/plugins/` (untracked) | Harness hooks/agents/plugins | **Review for absolute paths/secrets before any commit** | Commit only if generic + machine-independent | Med |
| `.claude/settings.local.json` | Local settings | **Keep ignored** | `gitignore:7` covers it ✓ | Low |
| `.claude/skills/`, `.claude/plans/` | Sprint skill rotation | **Keep ignored** | `gitignore:27-28` ✓ (teardown protocol compatible) | Low |
| `_reference_repo/` | Vendor reference | **Keep ignored** | `gitignore:29` ✓ | Low |
| `data/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`, `.venv/`, `.coverage` | Runtime/cache/venv | **Keep ignored** | All covered by `.gitignore` ✓ | Low |

## 3. Secret-hygiene flags (no values quoted)

1. `opencode.json` (untracked) embeds a live `sk-or-v1-…` key → never stage; rotate.
2. `config/google_oauth_client.json` present on disk, correctly ignored — audit-only, no action.
3. `vault/State/*.enc` + `.env` remain untracked/ignored — no action.

## 4. Vault-boundary rule (binding for Phase 3)

- The Obsidian vault is `vault/` (owns `.obsidian/`; `graph.json` has
  `colorGroups: []`, `showTags: false` — clustering unconfigured).
- `vault/` is gitignored → **all vault-side graph work is local-only and excluded
  from every commit**.
- `docs/` therefore uses portable relative Markdown links (GitHub-safe), and
  `[[WikiLinks]]` are authored only inside `vault/`.

## 5. Proposed clean taxonomy tree (target state — moves need confirmation)

```text
<repo>                          # entry points + manifests only
├── README.md / CLAUDE.md / AI-INSTRUCTIONS.md / CONTRIBUTING.md / SECURITY.md
├── CHANGELOG.md                # single changelog (versions/* consolidated away)
├── docs/
│   ├── 00-MAP-OF-ARCHITECTURE.md          # MOC hub (this mission)
│   ├── 00-MAP-OF-TESTING-AND-AUDITS.md    # MOC hub (this mission)
│   ├── 01-PRODUCT-REQUIREMENTS.md … 15-ORACLE-DEPLOY.md
│   ├── specs/ / ai/
│   └── reports/                # ALL one-off reports live here (root + tests/reports relocated)
├── benchmarks/                 # transcripts + records + benchmark reports only
├── src/ / bridge/ / common/    # product code (unchanged)
├── tests/                      # code + fixtures only (reports relocated out)
├── scripts/                    # all runnable utilities (run_live_probe.py relocated in)
├── config/                     # whitelist + committable configs (oauth client stays ignored)
├── vault/                      # IGNORED local working copy (graph work local-only)
│   └── 00_Meta/00-MAP-OF-SYSTEM.md        # local-only MOC (never committed)
├── .github/ / .githooks /
└── .gitignore                  # + compile.txt, ruff_out.txt, litellm_config.yaml*, opencode.json
    (* litellm_config.yaml pending owner review: config/ vs ignore)
```

*End of proposal. No file was created, moved, or deleted except this report.*

## 6. Deep physical reorganization review (2026-09-16 — executed + vetoed)

Executed (all gitignored/untracked, zero suite impact):

| Action | Reclaimed |
|---|---|
| `_reference_repo/` (583 KB) → `archive/_reference_repo/` (filesystem move, stays ignored) | decluttered root |
| Root `__pycache__/`, `.ruff_cache/`, `.coverage` (491 KB), `.ingest/` deleted | ~0.5 MB + dirs |
| `Untitled.canvas` (2 B Obsidian debris, prior session) deleted | — |

Vetoed (moves would break pinned contracts — evidence):

| Proposed move | Veto evidence |
|---|---|
| `04_Resources/` → `vault/` | `src/vault.py:79-80` resolves repo-root `04_Resources/` as mirror SOURCE; `test_rag_vault_sync.py:16` pins `SOURCE = REPO/"04_Resources"`; `test_packaging.py:120` + 6 resilience tests read root-relative paths; `vault/` is gitignored → move = silent deletion from git |
| `common/` → `src/` | top-level `common.protocol`/`common.consent` imported by `src/bot.py`, `src/bridge_server.py`, `src/pc_actions.py`, `bridge/daemon.py`, ~12 test files |
| `config/` → `src/` | `config/whitelist.json` hardcoded in `src/bot.py` (×3), `src/app_indexer.py`, `bridge/__main__.py`, `bridge/daemon.py` (×2), `audit_harness.py`, `test_bridge_extensions.py` |
| `data/` → `src/`/`tests/fixtures/` | runtime paths (`data/app_sessions`, `data/inbox`, `data/joda`) in `bridge/__main__.py` + scripts; `data/` is gitignored runtime state, must stay untracked |
| `CHANGELOG.md` → `docs/` | `scripts/make_release.py:28` (`REPO/"CHANGELOG.md"`); release tooling + `test_release_metadata.py` pin root |
| `requirements*.txt` → `requirements/` | `test_packaging.py:119,242`, `test_release_metadata.py:44`, `test_openclaw_core.py:194,196` read root files; `Dockerfile`/`ci.yml`/`Makefile` consume root paths |
| `CONTRIBUTING.md` / `SECURITY.md` → `.github/` or `docs/` | root is the GitHub-native home; hook allowlists name root files; zero functional gain |
| `AI-INSTRUCTIONS.md` → `docs/` | `opencode.json` `instructions[]` references the root path; move breaks harness config |
