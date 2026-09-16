# Release v1.1 — Pass 4 (2026-09-04)

## Architectural leaps
- **Shutdown cleanliness proven at the loop level**: every background loop
  cancels with a pure CancelledError — a mid-tick shutdown never leaks a
  wrapper exception into the gather (the run_bot finally contract now rests
  on a tested primitive, not an assumption). Live-verified for the
  self-evolution worker and contract-tested for the loop family.

## Performance gains
- Verified all five run_forever loops are strict tick-gated idlers (idle
  ticks cost one sleep; no spin, no busy-wait anywhere).

## Humanization
- Indirect: the loops being provably reapsafe is what lets the owner
  restart Sara freely mid-day without ghost messages arriving later.

## Verification
- Gate: 494 passed / 1 skipped / ruff + security + docs green.
