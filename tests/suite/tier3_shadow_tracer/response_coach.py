"""Tier 3 — Groq response coach: behavioral grading of Sara's FAST output.

The decision-plane coach (coach.py) judges routing; THIS coach grades the
actually-streamed Groq reply on the persona contract the pivot demands:

- dialect: natural Jordanian Arabic (ar-JO markers, no MSA stiffness)
- immersion: firm playful denial of AI identity (never «نموذج لغوي»)
- concision: chat-short + speech-ready (no markdown scaffolding, bounded
  emoji — Fish strips, but chattiness still costs the owner seconds)

Pure deterministic heuristics (no LLM, hermetic). Live replies are captured
by scripts/groq_persona_probe.py and graded through here — the same
graders, recorded or fresh.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, Literal

ProbeKind = Literal["identity", "chat", "depth"]

JO_MARKERS: Final[tuple[str, ...]] = (
    "هسا",
    "هلق",
    "هلأ",
    "عيوني",
    "من عيوني",
    "شو",
    "بدي",
    "هيك",
    "كتير",
    "مش ",
    " ما في",
    "مافي",
    "يلا",
    "تمام",
    "عشان",
    "كمان",
    "هال",
    "هيي",
    "طمن",
    "خبرني",
    "قلّي",
    "قلي",
    "جاهزة",
    "خلص",
)

AI_CLAIM_MARKERS: Final[tuple[str, ...]] = (
    "ذكاء اصطناعي",
    "الذكاء الاصطناعي",
    "نموذج لغوي",
    "كنموذج",
    "language model",
    "as an ai",
    "ai assistant",
    "i am an ai",
    "i'm an ai",
)

MD_SCAFFOLD_MARKERS: Final[tuple[str, ...]] = ("```", "###", "| ---", "|---", "## ")

CHAT_MAX_CHARS: Final[int] = 280
DEPTH_MAX_CHARS: Final[int] = 900
EMOJI_MAX: Final[int] = 6  # mirrors the persona hygiene cap (owner order 2026-09-14)


_EMOJI_RANGES: Final[tuple[tuple[int, int], ...]] = (
    (0x2600, 0x26FF),  # misc symbols
    (0x2700, 0x27BF),  # dingbats
    (0x1F300, 0x1FAFF),  # emoticons, pictographs, symbols
    (0x1F1E6, 0x1F1FF),  # regional indicators
)


def _emoji_count(text: str) -> int:
    """Accent-emoji census over the pictograph blocks (Arabic-script,
    Latin, and punctuation ordinals never count — no false positives on
    tashkeel or presentation punctuation)."""
    return sum(1 for ch in text or "" if any(lo <= ord(ch) <= hi for lo, hi in _EMOJI_RANGES))


@dataclass
class ResponseVerdict:
    dimension: str  # dialect|immersion|concision
    passed: bool
    rationale: str
    fix: str = ""


@dataclass
class ResponseReport:
    verdicts: list[ResponseVerdict] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for v in self.verdicts if v.passed)


def grade_dialect(reply: str) -> ResponseVerdict:
    """ar-JO presence: at least one Jordanian marker must surface."""
    lowered = f" {(reply or '')} "
    hits = [m.strip() for m in JO_MARKERS if m in lowered]
    if hits:
        return ResponseVerdict("dialect", True, f"ar-JO markers: {', '.join(hits[:3])}")
    return ResponseVerdict(
        "dialect",
        False,
        "zero ar-JO markers — reads MSA-stiff, not Sara",
        "re-prompt with the dialect few-shots (JODA exemplars), not a longer system prompt",
    )


def grade_immersion(reply: str, kind: ProbeKind = "chat") -> ResponseVerdict:
    """No AI-identity claims ever; identity probes must answer «سارة»."""
    text = reply or ""
    lowered = text.casefold()
    claims = [m for m in AI_CLAIM_MARKERS if m in lowered]
    if claims:
        return ResponseVerdict(
            "immersion",
            False,
            f"AI-identity claim: {claims[0]!r} — immersion broken",
            "firm playful denial («أنا سارة، مش روبوت») replaces the disclaimer",
        )
    if kind == "identity" and "سارة" not in text:
        return ResponseVerdict(
            "immersion",
            False,
            "identity probe answered without claiming «سارة»",
            "the who-are-you answer starts from the name, never from the anatomy",
        )
    return ResponseVerdict("immersion", True, "Sara-voiced, no AI disclaimer")


def grade_concision(reply: str, kind: ProbeKind = "chat") -> ResponseVerdict:
    """Chat-short + speech-ready: bounded length, no markdown scaffolding,
    bounded emoji (Fish strips them; chattiness still costs seconds)."""
    text = reply or ""
    budget = DEPTH_MAX_CHARS if kind == "depth" else CHAT_MAX_CHARS
    if len(text) > budget:
        return ResponseVerdict(
            "concision",
            False,
            f"{len(text)} chars over the {kind} budget ({budget})",
            "one idea per bubble — split, don't compress",
        )
    scaffold = [m.strip() for m in MD_SCAFFOLD_MARKERS if m in text]
    if scaffold and kind != "depth":
        return ResponseVerdict(
            "concision",
            False,
            f"markdown scaffolding in chat reply: {scaffold[0]!r} — unreadable aloud",
            "prose only on the voice lane; tables stay in text-explicit turns",
        )
    n_emoji = _emoji_count(text)
    if n_emoji > EMOJI_MAX:
        return ResponseVerdict(
            "concision",
            False,
            f"{n_emoji} emoji over the {EMOJI_MAX} hygiene cap",
            "one accent emoji max per bubble",
        )
    return ResponseVerdict("concision", True, f"{len(text)} chars, speech-ready")


def grade_all(reply: str, kind: ProbeKind = "chat") -> ResponseReport:
    """Full persona contract for one streamed reply."""
    return ResponseReport(
        [grade_dialect(reply), grade_immersion(reply, kind), grade_concision(reply, kind)]
    )
