r"""A-3 — the OVER-TRIM guard: the hazard this node could have caused.

THE HAZARD, MEASURED. A delete-anywhere filler list run against real reminder
content (measured at `b5f3953`, before any code changed):

    'ذكّرني اشتري حليب اليوم من السوق'  ->  'ذكّرني اشتري حليب السوق'
    'ذكّرني راجع تقرير اليوم مع خالد'    ->  'ذكّرني راجع تقرير مع خالد'
    'ذكّرني اليوم إلا إذا صار في طوارئ'  ->  'ذكّرني إلا إذا صار طوارئ'

The first is the one that matters. "Remind me to buy milk today FROM THE
MARKET" becomes "buy the market". No tool fails, no error surfaces, no log line
changes — the owner simply gets a WRONG reminder. That is the failure class
`tests/test_f6_honesty_batch.py:1-13` is written against: a wrong answer
presented as a right one. `اليوم` is load-bearing CONTENT here, and `من السوق`
is a TWO-WORD prepositional phrase that single-word deletion cannot survive.

WHY IT CANNOT HAPPEN HERE — three structural guards, in order of strength.

  G1  SHAPE-SCOPED. `entity_from_phrase` is applied ONLY to a tool declared in
      `ARG_ENTITY_TOOLS` (`src/cognition.py`). `schedule` and `multi_task` are
      deliberately absent from that set, so their args never reach a filler list
      at ANY strength. This is structural, not heuristic: the code that could
      trim a reminder is not reachable from a reminder's route.

  G2  EDGE-ONLY. Trimming happens at the two edges of an extracted span and
      never in its interior. «اشتري حليب اليوم من السوق» has no edge to trim
      from — it is the entity.

  G3  DELETE-ONLY. The function removes tokens and never rewrites or reorders a
      token that survives, apart from one word-boundary proclitic shave. It
      cannot synthesise, so it cannot invent a place that geocodes somewhere
      real and wrong.

THE ALREADY-LIVE INSTANCE. This hazard is not hypothetical — `_strip_command`
(`src/task_orchestrator.py:58-72`) already ships it. Its first substitution is
`(?:بعد\s+[\d٠-٩]*\s*\S+|...)` at :64 with `count=1` and NO `^` anchor, and the
`[\d٠-٩]*` quantifies to ZERO digits, so a bare `بعد` followed by any
non-space token is eaten. Measured at `b5f3953`:

    _strip_command('ذكرني بعد ما أكل أتابع الدايت') -> 'أكل أتابع الدايت'
    _strip_command('ذكّرني بعد أن أخلّص شغلي قلي')  -> 'ذكّرني أخلّص شغلي قلي'

That is the A-3b surface, and `tests/test_a3_schedule_title_hygiene.py` pins it.

IMPORTS ARE LAZY, ON PURPOSE — see the module docstring of
`tests/test_a3_argument_hygiene.py`. A top-level import of a seam that does not
exist yet aborts collection and hides every other guard's failure.

WHAT THIS FILE DOES NOT CLAIM
-----------------------------
- `test_reminder_content_survives_the_entity_extractor_unchanged`,
  `test_schedule_arg_is_never_trimmed` and `test_multi_task_arg_is_never_trimmed`
  are PRESERVATION pins: GREEN before the fix and GREEN after, by design. A
  preservation guard that only ever went red would prove nothing. The RED
  guards are the ones that import the seam (`entity_from_phrase`) — those live
  in `tests/test_a3_argument_hygiene.py`.
- It does NOT claim the schedule TIMING parser is fixed. `قبل ساعتين` remains an
  HONEST REFUSAL (owner's decision, 2026-10-07, the same doctrine as the
  `نصف ساعة` row at `tests/test_task_orchestrator.py:49`); it is not implemented
  here.
- `src/associative._tokens` / `STOPWORDS` are NOT reused, deliberately.
  `STOPWORDS` (`src/associative.py:36-78`) contains `هسا`/`هلق`/`اليوم`/`بكرا`
  (:64-67) — exactly the right words and exactly the wrong policy: it is scoped
  to "question words must not match half the vault" (:35) and also carries
  `من`/`على`/`في` (:51-53), the three words whose deletion destroys
  «اشتري حليب اليوم من السوق». `_tokens` returns a `set` (:114-124), so it has
  no deterministic order, and its `ال`-strip at :122-123 turns «الأبواب» into
  «ابواب» — a different word. Reuse would import a recall policy into a
  correctness seam.
"""

from __future__ import annotations

# The exact string the hazard was measured on. Kept verbatim and un-normalized:
# a guard that reformats its own fixture is a guard that proves nothing.
HAZARD = "ذكّرني اشتري حليب اليوم من السوق"


def _entity(span: str) -> str:
    from src.cognition import entity_from_phrase

    return entity_from_phrase(span)


def _entity_tools() -> frozenset[str]:
    from src.cognition import ARG_ENTITY_TOOLS

    return ARG_ENTITY_TOOLS


# --------------------------------------------------------------------------
# G1 — shape scope. The structural guard, stated as data.
# --------------------------------------------------------------------------


def test_entity_tools_exclude_every_free_text_tool():
    """The premise of the whole file, as an assertion about the table rather
    than about a call site: nothing whose arg is free text can be reached."""
    for tool in ("schedule", "multi_task", "volume", "media", "knowledge_graph"):
        assert tool not in _entity_tools(), tool


def test_schedule_arg_is_never_trimmed():
    """The hazard string, through the real producer. G1 + G2 together: the
    schedule branch returns the whole turn by design
    (`src/dispatcher.py:730-734`, `src/cognition.py:513-514`) because the timing
    parser scans wherever the timing words sit."""
    from src.dispatcher import _keyword_net

    tool, arg = _keyword_net(HAZARD)
    assert tool == "schedule"
    assert arg == HAZARD, "the schedule arg must be the turn, unmodified"


def test_multi_task_arg_is_never_trimmed():
    """`multi_task` needs EVERY clause (its arm in `_keyword_net` in
    `src/dispatcher.py`): a single tool's arg would swallow the sibling tasks."""
    from src.dispatcher import _keyword_net

    turn = "ذكّرني اليوم اشتر حليب و افتحي كروم"
    tool, arg = _keyword_net(turn)
    assert tool == "multi_task"
    assert arg == turn, "multi_task's arg must be the whole turn"


# --------------------------------------------------------------------------
# G2 — edge-only, on the one tool that IS entity-shaped
# --------------------------------------------------------------------------


def test_reminder_content_survives_the_entity_extractor_unchanged():
    """THE PROOF THE OWNER ASKED FOR, stated first. Run the extractor that
    removes `هسا`/`اليوم`/`بكرة` over the hazard string and prove it removes
    NOTHING, because no filler-list call site can reach free text."""
    assert _entity(HAZARD) == HAZARD


def test_trailing_filler_trim_never_deletes_the_interior():
    """Even when an entity extractor IS applied, the interior is untouchable."""
    assert _entity("خريبة السوف") == "خريبة السوف"
    # A filler between two entity words is INTERIOR: both edges are real tokens,
    # so nothing is trimmed and the day survives. This is the case a naive
    # delete-anywhere list destroys.
    assert "اليوم" in _entity("الزرقاء اليوم العقبة")
    # and both real tokens survive with it
    assert "الزرقاء" in _entity("الزرقاء اليوم العقبة")
    assert "العقبة" in _entity("الزرقاء اليوم العقبة")


def test_reminder_content_keeps_both_the_day_and_the_source():
    """The two substrings the naive trimmer destroyed, asserted separately so a
    regression names WHICH one was lost."""
    from src.dispatcher import _keyword_net

    arg = _keyword_net(HAZARD)[1]
    assert "اليوم" in arg, "the day is CONTENT — «اشتري حليب اليوم» is not «اشتري حليب»"
    assert "من السوق" in arg, "«من السوق» is a two-word phrase; deletion took «من»"


# --------------------------------------------------------------------------
# G3 — delete-only, and the fail-safe
# --------------------------------------------------------------------------


def test_unchangeable_span_passes_through_byte_identical():
    """THE FAIL-SAFE PIN. An argument the extractor cannot clean is returned
    unchanged rather than mangled. A span with no filler, no topic noun and no
    connector is the case where a rewrite would be pure downside."""
    for span in ("خريبة السوف", "شارع المدينة", "dkjfhsdkjh", "إربد", "مادبا"):
        assert _entity(span) == span, span


def test_unknown_span_passes_through_byte_identical():
    """Same fail-safe, the case the acceptance report exercised: a name the
    geocoder could never resolve must arrive at the geocoder INTACT, so the
    honest «ما لقيت» line names what the owner actually typed."""
    assert _entity("خريييبة") == "خريييبة"


def test_empty_after_trim_returns_empty_not_the_filler():
    """A filler-only span must yield `""` so `src/tools.py:1205`'s home-city
    default governs. Returning the filler would geocode «اليوم»."""
    assert _entity("اليوم") == ""
    assert _entity("لو سمحت") == ""
    assert _entity("") == ""


def test_extractor_never_invents_a_token():
    """G3 as a property: every surviving token was in the input."""
    source = "شو الطقس اليوم في عمّان"
    produced = _entity(source)
    for token in produced.split():
        assert token in source, token
