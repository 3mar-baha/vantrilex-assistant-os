r"""A-3a — the PRODUCER seams: a routable tool must receive an ENTITY, not the turn.

FOUR REPRODUCTIONS, TWO SEAMS. The acceptance report's §7 proposal 3 ("One
function, four reproductions") is WITHDRAWN by §A-corrections-2 Item 1, and this
file is the code-level consequence of that withdrawal. `normalize_tool_arg`
(`src/decision_loop.py:65-68`) is NOT the defect and is NOT touched here: it is
applied at exactly one of the three `tools.call` sites
(`src/dispatcher.py:1072-1077`), and two of the four reproductions are direct
handler calls that never traverse it. The defect is upstream, in the two
PRODUCERS of (tool, arg):

  P1  `src/dispatcher._keyword_net` (:672-771) — the weather capture at :454 is
      `([^؟?،,]+)`, which runs to end-of-string. «شو الطقس في عمّان اليوم»
      yields `('weather', 'عمّان اليوم')`: a place name with conversational
      filler welded to it. The post-strip at :752-755 then makes it worse,
      because a bare `ب` prefix is shaved off ANY word, so «بكرة» (tomorrow)
      becomes «كرة» (ball) — verified at `b5f3953`:
          _keyword_net('شو الطقس بكرة بعمّان') -> ('weather', 'كرة بعمّان')
      And the worst case, which the acceptance report did not record:
          _keyword_net('تمام، شو الطقس اليوم') -> ('weather', 'اليوم')
      — the CITY IS the filler word. It geocodes to nothing.

  P2  `src/cognition._extract_arg` (:512-524) — for any tool outside
      {multi_task, schedule, volume, media} it ends in a last-two-words
      heuristic, `" ".join(parts[-2:])` (:522-523). Verified at `b5f3953`:
          _extract_arg('weather', 'شو الطقس بعمان')   -> 'الطقس بعمان'  (topic noun kept)
          _extract_arg('weather', 'شو الطقس في عمّان') -> 'في عمان'     (preposition kept)

  P3  the MERGE RULE, `src/dispatcher.py:985-995` — on a matching tool the net's
      arg OVERWRITES unconditionally (`arg = net_arg` at :995). Because
      `cognition._normalize` strips tashkeel (:271) while `_keyword_net`'s
      `clean` (:674) does not, the two args can never compare equal for a
      shadda'd city, so for «عمّان» the refinement branch ALWAYS fires and the
      WORSE arg deterministically overwrites the better one. §A-corrections-2
      Item 2 records that this branch refines the ROUTER's arg, not cognition's:
      cognition runs only inside `if tool == "none":` (:939).

THE SHAPE. `weather` wants a place name; `schedule` wants free text plus a
time; `convert_currency` and `crypto_price` scan the raw string themselves
(`src/tools.py:911-920`, `:941`). A generic trimmer helps one class and damages
another, so `entity_from_phrase` is applied ONLY to tools declared entity-shaped
(`ARG_ENTITY_TOOLS`), and every other tool's arg is returned untouched.

IMPORTS ARE LAZY, ON PURPOSE. A module-level `from src.cognition import
entity_from_phrase` aborts collection with a bare `ImportError` while the seam
is unbuilt, and then no guard in this file is ever SEEN failing — the failure
`tests/test_tool_catalog_completeness.py:64-70` writes down and works around.
Lazy imports make every guard in this file report its own assertion.

WHAT THIS FILE DOES NOT CLAIM
-----------------------------
- It does NOT claim `weather('عمّان هسا')` is fixed. That reproduction is a DIRECT
  handler call; no producer fix reaches it, and the honest reading of it is a
  separate capability question about `jordan_coords` (`src/skills/weather.py:70-72`,
  whose docstring claims "ar-insensitive" while the code is a bare
  `_STATIC_COORDS.get(place.strip())` — verified: `jordan_coords('عمّان')` is
  `None`). That module is outside this node's file ownership.
- It does NOT touch A-10 (error messages blame the owner, `src/tools.py:1213`)
  or A-13 (unknown coin -> bitcoin, `src/tools.py:941`). Different defects,
  different modules.
- The ARABIC-COMMA guard (`test_glued_arabic_comma_does_not_hide_the_imperative`)
  is routing, not argument extraction, and rides here as a DECLARED scope
  addition. It is RED for its own reason and has its own assertion.
- `ال` is NEVER stripped. `الزرقاء`, `العقبة`, `المفكرة` are canonical
  spellings in `src/skills/weather.py:53-66`.
- The outgoing arg PRESERVES the owner's surface form. `عمّان` goes downstream
  as `عمّان` (with the shadda), because `WeatherClient.current` echoes
  `place.strip()` into the narration (`src/skills/weather.py:120`). Tashkeel
  folding belongs to the LOOKUP KEY, which lives in another module.
"""

from __future__ import annotations

import pytest

from src.cognition import _normalize, deduce
from src.dispatcher import _keyword_net

AMMAN = "عمّان"  # with shadda — the owner's own spelling
AMMAN_BARE = "عمان"  # the static-table spelling (src/skills/weather.py:50)


def _entity(span: str) -> str:
    """Lazy: see the module docstring on why this is not a top-level import."""
    from src.cognition import entity_from_phrase

    return entity_from_phrase(span)


def _entity_tools() -> frozenset[str]:
    from src.cognition import ARG_ENTITY_TOOLS

    return ARG_ENTITY_TOOLS


def _cognition_extract(tool: str, clean: str) -> str:
    from src.cognition import _extract_arg

    return _extract_arg(tool, clean)


# --------------------------------------------------------------------------
# P1 — the keyword net: a place name, not the turn
# --------------------------------------------------------------------------


def test_weather_arg_is_the_place_not_the_turn():
    """Reproduction 3, the dispatcher's own words. `geocode found no place
    named عمّان اليوم` (`src/skills/weather.py:140`) is downstream of this."""
    assert _keyword_net("شو الطقس في عمّان اليوم") == ("weather", AMMAN)


def test_weather_arg_drops_the_here_now_filler():
    """Reproduction 1/2 as they arrive at the seam: the filler is appended to a
    real place name, so edge-trimming resolves it."""
    assert _keyword_net("شو الطقس في عمّان هسا") == ("weather", AMMAN)


def test_weather_interior_filler_does_not_become_the_city():
    """«شو الطقس اليوم بعمّان» — the filler is INTERIOR. Verified at `b5f3953`
    to yield `('weather', 'اليوم بعمّان')`, i.e. the filler LEADS. A trailing-
    only trim cannot touch this; it needs extraction from both edges."""
    assert _keyword_net("شو الطقس اليوم بعمّان") == ("weather", AMMAN)


def test_weather_bare_question_yields_empty_arg_for_the_tool_default():
    """The fail-safe, pinned. `src/tools.py:1205` owns the empty-arg default
    (`place = arg.strip() or "عمان"`); the net must keep handing it through,
    which is also what `tests/test_weather.py:109-113` already requires."""
    assert _keyword_net("شو الطقس؟") == ("weather", "")


def test_weather_filler_only_capture_yields_empty_never_the_filler():
    """THE WORST CASE, not in the acceptance report: at `b5f3953`
    `_keyword_net('تمام، شو الطقس اليوم')` returned `('weather', 'اليوم')` —
    the CITY IS THE FILLER. It must become `""` so the tool's home-city default
    governs, and must NEVER return a filler word as a place name."""
    assert _keyword_net("تمام، شو الطقس اليوم") == ("weather", "")


def test_weather_politeness_only_capture_yields_empty():
    """`شو الطقس لو سمحت` returned `('weather', 'لو سمحت')` at `b5f3953`,
    which geocodes a politeness phrase into the session's unknown-place set
    (`src/skills/weather.py:139`)."""
    assert _keyword_net("شو الطقس لو سمحت") == ("weather", "")


def test_weather_prefix_strip_never_eats_بكرة():
    """THE SAME-SEAM BUG, verified at `b5f3953`:
    `_keyword_net('شو الطقس بكرة بعمّان')` returned `('weather', 'كرة بعمّان')`.
    The post-strip shaved the `ب` off «بكرة» because it shaved a bare `ب` off
    ANY word. «بكرة» is TOMORROW; «كرة» is a BALL. Word-boundary only."""
    tool, arg = _keyword_net("شو الطقس بكرة بعمّان")
    assert tool == "weather"
    assert arg == AMMAN, f"«بكرة» must never become «كرة»: got {arg!r}"


def test_weather_propositional_forms_still_resolve():
    """The pre-existing contract (`tests/test_weather.py:101-106` and
    `tests/test_dispatcher.py:458-460`): a joined or spaced connector yields the
    bare place."""
    assert _keyword_net("شو الطقس في عمّان")[1] == AMMAN
    assert _keyword_net("شو الطقس على عمّان")[1] == AMMAN
    assert _keyword_net("شو الطقس مع عمّان")[1] == AMMAN
    # the literal `بعمان` alternation in the pattern (:454) — bare, no shadda
    assert _keyword_net("شو الطقس بعمان؟")[1] == AMMAN_BARE


def test_weather_multi_word_place_is_kept_whole():
    """A two-token place name must survive: trimming is per-token, and a real
    entity is never truncated to its first word."""
    assert _keyword_net("شو الطقس في خريبة السوف") == ("weather", "خريبة السوف")


# --------------------------------------------------------------------------
# P2 — cognition's extractor: no topic noun, no preposition
# --------------------------------------------------------------------------


def test_cognition_weather_arg_excludes_topic_noun_and_preposition():
    """At `b5f3953` `_extract_arg('weather', 'شو الطقس بعمان')` returned
    `'الطقس بعمان'` — the TOPIC NOUN is not the entity — and
    `_extract_arg('weather', 'شو الطقس في عمّان')` returned `'في عمان'` — the
    PREPOSITION is not the entity."""
    assert _cognition_extract("weather", _normalize("شو الطقس بعمان")) == AMMAN_BARE
    assert _cognition_extract("weather", _normalize("شو الطقس في عمّان")) == AMMAN


def test_cognition_and_net_agree_on_the_same_place():
    """The merge rule exists to reconcile these two producers. When they
    disagree about a shadda'd city, the disagreement is the bug (P3), so they
    must now agree on the place itself."""
    text = "شو الطقس في عمّان"
    assert _cognition_extract("weather", _normalize(text)) == _keyword_net(text)[1]


def test_cognition_arg_is_empty_when_the_turn_names_no_entity():
    """A bare question names no place. Empty is the correct arg and it reaches
    `src/tools.py:1205`'s default; inventing one would be the failure."""
    assert _cognition_extract("weather", _normalize("شو الطقس؟")) == ""


def test_entity_shaped_tools_are_declared_not_guessed():
    """The shape table is explicit, so an undeclared tool is IDENTITY by
    construction rather than by accident."""
    assert "weather" in _entity_tools()
    # free-text tools are NOT entity-shaped — that is the over-trim guard's
    # structural premise (`tests/test_a3_over_trim_guard.py`)
    for free_text in ("schedule", "multi_task", "volume", "media"):
        assert free_text not in _entity_tools(), free_text


# --------------------------------------------------------------------------
# P3 — the merge rule: refine, do not overwrite
# --------------------------------------------------------------------------


def test_merge_rule_normalizes_both_sides_before_choosing():
    """`src/dispatcher.py:985-995`. At `b5f3953` the rule was
    `if net_arg != arg: arg = net_arg` — an unconditional overwrite. Because
    `cognition._normalize` folds tashkeel (:271) and the net's `clean` (:674)
    does not, the compare is unequal for `عمّان` on EVERY turn, so the
    refinement always fired. The resolved entity must now be the same from
    both sides, which makes the branch a no-op for a correct input."""
    cognition_side = _cognition_extract("weather", _normalize("شو الطقس في عمّان"))
    net_side = _keyword_net("شو الطقس في عمّان")[1]
    assert _entity(cognition_side) == _entity(net_side)


def test_refinement_log_line_names_the_router_not_cognition():
    """§A-corrections-2 Item 2: the line `dispatcher keyword net refined
    cognition arg` misnames what it refines. Cognition populates `arg` only
    inside `if tool == "none":` (`src/dispatcher.py:939`, `:972`), so when this
    branch fires on a matching tool the arg came from the LLM router at :936.
    The message must not blame cognition for the router's arg."""
    import inspect

    from src import dispatcher

    assert "refined cognition arg" not in inspect.getsource(dispatcher), (
        "the refinement branch may refine the ROUTER's arg; the log line must "
        "say so (src/dispatcher.py:990-994, §A-corrections-2 Item 2)"
    )


# --------------------------------------------------------------------------
# DECLARED SCOPE ADDITION — the Arabic-comma routing bug
# --------------------------------------------------------------------------


def test_glued_arabic_comma_does_not_hide_the_imperative():
    """OWNER-APPROVED SCOPE ADDITION, with its own RED guard.

    `cognition._normalize` (:266-272) collapses whitespace only; it does not
    split on Arabic punctuation. A short-stem marker must anchor at a token
    START (`src/cognition.py:275-279`, `_SHORT_STEM_LEN = 5` at :279), so a
    verb glued behind «تمام،» is one token and is INVISIBLE. Verified at
    `b5f3953` — all 45 tools scored 0.0:
        deduce('تمام،ذكّرني قبل ساعتين من الغد أحضر Milk')
            -> tool='none', confidence=1.0
        deduce('تمام، ذكّرني قبل ساعتين من الغد أحضر Milk')   # one space
            -> tool='schedule', confidence=0.32
    A single missing space changed the ROUTE. That is a routing defect, not an
    argument defect, and it is fixed here because it is in the same
    normalization the entity extractor shares.
    """
    hyp = deduce("تمام،ذكّرني قبل ساعتين من الغد أحضر Milk")
    assert hyp.tool == "schedule", f"glued comma hid the imperative: {hyp.tool}"
    assert hyp.confidence >= 0.12, hyp.confidence


def test_normalize_splits_on_arabic_punctuation():
    """The primitive itself, stated directly. Arabic punctuation must become a
    separator; ASCII `.` must NOT, or every URL in the BM25 index
    (`src/associative.py:19` imports this function) would shatter."""
    assert _normalize("تمام،ذكّرني").split() == ["تمام", "ذكّرني"]
    assert _normalize("شو الطقس؟").split() == ["شو", "الطقس"]
    assert _normalize("بكرة،اليوم").split() == ["بكرة", "اليوم"]
    # ASCII full stop and colon survive — a URL is one token
    assert _normalize("اقرئي https://example.com/a").split()[-1] == "https://example.com/a"


@pytest.mark.parametrize(
    "phrase",
    [
        "ذكّرني بعد ساعتين أحضر حليب",
        "تمام، ذكّرني قبل ساعتين من الغد أحضر Milk",
        "ذكّرني أشتري حليب اليوم من السوق",
    ],
)
def test_punctuation_split_does_not_change_the_schedule_route(phrase: str):
    """The split must not disturb a turn that already routed correctly."""
    assert deduce(phrase).tool == "schedule", phrase


# --------------------------------------------------------------------------
# The shape predicate itself
# --------------------------------------------------------------------------


def test_entity_from_phrase_is_idempotent():
    """Applying it twice must not keep eating. A normalizer that shrinks its
    input on every pass is a trimmer with no floor."""
    once = _entity("شو الطقس اليوم في عمّان")
    assert _entity(once) == once


def test_entity_from_phrase_never_invents_a_token():
    """Every token it returns came from the input. No synthesis, ever — a
    hallucinated place name would geocode to a real, WRONG city."""
    source = "شو الطقس اليوم بعمّان"
    for token in _entity(source).split():
        assert token in source, token


def test_entity_from_phrase_preserves_the_surface_form():
    """Tashkeel belongs to the LOOKUP key, not to the outgoing arg.
    `WeatherClient.current` echoes the arg into the narration
    (`src/skills/weather.py:120`); Sara must not respell the owner's city."""
    assert _entity("شو الطقس في عمّان") == AMMAN
    assert _entity("عمّان") == AMMAN


def test_entity_from_phrase_keeps_the_definite_article():
    """`الزرقاء` / `العقبة` / `المفكرة` are CANONICAL spellings in the static
    table (`src/skills/weather.py:53,56,60`). Stripping `ال` would break every
    one. `src/associative._tokens` strips it (`src/associative.py:122-123`) and
    is deliberately NOT reused here."""
    assert _entity("الزرقاء") == "الزرقاء"
    assert _entity("شو الطقس بالعقبة") == "العقبة"
    assert _entity("المفكرة") == "المفكرة"
