"""Sovereign evolution loop (P2): repeated trajectories -> owner proposals.

Phase 1 of the ratified lifecycle (capture -> distill -> AST-verify ->
sandbox -> owner-gated promotion). This module owns distill + verify +
proposal rendering. NOTHING here registers skills: proposals are markdown
the owner promotes by hand (teaching law). Sandbox execution + promotion
gates are P3 (OverlayVault harness).

P3-A (§3.1, §6) adds the stage that must exist BEFORE a proposal can: the
`EvolutionTask` self-generation record, its two collision surfaces, the
append-only backlog, and the marker-gap / tool-gap split. These are diagnosis
primitives. They still register nothing and still promote nothing.

Known limit, stated here rather than hidden in a report: the forced
`sensitive` tier is a TOKEN SCAN over the task's own free text (`intent` +
`evidence`) for a member of `IRREVERSIBLE_TOOLS`. A PARAPHRASED irreversible
request — «سكّر البرنامج اللي مقفول» — names no tool and does not trip it. No
synonym list is invented to paper over that, because nobody measured one. The
structural backstop is the collision rule: `IRREVERSIBLE_TOOLS` is a subset of
`TOOL_CAPABILITIES`, so a task NAMED after an irreversible tool is refused in
`__post_init__` before a single character of prose is read.
"""

from __future__ import annotations

import ast
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Final

# `_VALID_TOOLS` and `_WEAK_SIGNAL_CAP` are underscore-private, but both are the
# ratified seam for P3-A: §3.1 names `_VALID_TOOLS` as a collision surface by
# name, and the router's own weak-signal cap is the measured trust floor. Reading
# a constant from the tree beats asserting a copy of it in this file.
from src.cognition import _WEAK_SIGNAL_CAP, evaluate_candidates
from src.skills.capabilities import IRREVERSIBLE_TOOLS, TOOL_CAPABILITIES
from src.tool_overlay import valid_tools

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


# --------------------------------------------------------------------------- #
# P3-A: the task record, the backlog, and the gap split (§3.1, §3.5.2, §6)
# --------------------------------------------------------------------------- #

#: Blueprint §3.1, byte for byte. Applied with `fullmatch`, not `match`: `$`
#: also matches just before a trailing newline, so `match` would accept
#: "gold_rate\n" as a task name and put a newline inside an identifier.
NAME_RE: Final = re.compile(r"^[a-z][a-z0-9_]{2,39}$")

#: Both collision surfaces, unioned, read from the live registries. The union
#: is load-bearing and NOT symmetric: `TOOL_CAPABILITIES` is a strict subset of
#: the routed set, so a guard reading only the capabilities registry provably
#: leaks every routed-but-uncatalogued name (`analytics`, `cloud_backup`,
#: `none`, `quota_safety` as of this writing). Snapshotting the union at import
#: keeps `is_valid_task_name` a pure predicate — no registry import per call.
#: P3-C: the routed half now reads the merged overlay view, so the snapshot still
#: equals `_VALID_TOOLS` today (the overlay ships empty). Directive 4: it stays an
#: IMPORT-TIME snapshot — a tool registered after import is not yet a collision
#: surface here. P3-D must re-decide that lifecycle if a name is ever registered
#: before a task is proposed for it.
_COLLIDING_TOOL_NAMES: Final[frozenset[str]] = frozenset(TOOL_CAPABILITIES) | frozenset(
    valid_tools()
)

#: §3.1 says JSONL ("one JSON object per line rather than a rewritten array")
#: while naming the file `.json`. A `.json` name holding JSONL is a lie in the
#: name that every future reader must re-derive, so the extension is honest.
#: `State/` is already mandatory in `vault.LOCAL_SCAFFOLD_DIRS` — no scaffolding
#: change is owed.
BACKLOG_RELPATH: Final = "State/evolution_backlog.jsonl"

#: §3.1, byte for byte, `xyz` placeholder intact. Three claims this string must
#: actually make, and none it must not: not built yet, runs only on the owner's
#: word, trialled before it runs with them. Any edit here is a promise change.
OWNER_NOTICE_TEMPLATE: Final = (
    "«هالميزة مش مبرمجة عندي هسا، بس جهزت مواصفات أداة جديدة باسم `xyz` ورفعتها "
    "لقائمة التطوير الذاتي. بتتنفذ لما توافق، وبتطلع للتجربة قبل ما تشتغل معاي.»"
)

#: Every registered tool name is an ASCII snake_case identifier, so splitting on
#: that character class isolates whole names and never matches a substring:
#: "closed" is a different token from "close" and cannot force the tier.
_TOOL_TOKEN_RE: Final = re.compile(r"[0-9A-Za-z_]+")


def is_valid_task_name(name: str) -> bool:
    """snake_case shape AND no collision with EITHER registry.

    A new capability must be nameable without shadowing a live tool: the
    dispatcher routes on the name, so a collision is a silent takeover of
    someone else's behaviour, not a style complaint.
    """
    return NAME_RE.fullmatch(name) is not None and name not in _COLLIDING_TOOL_NAMES


def _names_irreversible_tool(intent: str, evidence: list[str]) -> bool:
    """True when any `IRREVERSIBLE_TOOLS` member appears as a whole token."""
    haystack = " ".join([intent or "", *(evidence or [])])
    return not set(_TOOL_TOKEN_RE.findall(haystack)).isdisjoint(IRREVERSIBLE_TOOLS)


@dataclass
class EvolutionTask:
    """A capability Sara has specified but NOT built (§3.1).

    `kind` is the field §3.1's snippet omits and §3.5.2 requires: the backlog
    has to record whether the gap was a missing marker (a one-line `_TOOL_GOALS`
    edit) or a missing tool (the only case that earns synthesis). Without a
    discriminator on the record, "the backlog must record which it chose" cannot
    be satisfied by the backlog.

    `safety_tier` is FORCED, never trusted: naming a confirmation-gated tool in
    the task's own text overrules a `"safe"` declaration. The forcing is
    one-directional — declaring `"sensitive"` is never downgraded — and it is
    token-based, so a paraphrase that names no tool does not trip it. See the
    module docstring; the collision rule is the structural backstop.
    """

    name: str
    intent: str
    schema: dict
    safety_tier: str
    acceptance_criteria: list[str]
    evidence: list[str]
    occurrences: int
    created_day: str
    kind: str

    def __post_init__(self) -> None:
        if not is_valid_task_name(self.name):
            raise ValueError(f"unusable task name: {self.name!r}")
        if _names_irreversible_tool(self.intent, self.evidence):
            self.safety_tier = "sensitive"

    def as_record(self) -> dict[str, Any]:
        """The JSONL line body, one self-contained object."""
        return asdict(self)


def classify_gap(text: str, *, min_confidence: float = _WEAK_SIGNAL_CAP) -> str:
    """Which of the two failures this utterance is: `"marker"`, `"tool"`, or `""`.

    These are DIFFERENT problems and the split is the whole point (§3.1,
    §3.5.2). A verb cluster the router already knows but scored weakly is a
    one-line `_TOOL_GOALS` edit — synthesizing a tool there invents a capability
    the owner never asked for. A cluster matching nothing at all is the only
    case that may earn an `EvolutionTask`. A confident match is not a gap.

    The threshold is `_WEAK_SIGNAL_CAP`, the router's own do-not-trust floor,
    imported rather than copied: measured over the live registry the reachable-
    but-weak band sits at 0.20 and the confident band starts at 0.62, with the
    in-tree cap at 0.50 between them.
    """
    best = evaluate_candidates(text)[0]
    if best.confidence >= min_confidence:
        return ""
    return "marker" if best.confidence > 0.0 else "tool"


def read_backlog(path: Path) -> list[dict[str, Any]]:
    """Every well-formed task record in `path`, oldest first. Never raises.

    A backlog is a crash-survivor: a line torn mid-write is skipped, never
    fatal, and a line holding valid JSON that is not an object is not coerced
    into a record. An absent or empty backlog is empty, not an error.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    records: list[dict[str, Any]] = []
    for line in raw.splitlines():
        try:
            parsed = json.loads(line)
        except ValueError:
            continue  # torn mid-write, or a blank line — json.loads("") raises too
        if isinstance(parsed, dict):
            records.append(parsed)
    return records


def _needs_leading_newline(path: Path) -> bool:
    """True when a crash left the last line unterminated.

    A torn last line has no trailing newline. A plain append concatenates onto
    it, destroying the residue AND the new record at once — the exact corruption
    JSONL exists to prevent. The fix is to open a fresh line, never to rewrite
    the file and never to drop the garbage.
    """
    if not path.exists() or path.stat().st_size == 0:
        return False  # absent, or present but empty: no torn line to terminate
    with path.open("rb") as handle:
        handle.seek(-1, 2)  # SEEK_END: the last byte on disk
        return handle.read(1) != b"\n"


def append_task(path: Path, task: EvolutionTask) -> bool:
    """Append one record. `True` written, `False` if (name, created_day) exists.

    Append-only by construction: the file is opened in append mode and never
    truncated, so a reader-filter-rewrite implementation cannot silently delete
    crash residue. The idempotency key is (name, created_day), so a retried
    nightly tick cannot double-write and the backlog stays a ledger of days
    rather than a pile of retries.
    """
    if any(
        record.get("name") == task.name and record.get("created_day") == task.created_day
        for record in read_backlog(path)
    ):
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(task.as_record(), ensure_ascii=False, sort_keys=True)
    prefix = "\n" if _needs_leading_newline(path) else ""
    # newline="\n" so the file holds one 0x0A per record, not CRLF pairs.
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(f"{prefix}{line}\n")
    return True


def owner_notice(name: str) -> str:
    """The owner-facing Amman line for a queued task, `name` substituted.

    Says what is true — specified, not built, awaiting the owner's word — so a
    queued task never reads as a shipped one.
    """
    return OWNER_NOTICE_TEMPLATE.replace("xyz", name)
