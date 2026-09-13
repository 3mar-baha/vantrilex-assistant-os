"""Tier 1 — associative aliases matcher (Phase-1 Leap-2 slice). Hermetic."""

import time

from src.associative import match_aliases, parse_aliases

NOTES = [
    ("02_Areas/Finance/Budget.md", {"aliases": ["مصاري", "ميزانية", "budget"]}),
    ("02_Areas/Health/Fitness.md", {"aliases": ["رياضة", "جيم"]}),
    ("00_Inbox/scratch.md", {"title": "no aliases here"}),
    ("03_Projects/App.md", {"aliases": "تطبيق"}),
]


def test_exact_and_substring_match():
    assert match_aliases("مصاري", NOTES) == "02_Areas/Finance/Budget.md"
    assert match_aliases("شو صرفنا مصاري هالشهر؟", NOTES) == "02_Areas/Finance/Budget.md"
    assert match_aliases("وين اروح عالجيم اليوم؟", NOTES) == "02_Areas/Health/Fitness.md"


def test_first_note_wins_in_order():
    notes = [
        ("a.md", {"aliases": ["مشترك"]}),
        ("b.md", {"aliases": ["مشترك"]}),
    ]
    assert match_aliases("مشترك", notes) == "a.md"


def test_no_match_returns_none():
    assert match_aliases("شو الطقس اليوم؟", NOTES) is None
    assert match_aliases("", NOTES) is None
    assert match_aliases("   ", NOTES) is None
    assert match_aliases("مصاري", []) is None


def test_alias_shapes():
    assert parse_aliases({"aliases": "تطبيق"}) == ["تطبيق"]
    assert parse_aliases({"aliases": ["a", "", 7, None, "b"]}) == ["a", "b"]
    assert parse_aliases({}) == []
    assert parse_aliases(None) == []
    assert parse_aliases({"aliases": 42}) == []


def test_case_and_space_insensitive():
    assert match_aliases("  BUDGET  ", [("f.md", {"aliases": ["budget"]})]) == "f.md"


def test_sub_10ms_on_50_notes():
    notes = [(f"n{i}.md", {"aliases": [f"alias{i}", f"رديف{i}"]}) for i in range(50)]
    notes.append(("hit.md", {"aliases": ["مصاري"]}))
    t0 = time.perf_counter()
    for _ in range(200):
        assert match_aliases("وين مصاري الشهر؟", notes) == "hit.md"
    avg_ms = (time.perf_counter() - t0) / 200 * 1000
    assert avg_ms < 10.0, f"alias scan too slow: {avg_ms:.2f}ms avg"
