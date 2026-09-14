"""Reversibility Circuit Breaker (Phase 2) — deterministic, dual-layer.

Layer 1 (core): `src/openclaw/plans.py` PARKs DAGs with irreversible ops
lacking confirmation. Layer 2 (THIS module, daemon side): every op is
re-classified from its own (kind, target, value, verify) — the wire claim
is evidence, never authority — and execution requires a live
confirmation_id for anything committing.

Classes mirror `04_Resources/Knowledge_Bases/OpenClaw/
Reversibility_and_Safety_Boundaries.md` 1:1. Unclear defaults UP.
"""

from __future__ import annotations

import re
from typing import Final, Literal

from loguru import logger

from bridge.openclaw.protocol import Op, OpKind

Reversibility = Literal["reversible", "irreversible"]


class ActionForbiddenError(Exception):
    """An op outside the representable space (shell breakout, registry
    mutation, credential exfiltration shape). Never authorized, never
    executed — refused loudly at classification time."""


# Hotkeys that only move attention (T0 tier): focus, tabs, find, dismiss.
# Everything committing (close/save/submit) is absent ON PURPOSE — an
# unknown hotkey defaults UP to irreversible (classify() below).
SAFE_HOTKEYS: Final[frozenset[str]] = frozenset(
    {
        "ctrl+l",
        "ctrl+t",
        "ctrl+tab",
        "ctrl+shift+tab",
        "ctrl+f",
        "ctrl+r",
        "f6",
        "f5",
        "alt+tab",
        "alt+left",
        "alt+right",
        "escape",
        "esc",
        "tab",
        "shift+tab",
        "up",
        "down",
        "left",
        "right",
        "pageup",
        "pagedown",
        "home",
        "end",
        "ctrl+home",
        "ctrl+end",
        "win+d",
        "win+e",
        "win+v",
        "win+shift+s",
    }
)

# Clicks carrying one of these verify predicates commit owner-visible state.
COMMIT_VERIFIES: Final[frozenset[str]] = frozenset(
    {"submit", "save", "delete", "close", "send", "commit", "purchase", "publish"}
)

# Typing that submits: embedded newline or an explicit Enter token.
_SUBMIT_RE: Final = re.compile(r"\n|\r|\{enter\}", re.IGNORECASE)

# Forbidden shapes (matched against target + value, case-insensitive):
# shell-interpreter invocation, registry mutation paths, credential
# exfiltration assignments. Typing a password INTO a field is input, not
# exfiltration — only `key[:=]value` shapes trip (see tests).
_FORBIDDEN_RES: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(r"(powershell|pwsh|cmd\.exe\s*/[ck]|wscript|cscript|mshta|rundll32)\b"),
    re.compile(r"\breg\s+(add|delete|import)\b"),
    re.compile(r"hkey_|hklm|hkcu"),
    re.compile(r"(password|passwd|api[_-]?key|secret|token|credential)\s*[:=]"),
)


def _forbidden_text(op: Op) -> str | None:
    haystack = f"{op.target or ''} {op.value or ''}"
    if not haystack.strip():
        return None
    lowered = haystack.casefold()
    for pattern in _FORBIDDEN_RES:
        if pattern.search(lowered):
            return pattern.pattern
    return None


class SafetyCircuitBreaker:
    """Stateless classifier + fail-closed authorizer (all static: no
    per-process state to leak between turns)."""

    @staticmethod
    def classify(op: Op) -> Reversibility:
        """Deterministic verdict from the op itself. Raises
        ActionForbiddenError for shapes outside the representable space."""
        hit = _forbidden_text(op)
        if hit is not None:
            logger.warning("breaker forbidden shape | op={} pattern={!r}", op.op.value, hit)
            raise ActionForbiddenError(f"forbidden op shape ({op.op.value}): refuses by policy")
        kind = op.op
        if kind in (
            OpKind.SCREENSHOT,
            OpKind.INSPECT_TREE,
            OpKind.EXTRACT,
            OpKind.NAVIGATE,
            OpKind.FOCUS,
            OpKind.SCROLL,
        ):
            return "reversible"
        if kind is OpKind.HOTKEY:
            keys = (op.value or "").strip().casefold()
            return "reversible" if keys in SAFE_HOTKEYS else "irreversible"
        if kind is OpKind.TYPE_TEXT:
            if _SUBMIT_RE.search(op.value or "") or (op.verify or "").strip().casefold() in (
                "submit",
                "send",
            ):
                return "irreversible"
            return "reversible"
        # click / double_click / right_click: the verify predicate names the
        # consequence — a committing predicate gates, anything else is a
        # reversible selection/focus.
        return (
            "irreversible"
            if (op.verify or "").strip().casefold() in COMMIT_VERIFIES
            else "reversible"
        )

    @staticmethod
    def authorize(op: Op, confirmation_id: str | None) -> bool:
        """Fail-closed: forbidden raises, irreversible needs a live id,
        reversible always passes."""
        verdict = SafetyCircuitBreaker.classify(op)  # raises on forbidden
        if verdict == "reversible":
            return True
        return bool((confirmation_id or "").strip())
