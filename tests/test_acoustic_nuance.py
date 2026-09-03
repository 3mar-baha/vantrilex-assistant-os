"""Feature 3 (v1.1 roadmap): acoustic & paralinguistic nuance pipeline.

The owner's voice note carries more than words: tempo, laughter, hesitations,
pitch variance — the acoustic texture of HOW he spoke. A local extractor
(deterministic DSP: RMS energy contour + zero-crossing rate + silence gaps —
no cloud, no models) turns the note into a compact Arabic paralinguistic
block that rides the cognitive envelope, so Sara reads the tone WITH the
words. The sacred security boundary stays untouched: ECAPA-TDNN (the
biometric gate) is the ONLY authorization path; this module never sees and
never influences auth — it is pure interpretation context (DATA).
"""

from __future__ import annotations

from src.skills.acoustic_nuance import AcousticProfile, build_paralinguistic_block, extract_profile


def _pcm(frames: list[bytes]) -> bytes:
    return b"".join(frames)


def _loud(seconds: float = 1.0) -> bytes:
    # 16 kHz mono s16le; loud = alternating +/- amplitude at ~250 Hz
    import struct

    n = int(16000 * seconds)
    return struct.pack("<" + "h" * n, *[(4000 if i % 32 < 16 else -4000) for i in range(n)])


def _quiet(seconds: float = 1.0) -> bytes:
    return b"\x00" * int(16000 * 2 * seconds)


class TestExtraction:
    def test_fast_excited_speech_profile(self):
        """Loud, dense, no pauses → high energy + fast tempo + high
        activity — the paralinguistic block says so in Arabic."""
        profile = extract_profile(_loud(3.0))
        assert profile.activity > 0.8
        assert "طاقة" in build_paralinguistic_block(profile)
        assert "سريع" in build_paralinguistic_block(profile) or "حيوية" in (
            build_paralinguistic_block(profile)
        )

    def test_slow_hesitant_speech_profile(self):
        """Speech with long pauses → high pause ratio → hesitant/careful."""
        pcm = _pcm([_loud(1.0), _quiet(1.5), _loud(1.0), _quiet(1.5), _loud(1.0)])
        profile = extract_profile(pcm)
        assert profile.pause_ratio > 0.4
        block = build_paralinguistic_block(profile)
        assert "توقف" in block or "هدوء" in block

    def test_empty_audio_is_neutral(self):
        profile = extract_profile(b"")
        assert profile.activity == 0.0
        assert build_paralinguistic_block(profile) == ""

    def test_short_note_is_skipped_not_guessed(self):
        """Under ~1 s of PCM the metrics are meaningless — return an empty
        block rather than a guess (the round-3 short-clip lesson applied
        to interpretation too)."""
        assert build_paralinguistic_block(extract_profile(_loud(0.5))) == ""


class TestContract:
    def test_block_is_data_not_instructions(self):
        """The block carries the data-not-instructions boundary marker and
        guidance phrasing — never an order."""
        profile = extract_profile(_loud(2.0))
        block = build_paralinguistic_block(profile)
        assert "بيانات" in block or "مرجعية" in block

    def test_no_auth_surface_whatsoever(self):
        """The sacred boundary: the module NEVER touches verification,
        embeddings, or any auth surface — pure interpretation (AST guard)."""
        import ast
        from pathlib import Path

        source = Path("src/skills/acoustic_nuance.py").read_text(encoding="utf-8")
        banned = {"verify", "enroll", "match_vector", "request_launch", "send_cmd"}
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Attribute):
                assert node.attr not in banned, f"acoustic module must never call {node.attr}"
            if isinstance(node, ast.FunctionDef):
                assert node.name not in banned

    def test_profile_shape(self):
        profile = extract_profile(_loud(2.0))
        assert isinstance(profile, AcousticProfile)
        assert 0.0 <= profile.activity <= 1.0
        assert 0.0 <= profile.pause_ratio <= 1.0
        assert profile.duration_s > 0
