"""Stdlib BM25 ranker (P1 consensus): IDF-weighted retrieval primitive.

Seam: src.bm25.rank (pure function). Wiring into associative.py is P2 work;
here only the ranking math lands, tested against worked examples.
"""

from __future__ import annotations

from src.bm25 import rank


def test_rare_term_outranks_common_term() -> None:
    """IDF: a doc matching the rare word beats one matching the common word."""
    docs = [
        ["بريد", "يوم"],  # common-heavy: يوم appears in both docs
        ["يوم", "موعد"],  # rare hit: موعد
    ]
    assert rank(["يوم", "موعد"], docs) == [1, 0]


def test_empty_query_and_empty_corpus_never_raise() -> None:
    assert rank([], [["a"]]) == [0]
    assert rank(["a"], []) == []
    assert rank([], []) == []


def test_repeated_query_term_saturates_not_explodes() -> None:
    """k1 saturation: score increments shrink as term frequency grows."""
    from src.bm25 import score

    once = score(["x"], [["x"], ["y"]])[0]
    five = score(["x"], [["x"] * 5, ["y"]])[0]
    ten = score(["x"], [["x"] * 10, ["y"]])[0]
    assert five > once  # monotonic
    assert (ten - five) < (five - once)  # diminishing increments
