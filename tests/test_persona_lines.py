"""Remediation 1.6 (owner 2026-09-03): string-contract — no customer-service
register and no garbled wording in ANY owner-facing Arabic constant in src/.
Sara's written voice must match her spoken one: عمر صاحبها مش زبون.

The scan reads every string constant assignment in src/ via AST (not a plain
text grep) so the contract holds for what the code actually ships, and it is
exempt of SYSTEM_PROMPT_AR — the persona rulebook NAMES the banned service
phrases deliberately (its structure is enforced by the 1.2 contract tests).
"""

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"

# Service-desk register (banned for Sara), the «لسأ» misspelling, the garbled
# hearing/enrollment verbs, and the garbled mic line — none may ever return.
BANNED_SUBSTRINGS: tuple[str, ...] = (
    "كيف فيني ساعدك",
    "كيف أساعدك",
    "يسرني خدمتك",
    "لسأ",
    "سمسعتك",
    "انسمعت",
    "القريب من الميك",
)

# The persona rulebook quotes the banned phrases inside its prohibition clauses —
# that is the enforcement mechanism (1.2), not a violation.
EXEMPT_NAMES = {"SYSTEM_PROMPT_AR"}


def _string_constants() -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        rel = path.relative_to(SRC.parent)
        for node in ast.walk(tree):
            targets: list[str] = []
            if isinstance(node, ast.Assign):
                targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                targets = [node.target.id]
            if not targets or not isinstance(node.value, ast.Constant):
                continue
            value = node.value.value
            if isinstance(value, str):
                for name in targets:
                    if name not in EXEMPT_NAMES:
                        found.append((f"{rel}:{name}", value))
    return found


def test_no_service_desk_or_garbled_strings_in_constants():
    """No owner-facing Arabic constant carries service-desk phrasing or garbled
    wording (remediation 1.6 acceptance: zero such lines anywhere in src/)."""
    offenders: list[str] = []
    for label, text in _string_constants():
        for banned in BANNED_SUBSTRINGS:
            if banned in text:
                offenders.append(f"{label} carries {banned!r}")
    assert offenders == [], "\n".join(offenders)


def test_constants_scan_actually_finds_constants():
    """Guard the guard: the AST scan reaches the known owner-facing constants
    (a broken walk would silently green-light the contract above)."""
    labels = {label.split(":")[-1] for label, _ in _string_constants()}
    for expected in ("WELCOME_AR", "EMPTY_VOICE_AR", "GREETING_AR"):
        assert expected in labels, f"scan missed {expected}"
