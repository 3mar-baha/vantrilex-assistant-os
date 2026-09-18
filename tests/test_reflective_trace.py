"""ReflectiveTrace nightly ledger block (P1 consensus): append-only daily section.

Seam: src.cognition.render_ledger_block (pure function, public API).
"""

from __future__ import annotations

from src.cognition import ReflectiveTrace


def test_empty_trace_renders_nothing() -> None:
    """No friction, no write — the nightly worker skips silent days."""
    assert ReflectiveTrace().render_ledger_block("2026-09-18") == ""


def test_friction_renders_dated_arabic_section() -> None:
    trace = ReflectiveTrace()
    trace.record_outcome("gmail", False, "403 quota")
    trace.record_outcome("gmail", False, "403 quota")
    trace.record_outcome("calendar", True, "")
    block = trace.render_ledger_block("2026-09-18")
    assert "2026-09-18" in block
    assert "gmail" in block and "403 quota" in block
    assert "calendar" not in block  # successes stay out of the friction ledger
