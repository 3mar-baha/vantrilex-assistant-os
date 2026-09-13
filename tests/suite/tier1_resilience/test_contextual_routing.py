"""Tier 1 — contextual routing: paraphrases resolve by situational intent.

Deterministic net (no network): each phrasing must deduce the same tool —
proof the layer matches goal concepts, not rigid keyword spellings. Guards
pin the neighboring tools so enrichment never steals their traffic.
"""

import pytest

from src.cognition import deduce
from src.dispatcher import _ROUTER_PROMPT_AR, _VALID_TOOLS

CASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "volume",
        ("وطّي الصوت شوي", "ارفع الصوت", "اكتم الصوت", "حطي الصوت على النص", "علي الصوت شوي"),
    ),
    ("media", ("شغّلي أغنية", "حطي أغنية حلوة", "شغلي موسيقى", "بدي اسمع أغنية")),
    ("screen_ocr", ("اقرئيلي النص الظاهر عالشاشة", "استخرج الكود من الشاشة")),
    ("calendar", ("شو عندي مواعيد بكرا؟", "في اجتماعات اليوم؟")),
    ("list_reminders", ("شو التذكيرات المسجلة عندي؟", "فرجيني قائمة التذكيرات")),
    ("launch", ("افتحي المفكرة",)),
    ("screenshot", ("فرجيني شو طالع عالشاشة هسا",)),
    ("close", ("سكري الحاسبة",)),
)


@pytest.mark.parametrize("tool,text", [(tool, text) for tool, texts in CASES for text in texts])
def test_paraphrase_resolves_to_tool(tool, text):
    hyp = deduce(text)
    assert hyp.tool == tool, f"«{text}» -> {hyp.tool}@{hyp.confidence:.2f} ({hyp.rationale})"


def test_router_prompt_names_every_valid_tool():
    """The LLM router can only emit tools its catalog names (audit: volume/media
    verdicts of `none` traced to missing union entries)."""
    missing = [t for t in _VALID_TOOLS if t not in _ROUTER_PROMPT_AR]
    assert not missing, f"tools invisible to the router: {missing}"


def test_router_prompt_frames_situational_intent():
    """No keyword-list routing: the prompt must frame intent discovery."""
    assert "القصد الظرفي" in _ROUTER_PROMPT_AR
