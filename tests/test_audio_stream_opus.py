"""Sprint-1 §1.3 AC1-AC2: real-ffmpeg transcode proof + first-chunk latency ordering."""

import time

import pytest

from src.voice import VoicePipeline
from tests.helpers_voice import CANNED_MP3, _script, needs_ffmpeg

PIPE = {"voice": "ar-JO-SanaNeural", "rate": "+0%", "pitch": "+0Hz"}


@pytest.fixture(autouse=True)
def _reset_fakes():
    from tests.helpers_voice import FakeCommunicate

    FakeCommunicate.instances.clear()
    yield


@needs_ffmpeg
async def test_real_ffmpeg_emits_valid_ogg_opus(monkeypatch):
    """AC1: canned MP3 -> aggregate is Telegram-native Ogg Opus (OggS + OpusHead)."""
    monkeypatch.setattr("edge_tts.Communicate", _script([{"type": "audio", "data": CANNED_MP3}]))
    agg = await VoicePipeline(**PIPE).synthesize("أهلاً يا هلا")
    assert agg.startswith(b"OggS")
    assert b"OpusHead" in agg


@needs_ffmpeg
async def test_first_chunk_arrives_before_completion(monkeypatch):
    """AC2: first encoded chunk arrives strictly before producer completion / proc.wait()."""
    half = len(CANNED_MP3) // 2
    cls = _script(
        [
            {"type": "audio", "data": CANNED_MP3[:half]},
            0.6,
            {"type": "audio", "data": CANNED_MP3[half:]},
        ]
    )
    monkeypatch.setattr("edge_tts.Communicate", cls)
    first_at = None
    arrivals = 0
    async for chunk in VoicePipeline(**PIPE).synthesize_stream("أهلاً يا هلا"):
        if first_at is None:
            first_at = time.monotonic()
        arrivals += 1
    producer = cls.instances[-1]
    assert producer.done_at is not None
    assert first_at is not None, "no encoded chunks surfaced"
    assert first_at < producer.done_at  # first chunk beat producer completion
    assert arrivals >= 2  # genuinely streamed, not one blob at EOF
