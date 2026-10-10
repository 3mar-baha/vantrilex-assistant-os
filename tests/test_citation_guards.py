"""N6 — CITATION GUARDS: a ``file:line`` claim in prose must point somewhere REAL.

THE GAP, MEASURED NOT ASSUMED. N2's mutation check injected four false claims into
docstrings — a wrong ``file:line``, a wrong count, «NINE HUNDRED test modules», «all six
deny-listed names» — and ran the whole gate against the mutant. pytest, ``ruff check``,
``ruff format``, ``scripts/docs_guard.py`` and ``scripts/security_gate.py`` all reported
GREEN. **No existing guard detects docstring inaccuracy.** N2 was right to call that a
hole rather than a nuisance; this file closes the machine-checkable part of it.

THE CLAIM CLASSES. The boundary below is the point of the node, so it is declared before
the code rather than inferred from it:

  * **C — EOF violation.** A cited line past the end of the target file. GUARDED, and it
    is a provable falsehood: the file exists and the line does not.
  * **B — ``file:line`` PLUS a named symbol.** The second claim is separately checkable.
    GUARDED for the subset that is mechanically decidable; the rest is DEFERRED, one
    entry per pairing, each with a stated reason. See ``DEFERRED_CLASS_B``.
  * **A — bare ``file:line``, no symbol.** NOT GUARDED BY DESIGN. A bare line number
    carries no second, independent claim, so the only thing left to assert about it is
    «the line exists» — which is Class C. Checking that here would add a second code path
    to one check, not a second guarantee.
  * **D — counts as prose.** «fourteen test modules», «46 names today». NOT GUARDED BY
    DESIGN, and that is a boundary with a colleague rather than with myself: N7 is about
    to rewrite the documentation and may move every one of those numbers. A guard that
    pinned them would be guaranteed to collide with N7, dragging this node into N7's
    write-set and turning a guard into a maintenance sink. A wrong count is N7's lane.
  * **E — behavioural prose.** «R4 refuses», «the log never alters a result». NOT
    GUARDED BY DESIGN, because no citation checker can decide a behavioural claim — but
    the behavioural TEST is the guard, and it already exists. Citation checking must not
    be mistaken for a second opinion about behaviour.

NOT GUARDED BY DESIGN, ABOVE: A, D and E. The reasons are structural, not a budget.

WHAT THE TWO GUARDS DO. Guard 1 extracts ``path.py:NNN`` and ``NNN-MMM`` ranges from
DOCSTRINGS AND COMMENTS ONLY, across ``src/`` and ``tests/``, and asserts every cited
number lies inside the target file's CURRENT length. Guard 2 DISCOVERS the Class-B set
rather than assuming it, and asserts the named symbol resolves at the cited line.

FOUR PROPERTIES THAT MAKE THESE GUARDS TRUSTWORTHY, each asserted by a test below:

  1. A citation whose path cannot be resolved **FAILS**. It is never skipped. A guard
     that quietly declines what it cannot parse reports green while checking nothing,
     which is worse than having no guard at all.
  2. Zero extracted citations **FAILS**. This is the most important line in the file: it is
     what stops a refactor from silently turning both guards into no-ops.
  3. Line counts are **computed at runtime**. Nothing here pins «``src/tools.py`` has
     1,502 lines» — that assertion is precisely the defect this node exists to catch.
  4. The tree is **read**. No generated manifest, no cached index, no pinned corpus count
     to drift away from reality.

RESIDUAL STALENESS IS REAL AND IS THE INTENT. When code moves, a citation goes stale, the
guard goes red, and the fix is re-pointing one citation. That is the mechanism working,
not a false alarm; a guard that stayed green through a refactor would be the defect. What
this design cannot do is notice a citation that was wrong the moment it was written.

THE CEILING, STATED PLAINLY AND NOT SOFTENED. This guard proves REFUSALS and RESOLUTIONS.
It cannot prove a claim is *right* — only that it points somewhere real. A wrong-but-
plausible citation, and a wrong count, both still pass.

THE N7 BOUNDARY IS HARD. ``docs/`` is READ here and only to report coverage: nothing in
this file asserts a ``docs/`` citation is correct, so it can never go red because a
document is stale. That is N7's work. Every discovered Class-B pairing that cannot be
mechanically decided is recorded in ``DEFERRED_CLASS_B`` with a stated reason, and none of
it was fixed: owner decision 2026-10-03, option (a) — this node records B/C drift, it does
not edit prose to match it.

Hermetic: filesystem reads of the working tree only. No socket, no subprocess, no clock,
no network — so unlike a ``git ls-files`` walk this cannot be broken by a missing git, and
it measures the files a reader would actually open.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]

#: The segments Guard 1 and Guard 2 police. ``docs`` is DELIBERATELY absent — see the N7
#: boundary above. It is read for coverage only, by ``_markdown_prose_regions``.
CODE_SEGMENTS = ("src", "tests")

#: The coverage-only segment: read, counted, never asserted for correctness.
DOCS_SEGMENT = "docs"

#: Where a cited path is looked for, after the repo root itself: the shipped code and
#: documentation trees. Trees NOT in the shipped contract — ``.claude/``, ``.venv/``,
#: ``vault/``, ``archive/``, the never-staged analysis-report folder — are excluded ON
#: PURPOSE. A citation into a tree CI does not have cannot be verified from the
#: repository, so it counts as UNRESOLVED rather than being waved through. That is a
#: stated policy, not a silent skip.
SEARCH_ROOTS = ("src", "tests", "scripts", "bridge", "common", "docs")

#: ``path.py:NNN`` or ``path.py:NNN-MMM``. Requires a real file extension, so a clock
#: («23:50») or a port («localhost:20128») can never be read as a citation.
CITATION_RE = re.compile(r"([A-Za-z0-9_][A-Za-z0-9_./-]*\.(?:py|md)):(\d+(?:-\d+)?)(?!\d)")

#: A backticked code identifier, single or RST-double backticks. This is the ONLY way a
#: citation becomes Class B: the prose must name a symbol next to the line it cites.
SYMBOL_RE = re.compile(
    r"(?<!`)`{1,2}([A-Za-z_][A-Za-z0-9_]*(?:[.<>_][A-Za-z0-9_<>*]+)*)`{1,2}(?!`)"
)

#: Floors, never counts. Measured values at this commit sit far above every one of these
#: (src 28, tests 92, docs ~440 citations; 28 discovered Class-B pairings). A floor exists
#: only so that a broken extractor fails loudly instead of vacuously — it must never
#: encode the corpus, because a corpus constant is a number that goes stale exactly like
#: the prose it counts.
MIN_CODE_CITATIONS = {"src": 20, "tests": 80}
MIN_CLASS_B_PROVED = 1
MIN_DOCS_CITATIONS = 50

#: ``(source file, citation, symbol) -> reason`` for every discovered Class-B pairing that
#: Guard 2 canNOT mechanically decide. Read this as a work queue, not as a set of
#: excuses: an entry is a citation whose Class-B half is currently UNVERIFIED, and
#: several of them are stale.
#:
#: Keyed by ``(source file, citation, symbol)`` and deliberately NOT by source line, so
#: that editing an unrelated line of a citing file does not force this list to churn.
#: Changing the citation itself, or the symbol it names, still forces an update — which is
#: the point.
#:
#: Owner decision 2026-10-03, option (a): B/C drift found here is DEFERRED WITH REASON.
#: None of it was fixed in this node. A guard node that also rewrites prose becomes a
#: maintenance sink, and a stale sentence that is loudly listed beats a fresh sentence
#: nobody reviewed.
DEFERRED_CLASS_B: dict[tuple[str, str, str], str] = {
    ("src/action_log.py", "src/vault.py:353", "VaultClient"): (
        "STALE. Line 353 is a module-level `#:` comment about the rate-limit backoff "
        "window; `class VaultClient` is at 520. The claim is about where a secret gets "
        "registered, not about the class's own line, so no AST span carries it."
    ),
    ("src/action_log.py", "src/vault.py:353", "VaultClient.__init__"): (
        "STALE, and the same line as the entry above. The prose names "
        "`VaultClient.__init__`, whose real span is inside the class at 520-835; 353 is "
        "not in it."
    ),
    ("src/action_log.py", "src/dispatcher.py:885", "FrontDoorDispatcher.handle"): (
        "STALE post-C1 (7bc4a33, +29). Line 885 now reads `self,` inside `_store_verdict` "
        "(884-898); `FrontDoorDispatcher.handle` (`async def`) is at 914 (span 914-1052). "
        "Src-owned prose - re-point to :914 in the src round."
    ),
    ("src/bot_shell.py", "src/dispatcher.py:834", "handle"): (
        "HALF-RANGE CLAIM, not a stale one. One symbol, two citations: pairing 834 with "
        "`handle` is a reading, not a decidable claim. Re-derived post-src-round: "
        "line 834 IS `class FrontDoorDispatcher:`, and the same parenthetical gives "
        "`handle` at bare `:914` (Class A, undiscovered by design); `async def handle` "
        "is at 914 (span 914-1052)."
    ),
    ("src/bot_shell.py", "src/dispatcher.py:1200", "_plain_messages"): (
        "STALE post-ruff-format (8748eac, +19 from the tuple expansion at ~L285). "
        "Line 1200 is now a `# round DROPPED the job ids` comment inside `_tool_lane` "
        "(1116-1216); `def _plain_messages` is at 1219 (span 1219-1226). Src-owned "
        "prose - re-point to :1219 in the src round."
    ),
    ("src/tool_overlay.py", "src/tools.py:287", "ToolRegistry._do_<name>"): (
        "SYNTHETIC NAME. The cited line is in fact the right one - "
        '`handler = getattr(self, f"_do_{tool}", None)` - but `<name>` is a template '
        "segment, and no AST span can carry a name the source composes at runtime."
    ),
    ("tests/test_action_audit_log.py", "src/vault.py:479", "append_section"): (
        "STALE. Line 479 is inside `classify_rate_limit` (451-517); `append_section` is at 674-694."
    ),
    ("tests/test_action_audit_log.py", "src/vault.py:432", "upsert"): (
        "STALE. Line 432 is inside `_seconds` (422-436) and `upsert` is at 627-635. The "
        "citation appears twice in the citing file; one entry covers both."
    ),
    ("tests/test_bot_shell_repl.py", "src/dispatcher.py:744", "handle"): (
        'STALE ON BOTH HALVES. Re-derived post-C1 (7bc4a33): line 744 is `"create_task",` '
        "inside `_keyword_net` (701-800), and the same parenthetical puts `handle` at "
        ":824, which is now the `ack = DEFAULT_ACK_AR` clamp line; `handle` is at 914 "
        "(span 914-1052)."
    ),
    ("tests/test_greeter_persona_parity.py", "src/bot.py:195", "SARA_PERSONA_AR"): (
        "IMPORT, NOT A DEFINITION. `SARA_PERSONA_AR` has no `def` in `src/bot.py` - it is "
        "imported from `src/persona.py` - so the claim is about an imported binding and "
        "no span in the cited file can host it."
    ),
    ("tests/test_greeter_persona_parity.py", "src/dispatcher.py:1076", "_plain_messages"): (
        "STALE, and the citing file says so itself: the comment above records that "
        "`_plain_messages` is at 1200. Re-derived post-C1 (7bc4a33): line 1076 is "
        "`skill_block = (` inside `handle` (914-1052); `_tool_lane` is 1097-1197."
    ),
    ("tests/test_makefile_gate.py", "tests/test_quality_gate.py:65", "make"): (
        "DISCOVERY FALSE POSITIVE. `make` is the English word in the prose, not a Python "
        "symbol: no span, and no token on that line (the line is blank). Recorded so the "
        "pairing is visibly rejected rather than quietly unpaired."
    ),
    ("tests/test_p3d_seams.py", "src/cognition.py:418", "deduce"): (
        "STALE PAIRING. Line 418 is inside `evaluate_candidates` (404-495); `deduce` is "
        "at 527-559. The seam is real, but the named function is not the enclosing one."
    ),
    ("tests/test_p3d_seams.py", "src/cognition.py:550", "_goal_markers"): (
        "STALE. Line 550 is inside `deduce` (527-559); `_goal_markers` is at 393-401."
    ),
    ("tests/test_p3d_seams.py", "src/evolution.py:253", "_COLLIDING_TOOL_NAMES"): (
        "OFF-BY-ONE-BLOCK. Line 253 is the `#:` comment four lines above the `Final` "
        "assignment at 257-259. Adjacent-but-not-covering is not a proof, and widening the "
        "rule to «a span starting within N lines» would be exactly the tolerance fudge "
        "this node declines to buy."
    ),
    ("tests/test_p3d_seams.py", "src/skills/capabilities.py:353", "IRREVERSIBLE_TOOLS"): (
        'STALE. Line 353 is `"reversible": True,` inside the `_CAPABILITIES` literal; '
        "`IRREVERSIBLE_TOOLS` is at 439-441."
    ),
    ("tests/test_p3d_seams.py", "src/skills/capabilities.py:358", "markers_for"): (
        "STALE. Line 358 is a bare `#` comment; `markers_for` is at 444-445."
    ),
    ("tests/test_p3d_seams.py", "src/dispatcher.py:740", "parse_thought"): (
        "CROSS-FILE ATTRIBUTION, AMBIGUOUS PAIRING. One line carries two citations "
        "(`src/dispatcher.py:740` and `src/decision_loop.py:221`) and one symbol. "
        "`parse_thought` lives in `src/decision_loop.py`, not in `src/dispatcher.py`; "
        "which of the two citations it modifies is a reading, not a decidable fact."
    ),
    ("tests/test_p3d_seams.py", "src/cognition.py:430", "deduce"): (
        "STALE PAIRING. Line 430 is inside `evaluate_candidates`; `deduce` is at 527-559."
    ),
    ("tests/test_tool_overlay.py", "src/decision_loop.py:217", "_VALID_TOOLS"): (
        "CROSS-FILE ATTRIBUTION. `_VALID_TOOLS` is not defined in `src/decision_loop.py` "
        "- it is read from `src/dispatcher.py` - and line 217 is a comment inside "
        "`parse_thought`. The symbol the sentence names is not in the file it cites."
    ),
    ("tests/test_tool_overlay.py", "src/cognition.py:416", "_TOOL_GOALS"): (
        "STALE. Line 416 is `lead = clean[:_LEAD_WINDOW]` inside `evaluate_candidates`; "
        "`_TOOL_GOALS` is assigned at 32-100."
    ),
}


@dataclass(frozen=True)
class Citation:
    """One extracted claim, carrying everything a failure message needs to be actionable."""

    segment: str
    source: str
    lineno: int
    raw_path: str
    numbers: tuple[int, ...]

    @property
    def spec(self) -> str:
        if len(self.numbers) == 1:
            return str(self.numbers[0])
        return f"{self.numbers[0]}-{self.numbers[-1]}"

    @property
    def text(self) -> str:
        return f"{self.raw_path}:{self.spec}"

    @property
    def where(self) -> str:
        return f"{self.source}:{self.lineno}"


@dataclass(frozen=True)
class Pairing:
    """A discovered Class-B claim: a citation plus the symbol the prose attaches to it."""

    source: str
    lineno: int
    citation: str
    symbol: str

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.source, self.citation, self.symbol)

    def __str__(self) -> str:
        return f"{self.source}:{self.lineno}  `{self.citation}` -> `{self.symbol}`"


# ── the extractor: docstrings and comments, never code ─────────────────────────────


class UnreadableSource(RuntimeError):
    """A policed ``.py`` file the extractor cannot read.

    It is RAISED rather than swallowed. A file that will not parse contributes ZERO
    citations, so swallowing the error drops that file out of the corpus and shrinks the
    number Guard 1 checks — which is precisely the «skip what you cannot parse» failure
    this node exists to prevent. Found by the RED demonstration: a byte-order mark
    injected into a live module made the guard go vacuously green while reporting the
    segment as still covered, because the segment total stayed above its floor.
    """


def _code_prose_regions(path: Path) -> list[tuple[int, str]]:
    """``(lineno, text)`` for every physical line of every docstring, plus every comment.

    Reading code as prose would sweep in unrelated string literals — a port number, a model
    slug, a log message — and every one of those would have to be allow-listed before the
    guard could be trusted. Prose is exactly docstrings and comments, and that is where a
    citation is a CLAIM rather than an accident.
    """
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    regions: list[tuple[int, str]] = []
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise UnreadableSource(f"cannot parse ({exc.msg} at line {exc.lineno})") from exc
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if ast.get_docstring(node, clean=False) is None:
            continue
        head = node.body[0]  # the Expr(Constant(str)) that IS the docstring
        for lineno in range(head.lineno, head.end_lineno + 1):
            regions.append((lineno, lines[lineno - 1]))
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.COMMENT:
                regions.append((token.start[0], token.string))
    except (tokenize.TokenError, IndentationError, SyntaxError) as exc:
        raise UnreadableSource(f"cannot tokenize ({exc})") from exc
    return regions


def _unreadable_sources(root: Path, segments: tuple[str, ...]) -> list[str]:
    """Every policed source file the extractor had to give up on. Never silently empty.

    Found by the RED demonstration rather than by inspection: injecting a byte-order mark
    into a live module made that module contribute zero citations, the segment total fell
    from 28 to 21 — still above the floor of 20 — and BOTH guards reported green. A file
    that cannot be read is therefore a refusal, exactly like an unresolvable path.
    """
    unreadable: list[str] = []
    for segment in segments:
        if segment == DOCS_SEGMENT:
            continue
        for path in _segment_files(root, segment, ".py"):
            try:
                _code_prose_regions(path)
            except UnreadableSource as exc:
                unreadable.append(f"{path.relative_to(root).as_posix()}: {exc}")
    return unreadable


def _markdown_prose_regions(path: Path) -> list[tuple[int, str]]:
    """``(lineno, text)`` for every line of a markdown file. Coverage reporting only."""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return list(enumerate(lines, 1))


def _segment_files(root: Path, segment: str, suffix: str) -> list[Path]:
    base = root / segment
    if not base.is_dir():
        return []
    return sorted(
        p for p in base.rglob(f"*{suffix}") if p.is_file() and "__pycache__" not in p.parts
    )


def _regions(root: Path, segment: str) -> list[tuple[Path, int, str]]:
    """``(file, lineno, text)`` prose regions for a segment, docs included."""
    if segment == DOCS_SEGMENT:
        reader, suffix = _markdown_prose_regions, ".md"
    else:
        reader, suffix = _code_prose_regions, ".py"
    return [
        (path, lineno, text)
        for path in _segment_files(root, segment, suffix)
        for lineno, text in reader(path)
    ]


def _citations(root: Path, segment: str) -> list[Citation]:
    """Every ``path:NNN`` citation in one segment's prose, with its line numbers."""
    found: list[Citation] = []
    for path, lineno, text in _regions(root, segment):
        for match in CITATION_RE.finditer(text):
            found.append(
                Citation(
                    segment=segment,
                    source=path.relative_to(root).as_posix(),
                    lineno=lineno,
                    raw_path=match.group(1),
                    numbers=tuple(int(n) for n in re.split(r"-", match.group(2))),
                )
            )
    return found


def _citation_counts(root: Path) -> dict[str, int]:
    """How many citations each segment yields. Measured, for the coverage figures.

    Counts OCCURRENCES, not lines: one docstring line can carry two citations, and a count
    of lines would understate the corpus.
    """
    return {
        segment: sum(len(CITATION_RE.findall(text)) for _, _, text in _regions(root, segment))
        for segment in (*CODE_SEGMENTS, DOCS_SEGMENT)
    }


# ── the resolver: three citation dialects, one deterministic answer ─────────────────


def _basename_index(root: Path) -> dict[str, list[Path]]:
    """``basename -> [paths]`` over the shipped trees, plus repo-root files.

    This is what makes the third dialect work. The corpus mixes repo-root-relative
    (``src/tools.py:287``), segment-relative (``src/skills/capabilities.py:436``) and
    bare-module (``dispatcher.py:945-958``, ``test_skill_standard.py:25``) spellings, and a
    resolver that handled only the first would silently skip the other two.
    """
    index: dict[str, list[Path]] = defaultdict(list)
    for segment in SEARCH_ROOTS:
        base = root / segment
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix in (".py", ".md") and "__pycache__" not in path.parts:
                index[path.name].append(path)
    for path in root.glob("*"):
        if path.is_file() and path.suffix in (".py", ".md"):
            index[path.name].append(path)
    return dict(index)


def _resolve(raw: str, root: Path, index: dict[str, list[Path]]) -> list[Path]:
    """Every existing file a cited path can denote. Zero = unresolved, two = ambiguous.

    Both of those are FAILURES upstream. An empty list is not a licence to skip: it is the
    evidence that lets the guard say «I could not resolve this, and I will not pretend I
    did not see it».
    """
    cleaned = raw.replace("\\", "/").removeprefix("./")
    if (root / cleaned).is_file():
        return [root / cleaned]
    for segment in SEARCH_ROOTS:
        candidate = root / segment / cleaned
        if candidate.is_file():
            return [candidate]
    return list(index.get(cleaned.rsplit("/", 1)[-1], []))


def _line_count(path: Path) -> int:
    """The target's CURRENT length, computed at runtime. Pinned nowhere, anywhere."""
    return len(path.read_text(encoding="utf-8", errors="replace").splitlines())


def _eof_violations(root: Path, segments: tuple[str, ...]) -> list[str]:
    """One report line per citation that is unresolvable, ambiguous, or past EOF."""
    index = _basename_index(root)
    searched = ", ".join(SEARCH_ROOTS)
    problems: list[str] = []
    for segment in segments:
        for citation in _citations(root, segment):
            hits = _resolve(citation.raw_path, root, index)
            if not hits:
                problems.append(
                    f"{citation.where}  `{citation.text}` -> UNRESOLVED (no such file at the "
                    f"repo root or under {searched})"
                )
                continue
            if len(hits) > 1:
                names = ", ".join(sorted(p.relative_to(root).as_posix() for p in hits))
                problems.append(
                    f"{citation.where}  `{citation.text}` -> AMBIGUOUS ({len(hits)} files "
                    f"share that basename: {names})"
                )
                continue
            target = hits[0]
            length = _line_count(target)
            beyond = [n for n in citation.numbers if n < 1 or n > length]
            if beyond:
                problems.append(
                    f"{citation.where}  `{citation.text}` -> PAST EOF (target "
                    f"{target.relative_to(root).as_posix()} has {length} lines; cited "
                    f"{beyond})"
                )
    return problems


# ── the Class-B machinery ──────────────────────────────────────────────────────────


def _symbol_spans(path: Path) -> dict[str, list[tuple[int, int]]]:
    """``name -> [(first, last)]`` for every definition the file is able to prove.

    A definition is a ``def``, an ``async def``, a ``class``, or a name bound by an
    assignment. Nothing else earns a span: a bare mention is a use site, and a use site is
    exactly the thing that goes stale with nobody noticing.
    """
    spans: dict[str, list[tuple[int, int]]] = defaultdict(list)
    if path.suffix != ".py":
        return {}
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            spans[node.name].append((node.lineno, node.end_lineno or node.lineno))
        elif isinstance(node, ast.Assign):
            for bound in node.targets:
                if isinstance(bound, ast.Name):
                    spans[bound.id].append((bound.lineno, node.end_lineno or bound.lineno))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            spans[node.target.id].append(
                (node.target.lineno, node.end_lineno or node.target.lineno)
            )
    return dict(spans)


def _pairings(root: Path, segment: str) -> list[Pairing]:
    """Every discovered Class-B claim in one segment.

    DISCOVERED, never assumed. A citation becomes Class B when the same prose line names a
    backticked identifier, and the symbol paired with it is the NEAREST one by character
    distance. Nearest-identifier is a deterministic reading rule — «the symbol this
    citation is about is the one written closest to it» — and it is written down here
    because a heuristic nobody can audit is a heuristic nobody should trust.
    """
    found: list[Pairing] = []
    for path, lineno, text in _regions(root, segment):
        citations = list(CITATION_RE.finditer(text))
        symbols = list(SYMBOL_RE.finditer(text))
        if not citations or not symbols:
            continue
        source = path.relative_to(root).as_posix()
        for citation in citations:
            gaps = [max(0, s.start() - citation.end(), citation.start() - s.end()) for s in symbols]
            nearest = min(gaps)
            for symbol in sorted(
                {s.group(1) for s, g in zip(symbols, gaps, strict=True) if g == nearest}
            ):
                found.append(Pairing(source, lineno, citation.group(0), symbol))
    return found


def _pairing_verdict(root: Path, pairing: Pairing, index: dict[str, list[Path]]) -> bool | None:
    """True / False / None for a Class-B pairing. None means «cannot be decided».

    PROVEN (``True``) means the cited line falls INSIDE the named symbol's definition span,
    or the named symbol appears there as a whole-word token. Both readings are exact: there
    is no tolerance window, because a window is a place to hide a stale citation.
    """
    raw_path, _, spec = pairing.citation.rpartition(":")
    first = int(re.split(r"-", spec)[0])
    hits = _resolve(raw_path, root, index)
    if len(hits) != 1 or hits[0].suffix != ".py":
        return None  # no AST symbol table to prove against
    tail = pairing.symbol.rsplit(".", 1)[-1]
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", tail):
        return False  # a composed template such as `_do_<name>`: no span can carry it
    if any(start <= first <= end for start, end in _symbol_spans(hits[0]).get(tail, [])):
        return True
    line = hits[0].read_text(encoding="utf-8", errors="replace").splitlines()[first - 1]
    return bool(re.search(rf"\b{re.escape(tail)}\b", line))


def _report(header: str, lines: list[str]) -> str:
    return "\n".join([header, *(f"  {line}" for line in lines)])


# ── GUARD 1 ────────────────────────────────────────────────────────────────────────


def test_every_file_line_citation_points_inside_the_file() -> None:
    """GUARD 1 — Class C, and it never declines what it cannot parse.

    Every ``path.py:NNN`` in a ``src/`` or ``tests/`` docstring or comment must name a file
    that exists and a line that exists inside it. Lengths are read from the tree at the
    moment the guard runs, so this cannot pass because a cached count went stale.

    The message prints the offending citation, where it was written, the resolved target
    and that target's real length: everything needed to fix it by re-pointing one
    citation.
    """
    problems = _eof_violations(REPO, CODE_SEGMENTS)
    problems += _unreadable_sources(REPO, CODE_SEGMENTS)
    assert not problems, _report(
        f"{len(problems)} citation(s) point nowhere real, or a policed file could not be "
        f"read at all. Re-point or delete each. This guard does not skip what it cannot "
        f"resolve.",
        problems,
    )


def test_the_citation_walk_finds_citations_in_every_policed_segment() -> None:
    """THE ANTI-VACUITY LINE. Zero extracted citations is a FAILURE, not a pass.

    If the extractor ever stops seeing prose — a walker that skips a segment, a regex that
    no longer matches the corpus, a renamed tree — every guard above would report green
    while checking nothing at all. The floors sit far below the measured counts so they
    fire on a broken extractor and never on ordinary drift.

    A segment total alone is NOT enough, which the RED demonstration proved: a file that
    stopped parsing cost seven citations while the total stayed above its floor. So the
    per-file refusal is asserted here too, not only inside Guard 1.
    """
    unreadable = _unreadable_sources(REPO, CODE_SEGMENTS)
    assert not unreadable, _report(
        "these policed source files could not be read, so their citations were NOT "
        "checked — a silently dropped file is a smaller corpus reported as a green one",
        unreadable,
    )
    counts = _citation_counts(REPO)
    for segment, floor in MIN_CODE_CITATIONS.items():
        found = counts.get(segment, 0)
        assert found >= floor, (
            f"the extractor found {found} citation(s) under {segment}/, below the floor of "
            f"{floor}. Both guards are now vacuous: every other assertion in this file is "
            "reporting green while checking nothing."
        )


# ── GUARD 2 ────────────────────────────────────────────────────────────────────────


def test_every_symbol_bearing_citation_still_resolves() -> None:
    """GUARD 2 — the Class-B half, checked where it is decidable and queued where not.

    A pairing is PROVED when the cited line falls inside the named symbol's definition
    span, or carries that symbol as a whole-word token. Every discovered pairing that
    cannot be decided that way must appear in ``DEFERRED_CLASS_B`` with a stated reason, so
    a deferred citation is a visible queue entry rather than a silent pass.
    """
    index = _basename_index(REPO)
    proved: list[Pairing] = []
    deferred: list[Pairing] = []
    unaccounted: list[Pairing] = []
    for segment in CODE_SEGMENTS:
        for pairing in _pairings(REPO, segment):
            verdict = _pairing_verdict(REPO, pairing, index)
            if verdict is True:
                proved.append(pairing)
            elif pairing.key in DEFERRED_CLASS_B:
                deferred.append(pairing)
            else:
                unaccounted.append(pairing)
    assert not unaccounted, _report(
        f"{len(unaccounted)} Class-B citation(s) are neither proved nor on "
        "DEFERRED_CLASS_B. Re-point the line, or add an entry carrying the reason it "
        "cannot be checked — an unlisted pairing is a silent skip.",
        [str(p) for p in unaccounted],
    )
    assert len(proved) >= MIN_CLASS_B_PROVED, (
        f"{len(proved)} Class-B citation(s) proved, floor is {MIN_CLASS_B_PROVED}: the "
        "pairing extractor found nothing provable, so the guard above is checking an "
        "empty set"
    )
    assert deferred, (
        "no Class-B citation was deferred. Either the allow-list is stale or the corpus "
        "changed; both are worth a look before this stays green."
    )


def test_the_class_b_allow_list_states_a_reason_for_every_entry() -> None:
    """An allow-list entry with no reason is a silent skip wearing a label.

    This also fails when the list is EMPTY, which is the case where the guard has quietly
    stopped distinguishing anything.
    """
    assert DEFERRED_CLASS_B, (
        "the Class-B allow-list is empty. Either every discovered pairing is provable - in "
        "which case delete the list and say so - or the list is not being maintained."
    )
    unreasons = sorted(str(key) for key, reason in DEFERRED_CLASS_B.items() if len(reason) < 40)
    assert not unreasons, _report(
        "every deferred Class-B entry must carry a stated reason; these do not:", unreasons
    )


def test_the_class_b_allow_list_names_only_citations_that_still_exist() -> None:
    """The list cannot rot. An entry for a citation nobody writes any more reads like
    coverage while checking nothing, so it is a failure."""
    discovered = {p.key for segment in CODE_SEGMENTS for p in _pairings(REPO, segment)}
    orphans = sorted(str(key) for key in DEFERRED_CLASS_B if key not in discovered)
    assert not orphans, _report(
        "these allow-list entries match no discovered Class-B citation: the citation or its "
        "symbol was reworded, or the entry was never real. Re-derive or delete each.",
        orphans,
    )


# ── RED demonstration, held in the file rather than asserted in a commit message ────


def _scratch_tree(root: Path, cited_line: int) -> Path:
    """A two-file scratch tree whose only prose is one citation.

    This is the RED fixture. Nothing here is ever committed as a live citation: the wrong
    line number exists only inside a ``tmp_path`` tree that lives for the length of one
    test, so the demonstration cannot leave a defect behind in the repository.
    """
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "src" / "target.py").write_text(
        "\n".join(f"line_{i}" for i in range(1, 6)), encoding="utf-8"
    )
    (root / "src" / "citer.py").write_text(
        f'"""The reader lives at `src/target.py:{cited_line}`."""\n', encoding="utf-8"
    )
    return root


def test_guard_one_goes_red_on_a_citation_past_the_end_of_its_file(tmp_path: Path) -> None:
    """RED, structurally: a wrong citation is CAUGHT, and correcting it clears the guard.

    A guard written against an already-corrected tree is green on arrival, so without this
    there is no evidence it can fail at all. Asserted from both sides - the violation names
    the citation and the target's real length, and the same fixture with the citation
    pointed at a line that exists yields nothing.
    """
    red = _eof_violations(_scratch_tree(tmp_path, cited_line=9999), ("src",))
    assert len(red) == 1, f"expected exactly one violation, got {red}"
    assert "PAST EOF" in red[0], red[0]
    assert "src/target.py:9999" in red[0], red[0]
    assert "5 lines" in red[0], red[0]
    green = _eof_violations(_scratch_tree(tmp_path, cited_line=3), ("src",))
    assert green == [], f"a citation inside the file must be silent, got {green}"


def test_guard_one_reports_an_unresolvable_path_instead_of_skipping_it(tmp_path: Path) -> None:
    """The refusal that matters most: what the resolver cannot parse must FAIL.

    A guard that skipped an unparseable citation would report green while checking nothing,
    which is strictly worse than having no guard - so the unresolvable case is asserted as
    a violation, not as the absence of one.
    """
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "citer.py").write_text(
        '"""Lives at `src/vanished_module.py:12`, which is not in the tree."""\n',
        encoding="utf-8",
    )
    problems = _eof_violations(tmp_path, ("src",))
    assert len(problems) == 1, f"an unresolvable citation must be reported, got {problems}"
    assert "UNRESOLVED" in problems[0], problems[0]
    assert "src/vanished_module.py:12" in problems[0], problems[0]
    assert problems[0].startswith("src/citer.py:1"), problems[0]


def test_guard_one_reports_an_ambiguous_path_too(tmp_path: Path) -> None:
    """Two files sharing a basename is not a resolution, it is a coin toss.

    Bare-module citations are the dialect that needs the basename index, and the index must
    refuse to guess when the guess would be arbitrary.
    """
    (tmp_path / "src" / "a").mkdir(parents=True)
    (tmp_path / "src" / "b").mkdir()
    (tmp_path / "src" / "a" / "shared.py").write_text("x\n", encoding="utf-8")
    (tmp_path / "src" / "b" / "shared.py").write_text("y\n", encoding="utf-8")
    (tmp_path / "src" / "citer.py").write_text('"""See `shared.py:1`."""\n', encoding="utf-8")
    problems = _eof_violations(tmp_path, ("src",))
    assert len(problems) == 1, problems
    assert "AMBIGUOUS" in problems[0], problems[0]


def test_guard_two_goes_red_on_a_symbol_bearing_citation_that_points_elsewhere(
    tmp_path: Path,
) -> None:
    """RED for Guard 2: the named symbol is NOT at the line the citation names.

    The scratch tree is self-contained and the wrong citation exists only inside it, so
    this demonstration cannot leave a live stale citation behind. The first assertion is
    the RED and the next two are the GREENs: a guard proved only in its failing direction
    is a guard nobody can tell apart from a broken one.
    """
    target = tmp_path / "src" / "target.py"
    target.parent.mkdir(parents=True)
    target.write_text(
        "def other() -> None:\n    return None\n\n\ndef wanted() -> None:\n    return None\n",
        encoding="utf-8",
    )
    index = _basename_index(tmp_path)

    def verdict(line: int, symbol: str) -> bool | None:
        return _pairing_verdict(
            tmp_path, Pairing("citer.py", 1, f"src/target.py:{line}", symbol), index
        )

    assert verdict(1, "wanted") is False, "line 1 is `def other`, not `wanted`"
    assert verdict(5, "wanted") is True, "line 5 IS `def wanted`"
    assert verdict(6, "wanted") is True, "line 6 is inside `wanted`'s span"
    assert verdict(2, "renamed_away") is False, "a symbol the file no longer has cannot resolve"


def test_guard_one_reports_a_source_file_it_cannot_read(tmp_path: Path) -> None:
    """The refusal the RED demonstration forced into existence.

    A byte-order mark on a module makes ``ast.parse`` refuse it. Before this guard the
    extractor returned an empty list for that file, the segment total fell by seven
    citations, and everything stayed green — the file had left the corpus without saying
    so. It is now reported, which is the same rule as an unresolvable citation applied to
    the SOURCE rather than to the target.
    """
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "citer.py").write_text('"""Fine on its own."""\n', encoding="utf-8")
    (tmp_path / "src" / "broken.py").write_bytes(
        b'\xef\xbb\xbf"""A byte-order mark makes this unparseable."""\n'
    )
    unreadable = _unreadable_sources(tmp_path, ("src",))
    assert len(unreadable) == 1, f"the unparseable file must be reported, got {unreadable}"
    assert "src/broken.py" in unreadable[0], unreadable[0]
    assert "cannot parse" in unreadable[0], unreadable[0]
    assert _unreadable_sources(_scratch_tree(tmp_path / "clean", 3), ("src",)) == []


def test_guard_two_cannot_decide_a_pairing_whose_target_is_not_python(tmp_path: Path) -> None:
    """A markdown target has no AST symbol table, so the honest answer is «cannot decide».

    Returning False would push every markdown citation into the deferred queue for a reason
    that is not its fault; returning True would invent a proof. None is the only truthful
    third answer, and it routes the entry to the allow-list instead of failing it.
    """
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "note.md").write_text("# note\n", encoding="utf-8")
    index = _basename_index(tmp_path)
    verdict = _pairing_verdict(tmp_path, Pairing("c.py", 1, "docs/note.md:1", "anything"), index)
    assert verdict is None


# ── docs: READ for coverage, never asserted for correctness ────────────────────────


def test_the_docs_segment_is_read_for_coverage_only() -> None:
    """``docs/`` is measured, so this file can report how much it does NOT cover, and it
    is never asserted on - a stale document must never be able to turn this suite red.

    Every number this repository holds about ``docs/`` is N7's to re-derive, so this
    asserts only that the extractor still SEES the segment, which is a claim about the
    guard rather than about any document.
    """
    counts = _citation_counts(REPO)
    found = counts.get(DOCS_SEGMENT, 0)
    assert found >= MIN_DOCS_CITATIONS, (
        f"the extractor found {found} citation(s) under docs/, below the floor of "
        f"{MIN_DOCS_CITATIONS} - the coverage figure this file reports has stopped being "
        "measured"
    )


def test_the_docs_segment_is_never_policed_for_correctness() -> None:
    """The N7 boundary, asserted rather than promised.

    If a later edit adds ``docs`` to ``CODE_SEGMENTS``, this file's whole design changes
    and the suite would start failing for reasons that belong to N7. The boundary is cheap
    to state and expensive to rediscover the hard way.
    """
    assert CODE_SEGMENTS == ("src", "tests"), (
        "docs/ must stay out of the policed segments: its correctness is N7's write-set, "
        "and a citation guard that fails on a stale document would block N7 by "
        "construction"
    )
    assert DOCS_SEGMENT not in CODE_SEGMENTS


@pytest.mark.parametrize("dialect", ["repo-root", "segment-relative", "bare-module"])
def test_the_resolver_handles_every_dialect_the_corpus_uses(dialect: str, tmp_path: Path) -> None:
    """Three spellings, one answer. A resolver that handled only the first would silently
    skip the other two, which is the exact failure mode this node exists to prevent."""
    (tmp_path / "src" / "deeper").mkdir(parents=True)
    (tmp_path / "src" / "deeper" / "nested.py").write_text("a\nb\nc\n", encoding="utf-8")
    index = _basename_index(tmp_path)
    raw = {
        "repo-root": "src/deeper/nested.py",
        "segment-relative": "deeper/nested.py",
        "bare-module": "nested.py",
    }[dialect]
    assert _resolve(raw, tmp_path, index) == [tmp_path / "src" / "deeper" / "nested.py"]
    assert _eof_violations(tmp_path, ("src",)) == []
