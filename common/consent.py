"""Shared consent grammar (sprint-3 3.3; 3.4's confirmation flow imports the same rules).

The affirmative must FOLLOW an explicit prompt in the same conversational window —
enforced by the callers keeping prompt-minted pending state; this module only judges
the reply text itself. Ambiguous replies are never guessed as consent.

Remediation 1.8 (owner 2026-09-03, audit S-4): consent is a STANDALONE short
yes — at most 3 tokens, opening with an affirmative, and carrying NO negation
or reservation word (بس/لا/مش/مو/لسا/بعد شوي/بعدين/يمكن). «نعم بس استنى»
is a reservation, not a launch order; it never executes a guarded action.
"""

from __future__ import annotations

from typing import Final

AFFIRMATIVES: Final[tuple[str, ...]] = (
    "نعم",
    "ايه",
    "إيه",
    "أيوه",
    "ايوه",
    "أكيد",
    "اكيد",
    "تمام",
    "ok",
    "yes",
)
# A guarded action launches on a clean yes alone — any of these anywhere in
# the reply makes it a reservation/refusal, whatever it started with.
WITHHOLD_WORDS: Final[tuple[str, ...]] = (
    "لا",
    "بس",
    "مش",
    "مو",
    "لسا",
    "لسه",
    "بعد شوي",
    "بعدين",
    "يمكن",
    "وقف",
    "ألغها",
    "الغها",
)
MAX_CONSENT_TOKENS: Final[int] = 3
SUMMARY_PROMPT: Final[str] = "هل بتحب ألخص لك شو رح أعمل هسا؟"


def is_affirmative(text: str) -> bool:
    tokens = text.strip().casefold().split()
    if not tokens or tokens[0] not in AFFIRMATIVES:
        return False
    if len(tokens) > MAX_CONSENT_TOKENS:
        return False  # a clean yes is short; a tirade is a conversation, not consent
    return not any(word in WITHHOLD_WORDS for word in tokens)
