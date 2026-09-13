"""Tier 1 — cognitive DAG contracts (mission Stage-2 slice). Hermetic, no LLM.

Weight is structural (clauses x deduced tools), never vibes; the ephemeral
todo is built, checked, and flushed with zero persistence.
"""

from src.cognitive_dag import EphemeralTodo, classify_weight


def test_weight_1_banter():
    plan = classify_weight("مرحبا سارة")
    assert (plan.weight, plan.critical, plan.estimated_steps, plan.tools) == (1, False, 1, ())


def test_weight_1_empty():
    assert classify_weight("").weight == 1


def test_weight_2_single_tool():
    plan = classify_weight("شو عندي مواعيد بكرا؟")
    assert plan.weight == 2 and plan.tools == ("calendar",) and plan.estimated_steps == 2


def test_weight_4_three_tools_explicit_connectors():
    plan = classify_weight("شوفلي الإيميلات ثم سجلي موعد بكرا بعدين ذكرني بالدواء")
    assert plan.weight == 4 and plan.estimated_steps == 4 and plan.clauses == 3
    assert plan.tools == ("gmail", "create_event", "schedule")


def test_glued_wa_does_not_fracture():
    """Drill-hardened splitter contract: glued و is not a clause boundary."""
    plan = classify_weight("شوفلي الإيميلات وسجلي موعد بكرا")
    assert plan.clauses == 1 and plan.weight == 2


def test_critical_markers_both_languages():
    for text in ("السيرفر واقع الحقني", "production down الحقني", "build fail_alert"):
        plan = classify_weight(text)
        assert plan.critical is True and plan.weight == 5 and plan.estimated_steps == 1


def test_todo_build_check_flush():
    plan = classify_weight("شوفلي الإيميلات ثم سجلي موعد بكرا بعدين ذكرني بالدواء")
    todo = EphemeralTodo.from_plan(plan)
    assert todo.pending_count() == 4  # 3 tools + synthesis
    assert "[ ] gmail" in todo.render() and "[ ] synthesis" in todo.render()
    assert todo.check("gmail") is True
    assert todo.check("gmail") is False  # already done: no double-count
    assert todo.check("nope") is False
    assert todo.pending_count() == 3
    transcript = todo.flush()
    assert "[x] gmail" in transcript
    assert todo.pending_count() == 0 and todo.items == []


def test_todo_from_plan_empty_is_synthesis_only():
    todo = EphemeralTodo.from_plan(classify_weight("مرحبا"))
    assert [i.label for i in todo.items] == ["synthesis"]
