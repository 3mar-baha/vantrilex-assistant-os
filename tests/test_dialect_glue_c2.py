"""Node C2 RED-first guards: glue-guard allowlist in shape_for_tts."""

from src.dialect import shape_for_tts


def test_c2_glue_allowlist_splits():
    assert shape_for_tts("بشوف مواعيد بكراما في مواعيد") == "بشوف مواعيد بكرا ما في مواعيد"
    assert "وسهلاً هلا" in shape_for_tts("أهلاً وسهلاًهلا يا عمر")
    assert "بفحصلك عدد" in shape_for_tts("لحظة بفحصلكعدد خطواتك")
    assert "مشكلة ما" in shape_for_tts("ما في مشكلةما في مشكلة")
    assert "إنجازك واو" in shape_for_tts("مبروك إنجازكواو")


def test_c2_glue_normal_text_byte_identical():
    text = "شوف ساعتك أو موبايلك وبقولك"
    assert shape_for_tts(text) == text


def test_c2_glue_nonallowlisted_untouched():
    assert "بكتبلكأمّان" in shape_for_tts("لحظة بكتبلكأمّان من زمان")
