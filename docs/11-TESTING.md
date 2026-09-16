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

## 2. Metrics (HEAD: 1,457 passed, 0 failed)

Coverage ≥ 85% (gate-enforced). Sacred floor (never weaken): owner-middleware
silent-drop, whitelist guardrail, paid-model guillotine, zero-edge TTS purge,
confirmation-before-execution. Flaky policy: quarantine + rerun with evidence,
never mute.

## 3. Gate checklist (every change — `make gate`)

`ruff check .` + `ruff format --check .` (zero findings) → `pytest`
(0 failures; live probes may skip) → `scripts/security_gate.py` (bandit +
secret scan, 0 hits) → `scripts/docs_guard.py` (16 canonical files).
Docs change in the same commit as the behavior they describe; TDD
red→green→refactor; halt for owner review per task.

## See also (graph links)

- [10 — Sprint Checkpoint Ledger](./10-CHECKPOINT.md)
- [Full System Audit & Live Benchmark](./reports/SARA_FULL_SYSTEM_AUDIT_AND_LIVE_BENCHMARK_REPORT.md)
- [Benchmark harness](../scripts/live_interactive_benchmark.py)
- [Map of Testing & Audits](./00-MAP-OF-TESTING-AND-AUDITS.md)
