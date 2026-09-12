"""Tier 2b — Fish Audio live synthesis + in-memory Ogg Opus.

Strictly Fish (zero Edge-TTS footprint in this probe): asserts no edge_tts
import on the probe path, synthesizes via FishVoice, transcodes MP3->Opus
in memory. Skips soft when the Fish key is unconfigured or offline.
"""

import shutil

import pytest

pytestmark = pytest.mark.live_probe


async def test_fish_synthesis_to_opus():
    from src.config import get_settings

    try:
        settings = get_settings()
    except Exception as exc:  # noqa: BLE001 — fail-soft: settings absence is a skip
        pytest.skip(f"settings unavailable: {exc}")
    import sys

    assert "edge_tts" not in sys.modules, "probe must not touch Edge-TTS"
    if not settings.fish_audio_ready:
        pytest.skip("Fish unconfigured (no OPENROUTER_API_KEY) — honest skip")
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg missing — opus transcode needs it")

    from src.fish_voice import FishFirstVoice, FishVoice, FishVoiceError

    fish = FishVoice.from_settings(settings)
    lane = FishFirstVoice(fish=fish)
    try:
        opus = await lane.synthesize("مرحبا، هاي تجربة صوتية قصيرة")
    except FishVoiceError as exc:
        pytest.skip(f"Fish offline/quota: {exc}")
    finally:
        await fish.aclose()
    assert opus[:4] == b"OggS", f"expected OggS header, got {opus[:4]!r}"
    assert len(opus) > 1000, f"suspiciously small opus: {len(opus)} bytes"
    print(f"\n[LIVE] fish opus bytes={len(opus)}")
