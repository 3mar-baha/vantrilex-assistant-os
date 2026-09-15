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
from src.openclaw.intents import VALID_OPENCLAW_TOOLS
from src.openclaw.protocol import ActionDAG, Op, OpKind

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


def dag_for_tool(tool: str, arg: str = "", *, weight: int = 1) -> ActionDAG | None:
    """Mirror one pending registry step as an ActionDAG for observability.

    Returns None for non-OpenClaw tools (nothing to mirror). The mapping is
    deliberately conservative — probe-grade ops only, matching the Phase-2/3
    handler semantics (_do_openclaw_desktop's screenshot probe, fetch's
    extract, inspect's tree scan, browse's navigate-on-URL). Real multi-step
    DAGs arrive from the planner; this keeps every live openclaw turn
    DAG-observed without inventing actions the handlers won't take.
    """
    name = (tool or "").strip().casefold()
    if name not in VALID_OPENCLAW_TOOLS:
        return None
    clean = (arg or "").strip()
    if name == "openclaw_fetch":
        ops = [Op(op=OpKind.EXTRACT, value=clean or None)]
    elif name == "openclaw_inspect":
        ops = [Op(op=OpKind.INSPECT_TREE, target=clean or None)]
    elif name == "openclaw_desktop":
        ops = [Op(op=OpKind.SCREENSHOT)]
    elif name == "openclaw_browse":
        lowered = clean.casefold()
        ops = (
            [Op(op=OpKind.NAVIGATE, value=clean)]
            if lowered.startswith(("http://", "https://"))
            else []
        )
    else:  # pragma: no cover -- VALID set is exhaustive; belt first
        return None
    return build_dag(goal=clean or name, ops=ops, weight=weight)
