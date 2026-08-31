"""Shared consent grammar (sprint-3 3.3; 3.4's confirmation flow imports the same rules).

The affirmative must FOLLOW an explicit prompt in the same conversational window —
enforced by the callers keeping prompt-minted pending state; this module only judges
the reply text itself. Ambiguous replies are never guessed as consent.
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
SUMMARY_PROMPT: Final[str] = "هل بتحب ألخص لك شو رح أعمل هسا؟"


def is_affirmative(text: str) -> bool:
    tokens = text.strip().casefold().split()
    return bool(tokens) and tokens[0] in AFFIRMATIVES
