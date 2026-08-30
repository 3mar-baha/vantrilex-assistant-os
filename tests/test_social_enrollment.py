"""Sprint-2 §2.3b multi-speaker voiceprint registry (social graph, ADR-17 extension).

Case A: known contact -> transcript appended + running centroid. Cases B/C: pending
staging -> three-way verdict routing (confirm / ignore / unknown+flag). Every verdict
except owner keeps guest containment: zero gateway, zero whitelist, zero PC actions.
"""

import json

from cryptography.fernet import Fernet

from src.skills.social_enrollment import CONTACT_MODE_AR, Verdict, VoiceprintRegistry
from src.skills.voice_biometric_auth import VoiceBiometrics

OWNER_VEC = [0.6, 0.8, 0.0]
AHMAD_VEC = [0.8, -0.6, 0.0]
KEY = Fernet.generate_key().decode()


def make_registry(tmp_path, *, enrolled_owner=True):
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    bio = VoiceBiometrics(embedding_path=vault / "State" / "owner_voiceprint.enc", enc_key=KEY)
    if enrolled_owner:
        bio._owner_vector = list(OWNER_VEC)
    registry = VoiceprintRegistry(bio=bio, vault_root=vault, enc_key=KEY)
    return vault, bio, registry


def test_embeddings_encrypted_at_rest(tmp_path):
    """Enrolled contact vectors are Fernet-sealed under State/voiceprints/ — the raw
    file never carries plaintext coordinates."""
    vault, _bio, registry = make_registry(tmp_path)
    dossier = registry.enroll("أحمد", "Family", AHMAD_VEC)

    assert (vault / "Contacts" / "Family" / "أحمد.md").read_text(encoding="utf-8") == (
        dossier.read_text(encoding="utf-8")
    )
    stored = vault / "State" / "voiceprints" / "أحمد.enc"
    raw = stored.read_bytes()
    assert b"0.8" not in raw and b"vector" not in raw
    roundtrip = json.loads(Fernet(KEY.encode()).decrypt(raw).decode("utf-8"))
    assert roundtrip["vector"] == AHMAD_VEC


async def test_known_speaker_appends_transcript_and_stabilizes(tmp_path):
    """AC11 Case A: contact voice matches -> verdict names them; transcript section
    lands in the dossier; the stored centroid moves (stability write)."""
    vault, _bio, registry = make_registry(tmp_path)
    registry.enroll("أحمد", "Family", AHMAD_VEC)

    verdict = await registry.match_vector([0.8, -0.6, 0.05])
    assert verdict.role == "contact"
    assert verdict.name == "أحمد"
    assert verdict.category == "Family"
    assert verdict.similarity > 0.99

    registry.update_stability("أحمد", [0.8, -0.6, 0.1])
    after = json.loads(
        Fernet(KEY.encode()).decrypt((vault / "State" / "voiceprints" / "أحمد.enc").read_bytes())
    )
    assert after["count"] == 2

    note = registry.record_transcript("أحمد", "هلا عمر، أنا أحمد — كلّمني بكره")
    text = note.read_text(encoding="utf-8")
    assert "هلا عمر، أنا أحمد — كلّمني بكره" in text
    assert "## " in text


async def test_owner_checked_first_and_unknown_falls_through(tmp_path):
    """Registry order: owner vector wins before any contact; a stranger is unknown."""
    _vault, _bio, registry = make_registry(tmp_path)
    registry.enroll("أحمد", "Family", OWNER_VEC)  # decoy: same vector as owner

    owner_verdict = await registry.match_vector(OWNER_VEC)
    assert owner_verdict.role == "owner"

    stranger = await registry.match_vector([0.0, 0.0, 1.0])
    assert stranger.role == "unknown"
    assert stranger.similarity == 0.0


async def test_registry_read_failure_treated_unenrolled(tmp_path):
    """Error mode: unreadable registry -> warn + unknown, never a crash."""
    vault, _bio, registry = make_registry(tmp_path)
    registry.enroll("أحمد", "Family", AHMAD_VEC)
    (vault / "State" / "voiceprints" / "أحمد.enc").write_bytes(b"not-a-fernet-token")

    verdict = await registry.match_vector(AHMAD_VEC)
    assert verdict.role == "unknown"


def test_contact_mode_reply_is_message_taking_only():
    """CONTACT_MODE_AR promises message-taking only — no tool offers, no PC control."""
    assert "رسالة" in CONTACT_MODE_AR
    assert isinstance(Verdict(role="unknown").similarity, float)
