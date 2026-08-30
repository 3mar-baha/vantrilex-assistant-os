"""Sprint-2 §2.3 Guest Mode lockdown — SACRED FLOOR (joins test_owner_middleware
and test_whitelist_guardrail): a non-owner voice gets zero privileged effects."""

import json
import re
import subprocess

from cryptography.fernet import Fernet

from src.skills.voice_biometric_auth import (
    GUEST_LOCKDOWN_AR,
    GUEST_TRANSCRIPT_PLACEHOLDER,
    VoiceBiometrics,
    verify_or_lockdown,
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


async def test_guest_voice_note_lockdown_zero_privileged_effects(tmp_path, monkeypatch, fake_bot):
    bio = VoiceBiometrics(embedding_path=tmp_path / "State" / "owner_voiceprint.enc", enc_key=KEY)
    monkeypatch.setattr(bio, "_embed_sync", lambda ogg: list(OWNER_VEC))
    await bio.enroll(b"owner-ogg")
    monkeypatch.setattr(bio, "_embed_sync", lambda ogg: list(GUEST_VEC))

    subprocess_calls: list[object] = []
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess_calls.append(a))
    gateway = GatewaySpy()
    vault = tmp_path / "vault"
    vault.mkdir()
    before = {p for p in vault.rglob("*") if p.is_file()}
    bot = fake_bot()

    verdict = await verify_or_lockdown(
        bio=bio,
        bot=bot,
        chat_id=123456789,
        ogg_opus=b"guest-ogg",
        vault_root=vault,
        enc_key=KEY,
    )

    assert verdict is False
    assert gateway.calls == []
    assert subprocess_calls == []
    # exactly one outbound Telegram call: the lockdown reply, nothing else
    assert len(bot.session.calls) == 1
    send = bot.session.sent("SendMessage")[0].method
    assert send.text == GUEST_LOCKDOWN_AR
    # exactly one staging note; embedding sealed, never plaintext
    notes = sorted((vault / "Voice_Memos" / "Pending_Speakers").glob("*.json"))
    assert len(notes) == 1
    assert STAMP_PATTERN.match(notes[0].name)
    payload = json.loads(notes[0].read_text(encoding="utf-8"))
    assert payload["transcript"] == GUEST_TRANSCRIPT_PLACEHOLDER
    sealed = Fernet(KEY.encode()).decrypt(payload["voiceprint_enc"].encode())
    assert json.loads(sealed) == GUEST_VEC
    after = {p for p in vault.rglob("*") if p.is_file()}
    assert after - before == {notes[0]}  # zero other vault writes
