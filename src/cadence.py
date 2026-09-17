"""P2.2 rotation policy (master transformation plan, Phase P2.2).

Pure cadence logic: the 10-turn refresh trigger, the posture-conditioned
domain rotation key, and the MOBILE derivation rule. No I/O, no vault reads —
the transport layer owns persistence (src/turn_counter.py).
"""

from __future__ import annotations

from typing import Final, Literal

CADENCE_TURNS: Final[int] = 10
DOMAINS: Final[tuple[str, ...]] = ("dialect", "humor", "grace", "spotlight")

Posture = Literal["FOCUS", "FRAGMENTED", "AWAY", "NORMAL", "MOBILE"]


def refresh_due(count: int, *, session_fresh: bool = False) -> bool:
    """True on every 10th human turn, or on session start with a stale-but-
    nonzero persisted count (short sessions can never starve the mechanism)."""
    if count <= 0:
        return False
    if count % CADENCE_TURNS == 0:
        return True
    return bool(session_fresh)


def derive_context(*, bridge_posture: str, telegram_active: bool) -> Posture:
    """MOBILE derivation: an active Telegram turn while the desktop bridge
    reads AWAY means on-the-go. Unknown postures degrade to NORMAL, never
    AWAY-by-default (cold boot must not misroute)."""
    if bridge_posture not in ("FOCUS", "FRAGMENTED", "AWAY", "NORMAL"):
        return "NORMAL"
    if telegram_active and bridge_posture == "AWAY":
        return "MOBILE"
    return bridge_posture  # type: ignore[return-value]


def rotation_domain(
    *,
    context: Posture,
    last_domain: str | None,
    turn_index: int = 0,
) -> str:
    """Domain for this refresh. FOCUS forces the technical lane and suppresses
    humor/grace; MOBILE and FRAGMENTED take concise lanes; NORMAL wheels
    forward, never repeating the previous domain back-to-back."""
    if context == "FOCUS":
        return "spotlight"
    if context in ("MOBILE", "FRAGMENTED"):
        candidates = [d for d in ("spotlight", "dialect") if d != last_domain]
        return candidates[turn_index % len(candidates)]
    wheel = [d for d in DOMAINS if d != last_domain] or list(DOMAINS)
    return wheel[turn_index % len(wheel)]
