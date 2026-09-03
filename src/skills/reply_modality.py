"""Reply-modality skill (owner directives 2026-09-03, round-2 amended):
Sara's reply surface is chosen in priority order —
1. The owner's EXPLICIT channel request («رد صوتي» / «رد نصي») always wins;
2. Otherwise the ROUTER decides (voice_reply in the same FAST verdict — the
   model reads the intent and picks the channel; zero extra calls);
3. Origin default: a voice note begets a voice reply, text begets text.
The 70/30 probabilistic mirror is RETIRED (round-2: the model judges, not a
dice roll). This module now only parses the explicit request; the shell
composes the rest. Exactly ONE surface either way (remediation-1.4 contract).
"""

import random
import re
from typing import Final

VOICE_FORCE_RE: Final = re.compile(
    r"ردّ?\s*(ب)?صوتي|بصوتك|جاوبيني\s*(ب)?صوت|الرد\s*(ب)?صوتي"
    r"|(ابعثي|ابعتلي|بعتيلي|ارسلي|أرسلي)\s+(رسالة\s+)?صوتية|رسالة\s+صوتية|ملاحظة\s+صوتية"
    # live round-2 2026-09-03: «بدي اسمع صوتك» sailed past — hearing her voice
    # IS a voice turn; so is asking about her voice or telling her to speak.
    r"|(بدي|بدّي|بدي\s+اسمع|حابب\s+اسمع|سمعيني|اسمعي|خليني\s+اسمع|احكي\s+عن\s+حالك)\s*صوتك"
    r"|صوتك(?!\s+ك)\s*$|(احكيلي|حكيلي|احكي)\s+.*بصوت"
)
TEXT_FORCE_RE: Final = re.compile(
    r"ردّ?\s*(نصي|كتابي)|بالنص|رد\s*نص|جاوبيني\s*كتابة|اكتبيلي|بصيغة نص"
)


def forced_modality(text: str) -> str | None:
    """The owner's explicit channel request in his message, if any.

    Checked BEFORE the probabilistic chooser — an explicit request is always
    honored. Text-request patterns are evaluated first so «رد نصي مش صوتي»
    resolves to text (the strongest recent signal)."""
    if not text:
        return None
    if TEXT_FORCE_RE.search(text):
        return "text"
    if VOICE_FORCE_RE.search(text):
        return "voice"
    return None


def choose_reply_modality(*, voice_origin: bool, rng=random.random) -> str:
    """70/30 mirror: same-channel 70%, cross-channel 30%. rng injectable for
    deterministic tests. Exactly one surface is returned — never both."""
    roll = rng()
    if voice_origin:
        return "voice" if roll < 0.70 else "text"
    return "text" if roll < 0.70 else "voice"


def decide_reply_modality(text: str, voice_origin: bool) -> str | None:
    """Round-2 contract: return ONLY the owner's explicit channel request
    (or None). The router's voice_reply and the origin default compose in
    the shell — the model judges intent; this parser just obeys commands."""
    return forced_modality(text)
