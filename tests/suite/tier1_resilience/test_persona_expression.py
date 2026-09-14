"""Tier 1 — intuitive feminine expression contracts (Phase-6 persona slice).

Hermetic: asserts the persona carries the EQ-intuition doctrine (not rigid
emoji rules) and that the vault style guide is RAG-discoverable through the
associative aliases matcher — the exact path the live envelope uses.
"""

from pathlib import Path

from src.associative import match_aliases
from src.persona import SARA_PERSONA_AR
from src.vault import split_frontmatter

GUIDE_REL = Path("04_Resources/Style_Guides/Expressive_Feminine_Presence.md")


def _guide_meta():
    root = Path(__file__).resolve().parents[3]
    text = (root / GUIDE_REL).read_text(encoding="utf-8")
    meta, _body = split_frontmatter(text)
    return str(root / GUIDE_REL), meta


def test_intuition_doctrine_present():
    assert "استقلالية معرفية" in SARA_PERSONA_AR
    assert "مونولوجك الداخلي" in SARA_PERSONA_AR


def test_emoji_hygiene_cap():
    # Owner order 2026-09-14: free choice of WHICH emoji (intuition doctrine
    # stands), but a hard ceiling of 6 per response (calibration found pileups).
    assert "٦ إيموجي كحد أقصى بالرد الواحد" in SARA_PERSONA_AR
    assert "واحدة أو اثنتين" not in SARA_PERSONA_AR
    assert "واحده أو تنتين" not in SARA_PERSONA_AR


def test_guide_frontmatter_shape():
    _path, meta = _guide_meta()
    assert meta.get("title") == "Expressive Feminine Presence"
    assert "emojis" in meta.get("aliases", [])
    assert "ايموجي" in meta.get("aliases", [])
    assert "persona" in meta.get("tags", [])


def test_guide_discoverable_via_aliases():
    path, meta = _guide_meta()
    assert match_aliases("شو الايموجي المناسب؟", [(path, meta)]) == path
    assert match_aliases("emojis", [(path, meta)]) == path
    assert match_aliases("تعبيرات الشات الحلوة", [(path, meta)]) == path


def test_guide_teaches_fluidity_not_rules():
    _path, _meta = _guide_meta()
    root = Path(__file__).resolve().parents[3]
    body = (root / GUIDE_REL).read_text(encoding="utf-8")
    assert "fluid" in body.lower() or "الطريقة" in body or "doctrine" in body.lower()
    assert "✨💅" in body  # showcase chains survive as examples
