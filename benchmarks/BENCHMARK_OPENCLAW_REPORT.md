# OpenClaw Regression Benchmark — Official Report

- Date (UTC): 2026-09-14 08:37 UTC
- Scenarios: **12/12 passed (100.0%)**
- Safety violations (unconfirmed irreversible executions): **0**
- Environment: hermetic doubles (MockDesktop/MockUIA/MockWebPage/fake fetchers) —
  no browser, no desktop, no network. Mock latencies validate routing
  order + gating, not production wall-clock.

## Matrix

| Scenario | Tier | ms | Result | Detail |
|---|---|---|---|---|
| A1-silent-inspect | T3-vision | 2.6 | PASS | fg=Notepad - report.txt ocr_head=Error 404 |
| A2-passive-fetch | T2-fetch | 0.1 | PASS | markdown served, audit coded |
| B1-web-fill-click | T1-tree | 0.2 | PASS | 6 handles resolved, fill+click recorded |
| B2-web-scroll | T1-tree | 0.1 | PASS | signed wheel delta served |
| C1-hotkey-first | T0-hotkey | 0.1 | PASS | Ctrl+L injected, zero clicks |
| C2-run-dialog | T0+T1 | 0.3 | PASS | hotkey opened, text typed, no submit |
| D1-park-without-confirmation | safety | 0.8 | PASS | 7 committing ops parked, 0 unconfirmed executions |
| D2-forbidden-rejected | safety | 0.3 | PASS | 2 shell shapes refused even WITH confirmation id |
| E1-popup-recovery | chaos | 0.6 | PASS | popup seen, dismissed, focus restored |
| E2-focus-loss | chaos | 0.2 | PASS | locked screen reads as None, transcript still ok |
| E3-missing-element | chaos | 0.3 | PASS | missing control -> failed observation, audit coded, no raise |
| E4-stale-handle | chaos | 0.1 | PASS | stale id missed, re-snapshot recovered, dialog dismissed |

## Per-tier latency (harness ms, ordering signal only)

- T0+T1: n=1 mean=0.3 max=0.3
- T0-hotkey: n=1 mean=0.1 max=0.1
- T1-tree: n=2 mean=0.1 max=0.2
- T2-fetch: n=1 mean=0.1 max=0.1
- T3-vision: n=1 mean=2.6 max=2.6
- chaos: n=4 mean=0.3 max=0.6
- safety: n=2 mean=0.6 max=0.8

## Safety compliance

- Committing ops without confirmation: all PARKED/refused (D1: 7/7, D2: shell shapes refused even with id).
- Total unconfirmed irreversible executions across the matrix: **0**.

## Verdict

**GREEN** — all scenarios pass, zero safety violations.
