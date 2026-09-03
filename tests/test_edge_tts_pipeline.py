"""Sprint-1 §1.3 AC3-AC8: in-memory invariant, settings flow, guards, failure paths."""

import asyncio
import builtins
import tempfile

import pytest

from src.config import Settings
from src.voice import MAX_TTS_CHARS, VoicePipeline, VoicePipelineError
from tests.helpers_voice import CANNED_MP3, FakeCommunicate, _script, needs_ffmpeg

PIPE = {"voice": "ar-JO-SanaNeural", "rate": "+0%", "pitch": "+0Hz"}


@pytest.fixture(autouse=True)
def _reset_fakes():
    FakeCommunicate.instances.clear()
    yield


def _settings() -> Settings:
    return Settings(
        omniroute_base_url="http://gw/v1",
        omniroute_api_key="k",
        fast_model="f",
        medium_model="m",
        heavy_model="h",
        telegram_bot_token="t",
        authorized_user_id=1,
        vault_enc_key="your-fernet-key",
    )


@needs_ffmpeg
async def test_no_disk_writes_end_to_end(monkeypatch):
    """AC3: full round-trip completes with open()/tempfile forbidden — zero disk writes."""
    monkeypatch.setattr("edge_tts.Communicate", _script([{"type": "audio", "data": CANNED_MP3}]))

    def _forbidden(*args, **kwargs):
        raise AssertionError("disk access attempted")

    monkeypatch.setattr(builtins, "open", _forbidden)
    for name in (
        "NamedTemporaryFile",
        "TemporaryFile",
        "SpooledTemporaryFile",
        "TemporaryDirectory",
        "mkstemp",
        "mkdtemp",
    ):
        monkeypatch.setattr(tempfile, name, _forbidden)
    agg = await VoicePipeline(**PIPE).synthesize("أهلاً")
    assert agg.startswith(b"OggS")


@needs_ffmpeg
async def test_voice_params_flow_from_settings(monkeypatch):
    """AC4: edge_tts.Communicate receives Settings voice/rate/pitch verbatim."""
    settings = _settings()
    cls = _script([{"type": "audio", "data": CANNED_MP3}])
    monkeypatch.setattr("edge_tts.Communicate", cls)
    pipeline = VoicePipeline(
        voice=settings.voice_name, rate=settings.voice_rate, pitch=settings.voice_pitch
    )
    await pipeline.synthesize("مرحبا")
    fake = cls.instances[-1]
    assert (fake.text, fake.voice, fake.rate, fake.pitch) == (
        "مرحبا",
        settings.voice_name,
        settings.voice_rate,
        settings.voice_pitch,
    )


async def test_blank_or_oversized_text_rejected_pre_spawn(monkeypatch):
    """AC5: blank / >MAX_TTS_CHARS rejected before any spawn attempt."""
    spawns = []

    async def _no_spawn(*args, **kwargs):
        spawns.append(args)
        raise AssertionError("ffmpeg spawned despite invalid input")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _no_spawn)
    pipeline = VoicePipeline(**PIPE)
    with pytest.raises(ValueError):
        pipeline.synthesize_stream("   ")
    with pytest.raises(ValueError):
        pipeline.synthesize_stream("x" * (MAX_TTS_CHARS + 1))
    assert spawns == []


async def test_missing_ffmpeg_raises_actionable_error():
    """AC6: absent binary -> actionable VoicePipelineError pointing at the runbook."""
    pipeline = VoicePipeline(**PIPE, ffmpeg_bin="no-such-ffmpeg-bin")
    with pytest.raises(VoicePipelineError, match="ffmpeg binary not found"):
        await pipeline.synthesize("أهلاً")


@needs_ffmpeg
async def test_synthesis_failure_cancels_and_reaps_ffmpeg(monkeypatch):
    """AC7: mid-stream synthesis failure -> VoicePipelineError, ffmpeg reaped, no orphan."""
    procs = []
    real_spawn = asyncio.create_subprocess_exec

    async def _spy(*args, **kwargs):
        proc = await real_spawn(*args, **kwargs)
        procs.append(proc)
        return proc

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _spy)

    class _Broken(FakeCommunicate):
        async def stream(self):
            yield {"type": "audio", "data": CANNED_MP3[:1500]}
            raise RuntimeError("edge-tts network down")

    monkeypatch.setattr("edge_tts.Communicate", _Broken)
    with pytest.raises(VoicePipelineError, match="edge-tts network down"):
        await VoicePipeline(**PIPE).synthesize("أهلاً")
    assert procs and procs[0].returncode is not None  # child reaped on the failure path


def _mask_ogg_volatile(buf: bytes) -> bytes:
    """Zero per-stream Ogg serial (offset+14) + page checksum (offset+22) for equality."""
    b = bytearray(buf)
    i = b.find(b"OggS")
    while i >= 0:
        b[i + 14 : i + 18] = b"\0" * 4
        b[i + 22 : i + 26] = b"\0" * 4
        i = b.find(b"OggS", i + 4)
    return bytes(b)


@needs_ffmpeg
async def test_metadata_events_skipped_only_audio_forwarded(monkeypatch):
    """AC8: WordBoundary metadata never forwarded; audio output identical with/without it."""
    meta = {"type": "WordBoundary", "offset": 1000, "duration": 200, "text": {"text": "أهلا"}}
    audio = [
        {"type": "audio", "data": CANNED_MP3[:1500]},
        {"type": "audio", "data": CANNED_MP3[1500:]},
    ]
    monkeypatch.setattr("edge_tts.Communicate", _script([meta, *audio[:1], meta, *audio[1:], meta]))
    with_meta = await VoicePipeline(**PIPE).synthesize("أهلاً")
    monkeypatch.setattr("edge_tts.Communicate", _script(list(audio)))
    without_meta = await VoicePipeline(**PIPE).synthesize("أهلاً")
    assert with_meta.startswith(b"OggS")
    assert _mask_ogg_volatile(with_meta) == _mask_ogg_volatile(without_meta)


# --- Owner directive 2026-09-02: 64k audio-mode opus + dialect TTS shaper. --------


@needs_ffmpeg
async def test_opus_encoding_is_64k_audio_mode(monkeypatch):
    """Live 2026-09-02: 24k voip mode choked every voice (owner: صوت رديء) —
    the opus encode must be 64k in 'audio' application mode, never telephony."""
    args_seen = []
    real_spawn = asyncio.create_subprocess_exec

    async def _spy(*args, **kwargs):
        args_seen.append(args)
        return await real_spawn(*args, **kwargs)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _spy)
    monkeypatch.setattr("edge_tts.Communicate", _script([{"type": "audio", "data": CANNED_MP3}]))
    await VoicePipeline(**PIPE).synthesize("أهلاً")
    args = list(args_seen[0])
    assert args[args.index("-b:a") + 1] == "64k"
    assert args[args.index("-application") + 1] == "audio"
    assert "voip" not in args


@needs_ffmpeg
async def test_synthesis_applies_dialect_shaper(monkeypatch):
    """Text reaching edge_tts is shaped: emoji stripped + seed lexicon applied."""
    cls = _script([{"type": "audio", "data": CANNED_MP3}])
    monkeypatch.setattr("edge_tts.Communicate", cls)
    await VoicePipeline(**PIPE).synthesize("هسا 👋")
    assert cls.instances[-1].text == "هسَّا"


@needs_ffmpeg
async def test_synthesis_uses_owner_learned_pronunciation(monkeypatch):
    """Remediation 2.5 (dead loop): notes resolved from the vault at pipeline
    build ride the shaper — the owner's learned pair «كفيك -> كفايك» changes
    what the engine actually synthesizes."""
    from src.dialect import DialectNote

    cls = _script([{"type": "audio", "data": CANNED_MP3}])
    monkeypatch.setattr("edge_tts.Communicate", cls)
    pipeline = VoicePipeline(
        voice="ar-JO-SanaNeural",
        rate="+0%",
        pitch="+0Hz",
        notes=[DialectNote(term="كفيك", phonetic="كفايك")],
    )
    await pipeline.synthesize("كفيك")
    assert cls.instances[-1].text == "كفايك"  # the learned pronunciation won


async def test_emoji_only_text_rejected_pre_spawn(monkeypatch):
    """Emoji-only text shapes to blank -> rejected before any spawn."""
    spawns = []

    async def _no_spawn(*args, **kwargs):
        spawns.append(args)
        raise AssertionError("spawned despite emoji-only input")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _no_spawn)
    with pytest.raises(ValueError):
        VoicePipeline(**PIPE).synthesize_stream("👋🎉")
    assert spawns == []
