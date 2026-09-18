"""memory_upsert (P1 consensus): slot-collision supersession for User_Info.

Seam: src.memory.upsert_fact / resolve_current_facts (pure functions).
The LLM triple-emission side stays P2; here only storage + resolution land.
"""

from __future__ import annotations

from src.memory import filter_superseded_rows, resolve_current_facts, upsert_fact

NOTE = """## معلومة 2026-09-10 08:00
slot: owner/workout
value: 18:00
"""


def test_upsert_new_slot_appends_plain_section() -> None:
    body = upsert_fact("", "owner", "workout", "18:00", "2026-09-10 08:00")
    assert "slot: owner/workout" in body
    assert "value: 18:00" in body
    assert "superseded" not in body


def test_upsert_collision_marks_old_superseded_keeps_audit() -> None:
    """Live dialectic 2026-09-18: the 18:00→07:00 workout move must not leave
    two live facts. Old row retained but dead to RAG."""
    body = upsert_fact(NOTE, "owner", "workout", "07:00", "2026-09-18 09:00")
    assert "value: 18:00" in body  # audit trail preserved (append-only)
    assert body.count("superseded: owner/workout") == 1
    assert "value: 07:00" in body


def test_resolve_current_hides_superseded_rows() -> None:
    body = upsert_fact(NOTE, "owner", "workout", "07:00", "2026-09-18 09:00")
    current = resolve_current_facts(body)
    assert current == {"owner/workout": "07:00"}


def test_unrelated_slots_survive_upsert() -> None:
    body = upsert_fact(
        NOTE + "## معلومة 2026-09-11 08:00\nslot: owner/wake\nvalue: 06:00\n",
        "owner",
        "workout",
        "07:00",
        "2026-09-18 09:00",
    )
    current = resolve_current_facts(body)
    assert current == {"owner/workout": "07:00", "owner/wake": "06:00"}


def test_envelope_filter_drops_dead_rows_keeps_prose() -> None:
    """RAG sees live facts + free prose, never superseded rows or markers."""
    body = upsert_fact("عمر يحب الكنافة\n" + NOTE, "owner", "workout", "07:00", "2026-09-18 09:00")
    filtered = filter_superseded_rows(body)
    assert "عمر يحب الكنافة" in filtered
    assert "value: 07:00" in filtered
    assert "value: 18:00" not in filtered
    assert "superseded:" not in filtered


def test_envelope_filter_passthrough_without_markers() -> None:
    body = "عمر يحب الكنافة\n## معلومة 2026-09-10\nslot: owner/wake\nvalue: 06:00\n"
    assert filter_superseded_rows(body) == body
