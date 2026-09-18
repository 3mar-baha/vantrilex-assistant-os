"""Ephemeral Composition Cache (P1 consensus): session-scoped read-only chains.

Seam: src.cognition.CompositionCache (pure, in-memory).
Dispatcher wiring + safety_class derivation stay P2; the store/replay
mechanics and the read-only gate land here.
"""

from __future__ import annotations

from src.cognition import CompositionCache

READS = frozenset({"gmail", "calendar", "telemetry"})
CHAIN = (("gmail", ""), ("calendar", ""))


def test_store_and_replay_read_only_chain() -> None:
    cache = CompositionCache(read_only_tools=READS)
    assert cache.lookup("شوفيلي الايميلات") is None
    cache.store("شوفيلي الايميلات", CHAIN)
    assert cache.lookup("شوفيلي الايميلات") == CHAIN


def test_key_normalizes_whitespace() -> None:
    cache = CompositionCache(read_only_tools=READS)
    cache.store("شوفيلي الايميلات", CHAIN)
    assert cache.lookup("  شوفيلي   الايميلات  ") == CHAIN


def test_write_tool_chain_refused() -> None:
    cache = CompositionCache(read_only_tools=READS)
    cache.store("افتحي البريد", (("launch", "البريد"),))
    assert cache.lookup("افتحي البريد") is None


def test_clear_resets_session() -> None:
    cache = CompositionCache(read_only_tools=READS)
    cache.store("شوفيلي الايميلات", CHAIN)
    cache.clear()
    assert cache.lookup("شوفيلي الايميلات") is None
