# Release v1.1 — Pass 1 (2026-09-04)

## Architectural leaps
- **The v1.1 intelligence suite landed whole** (this session): multi-speaker
  diarization (CPU-only energy windows + ECAPA clustering + Contacts
  attribution + per-turn Whisper), the affect/trajectory engine (FAST-judged
  banter-vs-fatigue guidance in every envelope), the paralinguistic pipeline
  (deterministic DSP acoustic texture on every voice note), and the
  self-evolution engine (nightly idiom PROPOSALS — owner-reviewed, never
  silent).
- **Vault race condition fixed (audit C-9/V-4, the last MAJOR in the
  deferred queue)**: every write serializes on a client-wide asyncio.Lock;
  a 409 re-runs the WHOLE merge (re-read + re-append onto the LATEST remote)
  instead of re-PUTting stale content — concurrent ledger writes can no
  longer silently drop each other's sections. Shutdown now gathers in-flight
  persist tasks BEFORE closing the vault session (the last exchanges never
  die at restart).
- **Round-3 live defects fixed**: a ~2 s voice note can never lock the owner
  out as a guest (inconclusive clips ride middleware trust; re-enrollment
  blends a running centroid); a transient Fish 429 retries once and never
  becomes a capability denial; tool results narrate in 1-2 warm lines (no
  more support-desk manuals); long replies re-split into 2-3 short bubbles.

## Performance gains
- 482→489 tests while the tree SHRANK this session's baseline: import
  profile dominated by aiogram (2.26 s of the 2.84 s total); Sara's own
  path is featherweight. Vault writes now O(1) serialized instead of
  racy-retried.

## Humanization
- The reply channel is the ROUTER's judgment (voice_reply in the same FAST
  verdict — the model reads intent, not a dice roll or a brittle regex).
- The persona contract now bans robotic self-disclosure BY NAME, mandates
  the warm joke deflection, reads through typos silently, and answers in
  2-3 short human bubbles — all AST/contract-tested.
- Affect + acoustic context arrive as DATA markers, never as instructions —
  the brain reasons about tone with full freedom.

## Verification
- Gate: 489 passed / 1 skipped / 86.01% branch / security + docs green.
- Sacred floors green throughout (owner-middleware, whitelist-guardrail,
  guest-lockdown, consent-grammar).
