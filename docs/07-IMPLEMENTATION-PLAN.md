---
tags: [architecture]
---

# 07 — Implementation Plan (12-step living-core DAG — ALL COMPLETED)

> Every step below shipped behind TDD (failing test → minimal code →
> `make gate` → commit). No speculative layers; no open steps remain in
> this plan — future work lives in `docs/08-ROADMAP.md`.

| # | Step | Evidence | Status |
|---|---|---|---|
| 1 | MAC auto-discovery → `.env`; mirror to strict copy-if-missing | `PC_MAC_ADDRESS` live; `vault.py` + rewritten sync test | ✅ COMPLETED |
| 2 | Seed digest + slim profile + plant master digest | `Omar_Core_Digest.md` (301w, disjoint aliases); plant fn + boot hook | ✅ COMPLETED |
| 3 | Nested-archive resolver + 6 call sites + 90-day index | `daily_log_path` nested; compat readers; `iter_recent_daily_logs` | ✅ COMPLETED |
| 4 | Intent-gated injection + matrix | `ROUTINE_INTENTS`; digest+top-k on advisory; 7-test matrix | ✅ COMPLETED |
| 5 | Net hoist (inspect above screenshot) + collision suite | `«افحصي عناصر الشاشة»→openclaw_inspect` verified live | ✅ COMPLETED |
| 6 | `openclaw.browse` verb + BrowserArm bind + core handler | `CmdName` + daemon branch + `__main__` bind; fetch fallback | ✅ COMPLETED |
| 7 | Planner adapter + THOUGHT vocab | `dag_for_tool`; plan_out observability; PARK sole enforcer | ✅ COMPLETED |
| 8 | Dynamic PARK warnings + static floor | FAST-composed ask; `PARK_LINE_AR` fallback; form-agnostic tests | ✅ COMPLETED |
| 9 | /start WoL + reconnect hook + quiet hours | `wake_decision`; watcher (debounce + 08:00–23:30 Amman) | ✅ COMPLETED |
| 10 | Whitelist 5+1, exec.open, stream_heavy | 6 entries (cmd confirm-gated); `_do_open_path`; MoE reroutes | ✅ COMPLETED |
| 11 | Async write-back engine | `memory_ledger.py` (weight≥4/explicit, background, capped digest) | ✅ COMPLETED |
| 12 | Full gates + commit + summary | 1,457/0 suite, ruff clean, 0-hit scan | ✅ COMPLETED |

Acceptance was per-step proof (failing→passing tests, live route probes,
gate output) reported at each halt; the full matrix is in `docs/10-CHECKPOINT.md`.

## See also (graph links)

- [10 — Sprint Checkpoint Ledger](./10-CHECKPOINT.md)
- [11 — Testing](./11-TESTING.md)
- [Map of Architecture](./00-MAP-OF-ARCHITECTURE.md)
