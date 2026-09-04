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


# --- deferred queue V-1/V-2: total-timeout + stderr drain ---------------------------


async def test_synthesis_total_timeout_raises_and_reaps(monkeypatch):
    """V-1: a hung engine must hit the ~30s wall and die honestly — never a
    silent hang eating the turn; the ffmpeg child is reaped either way."""
    import asyncio as aio
    import time as _t

    from src.voice import VoicePipeline, VoicePipelineError, _spawn_ffmpeg

    procs = []
    real_spawn = _spawn_ffmpeg

    async def _spawn_and_track(*args, **kwargs):
        proc = await real_spawn(*args, **kwargs)
        procs.append(proc)
        return proc

    monkeypatch.setattr("src.voice._spawn_ffmpeg", _spawn_and_track)

    class _HungTTS:
        def __init__(self, *args, **kwargs):
            pass  # swallow the voice/rate/pitch constructor args

        def stream(self):
            # the real edge_tts contract: stream() returns an async generator
            async def _hang():
                await aio.sleep(3600)
                yield  # unreachable — a generator that never yields

            return _hang()

    monkeypatch.setattr("edge_tts.Communicate", _HungTTS)
    t0 = _t.monotonic()
    with pytest.raises(VoicePipelineError, match="timed out"):
        # the wall is injectable: 0.5s — proves the pipeline's OWN timeout
        # fires (not the test's) without waiting 30s in CI
        await VoicePipeline(**PIPE).synthesize("جملة", timeout_s=0.5)
    elapsed = _t.monotonic() - t0
    assert elapsed < 5.0  # the pipeline's own wall fired, fast
    await aio.sleep(0.2)
    assert all(p.returncode is not None for p in procs)  # reaped
