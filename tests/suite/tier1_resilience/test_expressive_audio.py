"""Tier 1 — expressive audio sanitizer contracts (Phase-4 Leap-4 slice). Hermetic."""

from src.skills.expressive_audio import (
    ALLOWLIST_BRACKET,
    BLOCKLIST_BRACKET,
    is_supported_tag,
)
from src.voice import sanitize_tags, strip_tags


def test_allowlist_covers_mandated_families():
    for tag in [
        "laughing",
        "chuckling",
        "giggle",
        "snicker",  # playful/warm
        "humming",
        "hesitant",
        "pause",
        "long pause",  # pensive
        "sigh",
        "sighing",
        "exhale",
        "inhale",  # relief
        "whispering",
        "soft voice",
        "calm",  # calm/intimate
        "gasp",
        "gasping",
        "surprised",  # surprise
        "confident",
        "clears throat",
        "emphasis",  # decisive
    ]:
        assert is_supported_tag(tag), tag
    assert "laughing" in ALLOWLIST_BRACKET


def test_blocklist_absent_from_allowlist():
    assert BLOCKLIST_BRACKET.isdisjoint(ALLOWLIST_BRACKET)
    for tag in ["shouting", "screaming", "crying", "sobbing", "crowd laughing", "angry"]:
        assert not is_supported_tag(tag), tag


def test_is_supported_tag_shape():
    assert not is_supported_tag("")
    assert not is_supported_tag("   ")
    assert is_supported_tag("Laughing")  # case-insensitive
    assert is_supported_tag("  sigh  ")
    assert not is_supported_tag("not-a-real-tag")
    assert is_supported_tag("sigh", parens=True)
    assert not is_supported_tag("audience laughing", parens=True)


def test_strip_tags_cleans_bubbles():
    assert strip_tags("[laughing] هههه يا زلمة") == "هههه يا زلمة"
    assert strip_tags("تعبنا (sigh) وخلصنا") == "تعبنا  وخلصنا".replace("  ", " ")
    assert strip_tags("نص عادي بدون تاغات") == "نص عادي بدون تاغات"
    assert strip_tags("") == ""
    assert strip_tags("[unclosed نص") == "[unclosed نص"  # well-formed pairs only


def test_sanitize_technical_strips_all():
    text = "[laughing] مرحبا [sigh] كيفك"
    assert sanitize_tags(text, mode="technical") == strip_tags(text)
    assert "[" not in sanitize_tags(text, mode="technical")


def test_sanitize_routine_keeps_first_supported_only():
    out = sanitize_tags("[laughing] أهلا [sigh] هلا [shouting] لا", mode="routine")
    assert "[laughing]" in out
    assert "[sigh]" not in out  # over cap
    assert "[shouting]" not in out  # not inventoried
    assert "أهلا" in out and "هلا" in out and "لا" in out  # prose survives


def test_sanitize_extended_keeps_two():
    out = sanitize_tags("[excited] فزنا [laughing] حلو [sigh] تمام", mode="extended")
    assert "[excited]" in out and "[laughing]" in out
    assert "[sigh]" not in out
    assert "فزنا" in out


def test_sanitize_unknown_mode_degrades_to_routine():
    out = sanitize_tags("[laughing] أ [sigh] ب", mode="weird")
    assert "[laughing]" in out and "[sigh]" not in out


def test_sanitize_parens_gated():
    out = sanitize_tags("تعبنا (sigh) وخلصنا", mode="routine")
    assert "(sigh)" in out  # calibration GO
    out2 = sanitize_tags("هلا (audience laughing) تمام", mode="extended")
    assert "(audience laughing)" not in out2
    assert "هلا" in out2 and "تمام" in out2
