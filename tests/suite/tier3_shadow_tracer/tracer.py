"""Tier 3 — autonomous shadow user + deep background tracer.

Headless synthetic prober: presents natural multi-turn scenarios while
monitoring the background execution plane (candidate scoring, tool rationale,
latency per sub-operation, state mutations, self-reflection records).

When behavior deviates from principles, `diagnose()` outputs the exact failure
point + minimal structural fix (hidden-failure diagnosis requirement).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from src.cognition import (
    ReflectiveTrace,
    deduce,
    evaluate_candidates,
    expand_horizon,
    explain_choice,
)


@dataclass
class TurnTrace:
    text: str
    winner: str
    confidence: float
    rationale: str
    latency_ms: float
    alternatives: list[str] = field(default_factory=list)
    horizon: list[str] = field(default_factory=list)
    friction: list[str] = field(default_factory=list)


@dataclass
class ShadowReport:
    turns: list[TurnTrace] = field(default_factory=list)

    def summary(self) -> str:
        lines = []
        for t in self.turns:
            lines.append(
                f"«{t.text[:40]}» → {t.winner}@{t.confidence:.2f} "
                f"({t.latency_ms:.0f}ms) | {t.rationale[:80]}"
            )
        return "\n".join(lines)


class ShadowTracer:
    """Synthetic owner + white-box observer over the cognition layer."""

    def __init__(self) -> None:
        self.trace = ReflectiveTrace()
        self.report = ShadowReport()
        self.tool_calls: list[dict[str, Any]] = []

    async def run_query(self, text: str, *, simulate_outcome: str = "ok") -> TurnTrace:
        t0 = time.perf_counter()
        ranked = evaluate_candidates(text, trace=self.trace)
        hyp = deduce(text, trace=self.trace)
        latency = (time.perf_counter() - t0) * 1000
        horizon = expand_horizon(hyp.tool) if hyp.tool != "none" else []
        # Simulate the tool outcome so the NEXT turn can show adaptation.
        if hyp.tool != "none":
            ok = simulate_outcome == "ok"
            self.trace.record_outcome(hyp.tool, ok, note=simulate_outcome if not ok else "")
            self.tool_calls.append({"tool": hyp.tool, "arg": hyp.arg, "ok": ok})
        turn = TurnTrace(
            text=text,
            winner=hyp.tool,
            confidence=hyp.confidence,
            rationale=explain_choice(ranked),
            latency_ms=latency,
            alternatives=[h.tool for h in ranked[1:4]],
            horizon=horizon,
            friction=self.trace.friction_notes(),
        )
        self.report.turns.append(turn)
        return turn

    def diagnose(self, turn: TurnTrace, *, expected: str) -> str:
        """Hidden-failure diagnosis: exact deviation point + minimal fix."""
        if turn.winner == expected:
            return f"OK: {turn.winner} matches principle (conf {turn.confidence:.2f})"
        return (
            f"DEVIATION at intent-deduction: text «{turn.text[:50]}» → {turn.winner} "
            f"(conf {turn.confidence:.2f}), expected {expected}. "
            f"Rationale: {turn.rationale[:160]}. "
            f"Minimal fix: extend _{expected.upper()}_GOALS with the missed paraphrase, "
            f"not a new regex branch; re-run shadow suite."
        )
