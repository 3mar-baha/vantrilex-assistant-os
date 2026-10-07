r"""A-3b — the CONSUMER seam: `_strip_command` must yield the TITLE.

REPRODUCTION 4 IS NOT HERE, AND SAYING WHY IS THE POINT. «تمام،ذكّرني قبل
ساعتين من الغد أحضر Milk» is not a filler-trimming defect. It is the absence of
argument EXTRACTION, in a different module, for a different reason, and it
survives any amount of trimming at the dispatcher. `schedule`'s arg is the
WHOLE TURN by design — `src/dispatcher.py:730-734` and `src/cognition.py:513-514`
both say so explicitly, because the timing parser scans for the timing words
wherever they sit in the sentence. What the turn BECOMES is decided here, in
`_strip_command`.

Three measured defects in `src/task_orchestrator.py:58-72`, all verified at
`b5f3953`:

  D1  SHADDA-BLIND VERB ALTERNATION. The alternation at :71 is
      `^(?:ذكريني|ذكرني|نبهيني|تنبيه|فكّرني)` — bare `ذكرني`. The owner's own
      spelling is `ذكّرني` (U+0651). The substitution runs on the RAW text
      (`_strip_command` is called with the original at `parse_delay_ar:86` and
      `parse_wallclock_ar:108`), so the verb NEVER matches and the verb SURVIVES
      into the title even on the happy path:
          parse_delay_ar('ذكّرني بعد ساعتين أحضر Milk')[1] == 'ذكّرني أحضر Milk'

  D2  NO LEADING-ACKNOWLEDGEMENT STRIP. «تمام، …» is the owner's own turn
      continuation, and it becomes part of the thing he is reminded about:
          parse_delay_ar('تمام، ذكّرني بعد ساعتين أحضر حليب')[1]
              == 'تمام، ذكّرني أحضر حليب'

  D3  THE BARE-«بعد» EATING BUG — THE OVER-TRIM HAZARD, ALREADY LIVE. The first
      substitution at :63-70 is `(?:بعد\s+[\d٠-٩]*\s*\S+|...)` with `count=1` and
      NO `^` anchor, and `[\d٠-٩]*` quantifies to ZERO digits, so a bare `بعد`
      followed by any non-space token is eaten:
          _strip_command('ذكرني بعد ما أكل أتابع الدايت') == 'أكل أتابع الدايت'
          _strip_command('ذكّرني بعد أن أخلّص شغلي قلي')  == 'ذكّرني أخلّص شغلي قلي'
      «بعد ما أكل» lost its meaning. This is the same class as the hazard in
      `tests/test_a3_over_trim_guard.py`, already shipped.

`قبل ساعتين` IS AN HONEST REFUSAL — OWNER DECISION, 2026-10-07. It is NOT
implemented here. It is exactly the `نصف ساعة` row at
`tests/test_task_orchestrator.py:49` ("unsupported shape -> honest None (no
guessing)"), and it is extended to every non-`بعد` delay preposition. What is
NOT acceptable, and is what this node fixes, is the honest `None` being followed
by the whole turn silently becoming the task title at `src/tools.py:1035,1066`.
An honest refusal is a correct outcome; a wrong title is not.

WHAT THIS FILE DOES NOT CLAIM
-----------------------------
- It does NOT claim `parse_delay_ar` learned a new form. The supported delay
  table is `_UNITS_S` (`src/task_orchestrator.py:45-55`) reached through
  `_DELAY_RE` (:32-34) and is UNCHANGED by this node.
- It does NOT claim the Google-lane title at `src/tools.py:1066` is rebuilt. That
  is `src/tools.py`, outside this node's ownership; what changes is that the
  shared `_strip_command` stops destroying `بعد ما` and stops leaving `ذكّرني`
  and `تمام،` inside the title it computes.
- It does NOT change which TOOL is chosen, and it does NOT trim reminder
  CONTENT. `tests/test_a3_over_trim_guard.py` owns that, and
  `test_strip_command_keeps_احضر_لا_يأكل_the_content` here is the same hazard
  seen at this seam.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from src.task_orchestrator import _strip_command, parse_delay_ar, parse_wallclock_ar

AMMAN = ZoneInfo("Asia/Amman")
NOW = datetime(2026, 10, 6, 10, 0, tzinfo=AMMAN)

# The owner's own spelling of the verb: shadda-bearing, as he writes it.
REMIND = "ذكّرني"  # with shadda
ACK = "تمام،"  # the leading acknowledgement, Arabic comma


# --------------------------------------------------------------------------
# D1 — the shadda-blind verb alternation
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "phrase",
    [
        f"{REMIND} بعد ساعتين أحضر حليب",
        f"{REMIND} بعد 60 ثانية اشتري بيض",
        f"{REMIND} على الساعة 3:47 مساء أحضر حليب",
        f"{ACK} {REMIND} بعد ساعتين أحضر حليب",
        f"{ACK}{REMIND} بعد ساعتين أحضر حليب",
    ],
)
def test_strip_command_removes_the_shadda_verb(phrase: str):
    """D1+D2. At `b5f3953` `_strip_command('ذكّرني بعد ساعتين أحضر Milk')`
    returned `'ذكّرني أحضر Milk'` — the verb survived because :71 spells it
    bare. The title is what he needs to remember, and the verb is not part of
    it (`src/skills/sara_tool_skills.py:170-172` says so in the product's own
    words: the title is what to remember, without the time word and without the
    verb itself)."""
    title = _strip_command(phrase)
    assert REMIND not in title, f"the verb survived into the title: {title!r}"
    assert "ذكرني" not in title, f"the verb survived into the title: {title!r}"


def test_strip_command_removes_a_bare_verb_too():
    """The existing spelling must keep working — a fix that only handles the
    shadda form is not a fix, it is a second special case."""
    assert _strip_command("ذكرني بعد ساعتين أحضر حليب") == "أحضر حليب"


def test_strip_command_removes_the_leading_acknowledgement():
    """D2. «تمام،» is turn continuation, not content. At `b5f3953` it rode the
    title verbatim: `parse_delay_ar('تمام، ذكّرني بعد ساعتين أحضر حليب')[1]`
    returned `'تمام، ذكّرني أحضر حليب'`."""
    for phrase in (
        f"{ACK} {REMIND} بعد ساعتين أحضر حليب",
        f"{ACK}{REMIND} بعد ساعتين أحضر حليب",
    ):
        title = _strip_command(phrase)
        assert "تمام" not in title, f"the acknowledgement survived: {title!r}"


def test_glued_arabic_comma_does_not_hide_the_verb_from_the_strip():
    """No space after the Arabic comma is how it arrives from a voice lane."""
    assert _strip_command(f"{ACK}{REMIND} بعد ساعتين أحضر حليب") == "أحضر حليب"


# --------------------------------------------------------------------------
# D3 — the bare-«بعد» eating bug
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "phrase",
    [
        "ذكرني بعد ما أكل أتابع الدايت",
        "ذكّرني بعد ما أكل أتابع الدايت",
        "ذكّرني بعد أن أخلّص شغلي قلي",
    ],
)
def test_strip_command_never_eats_بعد_ما(phrase: str):
    """THE OVER-TRIM CANARY, and it is RED today. At `b5f3953`
    `_strip_command('ذكرني بعد ما أكل أتابع الدايت')` returned
    `'أكل أتابع الدايت'`. `بعد` here is a CONJUNCTION, not a delay marker, and
    the two are told apart only by what follows: a digit or a unit from
    `_UNITS_S` (`src/task_orchestrator.py:45-55`)."""
    assert "بعد ما" in _strip_command(phrase), phrase


def test_strip_command_keeps_real_delay_content_out_of_the_title():
    """The counterpart: a REAL delay is still removed. A guard that only proves
    the bug is gone could pass by removing nothing at all."""
    assert "بعد" not in _strip_command("ذكّرني بعد ساعتين أحضر حليب")
    assert "بعد" not in _strip_command("ذكّرني بعد 60 ثانية اشتري بيض")


def test_strip_command_keeps_the_title_when_nothing_must_go():
    """Fail-safe: a title that carries no verb, no acknowledgement and no
    timing phrase is returned byte-identical. A stripper that eats `بعد` from a
    title like «قلي بعد يوم ننتقل» loses the owner's meaning."""
    for title in ("اشتري حليب من السوق", "راجع تقرير اليوم مع خالد"):
        assert _strip_command(title) == title, title


def test_strip_command_keeps_the_hazard_content_whole():
    """The hazard string from `tests/test_a3_over_trim_guard.py`, at this seam:
    the CONTENT keeps both its day and its two-word prepositional phrase."""
    title = _strip_command("ذكّرني اشتري حليب اليوم من السوق")
    assert "اليوم" in title, title
    assert "من السوق" in title, title


# --------------------------------------------------------------------------
# The honest refusal for an unsupported delay form
# --------------------------------------------------------------------------


def test_قبل_ساعتين_is_an_honest_refusal_not_a_guess():
    """OWNER DECISION, 2026-10-07: `قبل ساعتين` is an HONEST REFUSAL, the same
    doctrine as the `نصف ساعة` row at `tests/test_task_orchestrator.py:49`. It
    is NOT implemented, and this guard exists to keep it unimplemented — a
    silent improvement here would be a guess about what the owner meant, which
    is the exact failure the row documents ("unsupported shape -> honest None
    (no guessing)")."""
    assert parse_delay_ar("ذكّرني قبل ساعتين أحضر حليب", now=NOW) is None
    assert parse_wallclock_ar("ذكّرني قبل ساعتين أحضر حليب", now=NOW) is None


def test_supported_delay_forms_are_unchanged():
    """The delay table is NOT touched by this node. Every row of
    `tests/test_task_orchestrator.py:41-50` must keep its verdict."""
    assert parse_delay_ar("بعد 60 ثانية ذكريني اشتري بيض", now=NOW)[0].total_seconds() == 60
    assert parse_delay_ar("بعد ٥ ثواني افحص الفرن", now=NOW)[0].total_seconds() == 5
    assert parse_delay_ar("بعد 7 دقايق ذكريني افتح المسجد", now=NOW)[0].total_seconds() == 420
    assert parse_delay_ar("بعد 15 دقيقة نبهيني", now=NOW)[0].total_seconds() == 900
    assert parse_delay_ar("بعد ساعتين ذكريني اتصل", now=NOW)[0].total_seconds() == 7200
    assert parse_delay_ar("بعد 3 ساعات جربيني", now=NOW)[0].total_seconds() == 10800
    assert parse_delay_ar("بعد نصف ساعة", now=NOW) is None


def test_supported_wallclock_forms_are_unchanged():
    """Same for `tests/test_task_orchestrator.py:64-74`."""
    cases = {
        "على الساعة 3:47 مساء ذكريني اشتري بيض": (15, 47),
        "الساعة 9 صباحا ذكريني الدواء": (9, 0),
        "على الساعة 11:30 مساء": (23, 30),
        "على الساعة 12 مساء ذكريني الغدا": (12, 0),
        "على الساعة 12 صباح تذكير": (0, 0),
        "الساعة ٦:٣٠ مساء افحص": (18, 30),
        "الساعة 6:30 مساء": (18, 30),
        "ذكريني الساعة 8:15 مساء اغلاق الباب": (20, 15),
    }
    for phrase, (hour24, minute) in cases.items():
        when, _title = parse_wallclock_ar(phrase, now=NOW)
        assert when is not None, phrase
        assert (when.hour, when.minute) == (hour24, minute), phrase


def test_the_delay_parser_returns_a_title_that_is_actually_a_title():
    """The title contract is pinned NOW because
    `tests/test_task_orchestrator.py:53-83` DISCARDS `_title` (`_delay, _title =
    result` at :60; `when, _title = result` at :82). Before this node the title
    contract was pinned by NOTHING, which is how D1 and D2 shipped."""
    _delay, title = parse_delay_ar(f"{ACK} {REMIND} بعد ساعتين أحضر حليب", now=NOW)
    assert title == "أحضر حليب", title
