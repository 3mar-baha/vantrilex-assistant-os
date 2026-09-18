"""Stdlib BM25 ranker (P1 consensus): IDF-weighted retrieval primitive.

Pure math, zero I/O: k1 saturation + length normalization over token lists.
Wiring into associative.py is P2 work (p95 budget + existing tests).
"""

from __future__ import annotations

import math

K1: float = 1.5
B: float = 0.75


def score(query: list[str], docs: list[list[str]]) -> list[float]:
    """BM25 scores, one per doc, in corpus order."""
    if not docs or not query:
        return [0.0] * len(docs)
    doc_count = len(docs)
    doc_lens = [len(doc) or 1 for doc in docs]
    avg_len = sum(doc_lens) / doc_count
    doc_freq: dict[str, int] = {}
    for doc in docs:
        for term in set(doc):
            doc_freq[term] = doc_freq.get(term, 0) + 1
    totals = [0.0] * doc_count
    for term in query:
        df = doc_freq.get(term, 0)
        if not df:
            continue
        idf = math.log(1 + (doc_count - df + 0.5) / (df + 0.5))
        for i, doc in enumerate(docs):
            tf = doc.count(term)
            if not tf:
                continue
            norm = 1 - B + B * doc_lens[i] / avg_len
            totals[i] += idf * (tf * (K1 + 1)) / (tf + K1 * norm)
    return totals


def rank(query: list[str], docs: list[list[str]]) -> list[int]:
    """Doc indices, best first (stable for ties)."""
    scored = sorted(enumerate(score(query, docs)), key=lambda pair: (-pair[1], pair[0]))
    return [index for index, _ in scored]
