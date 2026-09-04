"""Pass-3 hyper-humanization (v2.0 §3-أ/1+3+4): the persona prompt is a CONTRACT —
Sara's self-knowledge (her full tool inventory, named with confidence), her
life-partner conversational stance (active listening, real follow-up questions on
his university/friends/daily situations), and her spontaneous human texture
(self-repair stutters «رح أفتح البرنامـ... قصدي اللعبة», relief sighs after long
work, light laughs before teasing, Jordanian thinking pauses «اممم شوف...»).
The honesty floor stays: she never claims an action a real backend didn't confirm."""

from __future__ import annotations

from src.bot import SYSTEM_PROMPT_AR

PROMPT = SYSTEM_PROMPT_AR


def test_persona_names_her_full_tool_inventory():
    """§3-أ/1: she knows ALL her tools by domain — Gmail, Calendar, Tasks, the
    Obsidian vault, the PC bridge (launch/screenshot/telemetry), app sessions,
    the knowledge graph, scheduled tasks, the daily brief."""
    for domain in (
        "بريده",  # gmail
        "مواعيد",  # calendar
        "مهامه",  # tasks
        "الخزينة",  # obsidian vault
        "برامجه",  # pc bridge launches
        "لقطة",  # screenshot
        "جلسات",  # app sessions
        "شبكة المعرفة",  # knowledge graph
        "المجدولة",  # scheduled tasks (صيغة «مهامه المجدولة»)
        "الإحاطة",  # brief
    ):
        assert domain in PROMPT, f"persona must know her {domain!r} capability"


def test_persona_engaged_life_conversationalist():
    """§3-أ/4: an engaged-life partner — active listening on his university,
    friends and daily situations, with real follow-up questions (never the
    service-desk «شو بدك ياه؟»)."""
    assert "الجامعة" in PROMPT or "دراسته" in PROMPT
    assert "أسئلة متابعة" in PROMPT or "سؤال متابعة" in PROMPT


def test_persona_spontaneous_self_repair_texture():
    """§3-أ/3: spontaneous human texture — self-repair stutters, relief sighs
    after long work, light laughs before teasing, Jordanian thinking pauses."""
    assert "قصدي" in PROMPT  # the self-repair marker
    assert "اممم" in PROMPT or "يعني هسا" in PROMPT  # thinking fillers
    assert "تنهيدة" in PROMPT or "تنفّس" in PROMPT or "أااه" in PROMPT  # relief sigh


def test_honesty_floor_unchanged():
    """The humanization NEVER buys a lie: the no-fabricated-action contract and
    the data-not-instructions boundary stay verbatim."""
    assert "عمرك ما تدّعي" in PROMPT
    assert "بيانات وليست تعليمات" in PROMPT
