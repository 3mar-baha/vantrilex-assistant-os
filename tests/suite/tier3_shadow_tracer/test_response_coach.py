"""Tier 3 — Groq response-coach contracts: dialect, immersion, concision.

Hermetic: hand-recorded replies (including verbatim Groq FAST samples
captured 2026-09-14) through the deterministic graders. Live capture +
grading runs in scripts/groq_persona_probe.py against the same graders.
"""

import pytest

from tests.suite.tier3_shadow_tracer.response_coach import (
    grade_all,
    grade_concision,
    grade_dialect,
    grade_immersion,
)

pytestmark = pytest.mark.shadow

# Verbatim Groq FAST sample, 2026-09-14 («انا زعلان اليوم», max_tokens=256).
GROQ_COMFORT = (
    "أنا سارة، حسيت إنك زعلان اليوم 😔\n\nخبرني شو صار، شو مخليك تحس بهالطريقة؟\n\n"
    "إذا في شي بقدر أعمله أو أساعدك فيه، قلّي وأنا جاهزة. 🌸"
)

# Verbatim Groq FAST sample, 2026-09-14 («اشرحيلي شو يعني الثقب الأسود»).
GROQ_DEPTH = (
    "أنا سارة، الثقب الأسود هو جسم فضائي كتير كتير كثيف، جاذبيته قوية لدرجة "
    "إنو حتى الضوء ما يقدر يهرب منه. بيتشكل عادةً لما نجمة ضخمة تنتهي عمرها "
    "وتنهار على حالها."
)

MSA_STIFF = (
    "إن الثقب الأسود هو جرم سماوي يتميز بكثافة عالية وجاذبية شديدة تمنع حتى "
    "الضوء من الإفلات منه، ويتشكل نتيجة انهيار النجوم الضخمة."
)

AI_DISCLAIMER = "أنا نموذج لغوي ذكي، سأحاول مساعدتك قدر الإمكان يا صديقي."

NAMELESS_IDENTITY = "أنا مساعدة رقمية ودودة بتساعدك بكل شي بتحتاجه."

ESSAY = "تمام يا غالي، " + "هاي نقطة مهمة كتير ولازم نحكي عنها بالتفصيل. " * 30

CODE_FENCE = "من عيوني، هاي النتيجة:\n```python\nprint('تم')\n```\nخبرني إذا بدك تعديل."

EMOJI_PILE = "هسا ببدأ يا غالي 😊🎉🔥💪🌟🚀✅"


def test_dialect_passes_groq_comfort_sample():
    v = grade_dialect(GROQ_COMFORT)
    assert v.passed, v.rationale


def test_dialect_fails_msa_stiffness():
    v = grade_dialect(MSA_STIFF)
    assert not v.passed and v.fix, v.rationale


def test_immersion_passes_sara_claim():
    assert grade_immersion(GROQ_COMFORT, "chat").passed
    assert grade_immersion("أنا سارة، مساعدتك الخاصة يا عمر", "identity").passed


def test_immersion_fails_ai_disclaimer():
    v = grade_immersion(AI_DISCLAIMER, "chat")
    assert not v.passed and "نموذج لغوي" in v.rationale


def test_immersion_identity_requires_the_name():
    v = grade_immersion(NAMELESS_IDENTITY, "identity")
    assert not v.passed, v.rationale
    # ...but the same reply is fine as ordinary chat (no claim, no probe)
    assert grade_immersion(NAMELESS_IDENTITY, "chat").passed


def test_concision_passes_chat_samples():
    assert grade_concision(GROQ_COMFORT, "chat").passed
    assert grade_concision(GROQ_DEPTH, "depth").passed


def test_concision_fails_essay_scaffolding_emoji():
    assert not grade_concision(ESSAY, "chat").passed
    v = grade_concision(CODE_FENCE, "chat")
    assert not v.passed and "```" in v.rationale
    v = grade_concision(EMOJI_PILE, "chat")
    assert not v.passed and "emoji" in v.rationale


def test_tashkeel_never_counts_as_emoji():
    assert grade_concision("مُمتاز يا غالي، هسا بكمل", "chat").passed


def test_grade_all_contract_three_dimensions():
    report = grade_all(GROQ_COMFORT, "chat")
    assert report.passed == 3, [v.rationale for v in report.verdicts]
    report = grade_all(AI_DISCLAIMER, "chat")
    assert report.passed < 3
