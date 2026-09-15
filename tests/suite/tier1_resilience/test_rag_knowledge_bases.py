"""Tier 1 — RAG knowledge-base index contracts (STAGE 1 mission slice). Hermetic.

Every committed knowledge/style file must carry retrievable frontmatter
(title/aliases/tags/summary) and resolve through the exact associative
aliases path the live envelope uses — unindexed knowledge is dead weight.
"""

from pathlib import Path

from src.associative import match_aliases
from src.vault import split_frontmatter

FILES = {
    "04_Resources/Knowledge_Bases/Languages/British_Conversational_English.md": [
        "british english",
        "انجليزي بريطاني",
    ],
    "04_Resources/Knowledge_Bases/STEM/Physics_and_Math_Reasoning.md": [
        "physics",
        "رياضيات",
    ],
    "04_Resources/Knowledge_Bases/Engineering/System_Architecture_and_Scale.md": [
        "architecture",
        "معمارية الأنظمة",
    ],
    "04_Resources/Style_Guides/Feminine_Grace_and_Softness.md": [
        "softness",
        "الرقة",
    ],
}


def _load(rel: str):
    root = Path(__file__).resolve().parents[3]
    text = (root / rel).read_text(encoding="utf-8")
    meta, body = split_frontmatter(text)
    return str(root / rel), meta, body


def test_frontmatter_complete():
    for rel in FILES:
        _path, meta, body = _load(rel)
        for key in ("title", "aliases", "tags", "summary"):
            assert meta.get(key), f"{rel} frontmatter missing {key!r}"
        assert isinstance(meta["aliases"], list) and len(meta["aliases"]) >= 3, rel
        assert len(body.strip()) > 500, f"{rel} body too thin for retrieval"


def test_aliases_resolve_via_matcher():
    notes = []
    for rel in FILES:
        path, meta, _body = _load(rel)
        notes.append((path, meta))
    assert match_aliases("علمني انجليزي بريطاني", notes).endswith(
        "British_Conversational_English.md"
    )
    assert match_aliases("اشرحلي فيزيا", notes).endswith("Physics_and_Math_Reasoning.md")
    assert match_aliases("معمارية الأنظمة", notes).endswith("System_Architecture_and_Scale.md")
    assert match_aliases("الرقة والحنية", notes).endswith("Feminine_Grace_and_Softness.md")
