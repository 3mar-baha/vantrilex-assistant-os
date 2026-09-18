"""Sovereign evolution loop (P2): distill repeated trajectories into proposals.

Seam: src.evolution.distill_chains / verify_proposal_code / format_proposal.
Proposals are owner-promoted markdown — nothing self-registers, ever.
"""

from __future__ import annotations

from src.evolution import distill_chains, format_proposal, verify_proposal_code

CHAIN = [("gmail", ""), ("calendar", "بكرة")]


def test_distill_finds_triple_repeated_chain() -> None:
    trajectories = [CHAIN, [("gmail", "")], CHAIN, CHAIN]
    proposals = distill_chains(trajectories, min_repeats=3)
    assert len(proposals) == 1
    assert proposals[0]["chain"] == [list(step) for step in CHAIN]
    assert proposals[0]["occurrences"] == 3


def test_distill_ignores_sub_threshold_noise() -> None:
    assert distill_chains([CHAIN, CHAIN], min_repeats=3) == []
    assert distill_chains([], min_repeats=3) == []


def test_verify_rejects_unsafe_code() -> None:
    ok, _ = verify_proposal_code("import os\nos.system('x')")
    assert ok is False
    ok, _ = verify_proposal_code("eval('1+1')")
    assert ok is False
    ok, _ = verify_proposal_code("import socket")
    assert ok is False


def test_verify_rejects_syntax_errors() -> None:
    ok, reason = verify_proposal_code("def broken(:")
    assert ok is False and "syntax" in reason.lower()


def test_verify_accepts_stdlib_helpers() -> None:
    ok, _ = verify_proposal_code("import re\nimport math\nx = re.sub('a', 'b', 'a')")
    assert ok is True


def test_proposal_format_carries_chain_and_counts() -> None:
    text = format_proposal(
        {"chain": [["gmail", ""], ["calendar", "بكرة"]], "occurrences": 4}, "2026-09-18"
    )
    assert "2026-09-18" in text and "gmail" in text and "4" in text
