"""Tier 1 — expressive audio sanitizer contracts (Phase-4 Leap-4 slice). Hermetic."""

import httpx

from src.fish_voice import FishVoice
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
    assert strip_tags("تعبنا (sigh) وخلصنا") == "تعبنا وخلصنا"
    assert strip_tags("نص عادي بدون تاغات") == "نص عادي بدون تاغات"
    assert strip_tags("") == ""
    assert strip_tags("[unclosed نص") == "[unclosed نص"  # well-formed pairs only


def test_strip_tags_preserves_links_and_refs():
    # Text surface keeps structural brackets; only expressive tags go.
    assert strip_tags("شوف [[Budget]] للمصاريف") == "شوف [[Budget]] للمصاريف"
    assert strip_tags("النقطة [1] مهمة") == "النقطة [1] مهمة"
    assert strip_tags("[foo] نص") == "[foo] نص"  # unknown: voice path handles it


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


async def test_sanitizer_applied_before_wire():
    """Leap-4 voice surface: the Fish payload carries capped tags only."""

    def _handler(request: httpx.Request) -> httpx.Response:
        import json

        _handler.last = json.loads(request.content.decode())["input"]
        return httpx.Response(200, content=b"ID3fake", headers={"Content-Type": "audio/mpeg"})

    fish = FishVoice(
        model="m",
        voice_ref="r",
        api_key="k",
        transport=httpx.MockTransport(_handler),
    )
    try:
        await fish.synthesize("[laughing] أهلا [sigh] هلا [excited] تمام")
    finally:
        await fish.aclose()
    sent = _handler.last
    assert "[laughing]" in sent  # routine: first supported survives
    assert "[sigh]" not in sent and "[excited]" not in sent
    assert "أهلا" in sent

    fish2 = FishVoice(
        model="m",
        voice_ref="r",
        api_key="k",
        transport=httpx.MockTransport(_handler),
    )
    try:
        await fish2.synthesize("[laughing] أهلا", tag_mode="technical")
    finally:
        await fish2.aclose()
    assert "[" not in _handler.last  # technical: zero tags
