"""Tier 1 — live vault RAG sync contracts (audit 2026-09-14 slice). Hermetic.

VaultIndex reads the VAULT, not the repo — 04_Resources/*.md must be
mirrored under the vault root to be indexed live. These tests lock the
mirror (idempotent, byte-accurate, never deleting) and the discoverability
of every mirrored knowledge file through the real VaultIndex.
"""

from pathlib import Path

from src.associative import VaultIndex, match_aliases
from src.vault import ensure_resources_scaffolding, split_frontmatter

REPO = Path(__file__).resolve().parents[3]
SOURCE = REPO / "04_Resources"


def _source_files() -> list[Path]:
    return sorted(
        p for p in SOURCE.rglob("*.md") if not any(part.startswith(".") for part in p.parts)
    )


def test_mirror_copies_every_knowledge_file(tmp_path):
    mirrored = ensure_resources_scaffolding(tmp_path / "vault")
    expected = sorted(p.relative_to(SOURCE).as_posix() for p in _source_files())
    assert sorted(mirrored) == expected
    for rel in expected:
        assert (tmp_path / "vault" / "04_Resources" / rel).is_file()


def test_mirror_is_idempotent_and_preserves_mtime(tmp_path):
    root = tmp_path / "vault"
    assert ensure_resources_scaffolding(root)
    target = (
        root
        / "04_Resources"
        / "Knowledge_Bases"
        / "Engineering"
        / "System_Architecture_and_Scale.md"
    )
    mtime = target.stat().st_mtime_ns
    assert ensure_resources_scaffolding(root) == []
    assert target.stat().st_mtime_ns == mtime


def test_mirror_rewrites_changed_source_only(tmp_path):
    src = tmp_path / "src"
    (src / "sub").mkdir(parents=True)
    (src / "a.md").write_text("v1", encoding="utf-8")
    (src / "sub" / "b.md").write_text("same", encoding="utf-8")
    root = tmp_path / "vault"
    assert sorted(ensure_resources_scaffolding(root, source=src)) == ["a.md", "sub/b.md"]
    (src / "a.md").write_text("v2!!", encoding="utf-8")
    assert ensure_resources_scaffolding(root, source=src) == ["a.md"]
    assert (root / "04_Resources" / "a.md").read_text(encoding="utf-8") == "v2!!"


def test_mirror_never_deletes_vault_side_files(tmp_path):
    root = tmp_path / "vault"
    keep = root / "04_Resources" / "owner-note.md"
    keep.parent.mkdir(parents=True)
    keep.write_text("owner's own note", encoding="utf-8")
    ensure_resources_scaffolding(root, source=tmp_path / "empty-src")
    assert keep.read_text(encoding="utf-8") == "owner's own note"


def test_mirror_missing_source_is_honest_empty(tmp_path):
    assert ensure_resources_scaffolding(tmp_path / "vault", source=tmp_path / "nope") == []


def test_mirrored_vault_indexes_every_kb(tmp_path):
    root = tmp_path / "vault"
    ensure_resources_scaffolding(root)
    idx = VaultIndex(root)
    assert idx.refresh_if_stale() is True
    rels = {d.path for d in idx._docs}
    for src in _source_files():
        assert f"04_Resources/{src.relative_to(SOURCE).as_posix()}" in rels


def test_mirrored_kb_recall_spot_check(tmp_path):
    root = tmp_path / "vault"
    ensure_resources_scaffolding(root)
    idx = VaultIndex(root)
    idx.refresh_if_stale()
    probes = {
        "شو اختصار النسخ؟": "Keyboard_Shortcuts_and_Accelerators.md",
        "أمان التحرك": "Reversibility_and_Safety_Boundaries.md",
        "لهجة أردنية": "JODA_Jordanian_Patterns.md",
        "معمارية الأنظمة": "System_Architecture_and_Scale.md",
        "اشرحلي فيزيا": "Physics_and_Math_Reasoning.md",
    }
    for query, expected in probes.items():
        top3 = [s.doc.path for s in idx.query(query)]
        assert any(p.endswith(expected) for p in top3), (query, top3)


NEW_KBS = {
    "04_Resources/Knowledge_Bases/Personal_Context/Omar_Executive_Profile_and_Rhythms.md": [
        "بروفايل عمر",
        "صاحب الشغل",
    ],
    "04_Resources/Dialect_Encyclopedia/Ammani_Urban_Humor_and_Banter.md": [
        "نكش مخ",
        "مزح أردني",
    ],
    "04_Resources/Knowledge_Bases/Productivity/Deep_Work_and_Attention_Sovereignty.md": [
        "شغل عميق",
        "مشتت",
    ],
    "04_Resources/Knowledge_Bases/Engineering/First_Principles_Debugging_and_Rubber_Ducking.md": [
        "ديبج",
        "علة",
    ],
}


def _load(rel: str):
    text = (REPO / rel).read_text(encoding="utf-8")
    meta, body = split_frontmatter(text)
    return str(REPO / rel), meta, body


def test_new_kb_frontmatter_and_density():
    """Step-2 contract: full frontmatter + 800-1500 words + full-text
    indexability (body within the VaultIndex per-doc cap)."""
    for rel in NEW_KBS:
        _path, meta, body = _load(rel)
        assert meta.get("title"), rel
        assert meta.get("type") == "knowledge-base", rel
        assert meta.get("summary"), rel
        assert isinstance(meta.get("aliases"), list) and len(meta["aliases"]) >= 3, rel
        assert isinstance(meta.get("tags"), list) and len(meta["tags"]) >= 3, rel
        words = len(body.split())
        assert 800 <= words <= 1500, f"{rel}: {words} words"
        assert 500 < len(body) <= 8000, f"{rel}: {len(body)} chars"


def test_new_kb_aliases_resolve_via_matcher():
    notes = []
    for rel in NEW_KBS:
        path, meta, _body = _load(rel)
        notes.append((path, meta))
    assert match_aliases("بروفايل عمر", notes).endswith("Omar_Executive_Profile_and_Rhythms.md")
    assert match_aliases("نكش مخ", notes).endswith("Ammani_Urban_Humor_and_Banter.md")
    assert match_aliases("شغل عميق", notes).endswith("Deep_Work_and_Attention_Sovereignty.md")
    assert match_aliases("ديبج", notes).endswith("First_Principles_Debugging_and_Rubber_Ducking.md")


def test_new_kb_recall_in_mirrored_vault(tmp_path):
    root = tmp_path / "vault"
    ensure_resources_scaffolding(root)
    idx = VaultIndex(root)
    idx.refresh_if_stale()
    probes = {
        "عمر مشتت اليوم وبده يركز، كيف يتصرف؟": "Deep_Work_and_Attention_Sovereignty.md",
        "بروفايل عمر": "Omar_Executive_Profile_and_Rhythms.md",
        "علة بالكود ومش عارف السبب": "First_Principles_Debugging_and_Rubber_Ducking.md",
        "نكش مخ": "Ammani_Urban_Humor_and_Banter.md",
    }
    for query, expected in probes.items():
        top3 = [s.doc.path for s in idx.query(query)]
        assert any(p.endswith(expected) for p in top3), (query, top3)


def test_joda_frontmatter_complete():
    text = (SOURCE / "Dialect_Encyclopedia" / "JODA_Jordanian_Patterns.md").read_text(
        encoding="utf-8"
    )
    meta, body = split_frontmatter(text)
    assert meta.get("title") == "JODA Jordanian Patterns"
    assert meta.get("type") == "knowledge-base"
    assert str(meta.get("date")) == "2026-09-14"  # YAML may parse to datetime.date
    assert meta.get("summary")
    assert isinstance(meta.get("aliases"), list) and len(meta["aliases"]) >= 3
    assert isinstance(meta.get("tags"), list) and len(meta["tags"]) >= 3
    assert len(body.strip()) > 500


def test_joda_resolves_via_matcher():
    text = (SOURCE / "Dialect_Encyclopedia" / "JODA_Jordanian_Patterns.md").read_text(
        encoding="utf-8"
    )
    meta, _body = split_frontmatter(text)
    notes = [("04_Resources/Dialect_Encyclopedia/JODA_Jordanian_Patterns.md", meta)]
    assert match_aliases("لهجة أردنية", notes).endswith("JODA_Jordanian_Patterns.md")
    assert match_aliases("حكي أردني", notes).endswith("JODA_Jordanian_Patterns.md")
