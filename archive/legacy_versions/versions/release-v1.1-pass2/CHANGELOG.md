# Release v1.1 — Pass 2 (2026-09-04)

## Architectural leaps
- **Edge-case hardening of the v1.1 lanes**: the affect engine now survives
  brain timeouts (envelope stays clean, mode neutral) and REJECTS invalid
  mode words (a garbled/malicious verdict can never inject into the prompt);
  the proactive outreach rolls its 3/day cap with the LOCAL day (the
  midnight-rollover lesson, now proven) and honors the exact window
  boundaries (08:00 sharp opens, 22:30 sharp still inside).

## Performance gains
- None claimed this pass — it was correctness-only (4 new edge tests, zero
  new runtime code; the lanes were already lean).

## Humanization
- The affect guide's failure mode IS the human one: when Sara can't read
  the room, she doesn't guess a mood — she just answers plainly. Verified.

## Verification
- Gate: 493 passed / 1 skipped / 86.03% branch / ruff + security + docs green.
