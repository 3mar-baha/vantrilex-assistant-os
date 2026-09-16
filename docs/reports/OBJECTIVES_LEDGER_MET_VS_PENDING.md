---
tags: [decision]
---

# Objectives Ledger — Met vs Pending (2026-09-16)

> Executive summary: every v1.0 construction objective is met and test-pinned.
> Everything pending is owner-physical (credentials, hosts, keys) or explicitly
> parked scope — zero engineering unknowns block going live.

## Met (with proof)

| Objective | Proof |
|---|---|
| 3-tier OmniRoute brain + front-door dispatcher | `src/gateway.py`, `src/dispatcher.py`; `test_dispatcher.py`, benchmark F |
| Telegram shell, owner-only gate, voice notes | `src/bot.py`, `src/middleware.py`; sacred floor |
| Voice biometrics + Guest Mode (threshold 0.60) | `src/skills/voice_biometric_auth.py`; `test_guest_lockdown.py` |
| Fish-only voice, no Edge fallback | `src/fish_voice.py`; `test_fish_audio_pipeline.py`; voice policy |
| Gmail triage + daily brief + evening journaler | `src/email_triage.py`, `src/daily_brief.py`, `src/skills/evening_journaler.py` |
| Vault client + two-tier memory + RAG mirror | `src/vault.py`, `src/memory*.py`, `src/associative.py` |
| PC bridge + whitelist + OpenClaw bench 12/12 | `bridge/`; `test_whitelist_guardrail.py`; bench harness |
| 46-tool registry, all connected-path tested | `src/tools.py`; `test_tool_coverage_gaps.py`; matrix report |
| Benchmark 6/6 + 5/5 invariants | `scripts/live_interactive_benchmark.py`; transcript |
| Governance: 4-tier workflows, teardown, branch rule | `docs/16-WORKFLOWS.md`, `CLAUDE.md` gate |

## Pending (owner-physical, ordered)

1. Start OmniRoute with provider keys → flips all LLM tiers LIVE.
2. `sara.ps1` cycle → `/start` → `/enroll-voice` (≥5 s note).
3. Google OAuth consent refresh (watch known 403 on the Cloud project).
4. Oracle VM deploy per `docs/15-ORACLE-DEPLOY.md` (optional after local-first).
5. Key rotation (OpenRouter key exposed in untracked `opencode.json`; GitHub PAT; Telegram API_HASH).
6. Optional keys: Firecrawl, Places, Instagram session, PubSub topic.

## Parked (authority: `docs/08-ROADMAP.md`)

v1.1 live voice calls · Instagram live · Civ6 fate · diarization trigger ·
v1.5 SIP · v2.0 social agent · Mem0/Firestore eval · health monitor ·
emotional memory · silent backup.

## Appendix — sacred floor test IDs

`test_owner_middleware.py` · `test_whitelist_guardrail.py` ·
`test_guest_lockdown.py` — must exist, run, and block every merge.

## See also (graph links)

- [Timeline](./PROJECT_TIMELINE_AND_MILESTONES.md)
- [08 — Roadmap](../08-ROADMAP.md) · [Master Roadmap](../MASTER_ROADMAP_AND_REMAINING_WORK.md)
- [Map of Testing & Audits](../00-MAP-OF-TESTING-AND-AUDITS.md)
