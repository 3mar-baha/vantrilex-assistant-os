"""Concurrent runner for Sara's four reconnaissance scouts.

The honest split
----------------
A Python process cannot spawn OpenCode harness sub-agents: the harness itself
dispatches `explore` / `general` agents. Pretending otherwise would produce a
report full of fabricated findings. So the four scouts are split in two:

* **Group A — internal, deterministic, really runs here.** `internal-codebase-sleuth`
  and `architecture-debt-auditor` reduce to static AST scans over this repo, so
  they are implemented as real detectors and run *concurrently* on a
  `concurrent.futures.ThreadPoolExecutor` (AST work is C-bound and the scanners
  block on file I/O, so threads overlap cleanly; a process pool would pay
  interpreter start-up per scout for no gain).

* **Group B — external, LLM-driven, deferred to the harness.**
  `web-intelligence-scout` and `github-ecosystem-miner` need live web and GitHub
  access *from a model*. This script emits a dispatch manifest — the role and
  prompt to hand the harness — and records them as `deferred_to_harness` with
  zero findings. A deferred scout never claims to have scanned anything.

What Group A detects (all verified against this repo, not invented):

1. `read_text()` / `open()` with no `encoding=` — the defect that broke CI on a
   sealed Arabic note with `UnicodeDecodeError` under the cp1252 default.
2. Static registration literals: `Final` containers of tool names. Any
   dynamic-tool work has to touch these by hand; they are the hot spots.
3. Built-but-unwired modules: a `src/<name>.py` with a matching
   `tests/test_<name>.py` but no importer anywhere under `src/` (`bm25` is the
   known one).
4. Fan-out sites: `asyncio.gather` / `create_task` / `TaskGroup`. The detector
   resolves the cap before calling anything unbounded — including one applied
   upstream by a same-file helper — and when it cannot resolve one it says so
   as an absence of evidence rather than an absence of a bound.
5. Silent exception swallows: broad `except` whose whole body is `pass`/`return`
   with no logging — classified as deliberate degradation or unjustified silent
   loss by one question: **did the author state a reason?** The reason is read
   from the real source line via `tokenize`; `ast.unparse` discards comments,
   so it cannot be used for this. A bare `# noqa` is a suppression, not a
   reason. **The judgement that a stated reason is good enough is a heuristic**;
   the report says so on every row.

Usage:
    python scripts/launch_parallel_scouts.py            # -> benchmarks/PARALLEL_SCOUT_REPORT.md
    python scripts/launch_parallel_scouts.py --delay 1.0   # prove the overlap on the clock
    python scripts/launch_parallel_scouts.py --out /tmp/r.md --max-workers 2

Standard library only — no project dependencies, so this runs standalone.
Writes exactly one file, and nothing outside `benchmarks/` unless `--out` says
otherwise. A missing or unparseable repo is reported, never a traceback.
"""

from __future__ import annotations

import argparse
import ast
import concurrent.futures
import dataclasses
import io
import pathlib
import re
import sys
import time
import tokenize
from collections.abc import Callable, Mapping, Sequence

REPO = pathlib.Path(__file__).resolve().parents[1]
SCAN_TREES = ("src", "tests")
DEFAULT_REPORT = REPO / "benchmarks" / "PARALLEL_SCOUT_REPORT.md"
MAX_FINDINGS_IN_TABLE = 200

SKIP_DIRS = frozenset(
    {".git", ".venv", "__pycache__", ".pytest_cache", ".ruff_cache", "htmlcov", "node_modules"}
)

GROUP_A = ("internal-codebase-sleuth", "architecture-debt-auditor")
GROUP_B = ("web-intelligence-scout", "github-ecosystem-miner")
SCOUT_NAMES = GROUP_A + GROUP_B
INFORMATIONAL_KINDS = frozenset({"bounded-fanout"})

DEGRADATION_HINTS = (
    "degrade",
    "offline",
    "fallback",
    "fall back",
    "best-effort",
    "best effort",
    "optional",
    "no-op",
    "noop",
    "unavailable",
    "unsupported",
    "never blocks",
    "never kills",
    "stale",
    "unreachable",
)
BOUND_HINTS = ("semaphore", "capacitylimiter", "max_concurrency", "throttl")


# --------------------------------------------------------------------------------------
# data shapes
# --------------------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True, slots=True)
class Finding:
    """One verified code fact, anchored at file:line.

    `verdict` is the machine-readable classification the detector reached
    ("deliberate" / "unjustified" for a silent swallow, "" when the detector
    makes no call). Tests assert on it rather than on the detail prose: prose
    is for humans, and grepping it is how a guard silently stops being able to
    fail.
    """

    kind: str
    path: str
    line: int
    symbol: str
    detail: str
    verdict: str = ""

    @property
    def location(self) -> str:
        return f"{self.path}:{self.line}" if self.line else self.path


@dataclasses.dataclass(frozen=True, slots=True)
class ScoutResult:
    """What one scout did. `status` is the honesty contract:

    * ``completed``           — the scout ran in this process and these are its findings
    * ``deferred_to_harness`` — not scriptable here; findings is always empty
    * ``failed``              — the scout raised; the run continued without it
    """

    scout: str
    group: str
    status: str
    findings: tuple[Finding, ...] = ()
    notes: tuple[str, ...] = ()
    duration_s: float = 0.0
    detectors: tuple[str, ...] = ()
    manifest: str = ""
    error: str = ""

    @property
    def finding_count(self) -> int:
        return len(self.findings)


@dataclasses.dataclass(frozen=True, slots=True)
class DeferredScout:
    """A scout a model must run. This script only writes its orders."""

    name: str
    role: str
    objective: str
    focus: tuple[str, ...]
    deliverable: str

    def prompt(self) -> str:
        lines = [
            f"role: {self.role}",
            f"objective: {self.objective}",
            "",
            "focus:",
            *(f"  - {item}" for item in self.focus),
            "",
            f"deliverable: {self.deliverable}",
            "",
            "Ground every claim in a URL or an exact file:line. Report what you could",
            "NOT verify as explicitly unverified. Do not restate this repo's own docs",
            "as if they were external evidence.",
        ]
        return "\n".join(lines)


DEFERRED_SPECS = (
    DeferredScout(
        name="web-intelligence-scout",
        role="general (needs live web fetch; `explore` is repo-local and cannot)",
        objective=(
            "Map what the outside world publishes about Telegram LLM assistants, "
            "Arabic/Jordanian dialect voice UX, and personal-assistant memory "
            "design, and separate signal from marketing copy."
        ),
        focus=(
            "production write-ups of Telegram bots with LLM routing (not toy repos)",
            "Arabic (incl. Levantine dialect) speech/NLU UX: what users actually accept",
            "retrieval + memory architectures that survived contact with real users",
            "failure reports: rate limits, model drift, prompt-injection incidents",
        ),
        deliverable=(
            "a dated, URL-cited list of 5-10 findings, each tagged "
            "actionable-for-Sara / not-actionable, plus an explicit unverified list"
        ),
    ),
    DeferredScout(
        name="github-ecosystem-miner",
        role="general (needs GitHub API + network; a model has to do the fetching)",
        objective=(
            "Find the maintainers, forks and dependents that matter for the libraries "
            "and patterns this repo bet on, and where those bets are going stale."
        ),
        focus=(
            "health of the Telegram/aiogram + LLM-gateway dependencies pinned in requirements.txt",
            "active alternatives to the dispatch/keyword-routing pattern in src/dispatcher.py",
            "forks and downstream dependents of any repo this project tracks",
            "recurring CVEs and abandoned-maintainer signals for what we depend on",
        ),
        deliverable=(
            "a table of dependency -> last release -> open-issue/CVE signal -> "
            "recommendation, each row with a source URL"
        ),
    ),
)


# --------------------------------------------------------------------------------------
# repo index (built once per scout run, shared by every detector)
# --------------------------------------------------------------------------------------


@dataclasses.dataclass(slots=True)
class RepoIndex:
    """Parsed source for the scanned trees, plus what could not be read.

    `lines` and `comment_rows` exist because `ast` throws comments away: a
    justification written on a handler line is invisible to `ast.unparse`, so
    anything that reasons about a comment must read the real text.
    """

    root: pathlib.Path
    files: tuple[pathlib.Path, ...] = ()
    missing_trees: tuple[str, ...] = ()
    unparseable: tuple[tuple[str, str], ...] = ()
    trees: dict[str, ast.Module] = dataclasses.field(default_factory=dict)
    lines: dict[str, tuple[str, ...]] = dataclasses.field(default_factory=dict)
    defs: dict[str, list[tuple[str, ast.AST]]] = dataclasses.field(default_factory=dict)
    _comments: dict[str, dict[int, str]] = dataclasses.field(default_factory=dict, repr=False)

    def rel(self, path: pathlib.Path) -> str:
        try:
            return path.relative_to(self.root).as_posix()
        except ValueError:
            return path.as_posix()

    def comment_rows(self, rel: str) -> dict[int, str]:
        """{1-based line: comment text} for one file, or {} if it cannot be read.

        Built with `tokenize`, not `str.split("#")`: a `#` inside a string
        literal is not a comment.
        """
        if rel in self._comments:
            return self._comments[rel]
        rows: dict[int, str] = {}
        source = "\n".join(self.lines.get(rel, ()))
        if source:
            try:
                tokens = tokenize.generate_tokens(io.StringIO(source).readline)
                rows = {t.start[0]: t.string for t in tokens if t.type == tokenize.COMMENT}
            except (tokenize.TokenError, IndentationError, SyntaxError, ValueError):
                rows = {}
        self._comments[rel] = rows
        return rows

    def notes(self) -> tuple[str, ...]:
        out = [
            f"missing tree: `{tree}/` not found — nothing scanned there"
            for tree in self.missing_trees
        ]
        for rel, err in self.unparseable:
            out.append(f"`{rel}` is unparseable ({err}) — skipped, not silently ignored")
        return tuple(out)


def missing_trees(repo: pathlib.Path | str) -> tuple[str, ...]:
    """The scanned trees that do not exist under `repo`. Never raises."""
    root = pathlib.Path(repo)
    return tuple(tree for tree in SCAN_TREES if not (root / tree).is_dir())


def build_index(repo: pathlib.Path | str) -> RepoIndex:
    index = RepoIndex(root=pathlib.Path(repo))
    files: list[pathlib.Path] = []
    for tree in SCAN_TREES:
        base = index.root / tree
        if not base.is_dir():
            index.missing_trees += (tree,)
            continue
        files.extend(p for p in sorted(base.rglob("*.py")) if not _skipped(p, index.root))
    index.files = tuple(files)
    unparseable: list[tuple[str, str]] = []
    trees: dict[str, ast.Module] = {}
    lines: dict[str, tuple[str, ...]] = {}
    defs: dict[str, list[tuple[str, ast.AST]]] = {}
    for path in index.files:
        rel = index.rel(path)
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError as error:
            unparseable.append((rel, f"unreadable: {error.__class__.__name__}"))
            continue
        lines[rel] = tuple(source.splitlines())
        try:
            tree = ast.parse(source, filename=rel)
        except (SyntaxError, ValueError) as error:
            unparseable.append((rel, f"{error.__class__.__name__}: {error}"))
            continue
        trees[rel] = tree
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                defs.setdefault(node.name, []).append((rel, node))
    index.trees = trees
    index.lines = lines
    index.defs = defs
    index.unparseable = tuple(unparseable)
    return index


def _skipped(path: pathlib.Path, root: pathlib.Path) -> bool:
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        return False
    return any(part in SKIP_DIRS for part in parts[:-1])


def _index(repo: pathlib.Path | str, index: RepoIndex | None) -> RepoIndex:
    return build_index(repo) if index is None else index


def _walk_scoped(
    node: ast.AST, scope: tuple[str, ...] = (), owner: ast.AST | None = None
) -> Callable:
    """Yield (node, dotted-scope-name, nearest-enclosing-function) for a whole tree."""
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        scope = (*scope, node.name)
        owner = node
    yield node, (".".join(scope) or "<module>"), owner
    for child in ast.iter_child_nodes(node):
        yield from _walk_scoped(child, scope, owner)


# --------------------------------------------------------------------------------------
# detector 1 — read_text()/open() with no encoding=
# --------------------------------------------------------------------------------------


def find_missing_encodings(
    repo: pathlib.Path | str, *, index: RepoIndex | None = None
) -> tuple[Finding, ...]:
    """Text reads that inherit the platform codec (cp1252 on Windows).

    The exact shape that failed CI: a sealed Arabic note read with the default
    codec raises UnicodeDecodeError. Binary mode cannot raise it, so `"rb"` is
    not flagged.
    """
    idx = _index(repo, index)
    out: list[Finding] = []
    for rel, tree in idx.trees.items():
        for node, scope, _ in _walk_scoped(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "read_text":
                if _has_encoding(node):
                    continue
                out.append(
                    Finding(
                        kind="missing-encoding",
                        path=rel,
                        line=node.lineno,
                        symbol=scope,
                        detail=(
                            "`read_text()` with no `encoding=` — inherits the platform "
                            "default codec (cp1252 on Windows), so non-ASCII notes raise "
                            "UnicodeDecodeError"
                        ),
                    )
                )
            elif _is_open_call(func) and not _has_encoding(node) and not _is_binary(node):
                out.append(
                    Finding(
                        kind="missing-encoding",
                        path=rel,
                        line=node.lineno,
                        symbol=scope,
                        detail=(
                            "`open()` in text mode with no `encoding=` — same cp1252 trap "
                            "as a bare `read_text()`"
                        ),
                    )
                )
    return _sorted(out)


def _is_open_call(func: ast.AST) -> bool:
    if isinstance(func, ast.Name):
        return func.id == "open"
    return isinstance(func, ast.Attribute) and func.attr == "open"


def _has_encoding(call: ast.Call) -> bool:
    if any(kw.arg == "encoding" for kw in call.keywords):
        return True
    first = call.args[0] if call.args else None
    return isinstance(first, ast.Constant) and isinstance(first.value, str)


def _is_binary(call: ast.Call) -> bool:
    mode = "r"
    if len(call.args) > 1 and isinstance(call.args[1], ast.Constant):
        mode = str(call.args[1].value or "")
    for kw in call.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
            mode = str(kw.value.value or "")
    return "b" in mode


# --------------------------------------------------------------------------------------
# detector 2 — static registration literals (dynamic-tool hot spots)
# --------------------------------------------------------------------------------------


def find_registration_literals(
    repo: pathlib.Path | str, *, index: RepoIndex | None = None
) -> tuple[Finding, ...]:
    """`Final` containers of tool-name literals — the hand-edited registries.

    A tool that is not in these literals is not routable, so any dynamic-tool
    work has to start here. Names containing TOOL are the registries proper;
    other `Final` string containers are reported as adjacent, lower-confidence
    candidates.
    """
    idx = _index(repo, index)
    out: list[Finding] = []
    for rel, tree in idx.trees.items():
        for node, _scope, _ in _walk_scoped(tree):
            if not isinstance(node, ast.AnnAssign) or not isinstance(node.target, ast.Name):
                continue
            if not _is_final(node.annotation):
                continue
            count = _container_size(node.value)
            if not count:
                continue
            name = node.target.id
            registry = "TOOL" in name.upper()
            verdict = (
                "hot spot for any dynamic-tool work: a new tool is unroutable until it "
                "is added here by hand"
                if registry
                else "adjacent `Final` string container — not a tool registry by name"
            )
            out.append(
                Finding(
                    kind="registration-literal",
                    path=rel,
                    line=node.lineno,
                    symbol=name,
                    detail=f"`Final` container holding {count} names — {verdict}",
                )
            )
    return _sorted(out)


def _is_final(annotation: ast.AST) -> bool:
    if isinstance(annotation, ast.Name):
        return annotation.id == "Final"
    if isinstance(annotation, ast.Subscript):
        return _is_final(annotation.value)
    return False


def _container_size(value: ast.AST | None) -> int:
    """How many string names a literal container holds; 0 when it is not one."""
    if isinstance(value, ast.Tuple | ast.List | ast.Set):
        return sum(1 for item in value.elts if isinstance(item, ast.Constant))
    if isinstance(value, ast.Dict):
        return sum(1 for key in value.keys if isinstance(key, ast.Constant))
    return 0


# --------------------------------------------------------------------------------------
# detector 3 — built-but-unwired modules
# --------------------------------------------------------------------------------------


def find_unwired_modules(
    repo: pathlib.Path | str, *, index: RepoIndex | None = None
) -> tuple[Finding, ...]:
    """Modules that have a test but no importer — built and proven, never shipped.

    Import is resolved by AST, so a mention in a docstring or a string does not
    count. A module reached only through a dynamic import would be a false
    positive; no such mechanism exists in this repo today.
    """
    idx = _index(repo, index)
    src = idx.root / "src"
    if not src.is_dir():
        return ()
    tests = idx.root / "tests"
    out: list[Finding] = []
    for path in sorted(src.rglob("*.py")):
        if _skipped(path, idx.root):
            continue
        stem = path.stem
        if stem == "__init__":
            continue
        test_file = tests / f"test_{stem}.py"
        if not test_file.is_file():
            continue
        if _is_imported(stem, idx, exclude=path):
            continue
        test_rel = test_file.relative_to(idx.root).as_posix()
        out.append(
            Finding(
                kind="unwired-module",
                path=idx.rel(path),
                line=0,
                symbol=stem,
                detail=(
                    f"has `{test_rel}` but no importer anywhere under `src/` — "
                    "built and tested, never wired into the running bot"
                ),
            )
        )
    return _sorted(out)


def _is_imported(stem: str, idx: RepoIndex, *, exclude: pathlib.Path) -> bool:
    """True when a module *under src/* imports `stem`.

    Only `src/` counts. A module whose sole importer is its own test is exactly
    the built-but-unwired case, so scanning `tests/` here would hide every hit
    behind the test that is supposed to prove it works.
    """
    exclude_rel = idx.rel(exclude)
    for rel, tree in idx.trees.items():
        if rel == exclude_rel or not rel.startswith("src/"):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                if any(alias.name.split(".")[-1] == stem for alias in node.names):
                    return True
            elif isinstance(node, ast.ImportFrom):
                base = node.module.split(".")[-1] if node.module else ""
                if base == stem or any(alias.name == stem for alias in node.names):
                    return True
    return False


# --------------------------------------------------------------------------------------
# detector 4 — unbounded concurrency
# --------------------------------------------------------------------------------------


def find_unbounded_concurrency(
    repo: pathlib.Path | str, *, index: RepoIndex | None = None
) -> tuple[Finding, ...]:
    """Fan-out sites, split by whether this tool can resolve a bound.

    Three outcomes, and the difference matters more than the count:

    * **no output** — a bound is in scope (semaphore, `timeout=`, `MAX_*` slice).
    * **`bounded-fanout`** — the cap was found *upstream*: the awaited iterable
      is produced by a same-file helper that slices it. This is a fact, not a
      defect, and it is reported so the audit trail shows where the bound is
      instead of staying silent.
    * **`unbounded-concurrency`** — no bound was resolved. The wording states
      that this is an absence of evidence in the enclosing function and the
      same-file helpers it calls, never an absence of a bound anywhere: a cap
      enforced by an outer queue, another process, or a limit set above this
      file is invisible to a per-file AST walk.

    A `MAX_*` constant merely *mentioned* in the body is not a cap. `MAX_LINES`
    in `agent_manager.py` bounds how many lines exist, not how many run at
    once; the cap that matters is the `lines[:MAX_LINES]` inside `_trim_lines`.
    """
    idx = _index(repo, index)
    out: list[Finding] = []
    for rel, tree in idx.trees.items():
        parents = _parent_map(tree)
        for node, scope, owner in _walk_scoped(tree):
            call = _fanout_call(node)
            if call is None or _bounded(call, owner):
                continue
            name = _call_name(call)
            cap = _upstream_cap(call, owner, idx, parents, rel)
            if cap is not None:
                cap_line, cap_reason = cap
                out.append(
                    Finding(
                        kind="bounded-fanout",
                        path=rel,
                        line=cap_line,
                        symbol=scope,
                        detail=(
                            f"bound RESOLVED for `{name}()`: {cap_reason}. The fan-out at "
                            f"line {call.lineno} draws from a capped iterable. "
                            f"Informational — not a defect"
                        ),
                        verdict="bounded",
                    )
                )
                continue
            out.append(
                Finding(
                    kind="unbounded-concurrency",
                    path=rel,
                    line=call.lineno,
                    symbol=scope,
                    detail=(
                        f"`{name}()` fans out and no bound was resolved: none in the "
                        f"enclosing function, and none in any same-file helper it calls. "
                        f"That is an absence of evidence in this file, not proof of "
                        f"unboundedness — a cap enforced by an outer queue, another "
                        f"process, or a limit set above this file would not be visible "
                        f"here"
                    ),
                    verdict="unresolved",
                )
            )
    return _sorted(out)


def _parent_map(tree: ast.AST) -> dict[int, ast.AST]:
    parents: dict[int, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[id(child)] = parent
    return parents


def _driver_names(call: ast.Call, parents: Mapping[int, ast.AST]) -> set[str]:
    """The names the fan-out iterates over — what a cap would have to apply to."""
    names: set[str] = set()
    for arg in call.args:
        for node in ast.walk(arg):
            if isinstance(node, ast.GeneratorExp | ast.ListComp | ast.SetComp):
                names.update(
                    gen.iter.id for gen in node.generators if isinstance(gen.iter, ast.Name)
                )
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "map"
                and node.args
                and isinstance(node.args[-1], ast.Name)
            ):
                names.add(node.args[-1].id)
    current = parents.get(id(call))
    while current is not None:
        if isinstance(current, ast.For) and isinstance(current.iter, ast.Name):
            names.add(current.iter.id)
        current = parents.get(id(current))
    return names


def _upstream_cap(
    call: ast.Call, owner: ast.AST | None, idx: RepoIndex, parents: Mapping[int, ast.AST], rel: str
) -> tuple[int, str] | None:
    """Find a cap on the awaited iterable: (line holding the cap, why)."""
    if owner is None:
        return None
    for driver in _driver_names(call, parents):
        for node in ast.walk(owner):
            if isinstance(node, ast.Assign) and _binds(node.targets, driver):
                hit = _cap_in_value(node.value, idx, rel)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                hit = _cap_in_value(node.value, idx, rel) if node.target.id == driver else None
            elif (
                isinstance(node, ast.For)
                and isinstance(node.iter, ast.Name)
                and node.iter.id == driver
            ):
                hit = _cap_in_value(node.iter, idx, rel)
            else:
                hit = None
            if hit is not None:
                return hit
    return None


def _binds(targets: list[ast.expr], name: str) -> bool:
    for target in targets:
        if isinstance(target, ast.Name) and target.id == name:
            return True
        if isinstance(target, ast.Tuple | ast.List) and any(
            isinstance(el, ast.Name) and el.id == name for el in target.elts
        ):
            return True
    return False


def _slice_bound(node: ast.Slice) -> str | None:
    """The constant a slice caps at, as source text; None when it caps nothing."""
    upper = node.upper
    if isinstance(upper, ast.Constant) and isinstance(upper.value, int) and upper.value > 0:
        return str(upper.value)
    if isinstance(upper, ast.Name):
        return upper.id
    return None


def _cap_in_value(value: ast.AST, idx: RepoIndex, rel: str) -> tuple[int, str] | None:
    """A slice cap, either inline or inside a same-file helper we can resolve."""
    for node in ast.walk(value):
        if isinstance(node, ast.Slice):
            bound = _slice_bound(node)
            if bound:
                return node.lineno, f"the iterable is sliced at `{bound}`"
    if isinstance(value, ast.Call):
        callee = _call_name(value)
        for other_rel, node in idx.defs.get(callee, ()):
            if other_rel != rel:
                continue
            for inner in ast.walk(node):
                if isinstance(inner, ast.Slice):
                    bound = _slice_bound(inner)
                    if bound:
                        return inner.lineno, (
                            f"`{callee}()` (line {value.lineno}) caps the iterable by "
                            f"slicing it at `{bound}`"
                        )
    return None


FANOUT_ATTRS = frozenset({"gather", "create_task", "as_completed", "wait_for", "TaskGroup"})


def _fanout_call(node: ast.AST) -> ast.Call | None:
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    if isinstance(func, ast.Attribute) and func.attr in FANOUT_ATTRS:
        return node
    return None


def _call_name(call: ast.Call) -> str:
    return call.func.attr if isinstance(call.func, ast.Attribute) else "call"


def _bounded(call: ast.Call, owner: ast.AST | None) -> bool:
    if any(kw.arg in {"timeout", "max_concurrency"} for kw in call.keywords):
        return True
    if any(_has_max_slice(arg) for arg in call.args):
        return True
    if owner is None:
        return False
    body = ast.unparse(owner).lower()
    return any(hint in body for hint in BOUND_HINTS)


def _has_max_slice(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if (
            isinstance(child, ast.Slice)
            and isinstance(child.upper, ast.Name)
            and child.upper.id.upper().startswith("MAX")
        ):
            return True
    return False


# --------------------------------------------------------------------------------------
# detector 5 — silent exception swallows
# --------------------------------------------------------------------------------------


def find_silent_swallows(
    repo: pathlib.Path | str, *, index: RepoIndex | None = None
) -> tuple[Finding, ...]:
    """Broad `except` whose entire body is `pass`/`return` and which logs nothing.

    The verdict asks one question: **did the author state a reason?** The
    primary evidence is the handler's own comment, read from the real source
    line via `tokenize` — never via `ast.unparse`, which discards comments and
    would make the signal permanently dead. A comment that survives pragma
    stripping counts whatever its wording, because prose reasons are not
    keywords; keyword matching is only the fallback for an enclosing docstring
    or function name, and it is labelled as such.
    """
    idx = _index(repo, index)
    out: list[Finding] = []
    for rel, tree in idx.trees.items():
        for node, scope, owner in _walk_scoped(tree):
            if not isinstance(node, ast.ExceptHandler) or not _is_broad(node):
                continue
            if not _is_silent_body(node):
                continue
            action = "pass" if _is_pass_body(node) else "return"
            verdict, reason, where = _justification(node, owner, idx, rel)
            if verdict == "deliberate":
                detail = (
                    f"broad `except {BROAD_NAMES}` whose whole body is a bare `{action}` "
                    f"and which logs nothing — deliberate degradation: a reason is stated "
                    f'in {where} — "{reason}". Heuristic: this judges whether a reason was '
                    f"stated, not whether it is a good one"
                )
            else:
                detail = (
                    f"broad `except {BROAD_NAMES}` whose whole body is a bare `{action}` "
                    f"and which logs nothing — unjustified silent loss: no reason is "
                    f"given, so the error is dropped without explanation. Looked at "
                    f"{where}; a bare `# noqa` or `type: ignore` is a suppression, not a "
                    f"reason. Heuristic: absence of a stated reason is treated as the "
                    f"expensive case"
                )
            out.append(
                Finding(
                    kind="silent-swallow",
                    path=rel,
                    line=node.lineno,
                    symbol=scope,
                    detail=detail,
                    verdict=verdict,
                )
            )
    return _sorted(out)


BROAD_NAMES = "Exception/BaseException/bare except"
PRAGMA_RE = re.compile(
    r"(?:noqa(?::\s*[\w\s.,*]+)?"
    r"|type:\s*ignore[\w\[\], ]*"
    r"|pylint:\s*disable[\w\s.,-]*"
    r"|nosec[\w\s.,-]*"
    r"|pragma:\s*no\s*cover"
    r"|ruff:\s*noqa[\w\s.,-]*"
    r"|fmt:\s*(?:on|off|skip))",
    re.IGNORECASE,
)
SIGNALS = "the handler's own comment, its enclosing docstring and its name"


def _comment_rationale(comment: str) -> str:
    """The part of a comment that says *why*, with suppression pragmas removed.

    `# noqa: BLE001 — stale index beats no index` keeps the rationale;
    a bare `# noqa: BLE001` leaves nothing, because acknowledging that an
    `except` is broad is not a reason for dropping the error.
    """
    text = comment.lstrip("#").strip()
    match = PRAGMA_RE.match(text)
    if match:
        text = text[match.end() :]
    return text.strip(" \t—–-:;,.")


def _justification(
    handler: ast.ExceptHandler, owner: ast.AST | None, idx: RepoIndex, rel: str
) -> tuple[str, str, str]:
    """-> (verdict, reason, where the reason was found)."""
    rationale = _comment_rationale(idx.comment_rows(rel).get(handler.lineno, ""))
    if rationale:
        return "deliberate", rationale, "the handler's own comment"
    doc = ast.get_docstring(owner) if owner is not None else None
    name = owner.name if isinstance(owner, ast.FunctionDef | ast.AsyncFunctionDef) else ""
    for hint in DEGRADATION_HINTS:
        quote = _sentence_with(doc or "", hint)
        if quote:
            return "deliberate", quote, "the enclosing docstring"
        if hint in name.lower():
            return "deliberate", f"the function name `{name}`", "the enclosing function name"
    return "unjustified", "", SIGNALS


def _sentence_with(text: str, needle: str) -> str:
    """The first sentence of `text` containing `needle` — quoted, not paraphrased."""
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if needle in sentence.lower():
            return sentence.strip()
    return ""


def _is_broad(handler: ast.ExceptHandler) -> bool:
    kind = handler.type
    if kind is None:
        return True
    if isinstance(kind, ast.Name):
        return kind.id in {"Exception", "BaseException"}
    if isinstance(kind, ast.Attribute):
        return kind.attr in {"Exception", "BaseException"}
    return False


def _meaningful(statements: Sequence[ast.stmt]) -> list[ast.stmt]:
    body = list(statements)
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    return body


def _is_pass_body(handler: ast.ExceptHandler) -> bool:
    body = _meaningful(handler.body)
    return len(body) == 1 and isinstance(body[0], ast.Pass)


def _is_silent_body(handler: ast.ExceptHandler) -> bool:
    body = _meaningful(handler.body)
    if not body:
        return False
    if not all(isinstance(stmt, ast.Pass | ast.Return) for stmt in body):
        return False
    return not _logs(body)


def _logs(body: Sequence[ast.stmt]) -> bool:
    for stmt in body:
        for node in ast.walk(stmt):
            if not isinstance(node, ast.Call):
                continue
            name = _call_name(node)
            if name in {"warning", "error", "exception", "info", "debug", "print", "warn"}:
                return True
    return False


def _sorted(findings: list[Finding]) -> tuple[Finding, ...]:
    return tuple(sorted(findings, key=lambda f: (f.path, f.line, f.kind, f.symbol)))


# --------------------------------------------------------------------------------------
# the scouts
# --------------------------------------------------------------------------------------

SLEUTH_DETECTORS = (find_missing_encodings, find_registration_literals, find_unwired_modules)
AUDIT_DETECTORS = (find_unbounded_concurrency, find_silent_swallows)


def internal_codebase_sleuth(repo: pathlib.Path | str, *, delay: float = 0.0) -> ScoutResult:
    """Static facts about the code: encoding safety, tool registries, dead modules."""
    started = time.perf_counter()
    if delay:
        time.sleep(delay)
    index = build_index(repo)
    findings = _sweep(SLEUTH_DETECTORS, index)
    return _result("internal-codebase-sleuth", "A", findings, index, started, SLEUTH_DETECTORS)


def architecture_debt_auditor(repo: pathlib.Path | str, *, delay: float = 0.0) -> ScoutResult:
    """Structural debt: unbounded fan-out and swallows that lose errors silently."""
    started = time.perf_counter()
    if delay:
        time.sleep(delay)
    index = build_index(repo)
    findings = _sweep(AUDIT_DETECTORS, index)
    return _result("architecture-debt-auditor", "A", findings, index, started, AUDIT_DETECTORS)


def _sweep(
    detectors: Sequence[Callable[..., tuple[Finding, ...]]], index: RepoIndex
) -> tuple[Finding, ...]:
    found: list[Finding] = []
    for detect in detectors:
        found.extend(detect(index.root, index=index))
    return _sorted(found)


def _result(
    scout: str,
    group: str,
    findings: tuple[Finding, ...],
    index: RepoIndex,
    started: float,
    detectors: Sequence[Callable[..., tuple[Finding, ...]]],
) -> ScoutResult:
    notes = list(index.notes())
    notes.append(
        f"scanned {len(index.files)} Python file(s) across "
        f"{len(SCAN_TREES) - len(index.missing_trees)}/{len(SCAN_TREES)} tree(s)"
    )
    return ScoutResult(
        scout=scout,
        group=group,
        status="completed",
        findings=findings,
        notes=tuple(notes),
        duration_s=time.perf_counter() - started,
        detectors=tuple(detect.__name__.removeprefix("find_") for detect in detectors),
    )


GROUP_A_SCOUTS: Mapping[str, Callable[..., ScoutResult]] = {
    "internal-codebase-sleuth": internal_codebase_sleuth,
    "architecture-debt-auditor": architecture_debt_auditor,
}


def run_group_a(
    repo: pathlib.Path | str,
    *,
    max_workers: int = 2,
    delays: Mapping[str, float] | None = None,
) -> tuple[ScoutResult, ...]:
    """Run the scriptable scouts concurrently and return them in canonical order.

    One thread per scout. Each scout builds its own index, so they touch no
    shared mutable state and a crash in one cannot corrupt the other.
    """
    delays = delays or {}
    workers = max(1, min(max_workers, len(GROUP_A)))
    results: dict[str, ScoutResult] = {}
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=workers, thread_name_prefix="scout"
    ) as pool:
        futures = {
            pool.submit(GROUP_A_SCOUTS[name], repo, delay=delays.get(name, 0.0)): name
            for name in GROUP_A
        }
        for future in concurrent.futures.as_completed(futures):
            name = futures[future]
            try:
                results[name] = future.result()
            except Exception as error:  # noqa: BLE001 - one scout must not sink the run
                results[name] = ScoutResult(
                    scout=name,
                    group="A",
                    status="failed",
                    notes=(f"scout raised {error.__class__.__name__}: {error}",),
                    error=f"{error.__class__.__name__}: {error}",
                )
    return tuple(results[name] for name in GROUP_A)


def deferred_to_harness() -> tuple[ScoutResult, ...]:
    """The Group B scouts, recorded as orders to hand the harness — never as findings."""
    return tuple(
        ScoutResult(
            scout=spec.name,
            group="B",
            status="deferred_to_harness",
            notes=(
                (
                    "not scriptable from Python: this scout needs live web/GitHub access "
                    "from a model, and a Python process cannot spawn OpenCode harness "
                    "sub-agents"
                ),
                f"dispatch role: {spec.role}",
            ),
            manifest=spec.prompt(),
        )
        for spec in DEFERRED_SPECS
    )


def run_all_scouts(
    repo: pathlib.Path | str,
    *,
    max_workers: int = 2,
    delays: Mapping[str, float] | None = None,
) -> tuple[ScoutResult, ...]:
    return run_group_a(repo, max_workers=max_workers, delays=delays) + deferred_to_harness()


# --------------------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------------------


def render_report(
    results: Sequence[ScoutResult],
    *,
    repo: pathlib.Path | str | None = None,
    elapsed_s: float = 0.0,
    missing: Sequence[str] = (),
) -> str:
    """Render the aggregate scout report as markdown (one section per scout)."""
    if not missing and repo is not None:
        missing = missing_trees(repo)
    total = sum(r.finding_count for r in results)
    completed = [r for r in results if r.status == "completed"]
    deferred = [r for r in results if r.status != "completed"]
    informational = sum(1 for r in results for f in r.findings if f.kind in INFORMATIONAL_KINDS)
    defects = total - informational
    out: list[str] = [
        "# Parallel Scout Report",
        "",
        "Produced by `scripts/launch_parallel_scouts.py`. Read the status column first:",
        "only `completed` scouts produced findings, and a Python process cannot spawn",
        "harness sub-agents, so the LLM-driven scouts are shipped as orders, not results.",
        "",
        f"- **Repo:** `{pathlib.Path(repo) if repo is not None else REPO}`",
        f"- **Scanned trees:** {', '.join(f'`{t}/`' for t in SCAN_TREES)}",
        f"- **Missing trees:** {', '.join(f'`{t}/`' for t in missing) if missing else 'none'}",
        f"- **Wall clock:** {elapsed_s:.3f}s for {len(completed)} internal scout(s)",
        (
            f"- **Total findings:** {total} across {len(completed)} completed scout(s) "
            f"— {defects} to look at, {informational} informational"
        ),
        f"- **Deferred to harness:** {len(deferred)}",
        "",
        "## Aggregate",
        "",
        "| Scout | Group | Status | Findings | Wall clock |",
        "| --- | --- | --- | --- | --- |",
    ]
    for result in results:
        count = str(result.finding_count) if result.status == "completed" else "—"
        clock = f"{result.duration_s:.3f}s" if result.status == "completed" else "—"
        out.append(f"| `{result.scout}` | {result.group} | `{result.status}` | {count} | {clock} |")
    out += [
        "",
        "## How to read this report",
        "",
        "- **Group A** ran here, in this process, on real source. Its findings are facts",
        "  about the tree at the moment the report was written.",
        "- **Group B** did not run. Its sections are dispatch manifests: hand the prompt",
        "  to the OpenCode harness and let it dispatch a sub-agent.",
        "- Locations are `path:line`. A finding is a location to look at, not a verdict —",
        "  open it before acting.",
        "- Rows whose kind is `bounded-fanout` are **not defects**. They record a cap this",
        "  tool resolved so the audit trail shows where the bound is, instead of the",
        "  fan-out being reported as unbounded. The summary above counts them separately.",
    ]
    for position, result in enumerate(results, start=1):
        out += ["", f"## {position}. {result.scout}", ""]
        out += _render_scout(result)
    out += ["", "## Method notes", ""]
    out += [
        "- The silent-swallow verdict asks whether a reason was **stated**, not whether it is",
        "  good. The reason is read from the handler's own source line (`tokenize`), because",
        "  `ast.unparse` discards comments; a bare `# noqa` / `type: ignore` is treated as a",
        "  suppression rather than a reason, and the enclosing docstring is only consulted as",
        "  a keyword-matched fallback. The stated reason is quoted on every deliberate row so",
        "  you can disagree with it.",
        "- `unbounded-concurrency` means no bound was resolved **in the enclosing function or",
        "  in a same-file helper it calls**. It is an absence of evidence in this file, not",
        "  proof of unboundedness: a cap enforced by an outer queue, another process, or a",
        "  limit set above this file is invisible to a per-file AST walk. A `MAX_*` constant",
        "  merely mentioned in a body is not a cap — in `agent_manager.py`, `MAX_LINES` bounds",
        "  how many lines exist, while the cap on the fan-out is the `lines[:MAX_LINES]` inside",
        "  `_trim_lines`, which the detector resolves and reports as `bounded-fanout`.",
        "- The upstream-cap resolution is syntactic: it looks for a slice in the same file.",
        "  A slice in that helper that is unrelated to the fan-out would be over-attributed —",
        "  the row cites the exact line so it can be checked.",
        "- Unwired-module detection is **AST-based**; a module reached only by dynamic",
        "  import would be a false positive. Only importers under `src/` count: a module whose",
        "  sole importer is its own test is exactly the built-but-unwired case.",
        "- Group A scanned " + str(len(SCAN_TREES)) + " trees and used only the standard",
        "  library, so the script runs without the project's dependencies installed.",
    ]
    return "\n".join(out) + "\n"


def _render_scout(result: ScoutResult) -> list[str]:
    if result.status == "deferred_to_harness":
        return _render_deferred(result)
    lines = [
        f"- **Group:** {result.group} — internal, deterministic, ran in this process",
        f"- **Status:** `{result.status}`",
        f"- **Detectors:** {', '.join(f'`{d}`' for d in result.detectors) or '—'}",
        f"- **Wall clock:** {result.duration_s:.3f}s",
        f"- **Findings:** {result.finding_count}",
    ]
    if result.error:
        lines.append(f"- **Error:** `{result.error}`")
    lines.append("")
    if result.findings:
        lines += [
            "| # | Location | Kind | Symbol | What it says |",
            "| --- | --- | --- | --- | --- |",
        ]
        for number, finding in enumerate(result.findings[:MAX_FINDINGS_IN_TABLE], start=1):
            lines.append(
                f"| {number} | `{finding.location}` | `{finding.kind}` | `{finding.symbol}` "
                f"| {finding.detail} |"
            )
        hidden = len(result.findings) - MAX_FINDINGS_IN_TABLE
        if hidden > 0:
            lines.append(f"| … | — | — | — | {hidden} further finding(s) not shown |")
    else:
        lines.append("No findings in the scanned trees.")
    if result.notes:
        lines += ["", "**Notes**", ""]
        lines += [f"- {note}" for note in result.notes]
    return lines


def _render_deferred(result: ScoutResult) -> list[str]:
    lines = [
        f"- **Group:** {result.group} — external, LLM-driven",
        f"- **Status:** `{result.status}`",
        "- **Why this is not scriptable:** a Python process cannot spawn OpenCode",
        "  harness sub-agents — the harness dispatches `explore` / `general` itself. This",
        "  scout also needs live web or GitHub access from a model.",
        "- **Findings:** none collected — this scout never ran. Nothing below is a result.",
    ]
    lines += [f"- {note}" for note in result.notes]
    lines += ["", "**Dispatch manifest** — hand this to the harness:", "", "```text"]
    lines += result.manifest.splitlines()
    lines.append("```")
    return lines


def write_report(markdown: str, out: pathlib.Path | str) -> pathlib.Path:
    """Write the report, creating the parent directory if the caller asked for it."""
    target = pathlib.Path(out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markdown, encoding="utf-8")
    return target


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="launch_parallel_scouts",
        description=(
            "Run Sara's two scriptable scouts concurrently and emit dispatch manifests "
            "for the two that need a model. Writes one markdown report and nothing else."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Group A (runs here): " + ", ".join(GROUP_A) + "\n"
            "Group B (deferred to the harness): " + ", ".join(GROUP_B) + "\n"
            "Standard library only. Exit code: 0 clean, 1 if a scout raised or the "
            "report could not be written."
        ),
    )
    parser.add_argument(
        "--repo", type=pathlib.Path, default=REPO, help="repo root to scan (default: %(default)s)"
    )
    parser.add_argument(
        "--out",
        type=pathlib.Path,
        default=DEFAULT_REPORT,
        help="report path (default: %(default)s, inside benchmarks/)",
    )
    parser.add_argument(
        "--max-workers", type=int, default=2, help="Group A thread cap (default: %(default)s)"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.0,
        help="sleep injected per Group A scout; wall clock then proves they overlap",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    delays = {name: args.delay for name in GROUP_A} if args.delay > 0 else None
    started = time.perf_counter()
    results = run_all_scouts(args.repo, max_workers=args.max_workers, delays=delays)
    elapsed = time.perf_counter() - started
    markdown = render_report(results, repo=args.repo, elapsed_s=elapsed)
    try:
        written = write_report(markdown, args.out)
    except OSError as error:
        print(f"could not write the report to {args.out}: {error}", file=sys.stderr)
        return 1
    findings = sum(r.finding_count for r in results)
    print(f"repo: {args.repo}")
    if missing_trees(args.repo):
        print(f"missing trees (reported, not fatal): {', '.join(missing_trees(args.repo))}")
    print(
        f"scouts: {len(GROUP_A)} ran concurrently in {elapsed:.3f}s, "
        f"{len(GROUP_B)} deferred_to_harness"
    )
    print(f"findings: {findings}")
    for result in results:
        if result.status == "completed":
            print(f"  [{result.group}] {result.scout}: {result.finding_count} finding(s)")
        else:
            print(f"  [{result.group}] {result.scout}: {result.status} (manifest in report)")
    print(f"report: {written}")
    return 1 if any(r.status == "failed" for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
