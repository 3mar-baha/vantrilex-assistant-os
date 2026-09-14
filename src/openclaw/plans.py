"""ActionDAG builder + confirmation gate (Phase 2, Single-Brain policy).

Planning lives HERE: the core converts an approved goal into a typed DAG
and decides GO vs PARK before anything touches the tunnel. The daemon-side
breaker re-verifies every op (defense in depth) — this gate is the honest
ask, the breaker is the hard wall.

Coordinator binding is duck-typed (`has_confirmation(tool, arg) -> bool`),
the same seam `src/decision_loop.py` uses — Phase 3 binds the real
PCActionCoordinator; until then None parks every committing DAG.
"""

from __future__ import annotations

import itertools
import time
from typing import Any, Final

from loguru import logger

from bridge.openclaw.breaker import SafetyCircuitBreaker
from src.openclaw.protocol import ActionDAG, Op

PARK_LINE_AR: Final[str] = "هاي الخطوة بتحتاج تأكيدك الصريح قبل ما أنفذها — أكّدلي وأنا بكمل فوراً."

_plan_counter = itertools.count(1)


def build_dag(*, goal: str, ops: list[Op], weight: int = 1) -> ActionDAG:
    """Assemble a validated DAG and stamp a unique plan id."""
    dag = ActionDAG(
        goal=(goal or "").strip(),
        ops=list(ops),
        weight=max(1, int(weight)),
        plan_id=f"oc-{int(time.time())}-{next(_plan_counter)}",
    )
    if not dag.goal:
        raise ValueError("openclaw plan needs a non-empty goal")
    return dag


def irreversible_ops(dag: ActionDAG) -> list[Op]:
    """Ops the breaker would gate — recomputed, never trusted from the wire."""
    return [op for op in dag.ops if SafetyCircuitBreaker.classify(op) == "irreversible"]


def needs_confirmation(dag: ActionDAG) -> bool:
    return bool(irreversible_ops(dag))


def gate(dag: ActionDAG, *, coordinator: Any = None, tool: str = "openclaw") -> str:
    """GO (execute now) or PARK (honest ask, zero execution). A committing
    DAG without a recorded confirmation parks — no exceptions, no retries
    around the owner."""
    if not needs_confirmation(dag):
        return "go"
    has = getattr(coordinator, "has_confirmation", None)
    try:
        confirmed = bool(has(tool, dag.goal)) if callable(has) else False
    except Exception as error:  # noqa: BLE001 — a dead coordinator parks, never passes
        logger.warning("openclaw gate coordinator failed -> park: {}", error)
        confirmed = False
    if confirmed:
        return "go"
    logger.warning("openclaw gate parked committing DAG {}", dag.plan_id)
    return "park"
