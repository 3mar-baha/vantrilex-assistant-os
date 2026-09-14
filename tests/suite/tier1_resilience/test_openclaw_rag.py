"""Tier 1 — OpenClaw Phase-1 RAG discoverability gates. Hermetic.

The four foundational OpenClaw knowledge files must carry retrievable
frontmatter (title/aliases/tags/summary) and resolve through the exact
associative paths the live envelope uses (match_aliases + VaultIndex).
Recall bar: repository standard >= 93.3% top-3 (28/30 Leap-2 result).
"""

import shutil
from pathlib import Path

from src.associative import VaultIndex, inject, match_aliases
from src.vault import split_frontmatter

OPENCLAW_DIR = "04_Resources/Knowledge_Bases/OpenClaw"

FILES = {
    f"{OPENCLAW_DIR}/Keyboard_Shortcuts_and_Accelerators.md": [
        "اختصار",
        "نقر الماوس",
    ],
    f"{OPENCLAW_DIR}/Application_Topologies_and_Layouts.md": [
        "نافذة",
        "شريط العناوين",
    ],
    f"{OPENCLAW_DIR}/Popups_and_Interrupt_Recovery.md": [
        "بوب أب",
        "فقدان التركيز",
    ],
    f"{OPENCLAW_DIR}/Reversibility_and_Safety_Boundaries.md": [
        "أمان التحرك",
        "تأكيد بشري",
    ],
}

# Recall eval: representative owner queries -> expected doc (top-3).
QUERIES: tuple[tuple[str, str], ...] = (
    ("شو اختصار النسخ واللصق؟", "Keyboard_Shortcuts_and_Accelerators.md"),
    ("نقر الماوس أبطأ من الاختصار", "Keyboard_Shortcuts_and_Accelerators.md"),
    ("اختصارات الكروم لشريط العناوين", "Keyboard_Shortcuts_and_Accelerators.md"),
    ("افتح سجل الحافظة", "Keyboard_Shortcuts_and_Accelerators.md"),
    ("وين شريط العناوين بالنافذة؟", "Application_Topologies_and_Layouts.md"),
    ("خريطة واجهة الفيجوال", "Application_Topologies_and_Layouts.md"),
    ("معالم الواجهة قبل البكسل", "Application_Topologies_and_Layouts.md"),
    ("شريط المهام والصينية", "Application_Topologies_and_Layouts.md"),
    ("طلعلي بوب أب غريب شو أعمل؟", "Popups_and_Interrupt_Recovery.md"),
    ("فقدان التركيز أثناء المهمة", "Popups_and_Interrupt_Recovery.md"),
    ("سلم الاسترداد للحوار المفاجئ", "Popups_and_Interrupt_Recovery.md"),
    ("طلب صلاحيات UAC ظهر", "Popups_and_Interrupt_Recovery.md"),
    ("أمان التحرك قبل التنفيذ", "Reversibility_and_Safety_Boundaries.md"),
    ("هل هالخطوة بتحتاج تأكيد بشري؟", "Reversibility_and_Safety_Boundaries.md"),
    ("إغلاق تطبيق بذاكرة غير محفوظة", "Reversibility_and_Safety_Boundaries.md"),
    ("فعل ممنوع ومرفوض دائماً", "Reversibility_and_Safety_Boundaries.md"),
)

RECALL_BAR: float = 0.933


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load(rel: str):
    text = (_repo_root() / rel).read_text(encoding="utf-8")
    meta, body = split_frontmatter(text)
    return str(_repo_root() / rel), meta, body


def _seeded_vault(tmp_path: Path) -> Path:
    """Hermetic vault carrying the REAL committed OpenClaw files."""
    root = tmp_path / "vault"
    for rel in FILES:
        src = _repo_root() / rel
        dst = root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dst)
    return root


def test_frontmatter_complete():
    for rel in FILES:
        _path, meta, body = _load(rel)
        for key in ("title", "aliases", "tags", "summary"):
            assert meta.get(key), f"{rel} frontmatter missing {key!r}"
        assert isinstance(meta["aliases"], list) and len(meta["aliases"]) >= 3, rel
        assert "openclaw" in [str(t).casefold() for t in meta["tags"]], f"{rel} untagged"
        assert len(body.strip()) > 500, f"{rel} body too thin for retrieval"


def test_aliases_resolve_via_matcher():
    notes = []
    for rel in FILES:
        path, meta, _body = _load(rel)
        notes.append((path, meta))
    assert match_aliases("شو اختصار النسخ؟", notes).endswith(
        "Keyboard_Shortcuts_and_Accelerators.md"
    )
    assert match_aliases("نقر الماوس", notes).endswith("Keyboard_Shortcuts_and_Accelerators.md")
    assert match_aliases("وين النافذة وشريط العناوين؟", notes).endswith(
        "Application_Topologies_and_Layouts.md"
    )
    assert match_aliases("طلعلي بوب أب غريب", notes).endswith("Popups_and_Interrupt_Recovery.md")
    assert match_aliases("فقدان التركيز", notes).endswith("Popups_and_Interrupt_Recovery.md")
    assert match_aliases("أمان التحرك", notes).endswith("Reversibility_and_Safety_Boundaries.md")
    assert match_aliases("بحتاج تأكيد بشري؟", notes).endswith(
        "Reversibility_and_Safety_Boundaries.md"
    )


def test_alias_probes_cover_all_four_files():
    """Every probe word in FILES must hit its own file through the matcher."""
    notes = []
    for rel in FILES:
        path, meta, _body = _load(rel)
        notes.append((path, meta))
    for rel, probes in FILES.items():
        for probe in probes:
            hit = match_aliases(probe, notes)
            assert hit is not None and hit.endswith(Path(rel).name), (
                f"probe {probe!r} missed {rel} (hit={hit})"
            )


def test_vaultindex_recall_meets_repo_bar(tmp_path):
    idx = VaultIndex(_seeded_vault(tmp_path))
    assert idx.refresh_if_stale() is True
    assert idx.size == len(FILES)
    hits, misses = 0, []
    for query, expected in QUERIES:
        top3 = [s.doc.path for s in idx.query(query)]
        if any(p.endswith(expected) for p in top3):
            hits += 1
        else:
            misses.append((query, expected, top3))
    recall = hits / len(QUERIES)
    assert recall >= RECALL_BAR, f"recall {recall:.3f} ({hits}/{len(QUERIES)}); misses={misses}"


def test_inject_surfaces_openclaw_context(tmp_path):
    idx = VaultIndex(_seeded_vault(tmp_path))
    block = inject("شو اختصار النسخ واللصق بالكروم يا سارة؟", tmp_path / "vault", index=idx)
    assert "Keyboard_Shortcuts_and_Accelerators.md" in block
