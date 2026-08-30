"""M1 dialect engine contract (master-directive spec M1, task 1.4)."""

from src.dialect import (
    DialectNote,
    append_notes,
    learn,
    normalize,
    parse_notes,
    parse_teachings,
    prompt_block,
)


def test_normalize_applies_note_mapping():
    notes = [
        DialectNote(term="من عيوني", phonetic="من عُيونيّ", context="أكيد", date="2026-08-29"),
        DialectNote(term="هسا", phonetic="هَسّا", context="تستخدمها بمعنى الآن", date="2026-08-29"),
    ]
    assert normalize("هسا ببدأ من عيوني", notes) == "هَسّا ببدأ من عُيونيّ"
    # longest terms win when one is a prefix of another
    assert normalize("هسا", notes) == "هَسّا"
    # no notes -> text unchanged
    assert normalize("هسا", []) == "هسا"


def test_ingestion_appends_note_and_never_blocks():
    today = "2026-08-29"
    teach = "تعلمي: هسا -> هَسّا (تستخدمها بمعنى الآن)"

    notes = parse_teachings(teach, today=today)
    assert notes == [
        DialectNote(term="هسا", phonetic="هَسّا", context="تستخدمها بمعنى الآن", date=today)
    ]

    seed = "---\nnotes: []\n---\n# Dialect Notes\n"
    merged = append_notes(seed, notes)
    assert parse_notes(merged) == notes
    # duplicate term is skipped -> file unchanged
    assert append_notes(merged, notes) == merged

    # never blocks: any internal failure surfaces as None, never an exception
    import src.dialect as d

    original = d.parse_teachings
    d.parse_teachings = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom"))
    try:
        assert learn("تعلمي: فشل -> فشل", notes_md=seed, today=today) is None
    finally:
        d.parse_teachings = original


def test_snapshot_injection_into_prompt():
    notes = [DialectNote(term="هسا", phonetic="هَسّا", context="الآن", date="2026-08-29")]
    block = prompt_block(notes)
    assert "هسا" in block and "هَسّا" in block and "الدليل" in block

    # capped at max_entries
    many = [
        DialectNote(term=f"كلمة{i}", phonetic=f"نطق{i}", context="", date="2026-08-29")
        for i in range(50)
    ]
    assert prompt_block(many, max_entries=40).count("كلمة") == 40

    # empty registry -> nothing injected
    assert prompt_block([]) == ""
