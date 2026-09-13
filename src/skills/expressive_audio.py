"""Expressive audio inventory (Leap 4, Phase-4) — Fish Audio S2.1 tag authority.

Single source of truth for which inline tags Sara may emit. Autonomous LLM
placement (Q3: no hardcoded word→tag binding); this module only VALIDATES.
stdlib-only on purpose — imported by src/voice.py, so zero dependency risk.

Calibration basis: tests/reports/FISH_TAG_CALIBRATION.md (6/6 GO, paren
passthrough evidenced by byte deltas). Scarcity caps live with the caller
(src/voice.py sanitize_tags modes), not here.
"""

from __future__ import annotations

from typing import Final

# Full supported spectrum (Q3 mandate): playful/warm, pensive, relief/empathy,
# calm/intimate, surprise/alert, decisive/formal + Fish basic/advanced
# emotions, minus the hard-excluded set below. Canonical lowercase.
ALLOWLIST_BRACKET: Final[frozenset[str]] = frozenset(
    {
        # Playful / warm
        "laughing",
        "chuckling",
        "chuckle",
        "giggle",
        "giggling",
        "snicker",
        "snickering",
        # Pensive / thoughtful
        "humming",
        "hum",
        "hesitant",
        "hesitating",
        "pause",
        "long pause",
        # Relief / empathy
        "sigh",
        "sighing",
        "exhale",
        "exhaling",
        "inhale",
        "inhaling",
        "breath",
        "breathing",
        "relieved",
        "relief",
        # Calm / intimate
        "whispering",
        "whisper",
        "soft voice",
        "calm",
        "calmly",
        "relaxed",
        "relaxing",
        "gentle",
        "gently",
        # Surprise / alert
        "gasp",
        "gasping",
        "surprised",
        "shocked",
        "astonished",
        # Decisive / formal
        "confident",
        "confidently",
        "clears throat",
        "clear throat",
        "emphasis",
        "emphasize",
        # Basic emotions (Fish 24, minus hostile)
        "happy",
        "excited",
        "sad",
        "delighted",
        "curious",
        "interested",
        "grateful",
        "proud",
        "amused",
        "embarrassed",
        "confused",
        "content",
        "hopeful",
        # Advanced emotions (Fish 25, minus hostile)
        "anxious",
        "unhappy",
        "impatient",
        "guilty",
        "reluctant",
        "keen",
        "disapproving",
        "denying",
        "serious",
        "sarcastic",
        "conciliative",
        "comforting",
        "sincere",
        "yielding",
        "painful",
        "awkward",
        "indifferent",
        "negative",
        # Vocal effects (non-crowd, non-tearful)
        "laugh",
        "cough",
        "coughing",
        "groaning",
        "groan",
        "panting",
        "yawning",
        "yawn",
    }
)

# Hard-excluded even though Fish renders them: shouting/crowd/tearful lanes
# never fit Sara (firmness is lexical, audiences break single-speaker
# identity, tears gate on genuine grief only — enforced by absence here).
BLOCKLIST_BRACKET: Final[frozenset[str]] = frozenset(
    {
        "shouting",
        "shout",
        "screaming",
        "scream",
        "angry",
        "furious",
        "crying",
        "crying loudly",
        "sobbing",
        "sob",
        "snoring",
        "snore",
        "crowd laughing",
        "background laughter",
        "audience laughing",
        "audience laughter",
        "scornful",
        "sneering",
        "disdainful",
        "hysterical",
        "maniacal",
    }
)

# Paren paralanguage cues: OpenRouter normalization behavior was UNVERIFIED
# until calibration evidenced passthrough (byte-delta note in the report).
PARALANGUAGE_PAREN_ENABLED: Final[bool] = True
ALLOWLIST_PAREN: Final[frozenset[str]] = frozenset(
    {"sigh", "breath", "laugh", "cough", "lip-smacking", "break", "long-break"}
)

# Scarcity caps per turn kind (enforced by sanitize_tags, not placement).
CAP_TECHNICAL: Final[int] = 0
CAP_ROUTINE: Final[int] = 1
CAP_EXTENDED: Final[int] = 2
CAPS: Final[dict[str, int]] = {
    "technical": CAP_TECHNICAL,
    "routine": CAP_ROUTINE,
    "extended": CAP_EXTENDED,
}


def is_supported_tag(tag: str, *, parens: bool = False) -> bool:
    """Inventory check on the canonical (lowercased, stripped) tag body."""
    body = (tag or "").strip().lower()
    if not body:
        return False
    if parens:
        return PARALANGUAGE_PAREN_ENABLED and body in ALLOWLIST_PAREN
    return body in ALLOWLIST_BRACKET
