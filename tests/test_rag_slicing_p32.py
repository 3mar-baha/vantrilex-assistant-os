"""P3.2 budget slicing + quarantine coupling (master plan, Phase P3.2).

Closed arithmetic over ordered domains, sentence-boundary chunking, ceiling
halved while any lane is quarantined. Legacy inject path (domains=None) is
byte-identical — the existing suite pins it.
"""

from src.associative import (
    BLOCK_CEILING_CHARS,
    DOMAIN_FLOOR_CHARS,
    inject,
    sentence_chunks,
    slice_budgets,
)


def test_single_domain_takes_ceiling():
    assert slice_budgets(("kb",)) == [("kb", 3000)]
    assert BLOCK_CEILING_CHARS == 3000


def test_two_domains_split_sixty_forty():
    assert slice_budgets(("kb", "dialect")) == [("kb", 1800), ("dialect", 1200)]


def test_three_domains_split_fifty_thirty_twenty():
    assert slice_budgets(("a", "b", "c")) == [("a", 1500), ("b", 900), ("c", 600)]


def test_four_plus_equal_shares_with_floor():
    shares = slice_budgets(("a", "b", "c", "d"))
    assert [s for _, s in shares] == [750, 750, 750, 750]
    assert DOMAIN_FLOOR_CHARS == 400


def test_sub_floor_domains_dropped_loudly():
    shares = slice_budgets(tuple(f"d{i}" for i in range(10)))
    assert shares == []
    assert slice_budgets(tuple(f"d{i}" for i in range(7))) != []


def test_sentence_chunks_never_cut_mid_sentence():
    text = "أول جملة كاملة. ثاني جملة أطول بكثير من الأولى. ثالثة."
    out = sentence_chunks(text, budget=30)
    assert out.endswith((".", "!", "؟", "?"))
    assert "ثاني جملة أطول" not in out or out.endswith(".")


def test_chunks_fit_budget():
    text = "جملة واحد. جملة اثنان. جملة ثلاثة. جملة أربعة."
    out = sentence_chunks(text, budget=20)
    assert len(out) <= 20


def test_quarantine_halves_ceiling():
    from src import gateway

    assert gateway.any_quarantined() is False
    gateway._MODEL_COOLDOWNS["probe-model"] = 9999999999.0
    try:
        assert gateway.any_quarantined() is True
    finally:
        gateway._MODEL_COOLDOWNS.pop("probe-model", None)
    assert gateway.any_quarantined() is False


def test_inject_domains_none_legacy_bounded(tmp_path):
    note = tmp_path / "note.md"
    note.write_text("# Title\n\nكلمات مميزة للاسترجاع هنا\n", encoding="utf-8")
    out = inject("كلمات مميزة للاسترجاع", tmp_path)
    assert "كلمات مميزة" in out


def test_inject_domains_path_slices_block(tmp_path):
    (tmp_path / "Dialect_Encyclopedia").mkdir(parents=True, exist_ok=True)
    (tmp_path / "Dialect_Encyclopedia" / "d.md").write_text(
        "# D\n\nلهجة أردنية أصيلة جدا\n", encoding="utf-8"
    )
    out = inject("لهجة أردنية أصيلة جدا", tmp_path, domains=("dialect", "kb"), quarantined=False)
    assert "لهجة أردنية" in out
    small = inject("لهجة أردنية أصيلة جدا", tmp_path, domains=("dialect", "kb"), quarantined=True)
    assert len(small) <= len(out)
