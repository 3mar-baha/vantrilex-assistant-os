"""Cognitive task planning (mission DAG, Stage 2): dynamic Task Weight (1-5 +
Critical) plus an ephemeral in-memory todo list.

Pure logic, zero LLM calls: weight comes from clause structure (the
drill-hardened `_CONNECTORS` splitter shared with cognition.py) composed with
per-clause `deduce()` verdicts; the todo is built, checked off during the
tool flow, and flushed from memory at turn end. Nothing persists — the vault
ledger remains the only durable trace.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from loguru import logger

from src.cognition import _CONNECTORS, deduce

# Emergency markers: outages, crashes, production pain — in either language.
# Matched case-insensitively on the raw text (Latin) and literally (Arabic).
EMERGENCY_MARKERS: Final[tuple[str, ...]] = (
    "outage",
    "crash",
    "production down",
    "build fail",
    "pipeline fail",
    "alert",
    "سيرفر واقع",
    "السيرفر واقع",
    "عطل",
    "طوارئ",
    "الحقني",
    "النظام واقع",
    "الموقع واقع",
)

CRITICAL_WEIGHT: Final[int] = 5


@dataclass(frozen=True)
class TaskPlan:
    """Weight 1-5 (+critical flag), estimated steps, per-clause tool picks."""

    weight: int
    critical: bool
    estimated_steps: int
    clauses: int
    tools: tuple[str, ...]


def _clauses(text: str) -> list[str]:
    return [p for p in _CONNECTORS.split(text or "") if p.strip()]


def classify_weight(text: str) -> TaskPlan:
    """Deterministic weight from structure, never vibes.

    - Critical: any emergency marker (weight pinned 5, 1 step: mitigate now).
    - 0 tool clauses → weight 1 (banter/facts/reassurance, synthesis only).
    - 1 tool → weight 2, 2 tools → weight 3 (focused, +1 synthesis step).
    - 3+ tools → weight 4 (3 tools) / 5 (4+ tools), steps = tools + 1.
    """
    raw = text or ""
    lowered = raw.lower()
    parts = _clauses(raw)
    picked: list[str] = []
    for part in parts:
        try:
            hyp = deduce(part)
        except Exception as error:  # noqa: BLE001 — deduction never breaks planning
            logger.debug("cognitive_dag deduce failed on clause: {}", error)
            continue
        if hyp.tool != "none" and hyp.tool not in picked:
            picked.append(hyp.tool)
    tools = tuple(picked)
    if any(m in lowered or m in raw for m in EMERGENCY_MARKERS):
        # Critical pins weight/steps (mitigate NOW, no DAG), but still names
        # the deduced tools so the trace stays truthful (telemetry on a dead
        # server is signal, not a plan).
        return TaskPlan(
            weight=CRITICAL_WEIGHT,
            critical=True,
            estimated_steps=1,
            clauses=len(parts),
            tools=tools,
        )
    if not tools:
        return TaskPlan(weight=1, critical=False, estimated_steps=1, clauses=len(parts), tools=())
    if len(tools) == 1:
        return TaskPlan(
            weight=2, critical=False, estimated_steps=2, clauses=len(parts), tools=tools
        )
    if len(tools) == 2:
        return TaskPlan(
            weight=3, critical=False, estimated_steps=3, clauses=len(parts), tools=tools
        )
    weight = 4 if len(tools) == 3 else 5
    return TaskPlan(
        weight=weight,
        critical=False,
        estimated_steps=len(tools) + 1,
        clauses=len(parts),
        tools=tools,
    )


@dataclass
class TodoItem:
    label: str
    done: bool = False


class EphemeralTodo:
    """In-memory execution plan: [ ] Step 1 -> [ ] Step 2 -> [ ] Synthesis.

    Checked off as the tool flow advances; flush() returns the transcript and
    frees memory at turn end. Never persisted, never logged with secrets —
    labels carry tool names and short args only.
    """

    def __init__(self, steps: list[str] | None = None) -> None:
        self.items: list[TodoItem] = [TodoItem(label=s) for s in (steps or [])]

    @classmethod
    def from_plan(cls, plan: TaskPlan, router_arg: str = "") -> EphemeralTodo:
        steps = [f"{tool}:{router_arg}" if router_arg else tool for tool in plan.tools]
        steps.append("synthesis")
        return cls(steps)

    def check(self, tool: str) -> bool:
        """Mark the first pending item naming this tool done. Returns found."""
        for item in self.items:
            if not item.done and item.label.split(":")[0] == tool:
                item.done = True
                return True
        return False

    def pending_count(self) -> int:
        return sum(1 for item in self.items if not item.done)

    def render(self) -> str:
        return "\n".join(f"[{'x' if item.done else ' '}] {item.label}" for item in self.items)

    def flush(self) -> str:
        """Transcript + memory release. The turn owns nothing afterwards."""
        transcript = self.render()
        self.items.clear()
        return transcript
