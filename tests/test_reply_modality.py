"""Reply-modality contract (owner directive 2026-09-03): text/voice 70-30 mirror
+ explicit request always wins + reply-awareness (reply_to_message reaches the
brain) + media comprehension wiring (m3 image/video, Whisper audio)."""

import random

import pytest

from src.skills.reply_modality import choose_reply_modality, forced_modality

# --- explicit request always wins ------------------------------------------------


@pytest.mark.parametrize(
    "text,expected",
    [
        ("رد صوتي", "voice"),
        ("ردّ بصوتك", "voice"),
        ("جاوبيني بصوت", "voice"),
        ("الرد صوتي", "voice"),
        ("ابعثي رسالة صوتية", "voice"),  # live 2026-09-03 07:03 — explicit ask
        ("ابعتلي ملاحظة صوتية بتعرفي عن حالك", "voice"),
        ("رسالة صوتية", "voice"),
        ("رد نصي", "text"),
        ("ردّ كتابي", "text"),
        ("اكتبيلي الجواب", "text"),
        ("مرحبا", None),  # no request -> chooser decides
        ("", None),
    ],
)
def test_forced_modality(text, expected):
    assert forced_modality(text) == expected


def test_explicit_text_beats_voice_when_both_present():
    """«رد نصي مش صوتي» — the text request is the operative one."""
    assert forced_modality("رد نصي مش صوتي") == "text"


# --- 70/30 mirror ---------------------------------------------------------------


def test_mirror_70_30_text_origin():
    """Owner text -> 70% text / 30% voice."""
    assert choose_reply_modality(voice_origin=False, rng=lambda: 0.0) == "text"
    assert choose_reply_modality(voice_origin=False, rng=lambda: 0.69) == "text"
    assert choose_reply_modality(voice_origin=False, rng=lambda: 0.71) == "voice"


def test_mirror_70_30_flipped_for_voice_origin():
    """Owner voice -> the ratio flips: 70% voice / 30% text."""
    assert choose_reply_modality(voice_origin=True, rng=lambda: 0.69) == "voice"
    assert choose_reply_modality(voice_origin=True, rng=lambda: 0.71) == "text"


def test_statistical_split_near_70_30():
    """Over a large sample the split converges near the 70/30 target."""
    random.seed(2026)
    text_origin = [choose_reply_modality(voice_origin=False) for _ in range(20_000)]
    voice_ratio = text_origin.count("voice") / len(text_origin)
    assert 0.27 < voice_ratio < 0.33


def test_exactly_one_surface_always():
    """The chooser returns exactly one modality — never both, never none."""
    for roll in (0.0, 0.35, 0.5, 0.69, 0.70, 0.99):
        for origin in (True, False):
            result = choose_reply_modality(voice_origin=origin, rng=lambda r=roll: r)
            assert result in ("text", "voice")
