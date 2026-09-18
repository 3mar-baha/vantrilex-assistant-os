"""Sovereign evolution loop (P2): distill repeated trajectories into proposals.

Seam: src.evolution.distill_chains / verify_proposal_code / format_proposal.
Proposals are owner-promoted markdown — nothing self-registers, ever.
"""

from __future__ import annotations

from src.evolution import (
    PROMOTABLE_TOOLS,
    PromotionReport,
    distill_chains,
    evaluate_proposal,
    format_proposal,
    promotion_decision,
    verify_proposal_code,
)

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


def _overlay(tmp_path):
    import sys

    sys.path.insert(0, "tests/live_harness")
    from overlay import OverlayVault

    real = tmp_path / "real"
    real.mkdir()
    return OverlayVault(real, tmp_path / "shadow")


def test_evaluate_clean_proposal_passes(tmp_path) -> None:
    overlay = _overlay(tmp_path)
    proposal = {
        "chain": [["gmail", ""], ["calendar", "بكرة"]],
        "occurrences": 4,
        "code": "import re\nx = re.sub('a', 'b', 'a')",
    }
    report = evaluate_proposal(proposal, overlay)
    assert isinstance(report, PromotionReport)
    assert report.passed is True and report.reasons == []


def test_evaluate_rejects_irreversible_tool(tmp_path) -> None:
    overlay = _overlay(tmp_path)
    report = evaluate_proposal({"chain": [["launch", "الحاسبة"]], "occurrences": 5}, overlay)
    assert report.passed is False
    assert any("confirmation" in reason for reason in report.reasons)


def test_evaluate_rejects_unsafe_code(tmp_path) -> None:
    overlay = _overlay(tmp_path)
    report = evaluate_proposal(
        {"chain": [["gmail", ""]], "occurrences": 3, "code": "import os"},
        overlay,
    )
    assert report.passed is False


def test_evaluate_rejects_missing_vault_note(tmp_path) -> None:
    overlay = _overlay(tmp_path)
    report = evaluate_proposal(
        {"chain": [["gmail", ""]], "occurrences": 3, "notes": ["Studies/Nope.md"]},
        overlay,
    )
    assert report.passed is False


def test_promotable_set_never_contains_irreversible() -> None:
    from src.skills.capabilities import IRREVERSIBLE_TOOLS

    assert PROMOTABLE_TOOLS.isdisjoint(IRREVERSIBLE_TOOLS)


def test_promotion_decision_requires_report_owner_and_suite() -> None:
    good = PromotionReport(passed=True, reasons=[])
    assert promotion_decision(good, owner_approved=True, suite_green=True) is True
    assert promotion_decision(good, owner_approved=False, suite_green=True) is False
    assert promotion_decision(good, owner_approved=True, suite_green=False) is False
    bad = PromotionReport(passed=False, reasons=["unsafe"])
    assert promotion_decision(bad, owner_approved=True, suite_green=True) is False
