"""Sprint-2 §2.3 Guest Mode lockdown — SACRED FLOOR (joins test_owner_middleware
and test_whitelist_guardrail): a non-owner voice gets zero privileged effects.

§1 re-anchor (owner 2026-09-04): EXECUTION AUTHORIZATION IS 100% SENDER-ID.
The owner's account NEVER falls to Guest Mode (any device/mic — full owner
handling); the guest floor now pins the OTHER side of the boundary: a chat id
that is NOT the authorized account NEVER gains owner handling through the
voice gate — and the ECAPA lane, where it still runs, stays a labeling signal
with zero privileged side effects (no gateway, no subprocess, one staging
note, sealed vector)."""

import json
import re
import subprocess

from cryptography.fernet import Fernet

from src.skills.voice_biometric_auth import (
    VoiceBiometrics,
    owner_voice_gate,
)

OWNER_VEC = [0.6, 0.8, 0.0]
GUEST_VEC = [0.8, -0.6, 0.0]  # orthogonal -> similarity 0 -> below any threshold
KEY = Fernet.generate_key().decode()
STAMP_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{4}(-\d+)?\.json$")


class GatewaySpy:
    """Any brain call during lockdown is a sacred-floor breach."""

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def chat(self, *args, **kwargs):
        self.calls.append(("chat", args, kwargs))
        raise AssertionError("gateway called during guest lockdown")

    def stream_chat(self, *args, **kwargs):
        self.calls.append(("stream", args, kwargs))
        raise AssertionError("gateway stream called during guest lockdown")


async def test_owner_account_never_gusted_across_devices(tmp_path, monkeypatch, fake_bot):
    """§1 core: the OWNER'S OWN chat id passes the voice gate even when the
    biometric fails (different device/mic) — full owner handling, and the
    unmatched print is staged for the diarization lane."""
    bio = VoiceBiometrics(embedding_path=tmp_path / "State" / "owner_voiceprint.enc", enc_key=KEY)
    monkeypatch.setattr(bio, "_embed_note_sync", lambda ogg: list(OWNER_VEC))
    await bio.enroll(b"owner-ogg")
    # a DIFFERENT mic: embed diverges -> verify() False — the live lockout mode
    monkeypatch.setattr(bio, "_embed_pcm_sync", lambda pcm: list(GUEST_VEC))
    monkeypatch.setattr(bio, "_decode_pcm", lambda ogg: b"0" * 64000)  # decisive length

    subprocess_calls: list[object] = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess_calls.append(a))
    vault = tmp_path / "vault"
    vault.mkdir()

    verdict = await owner_voice_gate(
        bio=bio,
        ogg_opus=b"owner-new-mic-ogg",
        chat_id=123456789,  # the OWNER's account
        authorized_id=123456789,
        vault_root=vault,
        enc_key=KEY,
    )
    assert verdict is True  # §1: sender-ID wins, the owner is never the guest
    # the labeling lane got the print staged (sealed, never plaintext)
    notes = sorted((vault / "Voice_Memos" / "Pending_Speakers").glob("*.json"))
    assert len(notes) == 1
    sealed = Fernet(KEY.encode()).decrypt(
        json.loads(notes[0].read_text())["voiceprint_enc"].encode()
    )
    assert json.loads(sealed) == GUEST_VEC


async def test_non_owner_chat_still_locked(tmp_path, monkeypatch, fake_bot):
    """The OTHER side of the floor: a chat id that is NOT the authorized
    account never gains owner handling through the voice gate."""
    bio = VoiceBiometrics(embedding_path=tmp_path / "State" / "owner_voiceprint.enc", enc_key=KEY)
    monkeypatch.setattr(bio, "_embed_note_sync", lambda ogg: list(OWNER_VEC))
    await bio.enroll(b"owner-ogg")

    verdict = await owner_voice_gate(
        bio=bio,
        ogg_opus=b"some-ogg",
        chat_id=999,  # NOT the owner's account
        authorized_id=123456789,
        vault_root=tmp_path,
        enc_key=KEY,
    )
    assert verdict is False  # no owner handling for a foreign account


async def test_guest_stage_failure_never_blocks_owner(tmp_path, monkeypatch, fake_bot):
    """A dead labeling lane can never break the owner's turn (§1: the
    measurement is context, not a dependency)."""
    bio = VoiceBiometrics(embedding_path=tmp_path / "State" / "owner_voiceprint.enc", enc_key=KEY)
    monkeypatch.setattr(bio, "_embed_note_sync", lambda ogg: list(OWNER_VEC))
    await bio.enroll(b"owner-ogg")
    monkeypatch.setattr(bio, "_embed_pcm_sync", lambda pcm: list(GUEST_VEC))
    monkeypatch.setattr(bio, "_decode_pcm", lambda ogg: b"0" * 64000)
    monkeypatch.setattr(
        "src.skills.voice_biometric_auth.stage_guest_note",
        lambda *a, **k: (_ for _ in ()).throw(OSError("vault disk full")),
    )

    verdict = await owner_voice_gate(
        bio=bio,
        ogg_opus=b"owner-ogg",
        chat_id=123456789,
        authorized_id=123456789,
        vault_root=tmp_path,
        enc_key=KEY,
    )
    assert verdict is True  # the owner turn proceeds even with a dead staging lane
