"""P6 batch 7g — voice chain + biometrics + evolution + diarization +
outreach uncovered edges: sanitizer never-raise contracts, missing-ffmpeg pin,
drain failure/tail paths, blank-audio refusal, executor embed lane, real-tensor
embed path, model-load failure, reflection malformed-reply + write-failure +
loop survival, decode/rms/segment/identify micro-matrix, calendar-dead gate,
profile gaps, verdict skips, send-failure, loop survival.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from cryptography.fernet import Fernet

from src.skills.proactive_outreach import ProactiveOutreach
from src.skills.self_evolution import SelfEvolutionWorker
from src.skills.speaker_diarization import SpeakerDiarizer, _close
from src.skills.voice_biometric_auth import VoiceBiometrics, VoiceprintError
from src.voice import (
    OpusTranscodeError,
    _drain,
    _spawn_ffmpeg,
    sanitize_tags,
    strip_external_media_links,
    strip_tags,
    transcode_mp3_to_opus,
)

AMMAN = ZoneInfo("Asia/Amman")
KEY = Fernet.generate_key().decode()


def test_sanitizers_never_raise_on_foreign_shapes():
    assert strip_external_media_links(None) is None
    assert strip_tags(5) == 5
    assert sanitize_tags(5) == 5
    assert "s3" not in strip_external_media_links("اسمعي https://s3.amazonaws.com/x.mp3 هون")


async def test_spawn_missing_ffmpeg_is_honest():
    with pytest.raises(OpusTranscodeError):
        await _spawn_ffmpeg("definitely-not-ffmpeg-xyz")


async def test_transcode_blank_refuses():
    with pytest.raises(ValueError):
        await transcode_mp3_to_opus(b"")


class _Pipe:
    def __init__(self, chunks):
        self._chunks = chunks
        self.closed = False

    async def read(self, _n=-1):
        if isinstance(self._chunks, Exception):
            raise self._chunks
        return self._chunks.pop(0) if self._chunks else b""

    def close(self):
        self.closed = True


class _Proc:
    def __init__(self, chunks, code=0, err=b""):
        self.stdout = _Pipe(chunks)
        self.stderr = _Pipe([err] if err else [])
        self.stdin = _Pipe([])
        self._code = code
        self.killed = False

    async def wait(self):
        return self._code

    def kill(self):
        self.killed = True


async def test_drain_nonzero_exit_carries_tail():
    proc = _Proc([], code=1, err=b"boom-tail")
    task = asyncio.create_task(asyncio.sleep(0))
    with pytest.raises(OpusTranscodeError, match="boom-tail"):
        async for _ in _drain(proc, task):
            pass
    assert proc.killed and task.done()


async def test_drain_generic_error_wrapped():
    proc = _Proc(RuntimeError("read exploded"))
    task = asyncio.create_task(asyncio.sleep(0))
    with pytest.raises(OpusTranscodeError, match="read exploded"):
        async for _ in _drain(proc, task):
            pass


async def test_drain_happy_yields_and_reaps():
    proc = _Proc([b"chunk1", b"chunk2"])
    task = asyncio.create_task(asyncio.sleep(0))
    seen = [chunk async for chunk in _drain(proc, task)]
    assert seen == [b"chunk1", b"chunk2"]
    assert proc.killed and proc.stdout.closed


def _bio(tmp_path):
    return VoiceBiometrics(
        embedding_path=tmp_path / "State" / "owner.enc", enc_key=KEY, executor=None
    )


async def test_embed_runs_executor_lane(monkeypatch, tmp_path):
    bio = _bio(tmp_path)
    monkeypatch.setattr(bio, "_embed_sync", lambda _ogg: [0.5, 0.5])
    assert await bio.embed(b"x") == [0.5, 0.5]


def test_embed_sync_chains_decode_then_model(monkeypatch, tmp_path):
    bio = _bio(tmp_path)
    monkeypatch.setattr(bio, "_decode_pcm", lambda _ogg: b"pcm-bytes")
    seen = {}

    def _fake_embed(pcm):
        seen["pcm"] = pcm
        return [1.0]

    monkeypatch.setattr(bio, "_embed_pcm_sync", _fake_embed)
    assert bio._embed_sync(b"ogg") == [1.0]
    assert seen["pcm"] == b"pcm-bytes"


def test_embed_pcm_sync_real_tensor_path(tmp_path):
    import torch

    bio = _bio(tmp_path)

    class _Model:
        def encode_batch(self, wav):
            assert isinstance(wav, torch.Tensor) and wav.shape == (1, 4)
            return torch.tensor([0.25, 0.5])

    bio._model = _Model()
    assert bio._embed_pcm_sync(b"\x01\x00\x02\x00\x03\x00\x04\x00") == [0.25, 0.5]


def test_model_load_failure_is_honest_voiceprint_error(monkeypatch, tmp_path):
    from speechbrain.inference.speaker import EncoderClassifier

    def _boom(*args, **kwargs):
        raise RuntimeError("no weights offline")

    monkeypatch.setattr(EncoderClassifier, "from_hparams", staticmethod(_boom))
    with pytest.raises(VoiceprintError, match="ECAPA model load failed"):
        _bio(tmp_path)._load_model()


class _EvoVault:
    def __init__(self, files=None, boom_upsert=False):
        self.files = dict(files or {})
        self.boom_upsert = boom_upsert

    async def read(self, path):
        if path not in self.files:
            raise FileNotFoundError(path)
        return self.files[path]

    async def upsert(self, path, content, *, message):
        if self.boom_upsert:
            raise OSError("vault down")
        self.files[path] = content


class _EvoBrain:
    def __init__(self, reply):
        self.reply = reply

    async def chat(self, messages, **kwargs):
        return self.reply


def _evo_worker(brain, vault):
    return SelfEvolutionWorker(
        brain=brain,
        vault=vault,
        tz=AMMAN,
        now_fn=lambda: datetime(2026, 9, 3, 23, 30, tzinfo=UTC),
    )


_EVO_FILES = {
    "Daily_Logs/2026-09-04.md": "---\n---\n**المالك:** مرحبا",
    "02_Areas/Profile/Dialect_Notes.md": "---\nnotes:\n---\n",
}


async def test_reflection_without_json_skips():
    assert (
        await _evo_worker(_EvoBrain("prose without braces"), _EvoVault(_EVO_FILES)).reflect_once()
        == 0
    )


async def test_reflection_malformed_json_skips():
    assert await _evo_worker(_EvoBrain("{oops}"), _EvoVault(_EVO_FILES)).reflect_once() == 0


async def test_reflection_vault_write_failure_skips():
    brain = _EvoBrain(
        '{"discoveries": [{"term": "شقحط", "phonetic": "ش", "context": "x", "confidence": 0.9}]}'
    )
    assert await _evo_worker(brain, _EvoVault(_EVO_FILES, boom_upsert=True)).reflect_once() == 0


async def test_evolution_loop_survives_cycle_error(monkeypatch):
    worker = _evo_worker(_EvoBrain("x"), _EvoVault())
    calls = {"n": 0}

    async def _flaky():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("transient")
        raise asyncio.CancelledError

    monkeypatch.setattr(worker, "reflect_once", _flaky)
    monkeypatch.setattr(worker, "due", lambda _now: True)
    worker._poll = 0
    with pytest.raises(asyncio.CancelledError):
        await worker.run_forever()
    assert calls["n"] == 2


def _diarizer(**kw):
    base = {"embedder": None, "transcriber": None, "owner_vector": None, "registry": None}
    base.update(kw)
    return SpeakerDiarizer(**base)


def test_decode_empty_fail_and_ok(monkeypatch):
    diar = _diarizer()
    assert diar._decode_pcm(b"") == b""
    monkeypatch.setattr(
        "src.skills.speaker_diarization.subprocess.run",
        lambda *a, **k: SimpleNamespace(returncode=1, stdout=b""),
    )
    assert diar._decode_pcm(b"junk") == b""
    monkeypatch.setattr(
        "src.skills.speaker_diarization.subprocess.run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout=b"pcm!"),
    )
    assert diar._decode_pcm(b"junk") == b"pcm!"


def test_rms_empty_and_negative():
    diar = _diarizer()
    assert diar._rms(b"") == 0.0
    assert diar._rms(bytes([0xFF, 0xFF])) == pytest.approx(1.0)
    assert diar._segments(b"") == []


def test_segments_split_on_silence():
    diar = _diarizer()
    loud = bytes([0x10, 0x27]) * (38400 // 2)
    silence = bytes(38400)
    segments = diar._segments(loud + silence + loud)
    assert len(segments) == 2
    assert segments[0][0] == loud and segments[1][1] > segments[0][2]


async def test_identify_registry_contact_and_unknown(tmp_path):
    from src.skills.social_enrollment import VoiceprintRegistry

    vault = tmp_path / "vault"
    bio = VoiceBiometrics(embedding_path=vault / "State" / "o.enc", enc_key=KEY)
    registry = VoiceprintRegistry(bio=bio, vault_root=vault, enc_key=KEY)
    registry.enroll("أحمد", "Family", [0.1, 0.9, 0.0])
    diar = _diarizer(owner_vector=None, registry=registry, match_threshold=0.60)
    assert await diar._identify([0.1, 0.9, 0.0]) == "أحمد"
    assert await diar._identify([0.0, 0.0, 1.0]) == "متحدث غير معروف"
    assert await _diarizer()._identify([1.0, 0.0]) == "متحدث غير معروف"


async def test_identify_registry_owner_verdict(tmp_path):
    from src.skills.social_enrollment import VoiceprintRegistry

    vault = tmp_path / "vault"
    bio = VoiceBiometrics(embedding_path=vault / "State" / "o.enc", enc_key=KEY)
    bio._owner_vector = [0.6, 0.8, 0.0]
    registry = VoiceprintRegistry(bio=bio, vault_root=vault, enc_key=KEY)
    diar = _diarizer(owner_vector=None, registry=registry)
    assert await diar._identify([0.6, 0.8, 0.0]) == "عمر"


def test_close_rejects_mismatched_shapes():
    assert _close([1.0], [1.0, 2.0], 0.6) is False
    assert _close([], [], 0.6) is False


class _OBrain:
    def __init__(self, reply):
        self.reply = reply
        self.calls = 0

    async def chat(self, messages, *, tier, **kwargs):
        self.calls += 1
        return self.reply


class _OBot:
    def __init__(self, boom=False):
        self.boom = boom
        self.sent: list[str] = []

    async def send_message(self, chat_id, text):
        if self.boom:
            raise RuntimeError("telegram down")
        self.sent.append(text)


class _OVault:
    def __init__(self, files=None):
        self.files = dict(files or {})

    async def read(self, path):
        if path not in self.files:
            raise FileNotFoundError(path)
        return self.files[path]


class _OSuite:
    def __init__(self, error=None):
        self.error = error

    async def list_events(self, start, end):
        if self.error is not None:
            raise self.error
        return []


def _o_settings(tmp_path):
    from src.config import Settings
    from tests.conftest import ENV_EXAMPLE

    base = {name.lower(): value for name, value in ENV_EXAMPLE.items()}
    base.setdefault("vault_enc_key", "your-fernet-key")
    return Settings(_env_file=None, **base)


def _o_engine(tmp_path, *, brain, vault_files, suite_error=None, bot=None):

    return ProactiveOutreach(
        brain=brain,
        bot=bot or _OBot(),
        chat_id=1,
        vault=_OVault(vault_files),
        suite=_OSuite(error=suite_error),
        settings=_o_settings(tmp_path),
        state_path=tmp_path / "State" / "proactive.json",
    )


_IN_WINDOW = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)
_LEDGER = {"Daily_Logs/2026-09-01.md": "---\n---\n## دردشة\n\n**المالك:** مرحبا"}


async def test_dead_calendar_degrades_to_not_busy(tmp_path):
    brain = _OBrain('{"should": false}')
    engine = _o_engine(
        tmp_path, brain=brain, vault_files=dict(_LEDGER), suite_error=RuntimeError("cal down")
    )
    assert await engine.fire_once(_IN_WINDOW) is False
    assert brain.calls == 1  # the dead calendar never blocks the verdict


async def test_missing_and_empty_profile_degrade(tmp_path):
    brain = _OBrain('{"should": false}')
    assert (
        await _o_engine(tmp_path, brain=brain, vault_files=dict(_LEDGER)).fire_once(_IN_WINDOW)
        is False
    )
    files = dict(_LEDGER)
    files["02_Areas/Profile/User_Info.md"] = "---\n---\n"
    assert await _o_engine(tmp_path, brain=brain, vault_files=files).fire_once(_IN_WINDOW) is False
    assert brain.calls == 2


async def test_malformed_and_empty_verdicts_skip(tmp_path):
    files = dict(_LEDGER)
    files["02_Areas/Profile/User_Info.md"] = "---\n---\nالمالك عمر."
    assert (
        await _o_engine(tmp_path, brain=_OBrain("{oops}"), vault_files=files).fire_once(_IN_WINDOW)
        is False
    )
    empty = _OBrain('{"should": true, "message": "   "}')
    assert await _o_engine(tmp_path, brain=empty, vault_files=files).fire_once(_IN_WINDOW) is False


async def test_send_failure_retries_next_tick(tmp_path):
    files = dict(_LEDGER)
    files["02_Areas/Profile/User_Info.md"] = "---\n---\nالمالك عمر."
    brain = _OBrain('{"should": true, "message": "هلا عمر"}')
    engine = _o_engine(tmp_path, brain=brain, vault_files=files, bot=_OBot(boom=True))
    assert await engine.fire_once(_IN_WINDOW) is False
    assert "last_sent_at" not in engine._load_state()


async def test_outreach_loop_survives_cycle_error(tmp_path, monkeypatch):

    engine = _o_engine(tmp_path, brain=_OBrain("x"), vault_files={})
    calls = {"n": 0}

    async def _flaky(_now):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("transient")
        raise asyncio.CancelledError

    monkeypatch.setattr(engine, "fire_once", _flaky)
    import src.skills.proactive_outreach as _mod

    real_sleep = asyncio.sleep
    monkeypatch.setattr(_mod.asyncio, "sleep", lambda _s: real_sleep(0))
    with pytest.raises(asyncio.CancelledError):
        await engine.run_forever()
    assert calls["n"] == 2
