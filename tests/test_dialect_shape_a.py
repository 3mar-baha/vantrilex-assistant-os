"""Node A RED-first guards: dialect shaping (A1/A2/A3)."""

from src.dialect import _SEED_TTS_LEXICON, shape_for_tts, spell_numerals


def test_a1_km_per_hour_lexicon():
    assert _SEED_TTS_LEXICON.get("كم/س") == "كيلومتر بالساعة"
    assert "كيلومتر بالساعة" in shape_for_tts("السرعة 120 كم/س")


def test_a1_bal3man_lexicon():
    assert _SEED_TTS_LEXICON.get("بالعمان") == "بعمان"
    assert shape_for_tts("أنا بالعمان") == "أنا بعمان"


def test_a1_ci_unrushed_letters():
    assert _SEED_TTS_LEXICON.get("CI") == "سي آي"
    assert shape_for_tts("خدمة CI") == "خدمة سي آي"


def test_a2_symbols_stripped_no_double():
    out = shape_for_tts("الكود = 404")
    for sym in ("=", ">", "<", "|", "`"):
        assert sym not in out
    assert out.count("الكود") == 1
    assert "404" not in out and "4" not in out  # digits spelled, never leak


def test_a2_symbols_all_stripped():
    out = shape_for_tts("a > b < c | d `e`")
    for sym in ("=", ">", "<", "|", "`"):
        assert sym not in out


def test_a3_clock_15_43():
    assert spell_numerals("15:43") == "تلاتة وتلاتة وأربعين العصر"


def test_a3_clock_19_32():
    assert spell_numerals("19:32") == "سبعة واتنين وتلاتين المسا"


def test_a3_clock_midnight_and_periods():
    assert spell_numerals("0:00") == "اتناش بالزبط بالليل"
    assert spell_numerals("09:15") == "تسعة وربع الصبح"
    assert spell_numerals("12:30") == "اتناش ونص الظهر"
    assert spell_numerals("13:45") == "واحد إلا ربع الظهر"


def test_a3_nonclock_unchanged_behavior():
    # plain integers / ratios keep old spell behavior (no period words)
    assert spell_numerals("404") == "أربعمية وأربعة"
    for w in ("الصبح", "الظهر", "العصر", "المسا", "بالليل"):
        assert w not in spell_numerals("404")
