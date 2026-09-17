---
tags: [testing]
---

# 11 — Testing (strategy, pyramid, metrics)

> Absorbs `docs/05-TEST-PLAN.md` (retired): architecture §1, catalog §2,
> gate checklist §3, integration §4, exit criteria §5 — restated for HEAD.

## 1. Pyramid

- **Unit (bulk)**: pure logic + contracts — routing nets, breaker tables,
  RAG matcher/index, persona pins, plan/gate math. Hermetic tmp vaults and
  fake transports; no network, no clock, no filesystem outside `tmp_path`.
- **Integration**: registry handlers against fake bridges, daemon `_execute`
  against in-process executor+guard, decision-loop skeleton with scripted
  gateway, vault client against recorded GitHub fixtures.
- **Live probes** (`tests/live_probe/`, fail-soft): gateway TTFT, Fish opus,
  bridge health, vault memory — SKIP (never fail) when infra is absent.
- **E2E benches** (`scripts/benchmark_*.py` + `tests/suite/openclaw_bench/`):
  500-turn routing matrix, OpenClaw 12-scenario bench (doubles only),
  persona calibration probes. Reports land in `benchmarks/`.

## 2. Metrics (HEAD: 1,798 passed, 7 skipped)

Tiered coverage architecture (P6, `scripts/check_tiered_coverage.py`): 22
safety/cost/gender core modules (gateway, guard, executor, breaker, gender
pipeline, pc_actions, voice_policy, counter, cadence, associative, dispatcher,
decision_loop, cognition, memory, middleware, plans, consent, protocol) ≥98%
branch each (measured 98.2%–100%); global `src`+`bridge`+`common` ≥90%
(measured 91.8%). Sacred floor (never weaken): owner-middleware
silent-drop, whitelist guardrail, paid-model guillotine, zero-edge TTS purge,
confirmation-before-execution. Flaky policy: quarantine + rerun with evidence,
never mute. Live-harness fails under free-pool rate limits are environmental
(groq cooldown + gemma TTFT timeout), never suite regressions.

## 3. Gate checklist (every change — `make gate`)

`ruff check .` + `ruff format --check .` (zero findings) → `pytest`
(0 failures; live probes may skip) → `scripts/check_tiered_coverage.py`
(22 core ≥98%, total ≥90%) → `scripts/security_gate.py` (bandit +
secret scan, 0 hits) → `scripts/docs_guard.py` (16 canonical files).
Docs change in the same commit as the behavior they describe; TDD
red→green→refactor; halt for owner review per task.

## 4. Fault matrix + live harnesses (P5)

30-seam hermetic fault-injection registry (`tests/test_fault_matrix_p51.py`,
full inventory in the master plan Appendix A): every seam doubled in-suite,
no network — 27 covered at audit, 3 genuine gaps pinned (MEDIUM 429 cascade,
dead-coordinator park, missing-binary Arabic line). 10 live operational
harnesses (`tests/live_harness/test_h01–h10`, skip-soft, paced) run against
`OverlayVault` (`tests/live_harness/overlay.py`, copy-on-write shadow —
production diaries stay pristine).

## See also (graph links)

- [10 — Sprint Checkpoint Ledger](./10-CHECKPOINT.md)
- [Benchmark harness](../scripts/live_interactive_benchmark.py)
- [Map of Testing & Audits](./00-MAP-OF-TESTING-AND-AUDITS.md)
