"""Proactive associative context (Leap 2) — Phase-1 slice: frontmatter aliases.

Full TF-IDF body index lands in Phase-2. This module holds the deterministic
first stage: matching the message against note `aliases:` frontmatter lists
(«مصاري» → Finance/Budget.md) at sub-10ms with zero embeddings and zero
network. Pure function — trivially unit-tested, never blocks the reply.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Final

ALIAS_KEY: Final[str] = "aliases"


def _norm(text: str) -> str:
    return " ".join((text or "").split()).strip().casefold()


def parse_aliases(meta: Mapping[str, Any] | None) -> list[str]:
    """Frontmatter `aliases:` as a clean list — accepts str | list | missing."""
    if not isinstance(meta, Mapping):
        return []
    raw = meta.get(ALIAS_KEY, [])
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, (list, tuple)):
        return []
    return [a.strip() for a in raw if isinstance(a, str) and a.strip()]


def match_aliases(text: str, notes: Sequence[tuple[str, Mapping[str, Any]]]) -> str | None:
    """First note (in given order) with an alias occurring in the message.

    Substring match on normalized forms — colloquial synonyms resolve without
    embeddings («مصاري» hits even mid-sentence). Returns the note path or None.
    Deterministic and allocation-trivial (measured <10ms in tests).
    """
    needle = _norm(text)
    if not needle:
        return None
    for path, meta in notes:
        for alias in parse_aliases(meta):
            if _norm(alias) and _norm(alias) in needle:
                return path
    return None
