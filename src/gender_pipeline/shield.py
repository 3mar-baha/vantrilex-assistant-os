"""Stage 0 — first-person feminine protection (the shield).

Runs BEFORE every rewrite stage: masked spans are restored verbatim after.
Sara MUST keep feminine self-reference: أنا رتبّيت / أنا عملت / ما قدرت /
حاولت / رح أكون / أنا جاهزة / أنا مبسوطة / أنا متأكدة / كنت مشغولة.

Two mechanisms (both conservative):
- ANNA rule: «أنا» + next token (1st-person predication is unambiguous).
- Explicit phrases without أنا (كنت مشغولة). Standalone past verbs like
  قدرت/حاولت need NO shield entry: no rewrite rule matches them (all verb
  rules key on ي-suffixed 2nd-person forms), which the preservation tests pin.
"""

from __future__ import annotations

import re
from typing import Final

# Mask tokens live in Unicode private use: no rule pattern can match across
# them, and they never collide with Arabic/Latin/diacritic text.
_MASK_OPEN: Final[str] = "\ue100"
_MASK_CLOSE: Final[str] = "\ue101"

# Explicit shield phrases (no أنا present to trigger the general rule).
SHIELD_PHRASES: Final[tuple[str, ...]] = ("كنت مشغولة",)

_ANNA_RE: Final = re.compile(r"أنا\s+\S+")


def mask(text: str) -> tuple[str, list[str]]:
    """Replace shielded spans with placeholders. Returns (masked, vault)."""
    vault: list[str] = []

    def _store(match: re.Match[str]) -> str:
        vault.append(match.group(0))
        return f"{_MASK_OPEN}{len(vault) - 1}{_MASK_CLOSE}"

    masked = text
    # Explicit phrases first (longest wins), then the general أنا rule.
    for phrase in sorted(SHIELD_PHRASES, key=len, reverse=True):
        start = 0
        while True:
            idx = masked.find(phrase, start)
            if idx < 0:
                break
            vault.append(phrase)
            masked = (
                masked[:idx]
                + f"{_MASK_OPEN}{len(vault) - 1}{_MASK_CLOSE}"
                + masked[idx + len(phrase) :]
            )
            start = idx + 1
    masked = _ANNA_RE.sub(lambda m: _store(m), masked)
    return masked, vault


def unmask(text: str, vault: list[str]) -> str:
    """Restore shielded spans verbatim."""

    def _restore(match: re.Match[str]) -> str:
        idx = int(match.group(1))
        return vault[idx] if 0 <= idx < len(vault) else match.group(0)

    return re.sub(_MASK_OPEN + r"(\d+)" + _MASK_CLOSE, _restore, text)
