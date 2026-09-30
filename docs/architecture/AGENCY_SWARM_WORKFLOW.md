# Agency Swarm Roster & Workflow Manifest

**Status:** operational manifest. The 10 role definitions exist on disk under
`.claude/agents/`. Two of them — roles 7 and 8 — are additionally implemented as real
AST detectors in `scripts/launch_parallel_scouts.py`; whether the *harness* can dispatch
them as `explore` sub-agents is unproven and dated. See §3.
**Date:** 2026-09-30 · **Branch:** `main` · **Baseline commit:** `4ada2e5`
**Upstream:** [`msitarzewski/agency-agents`](https://github.com/msitarzewski/agency-agents),
MIT (`Copyright (c) 2025 AgentLand Contributors`), vendored verbatim under
`.claude/agents/agency/` and pinned at commit `765be423`.

Two things about this document are load-bearing, so they are stated here rather than
buried:

1. **The 10 role files are untracked.** `git status` reports `?? .claude/agents/` at
   baseline `4ada2e5`. Nothing in this roster is in git history yet, and nothing in
   `make gate` reads it.
2. **The swarm is not authorised during implementation.** `CLAUDE.md:165`,
   `.claude/WORKFLOW.md:56` and `.claude/PHASE-STATE.md:48` each bind the work to one
   implementer thread and forbid agent swarms. This roster is the reconnaissance and
   review surface, not a licence to parallelise the implementation loop. §3 states the
   enforcement gap in full.

An inbound link from the MOC is outstanding: `docs/00-MAP-OF-ARCHITECTURE.md`
§Deep-dive blueprints lists the sibling blueprint but not this file, so this page is an
orphaned node against that hub's own stated rule. The link is not made here because this
change touches one file.

---

## 1. Roster

`model` and `tools` below are read from each role file's YAML frontmatter. A role that
holds `Edit`/`Write` in its `tools:` grant is *capable* of writing; the "access" column
states what the role's own body permits, and where the two disagree, the body is the
ruling and this table flags it.

Two labelling axes exist in the source files and they do **not** line up. The role files
split reconnaissance into *Work Group A* (internal: `internal-codebase-sleuth`,
`architecture-debt-auditor`) and *Work Group B* (external: `web-intelligence-scout`,
`github-ecosystem-miner`). `engineering-director.md:23` then calls all four "Work
Group B". This document uses the on-disk labels and states the conflict rather than
picking a side silently.

| # | Role | Division | Access | Paths it may touch | Wraps | Mandate |
|---|---|---|---|---|---|---|
| 1 | `engineering-director` | Core (6) | read-only + dispatch | none — produces decompositions, dispatch plans, barrier verdicts | `agency/agents-orchestrator.md` | Root orchestrator; decomposes epics, dispatches, certifies barriers, reports to the Leader |
| 2 | `system-architect` | Core (6) | read-only | none — deliverables are documents; file grant includes `Bash` but the body forbids editing `src/` | `agency/engineering-software-architect.md` | Author RFCs and data contracts; verify the 5 Invariants by naming the file and the assertion |
| 3 | `backend-developer` | Core (6) | writable | `src/` only; `src/persona.py` reformat-locked, `src/config.py` / `src/gateway.py` / `.env` need Leader approval | `agency/engineering-senior-developer.md` | The only role that may write production Python; blocked until RED tests are committed |
| 4 | `qa-engineer` | Core (6) | writable | `tests/` only | `agency/testing-test-automation-engineer.md` | Author and commit RED tests before implementation; guard 98.0%/core-module and 90.0% total branch coverage |
| 5 | `security-auditor` | Core (6) | read-only + certify | none — no `Edit`/`Write` grant; runs gates via `Bash` | `agency/security-ai-generated-code-auditor.md` | Final sign-off; certify or block on the 5 Invariants and the AST gate |
| 6 | `technical-writer` | Core (6) | writable | `docs/` only — no `Bash` grant | `agency/engineering-technical-writer.md` | Own `docs/`, hold `scripts/docs_guard.py` at 16/16, write milestone ledger entries |
| 7 | `internal-codebase-sleuth` | Recon — internal (Work Group A) | read-only | none | `agency/specialized-codebase-archaeologist.md` | Static scan of `src/`, `tests/`, `scripts/` for unwired modules, silent swallows, encoding traps, unbounded awaits |
| 8 | `architecture-debt-auditor` | Recon — internal (Work Group A) | read-only | none | `agency/engineering-code-reviewer.md` | Audit cross-module seams for race conditions, doc-code drift, and unhandled ReAct edge cases |
| 9 | `web-intelligence-scout` | Recon — external (Work Group B) | read-only, non-blocking | none | `agency/research-synthesist.md` | Live web research behind the $0.00 filter; label vendor claims as claims |
| 10 | `github-ecosystem-miner` | Recon — external (Work Group B) | read-only, non-blocking | none | **none — local** | Mine MIT/Apache-2.0 candidates and record the rejection reasons |

Rows 1–6 declare `model: opus`; rows 7–10 declare `model: sonnet`.

The Work Group column is not decorative. `scripts/launch_parallel_scouts.py:68-69`
declares the identical pairings as `GROUP_A` and `GROUP_B`, which is what makes the
reconnaissance half executable: the internal pair becomes local detectors, the external
pair becomes deferred dispatch orders. §3 covers the mechanism.

Row 10 carries no upstream attribution by design. `github-ecosystem-miner.md:9-11` states
that the upstream repository has no open-source-repository-scout division, so the role was
authored for Sara. Its frontmatter records `upstream_persona: NONE` and its body repeats
the reason.

One vendored persona is **not** wrapped by any role:
`agency/product-trend-researcher.md`. It is retained in the vendor directory with the
other nine, and no Sara role binds to it.

---

## 2. Orchestration protocol

Four rules. Each is stated as a rule and, underneath, as the mechanism that would catch
its violation — because a rule with no detector is a preference, and this repo's history
(`mojito`'s unenforced auto/ask gate, recorded in
[the sibling blueprint](./CROSS_FRAMEWORK_ANALYSIS_AND_SELF_EVOLUTION.md) §4) is explicit
that the distinction matters.

### Rule 1 — Zero-Code Root

The Director does not edit `.py` files and does not execute the test suite. Every
implementation byte comes from `backend-developer`.

- **Declared at:** `engineering-director.md:12-18`.
- **Enforcement mechanism:** **none in this repository.** `make gate`
  (`Makefile:40`) runs `lint test security docs-guard` and none of those four targets
  reads the Director's session or file-grant history. The nearest real control is the
  file grant itself — `engineering-director.md:4` lists `tools: Read, Grep, Glob, Glob`
  with no `Edit` and no `Write`, so the harness would refuse an edit attempt made through
  the role. That is a capability boundary, not an audit. Nothing records *which role*
  produced a given commit.

### Rule 2 — Test-First Barrier

`backend-developer` is blocked until `qa-engineer` has authored and committed failing
tests in `tests/`.

- **Declared at:** `backend-developer.md:12-19` (as a precondition) and
  `qa-engineer.md:14-16` (as the mandate).
- **Enforcement mechanism:** **partial, and it is a convention rather than a gate.**
  The mechanical half is real — `pyproject.toml:17` sets
  `addopts = "--cov=src … --cov-fail-under=85"`, so a change that adds uncovered
  production code fails `pytest` on coverage. The ordering half is not: nothing records
  the commit order of `tests/` versus `src/`. `.claude/hooks/` contains a
  `PreToolUse` script for `Write` that refuses `.md`/`.txt` writes outside `docs/`,
  `archive/`, `benchmarks/`, `vault/` and `.claude/`
  (`.claude/hooks/block-creation-of-random-md-files-keeps-docs-consolidated.json`), but
  that gate is **path-based and currently unarmed** — no `PreToolUse` block is registered
  in `.claude/settings.json` or `.claude/settings.local.json`, and it says nothing about
  `.py` authorship in any case. The barrier holds because the Director enforces it, not
  because the repository can prove it.

### Rule 3 — Non-Blocking Scout Fan-Out

Read-only scouts launch concurrently, converge at a barrier, and the core pipeline
consumes the barrier's output only.

- **Declared at:** `engineering-director.md:22-27`, and as a non-blocking posture in
  `web-intelligence-scout.md:14` and `github-ecosystem-miner.md:15`.
- **Enforcement mechanism:** **the harness, for anything model-driven — but a real
  script now covers the deterministic half.** `scripts/launch_parallel_scouts.py` runs
  the two internal scouts concurrently and in-process (`run_group_a`, `:747`), and
  `engineering-director.md:22` still requires the *dispatch* to be concurrent rather than
  a blocking queue. What the script cannot cover: the harness-level `explore` dispatch
  for roles 7 and 8 as reviewing sub-agents, and any dispatch of roles 9 and 10, which
  need a model with live web access. Nothing in `make gate` runs the script, so the
  concurrency is available on demand and unrecorded in CI — see the limits in §3.

### Rule 4 — Security Sign-Off

Nothing lands on `main` without `security-auditor` certification.

- **Declared at:** `engineering-director.md:31-32` and `security-auditor.md:3`.
- **Enforcement mechanism:** **indirect and partial.** The auditor runs
  `scripts/security_gate.py` (bandit at `-lll -ii` over `src/`, then `scripts/secret_scan.py`)
  and `scripts/docs_guard.py`. Both are wired into `make gate` via `Makefile:40`, so
  those checks genuinely block a commit. What is *not* enforced: the 5-Invariant
  certification itself, and the AST-gate review in `src/evolution.py`, which is a
  code-reading judgement with no automated tripwire. A green `make gate` is evidence
  that the mechanical checks passed — it is not the auditor's certification, and the two
  should not be reported as the same thing.

---

## 3. Execution model — verified reality

**The harness exposes exactly two sub-agent types: `explore` and `general`. There is no
`explore-codebase` and no `explore-architecture` sub-agent type.** Roles 7 and 8 map onto
`explore`; their role files say so directly (`internal-codebase-sleuth.md:11`,
`architecture-debt-auditor.md:11`). This is asserted in
`engineering-director.md:25-27` and is the only statement of the sub-agent surface
anywhere in the repository.

**A Python process cannot spawn harness sub-agents.** The sub-agent type is a harness
dispatch decision, not a callable API, so no `.py` file can fan out scouts.
`scripts/launch_parallel_scouts.py:5-7` states this as its reason for existing, and gets
it right: pretending otherwise would produce a report of fabricated findings.

**The split is real, and it is Group A in-process / Group B deferred.**
`scripts/launch_parallel_scouts.py` is the only scout machinery in the repository. It
declares the split as data at `:68-69`:

- `GROUP_A = ("internal-codebase-sleuth", "architecture-debt-auditor")` — reduces to
  static AST scans, so they are implemented as real detectors and run **concurrently**
  on a `concurrent.futures.ThreadPoolExecutor` (`run_group_a`, `:747-780`; the executor
  is constructed at `:761`). One thread per scout, `max_workers` capped at
  `len(GROUP_A)` (`:759`). Each scout builds its own `RepoIndex`, so they share no
  mutable state and one raising cannot corrupt the other — the failure is caught at
  `:772-779` and recorded as a `failed` `ScoutResult`, not a traceback.
- `GROUP_B = ("web-intelligence-scout", "github-ecosystem-miner")` — need live web and
  GitHub access *from a model*. `deferred_to_harness()` (`:783-799`) returns them with
  `status="deferred_to_harness"` and a `manifest` of the role and prompt to hand the
  harness, carrying **zero findings**. A deferred scout never claims to have scanned
  anything.

Five deterministic detectors back Group A, each an AST pass over `src/` and `tests/`
(`SCAN_TREES`, `:60`): missing `encoding=` on `read_text()`/`open()` (`:295`),
`Final` registration literals (`:371`), built-but-unwired modules (`:434`), unbounded
concurrency (`:496`), and silent exception swallows (`:570`). The swallow classifier is
labelled a heuristic in the module docstring (`:35-36`) and says so in its own report.

| Claim | Verified state |
|---|---|
| A script runs the Group A scans concurrently in-process | **True.** `run_group_a` at `:747`; `ThreadPoolExecutor` at `:761`. `--delay N` exists specifically to prove the overlap on the wall clock (`:970-977`) |
| A dispatch manifest is emitted for Group B | **True.** `deferred_to_harness()` at `:783`; `status="deferred_to_harness"` at `:789` |
| Group B is recorded as `deferred_to_harness`, never as findings | **True.** `ScoutResult.findings` is documented as always-empty for this status at `:117`; the render path branches on it at `:885` |
| Sub-agent types are `explore` and `general` | Asserted at `engineering-director.md:25-27`; no `explore-codebase` or `explore-architecture` string exists in the tree |
| The report is an artefact of record | **Not yet produced.** The default output `benchmarks/PARALLEL_SCOUT_REPORT.md` (`:61`) does not exist in the working tree. Nothing in `make gate` runs this script, so a scout run leaves no trace unless someone runs it |
| The swarm runs concurrently today | **Blocked, and dated.** `.claude/PHASE-STATE.md:880-882` records, for the 2026-09-04 run: "Explore subagents 403-broken (harness token has no subagent-model access) → single-threaded closed loop, per CLAUDE §5 preference" |

Two honest limits on that table. The 403 row is a **2026-09-04 observation**, 26 days
before this document's date; it was not re-tested here. And its reach is narrower than it
first appears: `explore` is the sub-agent type roles 7 and 8 are bound to, but the script
implements those same two roles as local AST detectors, so **the Group A findings do not
depend on the harness at all** — they run whether or not `explore` is 403. What the 403
does block is running those roles as the reviewing sub-agents the roster describes, and
roles 9 and 10 are untouched by it either way since they use `WebSearch`/`WebFetch` in
the main thread.

The binding rule that makes all of this moot during implementation:

> "One implementer thread per task — no agent swarms during implementation."

Stated three times, in `CLAUDE.md:165`, `.claude/WORKFLOW.md:56` and
`.claude/PHASE-STATE.md:48-49` (the last adding "the spec fleet era is over"). The
"swarm" in this document's title therefore names a manifest of roles and rules, not a
parallel execution mode that the current engineering line authorises.

---

## 4. Directory layout

```
.claude/agents/                       18 .md files — 10 roster roles + 8 unrelated
.claude/agents/agency/                10 upstream personas, vendored verbatim
.claude/agents/agency/LICENSE-agency-agents
docs/architecture/AGENCY_SWARM_WORKFLOW.md   this file
```

`.claude/agents/` holds 18 Markdown files: the 10 that implement this roster, plus 8
that do not belong to it — `application-security-engineer.md`, `architect.md`,
`backend-architect.md`, `knowledge-graph-engineer.md`, `lead-system-architect.md`,
`planner.md`, `Sara_Autonomous_Behavioral_Engineer.md`, `workflow-architect.md`. None of
the 8 is wrapped by a roster role, and **none of the 8 declares an `upstream_persona`
key** — the 10 roster roles all do, so that key is the cleanest way to tell the two sets
apart. Two of the 8 (`planner.md:3`, `lead-system-architect.md:3`) describe themselves as
"Starter sub-agent scaffolded by Vantrilex". **None of the 8 is part of the agency
programme.** Neither `.claude` nor `.claude/agents` is in ruff's scope —
`pyproject.toml:7` sets `extend-exclude = [".claude", "archive"]` — so no file in this
roster is linted, format-checked, or counted by `make gate`.

`agency/` holds 10 persona files. Nine are wrapped by roles 1–9. The tenth,
`product-trend-researcher.md`, is vendored but unbound. The MIT licence text is retained
alongside the vendored content as `LICENSE-agency-agents`, as the licence's
redistribution clause requires.

The pinned commit is recorded in the short 8-character form `765be423`, which is the only
form present in the repository — it appears in the attribution line of all nine bound
role files. **The 40-character SHA is not recorded anywhere in this repository and is
unverified.** Verifying it requires a fetch of the upstream repository, which this
document did not perform.

---

## 5. The 5 Invariants

Every `file:line` below was read in the session that produced this document. Invariant
names follow the `/audit` mode list in `CLAUDE.md:15-16`.

| # | Invariant | Enforcing file | Verified location | How it is verified |
|---|---|---|---|---|
| 1 | ar-JO immersion | `src/persona.py` | `SARA_PERSONA_AR` at `src/persona.py:12`; module docstring `:2-5` | Byte-locked by `tests/suite/tier1_resilience/test_persona_extract.py`, per the docstring. Doc edits require owner sign-off |
| 2 | Masculine anchor for Omar | `src/gender_pipeline/rules_verbs.py`, `rules_imperatives.py`, `rules_clitics.py` | all three are named in the `CORE` list at `scripts/check_tiered_coverage.py:31-33` | 98.0% branch floor per module from `scripts/check_tiered_coverage.py`; behaviour tests at `tests/suite/tier1_resilience/test_gender_pipeline_exhaustive.py` and `test_persona_gender.py` |
| 3 | Fish-only voice, zero Edge-TTS | `src/voice_policy.py` | `assert_no_edge` at `src/voice_policy.py:15`; `BANNED_MODULES = ("edge_tts",)` at `:12` | Grep the diff for any non-Fish TTS import. The runtime check is narrow by design: it inspects `sys.modules`, so it catches an *already-imported* `edge_tts`, not an import that never ran |
| 4 | Zero unconfirmed commands | `src/pc_actions.py` | `confirmation_id = uuid.uuid4().hex[:12]` at `src/pc_actions.py:277`, inside `_confirm_and_execute`; `PENDING_TTL = timedelta(minutes=10)` at `:23` | Every irreversible tool path must demand a `confirmation_id`; sacred-floor test `tests/test_whitelist_guardrail.py` |
| 5 | $0.00 | `src/gateway.py` | `class PaidModelBlockedError(GatewayError)` at `src/gateway.py:48`; raised at `:61` by `assert_zero_paid_model` (`:54`) | No paid endpoint reachable from the diff. The check is a slug test — `groq/`-prefixed or `:free`-suffixed pass (`:59`) — so a renamed or aliased paid model is a gap, not a catch |

Two limits worth stating, because the security role treats Invariant 5 as structural. The
$0.00 check in `src/evolution.py` is an import allow-list of 8 stdlib modules
(`src/evolution.py:18`) plus a forbidden-call set of `eval, exec, compile, __import__,
open` (`src/evolution.py:21`). `socket`, `http`, `urllib` and `requests` are absent from
the allow-list, so synthesized network use is rejected at the import check rather than at
runtime. The auditor's own file states the limit: the gate does not execute code, so
`open` is bypassable via `pathlib.Path.read_text` and `__import__` via `importlib`. A
pass means structurally admissible, never safe. The disjointness of the promotable and
irreversible tool sets is asserted at `tests/test_evolution.py:109`.

---

## 6. Command reference

The gate chain, in the order `Makefile:40` runs it (`gate: lint test security docs-guard`),
cross-checked against the checklist at `docs/11-TESTING.md:37-42`. Those two disagree, and
the Makefile is the truth: `docs/11-TESTING.md:40` lists
`scripts/check_tiered_coverage.py` inside a checklist headed "every change — `make gate`",
but `Makefile:5` declares no coverage target and `Makefile:40` does not invoke it. The
tiered coverage gate is therefore a **manual** step, and a `make gate` pass does not
include it.

| Step | Command | What it does | Enforced by |
|---|---|---|---|
| lint | `.venv/Scripts/python.exe -m ruff check .` | Static lint. `line-length = 100`, `target-version = "py312"`, `.claude` and `archive` excluded (`pyproject.toml:3-7`) | `Makefile:25` |
| format | `.venv/Scripts/python.exe -m ruff format --check .` | Format check; no rewrite | `Makefile:26` |
| test | `.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --no-cov` | Suite without the coverage report. `--no-cov` is `pytest-cov`'s (present in `pytest --help`); `-p no:cacheprovider` disables the cache plugin. Coverage is **not** skipped in the real gate — `check_tiered_coverage.py` re-runs the suite with `--cov-branch` and a JSON report (`scripts/check_tiered_coverage.py:58-71`) | `Makefile:32`; flag combination per `backend-developer.md:37` |
| coverage | `.venv/Scripts/python.exe scripts/check_tiered_coverage.py` | Enforces 98.0% branch per core module and 90.0% total across 22 named core modules. Exits 1 with a breach table on failure. **Not in the `make gate` chain** — see the drift note below | no Makefile target; run by hand, per `backend-developer.md:38` |
| security | `.venv/Scripts/python.exe scripts/security_gate.py` | `bandit -q -lll -ii -r src/`, then `secret_scan.scan()` over tracked files. Skips with exit 0 if `src/` is absent (`scripts/security_gate.py:15-17`) | `Makefile:35` |
| docs | `.venv/Scripts/python.exe scripts/docs_guard.py` | Asserts 16 canonical files exist. The list is literal, at `scripts/docs_guard.py:11-28`: `README.md`, `.env.example`, `CLAUDE.md`, and `docs/01-` through `docs/13-` | `Makefile:38` |

`docs_guard.py` checks **presence only**. It does not read content, check MOC linkage,
or validate links, so this document cannot fail it and its passing tells you nothing
about this page's accuracy. Its docstring (`scripts/docs_guard.py:1-6`) also claims the
canonical set includes `docs/ai/`; the `CANONICAL_FILES` list at `:11-28` does not contain
that entry, and the count in the same list is 16 either way.

`check_tiered_coverage.py` names 22 core modules (`:24-47`). `docs/11-TESTING.md:26`
describes the same set as 22; the roster role files do not restate the count.

---

## 7. Preconditions that are not currently true

Each entry below was checked against source. A request that assumes any of them is
assuming a capability this repository does not have.

**Fish Audio SIP outbound calling does not exist.** `src/skills/live_calls.py` is
PyTgCalls voice calling over Telegram, not SIP. Its module docstring (`:1`) reads
"Live-call lane (v1.1 roadmap): PyTgCalls voice calling over Telegram", and the live
branch imports `from pytgcalls import PyTgCalls` (`:60`, `:73`) — both *inside* function
bodies, so `pytgcalls` is not a declared dependency either: it appears in no
`requirements*.txt`. The lane is mock-mode until `TELEGRAM_USER_SESSION_STRING` is
populated (`.env.example:61`). SIP telephony is
recorded as a **v1.5** deferral, not a v1.0/v1.1 feature: `docs/08-ROADMAP.md:43`,
`docs/09-DECISIONS.md:17-19` ("PSTN/SIP trunks carry per-minute fees; Telegram voice is
free"; "cloud SIP telephony deferred to v1.5"), and `docs/OWNER_ACTION_REQUIRED.md:14`
("no SIP trunk"). No SIP library appears in `requirements.txt`.

**No Laya or Laya-MLX runtime is installed or planned as a dependency.** It was assessed
as a pattern, not a dependency, because a model checkpoint violates the $0.00 invariant.
`.claude/agents/github-ecosystem-miner.md:47-48` records the same disposition. The
reasoning is in the sibling blueprint: §2.2 rejects the runtime dependency
("Laya would add a model checkpoint (multi-hundred-MB) plus an inference stack to a repo
that runs on a free tier with a hard $0.00 invariant") and §8.1 corrects the dossier
claim — the upstream README states 33 ms for a single forward pass, and §5.1 specifies a
deterministic scorer over features `cognition.evaluate_candidates` already computes, with
no weights. Neither `laya` nor `mlx` appears in `requirements.txt`,
`requirements-dev.txt`, or `requirements-bridge.txt`.

**Harness sub-agents do not consume OmniRoute's Groq/OpenRouter key pools.**
`.env.example` defines exactly one key per provider: `OMNIROUTE_API_KEY` at `:15`,
`OPENROUTER_API_KEY` at `:88`, and — a third single-valued variable the roster's
credential inventory should also carry — `FISH_AUDIO_API_KEY` at `:91`. There is no
comma-separated or indexed key list anywhere in that file. The free provider pools
(`google/gemma-4-31b-it:free`, `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free`) appear
only as *model slug* values in `FAST_MODEL_FALLBACKS`, `HEAVY_MODEL_FALLBACKS` and
`HEAVY_ESCALATION_*` (`:28`, `:43`, `:45-46`). The pool is server-side in OmniRoute
(`https://github.com/diegosouzapw/OmniRoute`, `.env.example:10-12`), bound to
`http://localhost:20128/v1`, and is not visible from this repository. A sub-agent that
reaches a free model therefore goes through the gateway, and inherits whatever quota the
shared pool has left — it does not get its own key, and the 50 req/day/account ceiling
recorded at `.env.example:25` applies across the whole session.

**There is no dedicated CMD REPL HUD module.** A case-insensitive search for `HUD`
returns zero hits across the whole tree. The nearest surfaces are `src/telemetry.py`,
which is a core-side client that fetches the PC's `LiveState` and renders it as one
Jordanian Arabic line (`src/telemetry.py:1-5`), and `scripts/live_shadow_tracer.py`, a
`rich`-based console tail of the cognition JSONL sink (`:1-11`). Neither is a REPL and
neither is a general heads-up display. `src/bridge_server.py` and `bridge/telemetry.py`
carry the transport and the state model respectively.

---

## 8. See also

- [Cross-Framework Analysis & Self-Evolution](./CROSS_FRAMEWORK_ANALYSIS_AND_SELF_EVOLUTION.md) — the 24-resource matrix, the disposition rule that rejects model checkpoints, and the mojito comparison
- [16 — Operational Workflows](../16-WORKFLOWS.md) — the 4-tier lifecycle this roster's barriers sit inside
- [00 — Map of Architecture (MOC)](../00-MAP-OF-ARCHITECTURE.md)
- [10 — Checkpoint Ledger](../10-CHECKPOINT.md) — the milestone record this roster's `technical-writer` role writes
- [11 — Testing and Gates](../11-TESTING.md) — the gate chain in §6
- [12 — Security](../12-SECURITY.md) — the confirmation and whitelist rules behind Invariant 4
