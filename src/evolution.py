"""Sovereign evolution loop (P2): repeated trajectories -> owner proposals.

Phase 1 of the ratified lifecycle (capture -> distill -> AST-verify ->
sandbox -> owner-gated promotion). This module owns distill + verify +
proposal rendering. NOTHING here registers skills: proposals are markdown
the owner promotes by hand (teaching law). Sandbox execution + promotion
gates are P3 (OverlayVault harness).
"""

from __future__ import annotations

import ast
from typing import Any, Final

ALLOWED_IMPORTS: Final[frozenset[str]] = frozenset(
    {"re", "math", "json", "datetime", "collections", "itertools", "functools", "pathlib"}
)
FORBIDDEN_CALLS: Final[frozenset[str]] = frozenset(
    {"eval", "exec", "compile", "__import__", "open"}
)


def _chain_key(chain: list) -> tuple:
    return tuple((str(tool), str(arg).strip()) for tool, arg in chain)


def distill_chains(trajectories: list[list], *, min_repeats: int = 3) -> list[dict[str, Any]]:
    """Repeated tool chains (-> proposals); sub-threshold noise dropped."""
    counts: dict[tuple, int] = {}
    for trajectory in trajectories:
        if trajectory:
            key = _chain_key(trajectory)
            counts[key] = counts.get(key, 0) + 1
    return [
        {"chain": [list(step) for step in key], "occurrences": count}
        for key, count in sorted(counts.items(), key=lambda item: -item[1])
        if count >= min_repeats
    ]


def verify_proposal_code(code: str) -> tuple[bool, str]:
    """AST gate: parses + stdlib-allowlisted imports + no dynamic exec."""
    try:
        tree = ast.parse(code or "")
    except SyntaxError as exc:
        return False, f"syntax error: {exc}"
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] not in ALLOWED_IMPORTS:
                    return False, f"import not allowlisted: {alias.name}"
        elif isinstance(node, ast.ImportFrom):
            if (node.level or 0) > 0 or (node.module or "").split(".")[0] not in ALLOWED_IMPORTS:
                return False, f"import not allowlisted: {node.module}"
        elif (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in FORBIDDEN_CALLS
        ):
            return False, f"forbidden call: {node.func.id}"
    return True, "ok"


def format_proposal(proposal: dict[str, Any], day_iso: str) -> str:
    """Owner-review markdown: chain steps + occurrence count + next action."""
    lines = [f"### مقترح مهارة {day_iso}", ""]
    for i, step in enumerate(proposal.get("chain", []), 1):
        tool, arg = (list(step) + [""])[:2]
        lines.append(f"{i}. {tool}" + (f" — {arg}" if arg else ""))
    lines += [
        "",
        f"تكررت {proposal.get('occurrences', 0)} مرات.",
        "التفعيل بيد المالك فقط — لا تسجيل تلقائي.",
    ]
    return "\n".join(lines) + "\n"
