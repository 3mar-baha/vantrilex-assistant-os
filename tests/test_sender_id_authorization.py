"""Directive §1 (2026-09-04): EXECUTION AUTHORIZATION IS 100% SENDER-ID. The
owner's account (AUTHORIZED_USER_ID) has full unrestricted permissions on text
AND voice from any device/microphone — voice biometrics NEVER gate the owner's
own account into Guest Mode. The ECAPA lane remains for what it's FOR:
multi-speaker transcript labeling (diarization), and the Guest-lockdown floor
still protects against NON-owner accounts (they never even reach the handlers —
OwnerOnlyMiddleware drops them silently; the tests here pin the owner path).
"""

from __future__ import annotations

from pathlib import Path

from src.skills.voice_biometric_auth import owner_voice_gate


class _Bio:
    """Deterministic biometric stub: always 'fails' to match (worst case)."""

    last_vector: list[float] | None = None  # class attr: stays None in tests

    def __init__(self) -> None:
        self.verify_calls = 0

    async def verify(self, ogg: bytes) -> bool:
        self.verify_calls += 1
        return False  # a different mic/device — the live failure mode


async def test_owner_sender_id_never_locks_out(tmp_path: Path):
    """The owner's chat + authorized id: a FAILED biometric match is a
    transcript-labeling note, NEVER Guest Mode — full owner handling continues."""
    allowed = await owner_voice_gate(
        bio=_Bio(),
        ogg_opus=b"fake-ogg",
        chat_id=123456,
        authorized_id=123456,  # the sender IS the owner
        vault_root=tmp_path,
        enc_key="k",
    )
    assert allowed is True, "sender-id authorization must win over the mic"


async def test_biometric_failure_on_owner_is_logged_not_fatal(tmp_path: Path):
    """The unmatched print is staged for the diarization lane (Pending_Speakers
    style note), but the owner turn proceeds — labeling data, not a gate."""
    bio = _Bio()
    await owner_voice_gate(
        bio=bio,
        ogg_opus=b"fake-ogg",
        chat_id=123456,
        authorized_id=123456,
        vault_root=tmp_path,
        enc_key="k",
    )
    assert bio.verify_calls == 1  # the measurement still runs (labeling)


async def test_non_owner_id_still_locked(tmp_path: Path):
    """The sacred floor: a chat that is NOT the authorized account never gains
    owner handling through this gate (belt under the middleware's suspenders)."""
    allowed = await owner_voice_gate(
        bio=_Bio(),
        ogg_opus=b"fake-ogg",
        chat_id=999,
        authorized_id=123456,  # different account
        vault_root=tmp_path,
        enc_key="k",
    )
    assert allowed is False
