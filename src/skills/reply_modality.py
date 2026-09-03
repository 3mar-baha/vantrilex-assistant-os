"""Reply-modality skill (owner directive 2026-09-03): Sara chooses her reply
surface — a text message or a voice note — mirroring the owner's channel with
a 70/30 split: he sends text -> 70% text / 30% voice; he sends voice -> the
ratio flips (70% voice / 30% text). An EXPLICIT owner request («رد صوتي» /
«رد نصي») always wins, whatever the channel. Exactly ONE surface either way
(the remediation-1.4 no-duplicates contract is untouched).
"""

import random
import re
from typing import Final

VOICE_FORCE_RE: Final = re.compile(r"ردّ?\s*(ب)?صوتي|بصوتك|جاوبيني\s*(ب)?صوت|الرد\s*(ب)?صوتي")
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
    if re.search(r"ردّ?\s*(ب)?صوتي|بصوتك|جاوبيني\s*(ب)?صوت|الرد\s*(ب)?صوتي", text):
        return "voice"
    return None


def choose_reply_modality(*, voice_origin: bool, rng=random.random) -> str:
    """70/30 mirror: same-channel 70%, cross-channel 30%. rng injectable for
    deterministic tests. Exactly one surface is returned — never both."""
    roll = rng()
    if voice_origin:
        return "voice" if roll < 0.70 else "text"
    return "text" if roll < 0.70 else "voice"


def decide_reply_modality(text: str, voice_origin: bool) -> str:
    """The shipped decision: an explicit request in the owner's text always
    wins; otherwise the 70/30 mirror decides."""
    forced = forced_modality(text)
    if forced:
        return forced
    return choose_reply_modality(voice_origin=voice_origin)
