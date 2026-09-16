---
tags: [security]
---

# Risks, Costs & Governance (2026-09-16)

> Executive summary: the system costs $0.00 by construction, is gated by a
> green suite plus sacred-floor tests, and carries four known risks — all with
> mitigations or owner actions attached.

## $0.00 cost proof

- All LLM traffic rides free pools (Groq + OpenRouter `:free`) behind the
  free-tier guard (`PaidModelBlockedError` kills non-free IDs pre-wire).
- Voice: Fish free tier; STT: local Whisper CPU; search/weather: keyless;
  storage/compute: Oracle Always-Free + git-backed vault.
- Quota guards: 4 s first-token guillotine, 15 min 429 quarantine, `quota_safety`
  tool reporting headroom. Measured spend to date: **$0.00**.

## Risk register

| Risk | Likelihood / Impact | Mitigation / Owner action |
|---|---|---|
| OmniRoute single point (all tiers DEGRADED when down) | High / High | Multi-pool fallbacks + quarantine doctrine; owner starts service with keys |
| Exposed OpenRouter key (untracked `opencode.json`) | Done / High | **Rotate now**; never commit the file (gitignored + audit-flagged) |
| Encrypted vault blobs with single local copies | Low / High | Define owner-side encrypted backup cadence (Silent Backup parked in `08-ROADMAP`) |
| Live-probe timing flake (TTFT gate under load) | Medium / Low | Fail-soft skips; hermetic suite unaffected (1,460 green) |
| Google 403 on Cloud project | Known / Medium | Console fix per `OWNER-NEXT-STEPS.md`; Gemini already retired over it |

## Governance recap

4-tier workflows (`/plan` default, `/code`, `/audit`, `/sync`) locked in
`CLAUDE.md` + `docs/16-WORKFLOWS.md` · direct-to-`main` branch rule · sprint
skill-rotation teardown · sacred floor
(`test_owner_middleware.py`, `test_whitelist_guardrail.py`,
`test_guest_lockdown.py`) blocks every merge · zero deletions without
confirmation · docs ship with behavior in the same commit.

## Appendix — incident log (threat → fix, all closed)

- Google 403 Gemini denial → Gemini retired, Groq/OpenRouter re-pinned.
- Owner biometric lockout (0.75 in variance band) → threshold 0.60.
- Microsoft-voice failover after Fish 429 → Fish-only re-raise + honest text.
- Arabic app names missing whitelist → alias table + basename/stem matching.
- Voice «نعم» bypassing pending confirmations → coordinator-first routing.
- Doubled core (venv + system polling) → `sara.ps1` kills both, verifies ports.

## See also (graph links)

- [12 — Security](../12-SECURITY.md) · [09 — Decisions](../09-DECISIONS.md)
- [API Wiring Audit](./API_WIRING_AND_USAGE_AUDIT.md)
- [Map of Testing & Audits](../00-MAP-OF-TESTING-AND-AUDITS.md)
