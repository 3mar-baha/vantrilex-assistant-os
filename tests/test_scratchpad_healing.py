"""In-turn scratchpad healing (P1 consensus): deterministic arg repair, zero LLM.

Seam: src.decision_loop.normalize_tool_arg / HealingBudget (pure).
Dispatcher wiring stays P2; here only the repair primitives land.
"""

from __future__ import annotations

from src.decision_loop import HealingBudget, normalize_tool_arg


def test_quotes_and_whitespace_stripped() -> None:
    assert normalize_tool_arg('  "الآلة الحاسبة"  ') == "الآلة الحاسبة"


def test_arabic_indic_digits_normalized() -> None:
    assert normalize_tool_arg("الساعة ٥:٠٠") == "الساعة 5:00"


def test_budget_allows_two_attempts_then_refuses() -> None:
    budget = HealingBudget()
    assert budget.may_retry("gmail") is True
    budget.note_failure("gmail")
    assert budget.may_retry("gmail") is True
    budget.note_failure("gmail")
    assert budget.may_retry("gmail") is False


def test_budget_is_per_tool() -> None:
    budget = HealingBudget()
    budget.note_failure("gmail")
    budget.note_failure("gmail")
    assert budget.may_retry("calendar") is True
