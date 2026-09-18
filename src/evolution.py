"""Sovereign evolution loop (P2): repeated trajectories -> owner proposals.

Phase 1 of the ratified lifecycle (capture -> distill -> AST-verify ->
sandbox -> owner-gated promotion). This module owns distill + verify +
proposal rendering. NOTHING here registers skills: proposals are markdown
the owner promotes by hand (teaching law). Sandbox execution + promotion
gates are P3 (OverlayVault harness).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Any, Final

from src.skills.capabilities import IRREVERSIBLE_TOOLS, TOOL_CAPABILITIES

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


# P3: promotion surface. Side-effect tools stay in the confirmation-gated
# tier forever — the structural test below pins PROMOTABLE disjoint from
# the capabilities registry's irreversible set.
PROMOTABLE_TOOLS: Final[frozenset[str]] = frozenset(
    {
        "gmail",
        "calendar",
        "tasks",
        "telemetry",
        "running_apps",
        "brief",
        "knowledge_graph",
        "read_page",
    }
)


@dataclass
class PromotionReport:
    passed: bool
    reasons: list[str] = field(default_factory=list)


def _check_chain_tools(chain: list) -> list[str]:
    tools = [str(step[0]) for step in chain if step]
    reasons: list[str] = []
    unknown = [tool for tool in tools if tool not in TOOL_CAPABILITIES]
    if unknown:
        reasons.append(f"unknown tools: {','.join(sorted(set(unknown)))}")
    irreversible = [tool for tool in tools if tool in IRREVERSIBLE_TOOLS]
    if irreversible:
        reasons.append(
            f"confirmation-gated tools never promote: {','.join(sorted(set(irreversible)))}"
        )
    unpromotable = [tool for tool in tools if tool not in PROMOTABLE_TOOLS]
    if unpromotable:
        reasons.append(
            "outside promotable set (stays confirmation-gated): "
            + ",".join(sorted(set(unpromotable)))
        )
    return reasons


def _check_vault_notes(paths: list, overlay) -> list[str]:
    reasons: list[str] = []
    for relpath in paths:
        try:
            if not overlay.resolve(relpath).is_file():
                reasons.append(f"vault note missing: {relpath}")
        except (ValueError, OSError) as exc:
            reasons.append(f"vault note unreadable: {relpath} ({exc})")
    return reasons


def evaluate_proposal(proposal: dict[str, Any], overlay) -> PromotionReport:
    """Sandbox verdict: known tools + promotable chain + clean AST + live notes.

    `overlay` is an OverlayVault (shadow-first reads, real vault untouched).
    No code executes here — verification is structural only.
    """
    reasons = _check_chain_tools(proposal.get("chain") or [])
    code = proposal.get("code")
    if code:
        ok, reason = verify_proposal_code(code)
        if not ok:
            reasons.append(f"AST gate: {reason}")
    reasons += _check_vault_notes(proposal.get("notes", []), overlay)
    return PromotionReport(passed=not reasons, reasons=reasons)


def promotion_decision(report: PromotionReport, *, owner_approved: bool, suite_green: bool) -> bool:
    """The gate itself: structural pass + owner word + green suite. All three."""
    return report.passed and owner_approved and suite_green
