"""Tier 3 — AI Coach Agent: multi-scenario behavioral coaching over the tracer.

The coach subjects Sara's decision plane (cognition ranking + latency +
friction ledger) to planned scenarios across four dimensions and returns a
verdict per scenario plus a minimal structural fix on deviation:

- initiative: contextual value vs interruption cost (engage now or defer)
- brevity: response depth modulated by the user's pace (short vs detailed)
- ambiguity: irreversible actions need concise clarification, not blind acts
- modality: voice demand -> voice, explicit text -> text, else origin default

All judgements are trace-local heuristics (no LLM, no latency overhead);
lessons land in `ReflectiveTrace` via the shared tracer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.skills.capabilities import IRREVERSIBLE_TOOLS
from tests.suite.tier3_shadow_tracer.tracer import ShadowTracer, TurnTrace

BUSY_MARKERS = ("مشغول", "بعدين", "لا تزعج", "busy")
VOICE_DEMAND_MARKERS = ("صوتية", "فويس", "بصوتك", "اسمع صوتك")
TEXT_DEMAND_MARKERS = ("رد نصي", "كتابة", "لخصي الجواب كتابة")


@dataclass
class CoachingVerdict:
    scenario: str
    dimension: str
    decision: str  # engage|defer|short|detailed|clarify|execute|voice|text
    expected: str
    passed: bool
    rationale: str
    fix: str = ""


@dataclass
class CoachReport:
    verdicts: list[CoachingVerdict] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for v in self.verdicts if v.passed)


class CoachAgent:
    """Headless coach: runs scenarios through a ShadowTracer, judges the plane."""

    def __init__(self, tracer: ShadowTracer | None = None) -> None:
        self.tracer = tracer or ShadowTracer()
        self.report = CoachReport()

    async def scenario(
        self,
        name: str,
        dimension: str,
        text: str,
        *,
        expected: str,
        context: dict[str, Any] | None = None,
    ) -> CoachingVerdict:
        context = context or {}
        turn = await self.tracer.run_query(text)
        judge = {
            "initiative": self._judge_initiative,
            "brevity": self._judge_brevity,
            "ambiguity": self._judge_ambiguity,
            "modality": self._judge_modality,
        }[dimension]
        decision, rationale = judge(turn, text, context)
        passed = decision == expected
        verdict = CoachingVerdict(
            scenario=name,
            dimension=dimension,
            decision=decision,
            expected=expected,
            passed=passed,
            rationale=rationale,
            fix=""
            if passed
            else (
                f"DEVIATION in {dimension} for «{text[:40]}»: got {decision}, "
                f"wanted {expected} ({rationale[:120]}). Minimal fix: "
                f"{self._fix_hint(dimension)}"
            ),
        )
        self.report.verdicts.append(verdict)
        return verdict

    def _judge_initiative(self, turn: TurnTrace, text: str, ctx: dict) -> tuple[str, str]:
        busy = any(m in text for m in BUSY_MARKERS) or ctx.get("user_busy", False)
        value = ctx.get("value", "low")
        if busy and value != "critical":
            return "defer", "interruption cost beats contextual value"
        if value in ("high", "critical"):
            return "engage", "contextual value justifies engagement"
        return "defer", "low value, no interruption warranted"

    def _judge_brevity(self, turn: TurnTrace, text: str, ctx: dict) -> tuple[str, str]:
        # Principle: an explicit depth ask outranks word count — «اشرحلي»
        # is short text demanding a long answer.
        pace = ctx.get("pace", "normal")
        if pace == "deep" or "اشرح" in text or "بالتفصيل" in text:
            return "detailed", "user asked for depth"
        if pace == "fast" or len(text.split()) <= 4:
            return "short", "user pace is fast — 1-2 lines max"
        return "short", "default Sara brevity (chat bubbles, not essays)"

    def _judge_ambiguity(self, turn: TurnTrace, text: str, ctx: dict) -> tuple[str, str]:
        # Principle: ambiguity is a missing target, not a low score — a named
        # irreversible act executes; a bare verb clarifies in one short line.
        if turn.winner in IRREVERSIBLE_TOOLS and not _arg_names_target(text):
            return "clarify", f"irreversible {turn.winner} without a clear target"
        return "execute", f"{turn.winner}@{turn.confidence:.2f} is actionable"

    def _judge_modality(self, turn: TurnTrace, text: str, ctx: dict) -> tuple[str, str]:
        if any(m in text for m in TEXT_DEMAND_MARKERS):
            return "text", "explicit text request wins"
        if any(m in text for m in VOICE_DEMAND_MARKERS):
            return "voice", "voice demand wins"
        return ("voice" if ctx.get("voice_origin") else "text"), "origin default"

    @staticmethod
    def _fix_hint(dimension: str) -> str:
        return {
            "initiative": "retune value-vs-cost weights, not a new timer.",
            "brevity": "extend pace signals (length/history), not a length constant.",
            "ambiguity": "add the missed target phrasing to the tool's capability markers.",
            "modality": "check demand-gate ordering (explicit text first).",
        }[dimension]


def _arg_names_target(text: str) -> bool:
    """A target exists when the text names something beyond the bare verb."""
    return len(text.split()) >= 3
