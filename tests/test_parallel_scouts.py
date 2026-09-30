"""Contract tests for scripts/launch_parallel_scouts.py.

Two guarantees are under test:

1. Honesty — the four scouts are NOT equivalent. The two internal scouts reduce
   to static AST scans and must return real findings; the two external scouts need
   live web/GitHub access from an LLM, so they must be recorded as
   `deferred_to_harness` with zero findings. Nothing may claim a Group B scout
   scanned anything.
2. Concurrency — the two Group A scouts must genuinely overlap, not run back to
   back. A test with injected delays asserts the wall clock tracks max(delays).

Every detector is exercised against a synthetic temp tree: a dirty fixture must
produce the specific finding, a clean fixture must produce none. The real repo
is never written to.
"""

from __future__ import annotations

import pathlib
import re
import textwrap
import time

import scripts.launch_parallel_scouts as lps

# --------------------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------------------

CLEAN_SRC = {
    "src/__init__.py": "",
    "src/alpha.py": """
        \"\"\"Alpha module.\"\"\"

        from __future__ import annotations

        HAYSTACK = "needle"


        def read_needle(path: object) -> str:
            return path.read_text(encoding="utf-8")
        """,
    "src/beta.py": """
        \"\"\"Beta wires alpha in, so alpha is not dead code.\"\"\"

        from __future__ import annotations

        from src import alpha

        NEEDLE = alpha.HAYSTACK
        """,
}

CLEAN_TESTS = {
    "tests/test_alpha.py": """
        \"\"\"Alpha's own test — the module is built, but it is also wired.\"\"\"

        from __future__ import annotations

        from src import alpha


        def test_haystack():
            assert alpha.HAYSTACK == "needle"
        """,
}


def _tree(tmp_path: pathlib.Path, files: dict[str, str]) -> pathlib.Path:
    """Materialise a synthetic repo from {relative path: source}."""
    root = tmp_path / "repo"
    for rel, body in files.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(textwrap.dedent(body), encoding="utf-8")
    return root


def _clean_tree(tmp_path: pathlib.Path) -> pathlib.Path:
    return _tree(tmp_path, {**CLEAN_SRC, **CLEAN_TESTS})


def _symbols(findings) -> set[str]:
    return {f.symbol for f in findings}


def _locs(findings) -> set[tuple[str, int]]:
    return {(f.path, f.line) for f in findings}


def _headings(markdown: str) -> list[str]:
    return [line for line in markdown.splitlines() if line.startswith("## ")]


# --------------------------------------------------------------------------------------
# 1. bare read_text() / open() without encoding=
# --------------------------------------------------------------------------------------


def test_missing_encoding_flags_bare_read_text(tmp_path):
    """AC1 — the exact defect that broke CI on the sealed Arabic note."""
    root = _tree(
        tmp_path,
        {
            "src/bad.py": """
                \"\"\"Reads a note with the platform default codec.\"\"\"

                from __future__ import annotations

                import pathlib


                def load(path: pathlib.Path) -> str:
                    return path.read_text()
                """,
        },
    )
    findings = lps.find_missing_encodings(root)
    assert ("src/bad.py", 10) in _locs(findings)
    assert any("read_text" in f.detail for f in findings)


def test_missing_encoding_ignores_explicit_encoding(tmp_path):
    """AC2 — read_text(encoding="utf-8") is the fix, not the bug."""
    root = _tree(
        tmp_path,
        {
            "src/good.py": """
                \"\"\"Every read names its codec.\"\"\"

                from __future__ import annotations

                import pathlib


                def load(path: pathlib.Path) -> str:
                    return path.read_text(encoding="utf-8")


                def load_bytes(path: pathlib.Path) -> bytes:
                    with path.open("rb") as handle:
                        return handle.read()
                """,
        },
    )
    assert lps.find_missing_encodings(root) == ()


def test_missing_encoding_flags_bare_open_but_not_binary(tmp_path):
    """AC3 — text-mode open() is exposed; "rb" cannot raise UnicodeDecodeError."""
    root = _tree(
        tmp_path,
        {
            "src/mixed.py": """
                \"\"\"One text open without a codec, one binary open.\"\"\"

                from __future__ import annotations

                import pathlib


                def text_mode(path: pathlib.Path) -> str:
                    with open(path) as handle:
                        return handle.read()


                def binary_mode(path: pathlib.Path) -> bytes:
                    with path.open("rb") as handle:
                        return handle.read()
                """,
        },
    )
    found = lps.find_missing_encodings(root)
    assert [f.line for f in found] == [10]
    assert "open" in found[0].detail


def test_missing_encoding_empty_on_clean_tree(tmp_path):
    assert lps.find_missing_encodings(_clean_tree(tmp_path)) == ()


# --------------------------------------------------------------------------------------
# 2. static registration literals (dynamic-tool hot spots)
# --------------------------------------------------------------------------------------


def test_registration_literals_flags_final_tool_containers(tmp_path):
    """AC4 — Final containers of tool names are the dynamic-tool hot spots."""
    root = _tree(
        tmp_path,
        {
            "src/dispatcher.py": """
                \"\"\"Tool routing table.\"\"\"

                from __future__ import annotations

                from typing import Final

                _VALID_TOOLS: Final = ("none", "gmail", "launch")
                """,
            "src/cognition.py": """
                \"\"\"Goal lexicon per tool.\"\"\"

                from __future__ import annotations

                from typing import Final

                _TOOL_GOALS: Final[dict[str, tuple[str, ...]]] = {
                    "gmail": ("mail", "inbox"),
                    "launch": ("open",),
                }
                _FRESH_MARKERS: Final[tuple[str, ...]] = ("هسا", "الحين")
                """,
        },
    )
    found = lps.find_registration_literals(root)
    assert _symbols(found) == {"_VALID_TOOLS", "_TOOL_GOALS", "_FRESH_MARKERS"}
    hot = [f for f in found if "hot spot" in f.detail]
    assert _symbols(hot) == {"_VALID_TOOLS", "_TOOL_GOALS"}
    assert any("3 names" in f.detail for f in found)


def test_registration_literals_empty_on_clean_tree(tmp_path):
    assert lps.find_registration_literals(_clean_tree(tmp_path)) == ()


# --------------------------------------------------------------------------------------
# 3. built-but-unwired modules
# --------------------------------------------------------------------------------------


def test_unwired_modules_flags_tested_but_unimported(tmp_path):
    """AC5 — a module with its own test but no importer is built, not shipped."""
    root = _tree(
        tmp_path,
        {
            **CLEAN_SRC,
            **CLEAN_TESTS,
            "src/bm25.py": """
                \"\"\"BM25 ranker: pure math, zero I/O.\"\"\"

                from __future__ import annotations

                import math

                K1: float = 1.5


                def score() -> float:
                    return math.log(K1)
                """,
            "tests/test_bm25.py": """
                \"\"\"Its own test exists.\"\"\"

                from __future__ import annotations


                def test_score():
                    assert True
                """,
        },
    )
    found = lps.find_unwired_modules(root)
    assert _symbols(found) == {"bm25"}
    assert found[0].path == "src/bm25.py"
    assert "tests/test_bm25.py" in found[0].detail


def test_unwired_modules_flags_a_module_only_its_own_test_imports(tmp_path):
    """A test importing the module is not wiring. Only a `src/` caller counts.

    `tests/test_bm25.py` does `from src.bm25 import rank`. Counting that would
    hide every unwired module behind its own test — the defect this test pins.
    """
    root = _tree(
        tmp_path,
        {
            **CLEAN_SRC,
            **CLEAN_TESTS,
            "src/bm25.py": """
                \"\"\"BM25 ranker: pure math, zero I/O.\"\"\"

                from __future__ import annotations

                import math

                K1: float = 1.5


                def score() -> float:
                    return math.log(K1)
                """,
            "tests/test_bm25.py": """
                \"\"\"Its own test imports it — which is not wiring.\"\"\"

                from __future__ import annotations

                from src import bm25


                def test_score():
                    assert bm25.score() > 0
                """,
        },
    )
    found = lps.find_unwired_modules(root)
    assert _symbols(found) == {"bm25"}


def test_unwired_modules_empty_when_every_tested_module_is_imported(tmp_path):
    assert lps.find_unwired_modules(_clean_tree(tmp_path)) == ()


def test_unwired_modules_ignores_modules_without_a_dedicated_test(tmp_path):
    """No matching test file -> nothing claims the module was 'built'."""
    root = _tree(tmp_path, {**CLEAN_SRC, "src/orphan.py": "X = 1\n"})
    assert lps.find_unwired_modules(root) == ()


# --------------------------------------------------------------------------------------
# 4. unbounded concurrency
# --------------------------------------------------------------------------------------


def test_unbounded_concurrency_flags_bare_gather(tmp_path):
    """AC6 — the agent_manager.py:247 shape: gather over an unbounded generator."""
    root = _tree(
        tmp_path,
        {
            "src/agent_manager.py": """
                \"\"\"Fan-out with nothing bounding it.\"\"\"

                from __future__ import annotations

                import asyncio

                MAX_LINES = 6


                async def run(lines: list[str]) -> list[str]:
                    reports = await asyncio.gather(*(line.upper() for line in lines))
                    return reports
                """,
        },
    )
    found = lps.find_unbounded_concurrency(root)
    assert _locs(found) == {("src/agent_manager.py", 12)}
    assert found[0].symbol == "run"
    assert "gather" in found[0].detail


def test_fanout_capped_by_an_upstream_helper_is_not_called_unbounded(tmp_path):
    """D1 — the real `agent_manager.py` shape: the cap is one call upstream.

    `lines, trimmed = self._trim_lines(all_lines)` feeds the gather, and
    `_trim_lines` returns `lines[:MAX_LINES]`. Reporting "no obvious bound"
    here is a false statement: the bound exists and is countable.
    """
    root = _tree(
        tmp_path,
        {
            "src/agent_manager.py": """
                \"\"\"Fan-out capped by a helper one call upstream.\"\"\"

                from __future__ import annotations

                import asyncio

                MAX_LINES: int = 4


                async def run(self, items: list[str]) -> list[str]:
                    lines, trimmed = self._trim_lines(items)
                    reports = await asyncio.gather(*(self._one(line) for line in lines))
                    return reports


                def _trim_lines(self, lines: list[str]) -> tuple[list[str], int]:
                    if len(lines) <= MAX_LINES:
                        return lines, 0
                    return lines[:MAX_LINES], len(lines) - MAX_LINES
                """,
        },
    )
    found = lps.find_unbounded_concurrency(root)
    assert [f for f in found if f.kind == "unbounded-concurrency"] == [], (
        "a fan-out capped upstream must not be reported as unbounded"
    )
    bounded = [f for f in found if f.kind == "bounded-fanout"]
    assert len(bounded) == 1
    detail = bounded[0].detail
    assert "_trim_lines" in detail, detail
    assert "MAX_LINES" in detail, detail
    assert bounded[0].line == _line_of(root / "src/agent_manager.py", "return lines[:MAX_LINES]"), (
        "the finding must cite the line that actually holds the cap"
    )


def test_fanout_whose_upstream_helper_does_not_cap_is_unbounded(tmp_path):
    """Control for the test above: same shape, helper returns everything."""
    root = _tree(
        tmp_path,
        {
            "src/runaway.py": """
                \"\"\"Identical shape, but the helper does not cap.\"\"\"

                from __future__ import annotations

                import asyncio

                MAX_LINES: int = 4


                async def run(self, items: list[str]) -> list[str]:
                    lines, trimmed = self._trim_lines(items)
                    reports = await asyncio.gather(*(self._one(line) for line in lines))
                    return reports


                def _trim_lines(self, lines: list[str]) -> tuple[list[str], int]:
                    return lines, 0
                """,
        },
    )
    found = lps.find_unbounded_concurrency(root)
    assert [f.kind for f in found] == ["unbounded-concurrency"]


def test_unbounded_wording_is_scoped_to_what_the_tool_resolved(tmp_path):
    """D1 wording — an absence this tool could not resolve is not an absence.

    The verdict must not read "no bound" flatly: it can only speak about the
    enclosing function and same-file helpers it actually walked.
    """
    root = _tree(
        tmp_path,
        {
            "src/runaway.py": """
                \"\"\"Fan-out with no resolvable cap.\"\"\"

                from __future__ import annotations

                import asyncio


                async def run(lines: list[str]) -> list[str]:
                    reports = await asyncio.gather(*(line.upper() for line in lines))
                    return reports
                """,
        },
    )
    detail = lps.find_unbounded_concurrency(root)[0].detail
    assert "same-file helper" in detail, detail
    assert "outer queue" in detail, detail


def test_unbounded_concurrency_accepts_a_semaphore_in_scope(tmp_path):
    """AC7 — a semaphore or timeout in the enclosing function counts as a bound."""
    root = _tree(
        tmp_path,
        {
            "src/guarded.py": """
                \"\"\"Same fan-out, but bounded.\"\"\"

                from __future__ import annotations

                import asyncio


                async def run(lines: list[str]) -> list[str]:
                    guard = asyncio.Semaphore(4)
                    async def one(line: str) -> str:
                        async with guard:
                            return line.upper()
                    return await asyncio.gather(*(one(line) for line in lines))
                """,
        },
    )
    assert lps.find_unbounded_concurrency(root) == ()


def test_unbounded_concurrency_flags_bare_create_task(tmp_path):
    root = _tree(
        tmp_path,
        {
            "src/fire.py": """
                \"\"\"Spawns work in a bare loop.\"\"\"

                from __future__ import annotations

                import asyncio


                async def run(items: list[str]) -> None:
                    for item in items:
                        asyncio.create_task(item)
                """,
        },
    )
    found = lps.find_unbounded_concurrency(root)
    assert [(f.path, f.line) for f in found] == [("src/fire.py", 11)]
    assert "create_task" in found[0].detail


def test_unbounded_concurrency_empty_on_clean_tree(tmp_path):
    assert lps.find_unbounded_concurrency(_clean_tree(tmp_path)) == ()


# --------------------------------------------------------------------------------------
# 5. silent exception swallows
# --------------------------------------------------------------------------------------


def test_silent_swallows_flags_unjustified_bare_pass(tmp_path):
    """AC8 — broad except + bare pass and no stated reason = silent loss."""
    root = _tree(
        tmp_path,
        {
            "src/quiet.py": """
                \"\"\"Swallows everything and says nothing.\"\"\"

                from __future__ import annotations


                def touch(path: str) -> None:
                    try:
                        raise RuntimeError(path)
                    except Exception:
                        pass
                """,
        },
    )
    found = lps.find_silent_swallows(root)
    assert _locs(found) == {("src/quiet.py", 10)}
    assert found[0].verdict == "unjustified", found[0].detail
    assert "silent" in found[0].detail.lower()
    # The classification is a judgement, so the finding has to say so. Case is
    # not part of the requirement — disclosure is.
    assert "heuristic" in found[0].detail.lower()


def test_silent_swallows_classifies_documented_degradation_as_honest(tmp_path):
    """AC9 — the same shape with a stated degradation reason is honest-offline."""
    root = _tree(
        tmp_path,
        {
            "src/honest.py": """
                \"\"\"Optional enrichment.\"\"\"

                from __future__ import annotations


                def probe() -> str:
                    \"\"\"Probe failure degrades to the greeting.\"\"\"
                    try:
                        raise RuntimeError("offline")
                    except Exception:
                        return ""
                """,
        },
    )
    found = lps.find_silent_swallows(root)
    assert len(found) == 1
    assert found[0].verdict == "deliberate", found[0].detail
    assert "degrades to the greeting" in found[0].detail, (
        "a docstring-stated reason must be quoted too, not just classified"
    )


def test_silent_swallows_ignores_logged_and_narrow_handlers(tmp_path):
    """AC10 — a handler that logs, or that catches a narrow type, is not silent."""
    root = _tree(
        tmp_path,
        {
            "src/loud.py": """
                \"\"\"Logs, and catches precisely.\"\"\"

                from __future__ import annotations

                import logging

                logger = logging.getLogger(__name__)


                def logged() -> None:
                    try:
                        raise RuntimeError
                    except Exception:
                        logger.warning("probe failure degrades", exc_info=True)


                def narrow() -> None:
                    try:
                        raise ValueError
                    except ValueError:
                        pass
                """,
        },
    )
    assert lps.find_silent_swallows(root) == ()


def _line_of(path: pathlib.Path, needle: str) -> int:
    """1-based line number of `needle` in the file — so a test never hardcodes
    line arithmetic and drifts when the fixture grows."""
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if needle in line:
            return number
    raise AssertionError(f"{needle!r} not found in {path}")


def test_silent_swallow_justified_only_by_its_inline_comment(tmp_path):
    """D2 — the handler's own comment is a justification source.

    `ast.unparse` reconstructs source from the AST and drops every comment, so
    reading the reason from there makes the whole signal dead: the comment can
    never be seen. The reason must come from the real source line.
    """
    root = _tree(
        tmp_path,
        {
            "src/only_comment.py": """
                \"\"\"No docstring, no keyword in the name — only the comment.\"\"\"

                from __future__ import annotations


                def _split_frontmatter_safe(text: str) -> tuple[dict, str]:
                    try:
                        return parse(text)
                    except Exception:  # noqa: BLE001 — no frontmatter is still a digest
                        return {}, text
                """,
        },
    )
    found = lps.find_silent_swallows(root)
    assert len(found) == 1
    assert found[0].verdict == "deliberate", found[0].detail
    assert "no frontmatter is still a digest" in found[0].detail, (
        "the stated reason must be quoted in the finding, not just classified"
    )


def test_identical_handlers_differing_only_in_comment_wording_share_a_verdict(tmp_path):
    """D2 invariant — the verdict class may not depend on the phrasing.

    These are the real `src/associative.py:194` and `:459` handlers: same shape,
    same `# noqa: BLE001 —` prefix, each stating its reason in prose. Before the
    fix `:194` was 'deliberate' only because the *function name* contained a
    hint word and `:459` was 'unjustified' because its comment was invisible.
    """
    root = _tree(
        tmp_path,
        {
            "src/twin_a.py": """
                \"\"\"Twin A states its reason on the handler line.\"\"\"

                from __future__ import annotations


                def refresh_if_stale(path: str) -> bool:
                    try:
                        return touch(path)
                    except Exception:  # noqa: BLE001 — stale index beats no index
                        return False
                """,
            "src/twin_b.py": """
                \"\"\"Twin B says the same thing in different words.\"\"\"

                from __future__ import annotations


                def _split_frontmatter_safe(text: str) -> tuple[dict, str]:
                    try:
                        return parse(text)
                    except Exception:  # noqa: BLE001 — no frontmatter is still a digest
                        return {}, text
                """,
        },
    )
    found = lps.find_silent_swallows(root)
    assert len(found) == 2
    verdicts = {f.path: f.verdict for f in found}
    assert verdicts == {"src/twin_a.py": "deliberate", "src/twin_b.py": "deliberate"}, (
        f"verdict flipped on comment wording alone: {verdicts}"
    )
    # The verdict alone is not enough to pin the mechanism: a bug that ignores
    # comments can still land on "deliberate" via the *function name* (twin A is
    # called refresh_if_stale, and "stale" is a hint word), or by treating
    # ast.unparse's `except Exception:` output as if it were a rationale. So
    # also pin that each row quotes its own comment and not the other's.
    quoted = {f.path: f.detail for f in found}
    assert "stale index beats no index" in quoted["src/twin_a.py"]
    assert "no frontmatter is still a digest" in quoted["src/twin_b.py"]
    assert "no frontmatter is still a digest" not in quoted["src/twin_a.py"]


def test_verdict_words_do_not_leak_across_branches(tmp_path):
    """The prose must not contain the opposite verdict's word.

    This is what made the invariant test above vacuous: the unjustified branch
    said "...marks it deliberate instead", so `"deliberate" in detail` was true
    for both classes and no assertion on prose could ever fail. A report reader
    grepping the word hits the same trap.
    """
    root = _tree(
        tmp_path,
        {
            "src/both.py": """
                \"\"\"One unjustified swallow and one deliberate.\"\"\"

                from __future__ import annotations


                def unjustified(path: str) -> None:
                    try:
                        return mark(path)
                    except Exception:
                        pass


                def justified(path: str) -> None:
                    try:
                        return mark(path)
                    except Exception:  # noqa: BLE001 — optional enrichment only
                        pass
                """,
        },
    )
    found = lps.find_silent_swallows(root)
    by_verdict = {f.symbol: f for f in found}
    assert by_verdict["unjustified"].verdict == "unjustified"
    assert by_verdict["justified"].verdict == "deliberate"
    assert "deliberate" not in by_verdict["unjustified"].detail
    assert "unjustified" not in by_verdict["justified"].detail


def test_bare_suppression_pragma_alone_is_not_a_reason(tmp_path):
    """Guard against the opposite failure: `# noqa: BLE001` on its own says the
    author knows the except is broad, not why swallowing is acceptable. That
    stays an unjustified silent loss."""
    root = _tree(
        tmp_path,
        {
            "src/pragma_only.py": """
                \"\"\"Suppression pragma with no stated reason.\"\"\"

                from __future__ import annotations


                def touch(path: str) -> None:
                    try:
                        return mark(path)
                    except Exception:  # noqa: BLE001
                        pass
                """,
        },
    )
    found = lps.find_silent_swallows(root)
    assert len(found) == 1
    assert found[0].verdict == "unjustified", found[0].detail


def test_silent_swallows_empty_on_clean_tree(tmp_path):
    assert lps.find_silent_swallows(_clean_tree(tmp_path)) == ()


# --------------------------------------------------------------------------------------
# scouts, concurrency, and the Group A / Group B split
# --------------------------------------------------------------------------------------


def test_group_a_scouts_cover_every_detector():
    assert lps.GROUP_A == ("internal-codebase-sleuth", "architecture-debt-auditor")
    assert lps.GROUP_B == ("web-intelligence-scout", "github-ecosystem-miner")
    assert lps.SCOUT_NAMES == lps.GROUP_A + lps.GROUP_B
    assert set(lps.GROUP_A).isdisjoint(lps.GROUP_B)


def test_sleuth_scout_reports_findings_for_a_dirty_tree(tmp_path):
    root = _tree(
        tmp_path,
        {
            "src/bad.py": """
                \"\"\"Two defects in one file.\"\"\"

                from __future__ import annotations

                import pathlib


                def load(path: pathlib.Path) -> str:
                    return path.read_text()
                """,
            "src/dead.py": "VALUE = 1\n",
            "tests/test_dead.py": "def test_value():\n    assert True\n",
        },
    )
    result = lps.internal_codebase_sleuth(root)
    assert result.scout == "internal-codebase-sleuth"
    assert result.group == "A"
    assert result.status == "completed"
    kinds = {f.kind for f in result.findings}
    assert "missing-encoding" in kinds
    assert "unwired-module" in kinds


def test_architecture_auditor_reports_findings_for_a_dirty_tree(tmp_path):
    root = _tree(
        tmp_path,
        {
            "src/debt.py": """
                \"\"\"Unbounded fan-out plus a silent swallow.\"\"\"

                from __future__ import annotations

                import asyncio


                async def run(items: list[str]) -> None:
                    await asyncio.gather(*(asyncio.sleep(0) for _ in items))


                def quiet() -> None:
                    try:
                        raise RuntimeError
                    except Exception:
                        pass
                """,
        },
    )
    result = lps.architecture_debt_auditor(root)
    assert result.scout == "architecture-debt-auditor"
    assert {f.kind for f in result.findings} == {"unbounded-concurrency", "silent-swallow"}


def test_scouts_degrade_gracefully_on_a_missing_repo(tmp_path):
    """A tree that does not exist is reported, never a traceback."""
    absent = tmp_path / "not-a-repo"
    results = lps.run_group_a(absent)
    assert [r.scout for r in results] == list(lps.GROUP_A)
    for result in results:
        assert result.status == "completed"
        assert result.findings == ()
        assert any("src" in note for note in result.notes)
    assert lps.missing_trees(absent) == ("src", "tests")


def test_scouts_survive_a_syntactically_broken_module(tmp_path):
    root = _tree(
        tmp_path,
        {
            "src/broken.py": "def oops(:\n",
            "src/fine.py": "VALUE = 1\n",
        },
    )
    result = lps.internal_codebase_sleuth(root)
    assert result.status == "completed"
    assert any("broken.py" in note for note in result.notes)


def test_group_a_scouts_run_concurrently_not_back_to_back(tmp_path):
    """The load-bearing test: wall clock tracks max(delays), not sum(delays)."""
    delay = 0.35
    delays = {name: delay for name in lps.GROUP_A}
    summed = sum(delays.values())

    started = time.perf_counter()
    results = lps.run_group_a(_clean_tree(tmp_path), delays=delays)
    concurrent_elapsed = time.perf_counter() - started

    assert [r.scout for r in results] == list(lps.GROUP_A)
    assert all(r.status == "completed" for r in results)
    assert concurrent_elapsed >= delay, "the injected work did not happen"
    assert concurrent_elapsed < 0.75 * summed, (
        f"expected overlap (max={delay}s), took {concurrent_elapsed:.3f}s "
        f"which is ~sum({summed}s) — the scouts ran serially"
    )


def test_single_worker_serialises_proving_the_knob_is_real(tmp_path):
    """Control for the concurrency test: max_workers=1 pays sum(delays)."""
    delay = 0.25
    delays = {name: delay for name in lps.GROUP_A}
    started = time.perf_counter()
    results = lps.run_group_a(_clean_tree(tmp_path), delays=delays, max_workers=1)
    serial_elapsed = time.perf_counter() - started
    assert len(results) == len(lps.GROUP_A)
    assert serial_elapsed >= 0.9 * sum(delays.values())


def test_group_b_is_deferred_to_the_harness_never_scanned():
    deferred = lps.deferred_to_harness()
    assert [r.scout for r in deferred] == list(lps.GROUP_B)
    for result in deferred:
        assert result.status == "deferred_to_harness"
        assert result.group == "B"
        assert result.findings == ()
        assert result.notes, "a deferred scout must still say what it would have done"


def test_run_all_scouts_returns_four_results_in_canonical_order(tmp_path):
    results = lps.run_all_scouts(_clean_tree(tmp_path))
    assert [r.scout for r in results] == list(lps.SCOUT_NAMES)
    assert [r.status for r in results] == ["completed", "completed"] + ["deferred_to_harness"] * 2


# --------------------------------------------------------------------------------------
# report + CLI
# --------------------------------------------------------------------------------------


def test_report_has_one_section_per_scout_and_stays_valid_markdown(tmp_path):
    results = lps.run_all_scouts(_clean_tree(tmp_path))
    markdown = lps.render_report(results, repo=_clean_tree(tmp_path))
    headings = _headings(markdown)
    for name in lps.SCOUT_NAMES:
        assert any(name in h for h in headings), f"no section for {name}"
    assert markdown.count("```") % 2 == 0, "unbalanced code fence"
    assert "deferred_to_harness" in markdown
    assert "Total findings" in markdown


def test_report_writes_to_the_requested_path(tmp_path):
    root = _clean_tree(tmp_path)
    results = lps.run_all_scouts(root)
    target = tmp_path / "out" / "PARALLEL_SCOUT_REPORT.md"
    written = lps.write_report(lps.render_report(results, repo=root), target)
    assert written == target
    assert target.read_text(encoding="utf-8") == lps.render_report(results, repo=root)
    assert target.parent.is_dir()


def test_default_report_lives_under_benchmarks():
    assert lps.DEFAULT_REPORT.name == "PARALLEL_SCOUT_REPORT.md"
    assert lps.DEFAULT_REPORT.parent.name == "benchmarks"
    assert lps.DEFAULT_REPORT == lps.REPO / "benchmarks" / "PARALLEL_SCOUT_REPORT.md"


def test_deferred_scouts_never_render_as_scanned_findings(tmp_path):
    root = _clean_tree(tmp_path)
    markdown = lps.render_report(lps.run_all_scouts(root), repo=root)
    sections = _split_sections(markdown)
    for name in lps.GROUP_B:
        section = sections[name]
        assert "deferred_to_harness" in section
        assert "not scriptable" in section.lower()
        assert re.search(r"^\s*-\s*Findings:\s*0", section, re.MULTILINE) is None, (
            f"{name} was rendered as a scanning scout"
        )


def test_report_counts_informational_rows_apart_from_defects(tmp_path):
    """A `bounded-fanout` row is a resolved cap, not something to fix.

    If it were counted as a defect the summary line would tell a reader to go
    look at 57 problems when the headline one is already resolved.
    """
    root = _tree(
        tmp_path,
        {
            "src/capped.py": """
                \"\"\"A fan-out whose cap lives one call upstream.\"\"\"

                from __future__ import annotations

                import asyncio

                MAX_LINES: int = 4


                async def run(self, items: list[str]) -> list[str]:
                    lines, trimmed = self._trim_lines(items)
                    reports = await asyncio.gather(*(self._one(line) for line in lines))
                    return reports


                def _trim_lines(self, lines: list[str]) -> tuple[list[str], int]:
                    if len(lines) <= MAX_LINES:
                        return lines, 0
                    return lines[:MAX_LINES], len(lines) - MAX_LINES
                """,
        },
    )
    markdown = lps.render_report(lps.run_all_scouts(root), repo=root)
    assert "0 to look at, 1 informational" in markdown, markdown[:1200]
    assert "bounded-fanout" in lps.INFORMATIONAL_KINDS
    assert "not defects" in markdown


def test_main_is_callable_and_writes_to_the_requested_out_path(tmp_path):
    root = _clean_tree(tmp_path)
    out = tmp_path / "benchmarks" / "REPORT.md"
    assert lps.main(["--repo", str(root), "--out", str(out)]) == 0
    assert out.is_file()
    assert "internal-codebase-sleuth" in out.read_text(encoding="utf-8")


def test_main_reports_a_missing_repo_without_crashing(tmp_path, capsys):
    assert lps.main(["--repo", str(tmp_path / "ghost"), "--out", str(tmp_path / "r.md")]) == 0
    assert "deferred_to_harness" in (tmp_path / "r.md").read_text(encoding="utf-8")
    assert "ghost" in capsys.readouterr().out


def _split_sections(markdown: str) -> dict[str, str]:
    """Map scout name -> the full '## ' section that announces it."""
    out: dict[str, str] = {}
    heading: str | None = None
    body: list[str] = []

    def flush() -> None:
        if heading is None:
            return
        for name in lps.SCOUT_NAMES:
            if name in heading:
                out[name] = "\n".join([heading, *body])

    for line in markdown.splitlines():
        if line.startswith("## "):
            flush()
            heading, body = line, []
        elif heading is not None:
            body.append(line)
    flush()
    return {name: out[name] for name in lps.SCOUT_NAMES if name in out}
