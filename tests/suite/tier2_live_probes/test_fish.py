"""Tier 2b — Fish Audio ONLY synthesis + in-memory Ogg Opus (Edge banned)."""

import shutil
import sys

import pytest

from src.voice_policy import assert_no_edge

pytestmark = pytest.mark.live_probe


async def test_fish_synthesis_to_opus():
    assert "edge_tts" not in sys.modules, "Edge-TTS loaded in Fish-only probe"
    assert_no_edge()
    from src.config import get_settings

    try:
        settings = get_settings()
    except Exception as exc:  # noqa: BLE001 — fail-soft: settings absence is a skip
        pytest.skip(f"settings unavailable: {exc}")
    if not settings.fish_audio_ready:
        pytest.skip("Fish unconfigured — honest skip")
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg missing")

    from src.fish_voice import FishFirstVoice, FishVoice, FishVoiceError

    fish = FishVoice.from_settings(settings)
    try:
        opus = await FishFirstVoice(fish=fish).synthesize("مرحبا، تجربة صوتية قصيرة")
    except FishVoiceError as exc:
        pytest.skip(f"Fish offline/quota: {exc}")
    finally:
        await fish.aclose()
    assert opus[:4] == b"OggS", f"expected OggS, got {opus[:4]!r}"
    assert len(opus) > 1000, f"suspiciously small opus: {len(opus)}"
    print(f"\n[LIVE] fish opus bytes={len(opus)}")
