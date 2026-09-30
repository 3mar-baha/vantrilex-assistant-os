"""P3-A guards: `EvolutionTask` schema, the two collision surfaces, the forced
safety tier, the append-only backlog, and the marker/tool gap split.

Spec: docs/architecture/CROSS_FRAMEWORK_ANALYSIS_AND_SELF_EVOLUTION.md §3.1
(schema, backlog, refusal invariant, owner string) and §6 P3-A (the assertion
list). Every dataset below is DERIVED from the live registries at collection
time — `TOOL_CAPABILITIES`, `_VALID_TOOLS`, `IRREVERSIBLE_TOOLS`, `_TOOL_GOALS`
— so a guard cannot rot into a vacuous truth when the catalog changes.

Three deliberate deviations from the blueprint, each argued in-line:

1. **The backlog file is `State/evolution_backlog.jsonl`, not `.json`.** §3.1
   names the file `State/evolution_backlog.json` and then specifies it as JSONL
   ("one JSON object per line (JSONL) rather than a rewritten array"). A `.json`
   name holding JSONL is a lie in the name that every future reader has to
   re-derive; the honest extension is `.jsonl`. `test_backlog_lives_in_state_under_its_honest_jsonl_name`
   pins it.
2. **`EvolutionTask` carries a `kind` field** ("marker" | "tool"). §3.1's
   dataclass snippet omits it, but §3.5.2 requires that "the backlog must record
   which it chose" — a dataclass without a discriminator cannot satisfy that.
3. **The classifier is `classify_gap(text) -> "marker" | "tool" | ""`.** The
   threshold lives in `src/evolution.py`, not in this file: a magic number in a
   test is a claim nobody measured (§5.1 Directive 6). This file asserts the
   OUTCOME for measured inputs, never a score.

Residual limit, stated rather than hidden: the forced safety tier scans the
task's own free text (`intent` + `evidence`) for a member of
`IRREVERSIBLE_TOOLS`. A PARAPHRASED irreversible request ("سكّر البرنامج اللي
مقفول") names no tool and will not trip it. The structural backstop is the
collision rule — `IRREVERSIBLE_TOOLS` is a subset of `TOOL_CAPABILITIES`, so a
task NAMED after an irreversible tool is rejected outright, text or no text.
`test_irreversible_deny_list_is_redundant_with_the_collision_rule` pins that.

No socket, no HTTP, no wall clock. `created_day` is a literal on purpose: a
`date.today()` in this file is a date bomb.

The seam this file requires on `src.evolution` — the smallest set that satisfies
§6 P3-A, nothing more:

    NAME_RE: Final = re.compile(r"^[a-z][a-z0-9_]{2,39}$")
    BACKLOG_RELPATH: Final = "State/evolution_backlog.jsonl"
    OWNER_NOTICE_TEMPLATE: Final  # the Amman string, `xyz` placeholder intact

    def is_valid_task_name(name: str) -> bool          # regex AND both collision surfaces
    def classify_gap(text: str, *, min_confidence=...) -> str   # "marker"|"tool"|""

    @dataclass
    class EvolutionTask:                                # 8 spec fields + `kind`
        name, intent, schema, safety_tier, acceptance_criteria,
        evidence, occurrences, created_day, kind
        # __post_init__ raises ValueError on a bad/colliding name and forces
        # safety_tier to "sensitive" when the task names an irreversible tool.

    def append_task(path, task) -> bool                 # True written / False no-op
    def read_backlog(path) -> list[dict]                # skips malformed, never raises
    def owner_notice(name: str) -> str                  # template with `xyz` replaced
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from src import evolution
from src.cognition import _TOOL_GOALS, evaluate_candidates
from src.dispatcher import _VALID_TOOLS
from src.skills.capabilities import IRREVERSIBLE_TOOLS, TOOL_CAPABILITIES
from src.vault import LOCAL_SCAFFOLD_DIRS

# Literal ISO date, never date.today() — a date bomb in a test file is a defect.
DAY = "2026-09-30"
OTHER_DAY = "2026-10-01"

#: Blueprint §3.1, byte for byte, with the `xyz` placeholder intact.
OWNER_NOTICE_BLUEPRINT = (
    "«هالميزة مش مبرمجة عندي هسا، بس جهزت مواصفات أداة جديدة باسم `xyz` ورفعتها "
    "لقائمة التطوير الذاتي. بتتنفذ لما توافق، وبتطلع للتجربة قبل ما تشتغل معاي.»"
)

#: Words that would turn "queued" into "ready", as (param-id, word). Each is
#: checked ABSENT: a paraphrase that still promises completion defeats the point.
#: Note "بتشتغل" is deliberately not here — the blueprint string contains it, in
#: the phrase "قبل ما تشتغل معاي" (before it runs with me), which is the honest
#: clause and not a promise.
PROMISE_WORDS = [
    pytest.param("جاهزة", id="ar-ready-f"),
    pytest.param("جاهز", id="ar-ready-m"),
    pytest.param("اشتغلت", id="ar-it-worked"),
    pytest.param("صارت جاهزة", id="ar-became-ready"),
    pytest.param("خلصت", id="ar-finished"),
    pytest.param("اكتملت", id="ar-completed"),
    pytest.param("تقدر تستخدمها", id="ar-you-can-use-it"),
    pytest.param("تم إنشاء", id="ar-was-created"),
    pytest.param("بتنفذ", id="ar-will-execute"),
    pytest.param("finished", id="en-finished"),
    pytest.param("ready", id="en-ready"),
    pytest.param("will work", id="en-will-work"),
    pytest.param("complete", id="en-complete"),
]

#: Claims §3.1 says the string must actually make, as (param-id, phrase). Checked
#: PRESENT: not-built-yet, needs-the-owner's-word, trialled-before-it-runs.
HONESTY_CLAIMS = [
    pytest.param("مش مبرمجة", id="not-programmed-yet"),
    pytest.param("لما توافق", id="when-you-approve"),
    pytest.param("قبل ما تشتغل", id="before-it-runs"),
    pytest.param("التطوير الذاتي", id="self-dev-backlog"),
]

# --- datasets derived from the live registries ---------------------------------

#: Both collision surfaces, union, derived. §3.1: "must not collide with
#: TOOL_CAPABILITIES or _VALID_TOOLS".
COLLIDING_NAMES = tuple(sorted(set(TOOL_CAPABILITIES) | set(_VALID_TOOLS)))

#: The asymmetric slice: routed by the dispatcher but absent from the
#: capabilities registry. Non-empty is the whole point — it is the only way a
#: collision guard that only reads TOOL_CAPABILITIES is caught.
ROUTER_ONLY_NAMES = tuple(sorted(set(_VALID_TOOLS) - set(TOOL_CAPABILITIES)))

#: Reversible counterpart for the "does not over-fire" control, derived.
REVERSIBLE_TOOLS = tuple(sorted(set(TOOL_CAPABILITIES) - IRREVERSIBLE_TOOLS))


#: Real goal markers from `_TOOL_GOALS` that the router scores weakest-but-
#: nonzero: reachable vocabulary, insufficient signal. Derived by measuring the
#: registry, so no marker here is invented by this file. Returns
#: (param-id, utterance) pairs; the id is the owning tool name, ASCII, so the
#: RED report is readable instead of \u-escaped.
def _weak_in_vocabulary_texts() -> tuple[tuple[str, str], ...]:
    scores: dict[str, list[tuple[float, str]]] = {}
    for tool, markers in _TOOL_GOALS.items():
        for marker in markers:
            if len(marker) < 2 or marker.strip() != marker:
                continue  # " و " and friends: whitespace markers are not vocabulary
            confidence = evaluate_candidates(marker)[0].confidence
            if confidence > 0:
                scores.setdefault(tool, []).append((confidence, marker))
    if not scores:
        return ()
    weakest = min(confidence for rows in scores.values() for confidence, _ in rows)
    return tuple(
        (tool, min(rows)[1])
        for tool, rows in sorted(scores.items())
        if min(confidence for confidence, _ in rows) == weakest
    )


WEAK_IN_VOCABULARY = _weak_in_vocabulary_texts()
WEAK_IN_VOCABULARY_IDS = tuple(tool for tool, _ in WEAK_IN_VOCABULARY)

#: Owner utterances that reach nothing in `_TOOL_GOALS`, as (param-id, text)
#: pairs — one source of truth, so the texts the precondition guard iterates can
#: never drift from the texts the classifier is fed. Guarded by
#: `test_out_of_vocabulary_texts_reach_no_router_marker` so a future registry
#: entry that captures one fails loudly instead of silently reclassifying it.
OUT_OF_VOCABULARY_PAIRS = (
    ("trip-planning", "دبر لي رحلة على الساحل"),
    ("cinema-ticket", "سجلي تذكرة السينما بكرة"),
    ("flight-booking", "حجز طيران"),
    ("bare-coffee", "قهوة"),
    ("bare-kilowatt", "كمبليتر"),
    ("gold-dividend", "مفرق ذهب مع Inflation"),
    ("yen-rate", "سعر صرف الين اليوم"),
    ("uml-diagram", "Inheritance diagram"),
)
OUT_OF_VOCABULARY_TEXTS = tuple(text for _, text in OUT_OF_VOCABULARY_PAIRS)
OUT_OF_VOCABULARY = [pytest.param(text, id=slug) for slug, text in OUT_OF_VOCABULARY_PAIRS]

#: Measured strong signal: `evaluate_candidates` picks a real tool with
#: confidence well clear of any plausible gap threshold. Asserted in the test
#: body, not assumed here.
CONFIDENT_TEXT = "افتح الورد برا"


# --- seam access ----------------------------------------------------------------


def _seam(symbol: str) -> Any:
    """Resolve a P3-A public symbol on `src.evolution`.

    A missing symbol FAILS the test; it never skips. Skipping would let an
    unbuilt phase report green, which is the exact failure mode §5.1 Directive 4
    is written against.
    """
    try:
        return getattr(evolution, symbol)
    except AttributeError:
        pytest.fail(f"src.evolution.{symbol} does not exist yet — P3-A is not built")


def _task(**overrides: Any) -> Any:
    """A valid baseline task; override one field per test."""
    fields: dict[str, Any] = {
        "name": "gold_rate_tracker",
        "intent": "«سعر الذهب اليوم»",
        "schema": {"params": {}, "returns": "str"},
        "safety_tier": "safe",
        "acceptance_criteria": ["returns the Amman price line"],
        "evidence": ["«شو سعر الذهب اليوم»"],
        "occurrences": 3,
        "created_day": DAY,
        "kind": "tool",
    }
    fields.update(overrides)
    return _seam("EvolutionTask")(**fields)


def _backlog(tmp_path: Any) -> Any:
    return tmp_path / "evolution_backlog.jsonl"


# --- 1. name validation ---------------------------------------------------------

BAD_NAMES = [
    pytest.param("", id="empty"),
    pytest.param("ab", id="too-short-2"),
    pytest.param("Gmail", id="uppercase"),
    pytest.param("GoldRate", id="mixed-case"),
    pytest.param("1tool", id="leading-digit"),
    pytest.param("_tool", id="underscore-leading"),
    pytest.param("a" + "b" * 40, id="41-chars"),
    pytest.param("gold-rate", id="hyphen"),
    pytest.param("gold rate", id="space"),
    pytest.param("أداة", id="arabic"),
    pytest.param("goldrate_الجديد", id="arabic-suffix"),
]

GOOD_NAMES = [
    pytest.param("abc", id="3-chars-minimum"),
    pytest.param("a" + "b" * 39, id="40-chars-maximum"),
    pytest.param("gold_rate_tracker", id="snake-case"),
    pytest.param("taj_mahal_guide", id="snake-case-2"),
    pytest.param("rate2day", id="digit-after-first"),
]


@pytest.mark.parametrize("name", BAD_NAMES)
def test_invalid_task_name_is_rejected(name: str) -> None:
    assert _seam("is_valid_task_name")(name) is False


@pytest.mark.parametrize("name", GOOD_NAMES)
def test_valid_task_name_is_accepted(name: str) -> None:
    assert _seam("is_valid_task_name")(name) is True


@pytest.mark.parametrize("name", BAD_NAMES)
def test_constructor_enforces_the_name_rule_not_just_the_predicate(name: str) -> None:
    """A predicate nobody calls is a hollow guard: the dataclass must refuse too."""
    with pytest.raises(ValueError):
        _task(name=name)


# --- 2. collision, both surfaces ------------------------------------------------


def test_collision_surfaces_are_non_empty_and_distinct() -> None:
    """Derived data must stay derived: an empty asymmetry silently retires the
    `_VALID_TOOLS` half of guard 2."""
    assert len(TOOL_CAPABILITIES) > 0
    assert ROUTER_ONLY_NAMES, "no name is routed-but-uncatalogued; guard 2 lost a surface"
    assert set(TOOL_CAPABILITIES) - set(_VALID_TOOLS) == set()
    assert set(ROUTER_ONLY_NAMES) & set(TOOL_CAPABILITIES) == set()


@pytest.mark.parametrize("name", COLLIDING_NAMES)
def test_task_name_may_not_collide_with_any_registered_tool(name: str) -> None:
    assert _seam("is_valid_task_name")(name) is False


@pytest.mark.parametrize("name", ROUTER_ONLY_NAMES)
def test_router_only_tool_name_is_still_a_collision(name: str) -> None:
    """Present in `_VALID_TOOLS` but absent from `TOOL_CAPABILITIES`. A guard
    reading only the capabilities registry lets these through."""
    assert name not in TOOL_CAPABILITIES
    assert name in set(_VALID_TOOLS)
    assert _seam("is_valid_task_name")(name) is False


@pytest.mark.parametrize("name", COLLIDING_NAMES)
def test_constructor_rejects_a_colliding_tool_name(name: str) -> None:
    with pytest.raises(ValueError):
        _task(name=name)


# --- 3. safety tier is forced ---------------------------------------------------


def test_irreversible_deny_list_is_redundant_with_the_collision_rule() -> None:
    """The structural backstop for the token-scan limit: naming an irreversible
    tool is a collision, so the task is refused before any text is read."""
    assert IRREVERSIBLE_TOOLS
    assert IRREVERSIBLE_TOOLS <= set(TOOL_CAPABILITIES)
    assert IRREVERSIBLE_TOOLS <= set(_VALID_TOOLS)
    assert REVERSIBLE_TOOLS


@pytest.mark.parametrize("tool", sorted(IRREVERSIBLE_TOOLS))
def test_irreversible_tool_forces_sensitive_tier_over_a_safe_declaration(tool: str) -> None:
    task = _task(
        safety_tier="safe",
        intent=f"«بدي أداة تسوي {tool}»",
        evidence=[f"«لما تكتب {tool} اعملها»"],
    )
    assert task.safety_tier == "sensitive"


def test_sensitive_tier_is_not_downgraded_by_a_safe_declaration() -> None:
    """The forcing is one-directional: safe never wins over the deny-list."""
    task = _task(
        safety_tier="safe",
        intent="«بدي أداة تسوي cancel_reminder»",
        evidence=["«الغِ التذكير»"],
    )
    assert task.safety_tier == "sensitive"


@pytest.mark.parametrize("tool", REVERSIBLE_TOOLS[:4])
def test_reversible_tool_does_not_over_fire_the_tier_forcing(tool: str) -> None:
    """A blanket 'always sensitive' implementation fails here."""
    task = _task(safety_tier="safe", evidence=[f"«{tool}»"])
    assert task.safety_tier == "safe"


def test_task_naming_nothing_forced_stays_as_declared() -> None:
    assert _task(safety_tier="safe").safety_tier == "safe"
    assert _task(safety_tier="sensitive").safety_tier == "sensitive"


# --- 4. append-only JSONL, idempotent per day ----------------------------------


def test_backlog_lives_in_state_under_its_honest_jsonl_name() -> None:
    """.jsonl, not .json: §3.1 specifies JSONL. A `.json` name holding JSONL is
    a lie every future reader must re-derive. `State/` is already a mandatory
    scaffold dir, so nothing needs adding to it."""
    relpath = _seam("BACKLOG_RELPATH")
    assert relpath == "State/evolution_backlog.jsonl"
    assert "State/" in LOCAL_SCAFFOLD_DIRS


def test_jsonl_append_only_so_a_crash_mid_write_cannot_corrupt_the_queue(
    tmp_path: Any,
) -> None:
    """The reason for JSONL at all: one torn line costs one task, not the queue.
    The same `name` + `created_day` is a no-op, so a retried nightly tick cannot
    double-write."""
    backlog = _backlog(tmp_path)
    append = _seam("append_task")
    read = _seam("read_backlog")

    assert append(backlog, _task()) is True
    assert append(backlog, _task()) is False
    assert len(read(backlog)) == 1


@pytest.mark.parametrize(
    "second",
    [
        pytest.param({"name": "taj_mahal_guide"}, id="different-name-same-day"),
        pytest.param({"created_day": OTHER_DAY}, id="same-name-different-day"),
        pytest.param({"name": "taj_mahal_guide", "created_day": OTHER_DAY}, id="both-differ"),
    ],
)
def test_a_distinct_task_always_appends(tmp_path: Any, second: dict[str, Any]) -> None:
    backlog = _backlog(tmp_path)
    append = _seam("append_task")
    assert append(backlog, _task()) is True
    assert append(backlog, _task(**second)) is True
    records = _seam("read_backlog")(backlog)
    assert len(records) == 2
    assert {record["name"] for record in records} == {
        "gold_rate_tracker",
        second.get("name", "gold_rate_tracker"),
    }
    assert {record["created_day"] for record in records} == {DAY, second.get("created_day", DAY)}


def test_each_backlog_line_is_one_standalone_json_object(tmp_path: Any) -> None:
    backlog = _backlog(tmp_path)
    append = _seam("append_task")
    append(backlog, _task())
    append(backlog, _task(name="taj_mahal_guide"))
    lines = backlog.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert all(isinstance(json.loads(line), dict) for line in lines)


def test_append_never_rewrites_and_never_drops_the_garbage_line_before_it(
    tmp_path: Any,
) -> None:
    """Append-only, proven by a line no implementation can reproduce: crash
    residue the reader skipped. A read-filter-rewrite implementation silently
    deletes it, which is data loss.

    The torn line deliberately carries NO trailing newline — the exact state a
    crash mid-write leaves. An appender that does not open a fresh line here
    concatenates its record onto the residue and destroys BOTH, which is the
    corruption JSONL exists to prevent. Caught twice: by the byte assertion on
    line 0, and by the appended record still being readable on its own line.
    """
    backlog = _backlog(tmp_path)
    backlog.write_text('{"name": "truncated", "cre', encoding="utf-8")
    append = _seam("append_task")
    assert append(backlog, _task()) is True
    lines = backlog.read_text(encoding="utf-8").splitlines()
    assert lines[0] == '{"name": "truncated", "cre'
    assert len(lines) == 2
    assert json.loads(lines[1])["name"] == "gold_rate_tracker"
    assert [r["name"] for r in _seam("read_backlog")(backlog)] == ["gold_rate_tracker"]


# --- 5. a malformed line is skipped, not fatal ----------------------------------


def test_malformed_line_is_skipped_and_the_valid_one_survives(tmp_path: Any) -> None:
    backlog = _backlog(tmp_path)
    append = _seam("append_task")
    append(backlog, _task())
    with backlog.open("a", encoding="utf-8") as handle:
        handle.write('{"name": "cut_off_mid_wri\n')
    records = _seam("read_backlog")(backlog)
    assert [record["name"] for record in records] == ["gold_rate_tracker"]


@pytest.mark.parametrize(
    "garbage",
    [
        pytest.param("{", id="open-brace"),
        pytest.param('{"name": ', id="truncated-mid-object"),
        pytest.param("not json at all", id="plain-prose"),
        pytest.param("[[[", id="broken-brackets"),
    ],
)
def test_garbage_line_does_not_raise(tmp_path: Any, garbage: str) -> None:
    backlog = _backlog(tmp_path)
    backlog.write_text(f"{garbage}\n", encoding="utf-8")
    assert _seam("read_backlog")(backlog) == []


@pytest.mark.parametrize(
    "line",
    [
        pytest.param("[1, 2, 3]", id="json-array"),
        pytest.param("42", id="json-number"),
        pytest.param('"a bare string"', id="json-string"),
        pytest.param("null", id="json-null"),
    ],
)
def test_valid_json_that_is_not_an_object_is_skipped(tmp_path: Any, line: str) -> None:
    """§3.1 asks for objects; a bare array or scalar is not one and must not be
    coerced into a record."""
    backlog = _backlog(tmp_path)
    _seam("append_task")(backlog, _task())
    with backlog.open("a", encoding="utf-8") as handle:
        handle.write(f"{line}\n")
    assert [r["name"] for r in _seam("read_backlog")(backlog)] == ["gold_rate_tracker"]


def test_empty_file_reads_as_empty_not_as_an_error(tmp_path: Any) -> None:
    backlog = _backlog(tmp_path)
    backlog.write_text("", encoding="utf-8")
    assert _seam("read_backlog")(backlog) == []


def test_absent_backlog_reads_as_empty(tmp_path: Any) -> None:
    assert _seam("read_backlog")(_backlog(tmp_path)) == []


# --- 6. marker gap and tool gap are never conflated -----------------------------


def test_out_of_vocabulary_texts_reach_no_router_marker() -> None:
    """Precondition for the tool-gap cases, asserted rather than assumed: if a
    future `_TOOL_GOALS` entry captures one of these, the tool-gap test would
    pass for the wrong reason."""
    assert len(OUT_OF_VOCABULARY_TEXTS) >= 2
    for text in OUT_OF_VOCABULARY_TEXTS:
        assert evaluate_candidates(text)[0].confidence == 0.0, text


def test_weak_in_vocabulary_texts_are_reachable_but_scored_low() -> None:
    """Precondition for the marker-gap cases, measured the same way."""
    assert WEAK_IN_VOCABULARY, "no reachable-but-weak marker found; guard 6a lost data"
    for tool, text in WEAK_IN_VOCABULARY:
        best = evaluate_candidates(text)[0]
        assert best.confidence > 0, text
        assert best.tool in _TOOL_GOALS, text
        assert tool in _TOOL_GOALS, tool


@pytest.mark.parametrize(("tool", "text"), WEAK_IN_VOCABULARY, ids=WEAK_IN_VOCABULARY_IDS)
def test_reachable_but_low_scoring_verb_cluster_is_a_marker_gap(tool: str, text: str) -> None:
    """The verb cluster IS in the router's vocabulary, so the fix is one line in
    `_TOOL_GOALS` — a registry edit, not a synthesis."""
    assert evaluate_candidates(text)[0].confidence > 0
    assert _seam("classify_gap")(text) == "marker"


@pytest.mark.parametrize("text", OUT_OF_VOCABULARY)
def test_unreachable_verb_cluster_is_a_tool_gap(text: str) -> None:
    """Nothing in `_TOOL_GOALS` matches, so a tool may genuinely be missing."""
    assert evaluate_candidates(text)[0].confidence == 0.0
    assert _seam("classify_gap")(text) == "tool"


def test_marker_gap_and_tool_gap_are_two_different_outcomes() -> None:
    """The highest-value guard in the file. Conflating them is how a system ends
    up synthesizing forty tools it never needed (§3.1, §3.5.2)."""
    classify = _seam("classify_gap")
    marker_kind = classify(WEAK_IN_VOCABULARY[0][1])
    tool_kind = classify(OUT_OF_VOCABULARY_TEXTS[0])
    assert marker_kind == "marker"
    assert tool_kind == "tool"
    assert marker_kind != tool_kind


def test_a_confident_utterance_raises_no_gap() -> None:
    """The negative case. Without it, 'always raise a tool task' is green."""
    assert evaluate_candidates(CONFIDENT_TEXT)[0].confidence > 0
    assert _seam("classify_gap")(CONFIDENT_TEXT) == ""


def test_the_backlog_records_which_gap_was_chosen(tmp_path: Any) -> None:
    """§3.5.2: the backlog must record the choice, not just hold a task."""
    classify = _seam("classify_gap")
    backlog = _backlog(tmp_path)
    append = _seam("append_task")
    append(backlog, _task(kind=classify(WEAK_IN_VOCABULARY[0][1]), name="gold_rate_tracker"))
    append(backlog, _task(kind=classify(OUT_OF_VOCABULARY_TEXTS[0]), name="taj_mahal_guide"))
    assert [record["kind"] for record in _seam("read_backlog")(backlog)] == [
        "marker",
        "tool",
    ]


# --- 7. the owner-facing Amman string -------------------------------------------


def test_owner_notice_template_is_the_blueprint_byte_for_byte() -> None:
    assert _seam("OWNER_NOTICE_TEMPLATE") == OWNER_NOTICE_BLUEPRINT


def test_owner_notice_renders_the_blueprint_verbatim_for_a_named_tool() -> None:
    rendered = _seam("owner_notice")("gold_rate_tracker")
    assert rendered == OWNER_NOTICE_BLUEPRINT.replace("xyz", "gold_rate_tracker")
    assert "gold_rate_tracker" in rendered


@pytest.mark.parametrize("word", PROMISE_WORDS)
def test_owner_notice_promises_nothing_about_completion(word: str) -> None:
    assert word not in OWNER_NOTICE_BLUEPRINT
    assert word not in _seam("owner_notice")("gold_rate_tracker")


@pytest.mark.parametrize("claim", HONESTY_CLAIMS)
def test_owner_notice_makes_the_honest_claims(claim: str) -> None:
    """The string is only accurate if it says all three things: not built yet,
    needs the owner's word, and trialed before it runs."""
    assert claim in OWNER_NOTICE_BLUEPRINT
    assert claim in _seam("owner_notice")("gold_rate_tracker")
