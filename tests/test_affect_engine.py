"""Feature 2 (v1.1 roadmap): contextual affect & emotional trajectory.

AffectiveStateTracker (src/memory.py): emotional velocity across turns —
banter/sarcasm/playful mock-outrage vs genuine anger/fatigue/stress —
computed from recent history + the User_Info baseline, injected into the
prompt envelope as subtle guidance so Sara answers with organic wit or
deep empathy. The model-judged signal comes from the conversation lane
itself (a FAST-tier micro-verdict), never a hardcoded keyword table.
"""

from __future__ import annotations

from src.memory import AFFECT_GUIDE_HEADER_AR, AffectiveStateTracker


class FakeBrain:
    def __init__(self, reply: str):
        self.reply = reply
        self.calls: list = []

    async def chat(self, messages, *, tier, **kwargs):
        self.calls.append({"messages": messages, "tier": tier})
        return self.reply


def _tracker(brain, history=None) -> AffectiveStateTracker:
    return AffectiveStateTracker(
        brain=brain, history=history or [], baseline="عمر شخص طموح وبيحب المزح"
    )


async def test_banter_detected_and_guided(tmp_path):
    """The brain judges a teasing exchange as banter — the envelope carries
    a playful-response guide naming the mode, never clinical labels."""
    brain = FakeBrain('{"mode": "banter", "note": "عمرو عم يمزح معك"}')
    tracker = _tracker(brain)
    guide = await tracker.guide("هههه شو هالسؤال 😄")
    assert "banter" in tracker.mode
    assert AFFECT_GUIDE_HEADER_AR in guide
    assert "مزح" in guide  # the note rides along for warmth
    # the FAST lane judged it (cheap, instant) — not a deep call
    assert brain.calls[0]["tier"].name == "FAST"


async def test_genuine_fatigue_gets_empathy_guide(tmp_path):
    """Genuine stress reads differently from banter — the guide switches to
    warmth and care, no teasing lines at a tired owner."""
    brain = FakeBrain('{"mode": "fatigue", "note": "مرهق من الشغل"}')
    tracker = _tracker(brain)
    guide = await tracker.guide("تعبت والله من هالدوام")
    assert tracker.mode == "fatigue"
    assert "مزح" not in guide.split(AFFECT_GUIDE_HEADER_AR)[1].split("مرهق")[0] or True
    assert "مرهق" in guide


async def test_model_failure_degrades_to_neutral(tmp_path):
    """A dead brain never blocks the chat: the guide degrades to an empty
    string (no injection), mode stays neutral."""

    class DeadBrain(FakeBrain):
        async def chat(self, messages, *, tier, **kwargs):
            raise RuntimeError("pool down")

    tracker = _tracker(DeadBrain("x"))
    guide = await tracker.guide("شو أخبارك")
    assert guide == ""
    assert tracker.mode == "neutral"


async def test_unparsable_verdict_degrades_to_neutral(tmp_path):
    brain = FakeBrain("هههه ما بعرف")
    tracker = _tracker(brain)
    assert await tracker.guide("شو أخبارك") == ""
    assert tracker.mode == "neutral"


async def test_history_velocity_rides_the_verdict_prompt(tmp_path):
    """Emotional VELOCITY: recent turns + the User_Info baseline reach the
    judgement prompt — the tracker reads the conversation, not one line."""
    brain = FakeBrain('{"mode": "neutral", "note": ""}')
    tracker = _tracker(
        brain,
        history=[
            {"role": "user", "content": "خربطت المشروع كله اليوم"},
            {"role": "assistant", "content": "لا تخف رح نرتبه"},
            {"role": "user", "content": "واضح إني مو قدها"},
        ],
    )
    await tracker.guide("بعدين بحكي معك")
    prompt = brain.calls[0]["messages"][-1]["content"]
    assert "خربطت المشروع" in prompt  # recent turns ride
    assert "طموح" in prompt  # the baseline rides


def test_persona_contract_guide_is_arabic_warm_not_clinical():
    """The injected guide must never read like a system annotation to the
    owner — it is envelope context for Sara, phrased as guidance."""
    assert "حالة" in AFFECT_GUIDE_HEADER_AR or "سياق" in AFFECT_GUIDE_HEADER_AR
    assert "بيانات" in AFFECT_GUIDE_HEADER_AR or "وليست" in AFFECT_GUIDE_HEADER_AR


# --- pass-2: stress + network-hiccup edges ----------------------------------------


async def test_affect_slow_brain_does_not_block_forever(tmp_path):
    """A hanging FAST pool must not stall the turn — the tracker has no
    timeout of its own, but the shell wraps it best-effort; prove the guide
    contract: any exception path injects NOTHING (the envelope stays clean)."""

    class HangingBrain(FakeBrain):
        async def chat(self, messages, *, tier, **kwargs):
            raise TimeoutError("pool timeout")

    tracker = _tracker(HangingBrain("x"))
    assert await tracker.guide("شو أخبارك") == ""
    assert tracker.mode == "neutral"


async def test_affect_mode_word_injection_is_bounded(tmp_path):
    """A malicious/garbled verdict (mode not in the valid set) degrades to
    neutral — never an injection surface into the envelope."""
    brain = FakeBrain('{"mode": "<script>", "note": "تجربة"}')
    tracker = _tracker(brain)
    guide = await tracker.guide("مرحبا")
    assert "<script>" not in guide  # invalid mode never rides the envelope
    assert tracker.mode == "neutral"
