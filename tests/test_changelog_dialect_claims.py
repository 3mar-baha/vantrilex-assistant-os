"""QW-1 — the CHANGELOG's dialect claims must be TRUE OF THE TREE (Directive 6).

`CLAUDE.md` §5.1 Directive 6: every claim in a document is re-derived from the
tree, and "unverifiable" is an error rather than a warning. A changelog is a
document, so a limitation it announces is a claim like any other — and a stale
one is worse than none, because a reader routes their trust by it.

THE DEFECT THIS PINS. `CHANGELOG.md` carried a "Known limitation — Terminal 1
answers in MSA, not ar-JO" entry whose stated cause was that importing
`src.persona` was forbidden. `src/bot_shell.py` imports `build_persona_joda`
(`TERMINAL_SYSTEM_PROMPT` at module scope, and `_live_shell` supplies the same
object as the `system` default), so the terminal speaks ar-JO and the entry was
false. It also contradicted its own suite: `tests/test_bot_shell_dialect.py`
asserts the module binds EXACTLY `build_persona_joda` from `src.persona`, so the
changelog named as the cause of a limitation the tests forbid.

WHY A GUARD AND NOT A DELETION. A one-line deletion leaves nothing behind, and
the next agent to add a capability-shaped note about Terminal 1 repeats the
error with no signal. The check below derives the shell's dialect binding from
the source and fails only when the changelog CONTRADICTS it — a legitimate
passive sentence about the ar-JO shell is not a failure, so this cannot force
the changelog to be silent about the topic.

The check is deliberately narrow: it looks for an announced MSA limitation on
the terminal, never the bare token "MSA". Two other changelog entries use "MSA"
truthfully (the G2P tanween entry and the prompt-bias entry), and a guard that
banned the token would force those to be reworded for no reason.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHANGELOG = ROOT / "CHANGELOG.md"
SHELL = ROOT / "src" / "bot_shell.py"

#: The persona builder that composes the JODA ar-JO few-shot exemplars. Named
#: once here and resolved against the source, so a future rename of the builder
#: moves this check with it instead of leaving it pinned to a dead name.
JODA_BUILDER = "build_persona_joda"
PERSONA_MODULE = "src.persona"

#: A changelog heading that announces a limitation and names the terminal.
_TERMINAL_LIMITATION_HEADING = re.compile(
    r"^#{2,3}\s*(?:known\s+limitation|limitation)\b[^\n]*terminal",
    re.IGNORECASE | re.MULTILINE,
)

#: An announced limitation is a dialect claim only when its body says so. The
#: token alone is not enough — an entry may use "MSA" truthfully while
#: describing G2P tanween or prompt bias.
_MSA_CLAIM = re.compile(r"\bMSA\b", re.IGNORECASE)

_NEXT_HEADING = re.compile(r"^#{2,3}\s", re.MULTILINE)


def _shell_binds_the_joda_builder() -> bool:
    """True when `src/bot_shell.py` imports the ar-JO persona builder.

    Parsed with `ast` rather than grepped, for the same reason the bot_shell
    guards parse it: a name inside a docstring or a comment is not a binding,
    and only a binding is what would make a changelog claim false.
    """
    tree = ast.parse(SHELL.read_text(encoding="utf-8"))
    return any(
        isinstance(node, ast.ImportFrom)
        and node.module == PERSONA_MODULE
        and any(alias.name == JODA_BUILDER for alias in node.names)
        for node in ast.walk(tree)
    )


def _section_at(text: str, start: int) -> str:
    """The announced-limitation section beginning at `start`, heading included."""
    following = _NEXT_HEADING.search(text, start + 1)
    return text[start : following.start() if following else len(text)]


def refuted_terminal_limitations(text: str, *, shell_speaks_ar_jo: bool) -> list[str]:
    """Sections that announce a terminal limitation the tree refutes.

    Split out from the guard so the break-verification test can plant text and
    run the REAL detector over it, instead of asserting that a regex it already
    matched still matches.
    """
    if not shell_speaks_ar_jo:
        return []
    refuted: list[str] = []
    for match in _TERMINAL_LIMITATION_HEADING.finditer(text):
        section = _section_at(text, match.start())
        if _MSA_CLAIM.search(section):
            refuted.append(section.strip())
    return refuted


def test_the_changelog_announces_no_terminal_dialect_limitation_the_tree_refutes() -> None:
    """The pin. A "known limitation" heading that names Terminal 1 AND claims MSA
    is honest only while `src/bot_shell.py` does NOT bind the ar-JO builder."""
    refuted = refuted_terminal_limitations(
        CHANGELOG.read_text(encoding="utf-8"),
        shell_speaks_ar_jo=_shell_binds_the_joda_builder(),
    )
    assert not refuted, (
        f"CHANGELOG.md announces an MSA limitation for Terminal 1, but src/bot_shell.py "
        f"imports {JODA_BUILDER!r} — the terminal speaks ar-JO. Correct or remove the "
        f"entry; a false known-limitation is worse than none.\n" + "\n---\n".join(refuted)
    )


def test_the_joda_builder_is_bound_so_the_pin_above_cannot_pass_vacuously() -> None:
    """Directive 2: a guard is real once you have seen it FAIL, and a guard that
    cannot fire is hollow. This pins the precondition the pin leans on — the
    shell really does import the builder — so the reachable failure is "the
    changelog still says MSA", never "the shell silently stopped speaking
    ar-JO"."""
    assert _shell_binds_the_joda_builder() is True, (
        f"src/bot_shell.py no longer imports {JODA_BUILDER!r} from {PERSONA_MODULE!r}. If "
        f"the terminal's dialect seam moved, the changelog check must move with it — this "
        f"failing means the pin's precondition no longer holds."
    )


def test_the_detector_fires_on_the_exact_entry_that_was_removed() -> None:
    """Break-verification against the REAL detector, not a copy of its regex.

    The text below is the stale entry verbatim. If `refuted_terminal_limitations`
    returns empty for it, the pin above is passing because the detector stopped
    matching, and this test is what says so.
    """
    stale = (
        "## [Unreleased]\n\n"
        "### Known limitation — Terminal 1 answers in MSA, not ar-JO\n"
        "The shell carries the front door's default prompt, not Sara's persona, because "
        "importing `src.persona` is what the safety rule forbids. Awaiting an owner "
        "decision between a persona-free engineering surface and a composed persona.\n\n"
        "### Added — something else\n"
        "Not a limitation.\n"
    )
    assert refuted_terminal_limitations(stale, shell_speaks_ar_jo=True), (
        "the detector no longer recognises the exact stale entry this pin was written for — "
        "the guard above would pass for the wrong reason"
    )
    assert refuted_terminal_limitations(stale, shell_speaks_ar_jo=False) == [], (
        "with no ar-JO binding there is nothing to refute, so an MSA announcement would be "
        "honest and the detector must stay silent"
    )


def test_an_honest_ar_jo_announcement_is_not_a_failure() -> None:
    """The negative control. A limitation section that does NOT claim MSA is
    left alone, so the guard cannot be satisfied by deleting the word from a
    false entry — it has to delete or correct the claim itself."""
    corrected = (
        "## [Unreleased]\n\n"
        "### Known limitation — Terminal 1 has no voice channel\n"
        "The shell streams text only; the Ogg Opus lane is Telegram's.\n"
    )
    assert refuted_terminal_limitations(corrected, shell_speaks_ar_jo=True) == []
