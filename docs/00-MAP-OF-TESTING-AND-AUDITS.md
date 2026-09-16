---
tags: [testing]
---

# 00 — Map of Testing & Audits (MOC hub)

Central navigation hub for the verification cluster. Every note below links
back here via its own `See also` block — no orphaned nodes.

## Test strategy & ledger

- [10 — Sprint Checkpoint Ledger](./10-CHECKPOINT.md)
- [11 — Testing](./11-TESTING.md)
- [Benchmark harness](../scripts/live_interactive_benchmark.py) (Tests A–F + 5 invariants)

## Audit reports (consolidated 2026-09-16 — the only reports)

- [Timeline & Milestones](./reports/PROJECT_TIMELINE_AND_MILESTONES.md)
- [Objectives Ledger](./reports/OBJECTIVES_LEDGER_MET_VS_PENDING.md)
- [Tools & API Compendium](./reports/TOOLS_AND_API_COMPENDIUM.md)
- [Risks, Costs & Governance](./reports/RISKS_COSTS_AND_GOVERNANCE.md)

## Benchmark evidence

- [Live benchmark transcript](../benchmarks/LIVE_BENCHMARK_TRANSCRIPT.json)
- [500-prompt benchmark report](../benchmarks/BENCHMARK_500_FULL_REPORT.md)
- [500-prompt thin-prompt run](../benchmarks/BENCHMARK_500_RUN1_THINPROMPT.md)
- [OpenClaw benchmark report](../benchmarks/BENCHMARK_OPENCLAW_REPORT.md)
- [Discovery & improvements](../benchmarks/DISCOVERY_AND_IMPROVEMENTS.md)

## Companion hub

- [Map of Architecture](./00-MAP-OF-ARCHITECTURE.md)

## Module ↔ test map (every link verified on disk)

- `src/bot.py` → [bot shell](../tests/test_bot_shell.py) · [voice demand](../tests/test_bot_voice_demand.py)
- `src/gateway.py` → [omniroute gateway](../tests/test_omniroute_gateway.py) · [failfast](../tests/test_gateway_failfast.py) · [rate windows](../tests/test_gateway_rate_windows.py)
- `src/dispatcher.py` → [dispatcher](../tests/test_dispatcher.py)
- `src/memory.py` + `memory_ledger.py` → [memory](../tests/test_memory.py) · [ledger](../tests/test_memory_ledger.py)
- `src/tools.py` → [tools](../tests/test_tools.py) · [expansion](../tests/test_tools_expansion.py) · [Sara skills](../tests/test_sara_tool_skills.py)
- `src/vault.py` → [vault dirs](../tests/test_vault_dirs.py) · [PARA](../tests/test_obsidian_para.py)
- `src/dialect.py` → [dialect](../tests/test_dialect.py)
- `src/voice.py` + `fish_voice.py` → [streaming](../tests/test_voice_streaming.py) · [Fish pipeline](../tests/test_fish_audio_pipeline.py)
- `src/gmail.py` + `email_triage.py` → [watch](../tests/test_gmail_watch.py) · [triage](../tests/test_email_triage.py) · [compaction](../tests/test_triage_compaction.py)
- `src/daily_brief.py` → [daily brief](../tests/test_daily_brief.py)
- `src/middleware.py` → [owner gate](../tests/test_owner_middleware.py) · [guest lockdown](../tests/test_guest_lockdown.py)
- `src/pc_actions.py` → [PC actions](../tests/test_pc_actions.py)
- `src/telemetry.py` → [desktop telemetry](../tests/test_desktop_telemetry.py)
- `bridge/guard.py` + `bridge/executor.py` → [whitelist guardrail](../tests/test_whitelist_guardrail.py) · [whitelist apps](../tests/test_whitelist_apps.py)
- `bridge/` online surface → [bridge online](../tests/test_bridge_online.py) · [protocol](../tests/test_bridge_protocol.py)
- `bridge/openclaw/` + `src/openclaw/` → [openclaw bench](../tests/suite/openclaw_bench/test_bench_scenarios.py) · [chaos](../tests/test_resilience_chaos.py)

## Test-tree reports (relocation candidates per audit — linked until moved)

- [Fish tag calibration](../tests/reports/FISH_TAG_CALIBRATION.md)
- [Full-system exhaustive audit](../tests/reports/FULL_SYSTEM_EXHAUSTIVE_AUDIT.md)
- [JODA schema note](../tests/reports/JODA_SCHEMA_NOTE.md)

## Release snapshots (archived 2026-09-16 — manifest in `archive/README.md`)

- [v1.1 pass 1](./../archive/legacy_versions/versions/release-v1.1-pass1/CHANGELOG.md) · [pass 2](./../archive/legacy_versions/versions/release-v1.1-pass2/CHANGELOG.md) · [pass 3](./../archive/legacy_versions/versions/release-v1.1-pass3/CHANGELOG.md) · [pass 4](./../archive/legacy_versions/versions/release-v1.1-pass4/CHANGELOG.md) · [pass 5](./../archive/legacy_versions/versions/release-v1.1-pass5/CHANGELOG.md)
- [v2.0 pass 1](./../archive/legacy_versions/versions/release-v2.0-pass1/CHANGELOG.md) · [pass 2](./../archive/legacy_versions/versions/release-v2.0-pass2/CHANGELOG.md) · [pass 3](./../archive/legacy_versions/versions/release-v2.0-pass3/CHANGELOG.md) · [pass 4](./../archive/legacy_versions/versions/release-v2.0-pass4/CHANGELOG.md) · [pass 5](./../archive/legacy_versions/versions/release-v2.0-pass5/CHANGELOG.md)
