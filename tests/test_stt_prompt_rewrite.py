"""STT-1 (owner 2026-09-04 evening): the faster-whisper transcription prompt
REWRITTEN for Jordanian Arabic — the live session transcribed «الآلة الحاسبة»
as «القادر الحاسبي» and dropped app names entirely, so the launch tool got
garbage it could never resolve.

The new contract (prompt-engineering for faster-whisper's initial_prompt):
- SEED sentences written as NATURAL Jordanian speech the owner actually says
  (app names + command verbs inside full sentences — the decoder biases toward
  this text's register, not MSA guessing)
- hotwords: the app-name list rides the hotwords param (exact-match bias)
- vad_filter: short notes with leading silence stop wasting decode on silence
- «تعلمي:» terms APPEND to the seed (never replace it — the live replacement
  lost the base register the moment one pair was taught)"""

from __future__ import annotations

from src.skills.voice_to_vault_transcriber import (
    _HOTWORDS,
    VoiceToVault,
    build_prompt,
)


def test_seed_prompt_is_natural_jordanian_speech():
    """The seed = full sentences in the owner's register, carrying his app
    names and command verbs (the decode-bias surface)."""
    prompt = build_prompt()
    assert "عمر" in prompt
    # app names present (the live failure: names vanished from transcripts)
    for app in ("الآلة الحاسبة", "كروم", "المفكرة", "يوتيوب"):
        assert app in prompt, f"missing app seed: {app}"
    # command verbs present (سكري/افتحي shape the imperative register)
    assert "افتحي" in prompt and "سكري" in prompt
    # within faster-whisper's practical prompt budget (~224 tokens)
    assert len(prompt) < 900


def test_hotwords_carry_the_app_names():
    """hotwords: exact-match bias list — the whitelist's colloquial names."""
    assert "الآلة الحاسبة" in _HOTWORDS
    assert "كروم" in _HOTWORDS
    assert len(_HOTWORDS) >= 10


def test_transcribe_uses_arabic_pin_beam_hotwords_vad():
    """The infer call: Arabic pinned, beam 5, the built prompt, hotwords,
    vad_filter — every live-session transcription parameter in one contract."""
    calls: dict[str, object] = {}

    class _Model:
        def transcribe(self, audio, **kw):
            calls.update(kw)
            return iter([]), object()

    import numpy as np  # noqa: F401 — module import parity

    t = VoiceToVault.__new__(VoiceToVault)
    t._whisper = _Model()
    t._taught_pairs = ()
    import numpy

    t._infer_sync(numpy.zeros(32000, dtype="<i2").tobytes())
    assert calls["language"] == "ar"
    assert calls["beam_size"] == 5
    assert calls["hotwords"] == " ".join(_HOTWORDS)
    assert calls["vad_filter"] is True
    assert "الآلة الحاسبة" in calls["initial_prompt"]


def test_teach_terms_append_never_replace():
    """«تعلمي:» pairs JOIN the seed — the base register survives every teach
    (the live bug: one taught pair wiped the whole seed)."""
    base = build_prompt()
    taught = build_prompt((("كفيك", "كفايك"),))
    assert "كفيك -> كفايك" in taught
    assert "الآلة الحاسبة" in taught  # the seed SURVIVED the teach
    assert len(taught) > len(base)
    # no teach -> plain seed
    assert build_prompt(()) == base


def test_prompt_budget_with_many_teachings():
    """A long teaching history still fits the budget — oldest teaches drop
    first (FIFO), the seed never drops."""
    many = tuple((f"كلمة{i}", f"لفظ{i}") for i in range(60))
    prompt = build_prompt(many)
    assert len(prompt) < 1200  # bounded: seed + newest teaches only
    assert "كلمة59" in prompt  # newest kept
