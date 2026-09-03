"""Sprint-2 §2.3 voice biometrics — AC7 mapped tests (spec is the contract)."""

from time import perf_counter

import pytest
from cryptography.fernet import Fernet

from src.skills.voice_biometric_auth import VoiceBiometrics

OWNER_VEC = [0.6, 0.8, 0.0]
GUEST_VEC = [0.8, -0.6, 0.0]  # orthogonal to the owner vector -> similarity 0
KEY = Fernet.generate_key().decode()


def make_bio(tmp_path, *, threshold: float = 0.75, enc_key: str = KEY) -> VoiceBiometrics:
    return VoiceBiometrics(
        embedding_path=tmp_path / "State" / "owner_voiceprint.enc",
        threshold=threshold,
        enc_key=enc_key,
    )


def patch_embed(monkeypatch, bio: VoiceBiometrics, vector: list[float]) -> None:
    monkeypatch.setattr(bio, "_embed_pcm_sync", lambda pcm: list(vector))
    # round-3: verify() decodes PCM first (the short-clip floor) — the double
    # serves a decisive-length PCM so the flow reaches the embedding.
    monkeypatch.setattr(
        bio,
        "_decode_pcm",
        lambda ogg: b"\x00" * 64000,  # 2 s of 16 kHz s16le mono
    )


async def test_unenrolled_falls_back_to_middleware_trust(tmp_path):
    bio = make_bio(tmp_path)
    assert bio.enrolled is False
    assert await bio.verify(b"ogg-opus-bytes") is True


async def test_below_threshold_routes_guest(tmp_path, monkeypatch):
    bio = make_bio(tmp_path)
    patch_embed(monkeypatch, bio, OWNER_VEC)
    await bio.enroll(b"owner-ogg")
    patch_embed(monkeypatch, bio, GUEST_VEC)
    assert await bio.verify(b"guest-ogg") is False
    assert bio.last_similarity == 0.0


async def test_short_clip_is_inconclusive_never_locks_owner_out(tmp_path, monkeypatch):
    """Live round-3 2026-09-03 22:58: the owner's own ~2s note scored 0.388
    (his genuine band: 0.67-0.72) and locked him out as a guest. A clip too
    short for a decisive embedding proceeds on middleware trust — the
    Telegram-ID gate is the security boundary; a real guest speaking longer
    is still caught."""
    from src.skills.voice_biometric_auth import _MIN_DECISIVE_PCM_BYTES

    bio = make_bio(tmp_path)
    patch_embed(monkeypatch, bio, OWNER_VEC)
    await bio.enroll(b"owner-ogg")
    patch_embed(monkeypatch, bio, GUEST_VEC)  # would fail decisively if embedded
    # a decoded PCM shorter than the decisive floor → inconclusive → trust
    monkeypatch.setattr(bio, "_decode_pcm", lambda ogg: b"\x00" * (_MIN_DECISIVE_PCM_BYTES - 1))
    assert await bio.verify(b"short-ogg") is True
    assert bio.last_similarity == 0.0  # never embedded, never judged


async def test_reenroll_blends_running_centroid(tmp_path, monkeypatch):
    """Round-3 protocol: every genuine re-enroll BLENDS with the print (running
    centroid) — short real notes strengthen the print instead of replacing it."""
    import json as _json

    bio = make_bio(tmp_path)
    v1 = [1.0, 0.0]
    v2 = [0.0, 1.0]
    patch_embed(monkeypatch, bio, v1)
    await bio.enroll(b"note-1")
    patch_embed(monkeypatch, bio, v2)
    await bio.enroll(b"note-2")
    from cryptography.fernet import Fernet as _F

    sealed = bio._embedding_path.read_bytes()
    payload = _json.loads(_F(KEY.encode()).decrypt(sealed))
    # centroid of [1,0] and [0,1] = [0.5, 0.5]
    assert payload["vector"] == pytest.approx([0.5, 0.5])


async def test_owner_match_latency_under_50ms(tmp_path, monkeypatch):
    bio = make_bio(tmp_path)
    patch_embed(monkeypatch, bio, OWNER_VEC)
    await bio.enroll(b"owner-ogg")
    raw = bio._embedding_path.read_bytes()
    assert b"vector" not in raw and b"0.6" not in raw  # sealed at rest, never plaintext
    patch_embed(monkeypatch, bio, list(OWNER_VEC))
    started = perf_counter()
    verdict = await bio.verify(b"owner-ogg")
    elapsed = perf_counter() - started
    assert verdict is True
    assert elapsed < 0.05
    assert bio.last_similarity == pytest.approx(1.0)


async def test_corrupt_embedding_treated_unenrolled(tmp_path):
    path = tmp_path / "State" / "owner_voiceprint.enc"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"definitely-not-a-fernet-token")
    bio = make_bio(tmp_path)
    assert bio.enrolled is False
    assert await bio.verify(b"ogg") is True


def test_decode_pcm_real_ffmpeg_contract(tmp_path):
    """Integration guard: a real Ogg Opus file decodes to non-empty 16 kHz mono
    s16le PCM (the in-memory ffmpeg contract _embed_sync depends on)."""
    import subprocess

    bio = make_bio(tmp_path)
    ogg = tmp_path / "sample.ogg"
    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=0.3",
            "-c:a",
            "libopus",
            "-b:a",
            "16k",
            str(ogg),
        ],
        check=True,
        capture_output=True,
    )
    pcm = bio._decode_pcm(ogg.read_bytes())
    assert len(pcm) > 0 and len(pcm) % 2 == 0
