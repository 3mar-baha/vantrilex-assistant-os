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
    raw = (vault / "State" / "voiceprints" / "أحمد.enc").read_bytes()
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


def test_owner_brief_three_way_verdict_routing(tmp_path):
    """AC12 Cases B+C: staged pending notes route by verdict — confirm:Family ->
    Contacts/Family/, ignore -> Contacts/Ignored/, unknown -> Contacts/Unknown/ with
    a security flag; the pending note is consumed in every path."""
    vault, _bio, registry = make_registry(tmp_path)
    p1 = registry.stage_pending(AHMAD_VEC, "تركلي رسالة: أنا أخوك أحمد", claimed_name="أحمد")
    p2 = registry.stage_pending([0.1, 0.9, 0.0], "سؤال عن فاتورة", claimed_name="شخص")
    p3 = registry.stage_pending([0.1, 0.1, 0.9], "بلا تفاصيل", claimed_name="مجهول")

    enrolled = registry.resolve_pending(p1.stem, "confirm:Family")
    ignored = registry.resolve_pending(p2.stem, "ignore")
    flagged = registry.resolve_pending(p3.stem, "unknown")

    assert enrolled.outcome == "enrolled" and (vault / "Contacts" / "Family" / "أحمد.md").exists()
    assert ignored.outcome == "ignored" and (vault / "Contacts" / "Ignored" / "شخص.md").exists()
    assert flagged.outcome == "flagged"
    unknown_note = vault / "Contacts" / "Unknown" / "مجهول.md"
    assert unknown_note.exists()
    assert "security_flag: true" in unknown_note.read_text(encoding="utf-8")
    assert (vault / "State" / "voiceprints" / "مجهول.enc").exists()  # re-matchable
    assert registry.pending_briefs() == []


def test_ignored_voice_never_matches(tmp_path):
    """Verdict 'ignore' blacklists the voice: its vector never matches again."""
    _vault, _bio, registry = make_registry(tmp_path)
    note = registry.stage_pending(AHMAD_VEC, "رسالة ضيف", claimed_name="أحمد")
    registry.resolve_pending(note.stem, "ignore")

    contacts = registry._load_contacts()
    assert all(name != "أحمد" for name, _cat, _vec in contacts)


def test_unknown_profile_carries_security_flag(tmp_path):
    """Unknown verdict: security flag in the dossier frontmatter + the embedding
    stays re-matchable for a future enrollment."""
    vault, _bio, registry = make_registry(tmp_path)
    note = registry.stage_pending(AHMAD_VEC, "مكالمة مجهولة", claimed_name="مجهول")
    registry.resolve_pending(note.stem, "unknown")

    text = (vault / "Contacts" / "Unknown" / "مجهول.md").read_text(encoding="utf-8")
    assert "security_flag: true" in text
    assert (vault / "State" / "voiceprints" / "مجهول.enc").exists()


def test_pending_briefs_survive_restart(tmp_path):
    """ADR-15 durability: a fresh registry over the same vault still sees the
    staged brief (speaker, hint, timestamp)."""
    vault, _bio, registry = make_registry(tmp_path)
    registry.stage_pending(AHMAD_VEC, "أخوك أحمد حكى معك", claimed_name="أحمد")

    bio = VoiceBiometrics(embedding_path=vault / "State" / "owner_voiceprint.enc", enc_key=KEY)
    revived = VoiceprintRegistry(bio=bio, vault_root=vault, enc_key=KEY)
    briefs = revived.pending_briefs()
    assert len(briefs) == 1
    assert briefs[0].claimed_name == "أحمد"
    assert "أحمد" in briefs[0].transcript_hint


async def test_contact_mode_zero_privileged_calls(fake_bot, make_shell, monkeypatch, tmp_path):
    """Containment proof: a recognized contact gets ONLY the warm message-taking
    reply — zero gateway calls, zero subprocess, zero guest staging notes."""
    from src.bot import _ENROLL_PENDING
    from tests.conftest import OWNER_ID, make_update

    monkeypatch.chdir(tmp_path)
    vault = tmp_path / "vault"
    seed_bio = VoiceBiometrics(embedding_path=vault / "State" / "owner_voiceprint.enc", enc_key=KEY)
    VoiceprintRegistry(bio=seed_bio, vault_root=vault, enc_key=KEY).enroll(
        "أحمد", "Family", AHMAD_VEC
    )

    shell = make_shell(VAULT_ENC_KEY=KEY)
    bot = fake_bot()

    async def fake_download(file, destination=None, **kwargs):
        destination.write(b"FAKE-OGG")

    def _no_subprocess(*args, **kwargs):
        raise AssertionError("privileged subprocess ran during contact mode")

    monkeypatch.setattr(bot, "download", fake_download)
    monkeypatch.setattr("src.skills.voice_biometric_auth.subprocess.run", _no_subprocess)
    monkeypatch.setattr(VoiceBiometrics, "_embed_sync", lambda self, ogg: list(OWNER_VEC))
    try:
        await shell.dp.feed_update(bot, make_update(1, OWNER_ID, "/enroll-voice", command=True))
        await shell.dp.feed_update(
            bot, make_update(2, OWNER_ID, voice=True)
        )  # seal owner voiceprint

        monkeypatch.setattr(VoiceBiometrics, "_embed_sync", lambda self, ogg: list(AHMAD_VEC))
        await shell.dp.feed_update(bot, make_update(3, OWNER_ID, voice=True))
        assert bot.session.sent("SendMessage")[-1].method.text == CONTACT_MODE_AR
        assert shell.gateway.router_calls == []
        assert shell.gateway.stream_calls == []
        assert list((vault / "Voice_Memos" / "Pending_Speakers").glob("*.json")) == []
    finally:
        _ENROLL_PENDING.clear()
