"""Tier 1 — benchmark matrix contracts (mission Stage-3 slice). Hermetic, no LLM.

Locks the 500-turn matrix shape (175/150/175, unique IDs, valid labels) and
the routing-accuracy floor. If cognition markers evolve and accuracy drifts,
triage explicitly: either the seeds went stale or the classifier regressed —
both readings are recorded in the dry-run log, never silently absorbed.
"""

from scripts.benchmark_500 import build_matrix, clause_tools
from src.cognitive_dag import classify_weight
from src.dispatcher import _VALID_TOOLS


def test_matrix_shape_exact():
    matrix = build_matrix()
    assert len(matrix) == 500
    counts: dict[str, int] = {}
    for turn in matrix:
        counts[turn["category"]] = counts.get(turn["category"], 0) + 1
    assert counts == {"A": 175, "B": 150, "C": 175}
    assert len({t["id"] for t in matrix}) == 500
    for turn in matrix:
        assert turn["exp_weight"] in (1, 2, 3, 4, 5)
        assert isinstance(turn["critical"], bool)
        assert set(turn["exp_tools"]) <= set(_VALID_TOOLS), turn["id"]
        if turn["critical"]:
            assert turn["exp_weight"] == 5


def test_routing_accuracy_floor():
    matrix = build_matrix()
    w_ok = t_ok = 0
    for turn in matrix:
        plan = classify_weight(turn["text"])
        w_ok += plan.weight == turn["exp_weight"] and plan.critical == turn["critical"]
        t_ok += set(clause_tools(turn["text"])) == set(turn["exp_tools"])
    assert w_ok / len(matrix) >= 0.98, f"weight accuracy drifted: {w_ok}/500"
    assert t_ok / len(matrix) >= 0.98, f"tool accuracy drifted: {t_ok}/500"
