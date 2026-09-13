"""Tier 1 — associative recall eval (Phase-2 Leap-2 slice). Hermetic tmp vaults.

30 hand-labeled message→note pairs over a synthetic vault mirroring the real
layout (Contacts/Projects/Studies/Daily/Finance/Health/Resources). Bars:
recall ≥80% top-3, p95 <40ms on a 500-note vault, injection block shaped.
"""

import time
from pathlib import Path

from src.associative import (
    INJECT_MAX_CHARS,
    VaultIndex,
    inject,
)

NOTES: tuple[tuple[str, dict, str], ...] = (
    (
        "Contacts/Family/Mother.md",
        {"aliases": ["أمي", "الوالدة"], "tags": ["عائلة"]},
        "صحة الوالدة تحتاج متابعة، دواء الضغط كل صباح مع الفطور",
    ),
    (
        "Contacts/Friends/Karim.md",
        {"aliases": ["كريم"], "tags": ["صداقة"]},
        "كريم صاحبي من الجامعة، يحب كرة القدم ويشتغل مبرمج",
    ),
    (
        "03_Projects/Store/plan.md",
        {"aliases": ["المتجر", "المشروع"], "tags": ["مشروع", "متجر"]},
        "خطة المتجر الإلكتروني: الدفع عند الاستلام ثم التوسع للشحن",
    ),
    (
        "03_Projects/App/notes.md",
        {"aliases": ["التطبيق"], "tags": ["مشروع", "برمجة"]},
        "ملاحظات تطبيق الجوال: شاشة الدخول أولاً ثم الإشعارات",
    ),
    (
        "Studies/Arabic/grammar.md",
        {"aliases": ["النحو", "القواعد"], "tags": ["دراسة", "لغة"]},
        "قواعد النحو: الفاعل مرفوع والمفعول منصوب دائماً",
    ),
    (
        "Studies/ML/embeddings.md",
        {"aliases": ["التضمينات"], "tags": ["دراسة", "ذكاء"]},
        "التضمينات تحول الكلمات لأرقام تقيس التشابه الدلالي",
    ),
    (
        "Daily_Logs/2026-09-13.md",
        {"tags": ["يومية"], "aliases": []},
        "اليوم رحت الجيم ساعة كاملة ولعبت صدر وكتف",
    ),
    (
        "02_Areas/Finance/Budget.md",
        {"aliases": ["مصاري", "ميزانية", "budget"], "tags": ["مالية"]},
        "ميزانية الشهر: الراتب يغطي الإيجار والمصاريف الأساسية",
    ),
    (
        "02_Areas/Health/Fitness.md",
        {"aliases": ["رياضة", "جيم"], "tags": ["صحة"]},
        "برنامج الرياضة الأسبوعي: ثلاث حصص حديد وحصتين كارديو",
    ),
    (
        "04_Resources/Recipes/mansaf.md",
        {"aliases": ["منسف", "المنسف"], "tags": ["طبخ"]},
        "وصفة المنسف: لحم بلدي ولبن جميد ورز بسمتي",
    ),
    (
        "Call_Transcripts/omar-call.md",
        {"aliases": ["المكالمة"], "tags": ["مكالمة"]},
        "ملخص المكالمة مع أحمد حول موعد تسليم المشروع الخميس",
    ),
    (
        "Studies/History/petra.md",
        {"aliases": ["البتراء"], "tags": ["تاريخ", "سفر"]},
        "البتراء مدينة وردية منحوتة بالصخر ورحلة العمر",
    ),
)

QUERIES: tuple[tuple[str, str], ...] = (
    # alias hits
    ("طمنيني عن أمي ودواها", "Contacts/Family/Mother.md"),
    ("شو أخبار الوالدة الصحية؟", "Contacts/Family/Mother.md"),
    ("وين صرفنا مصاري هالشهر؟", "02_Areas/Finance/Budget.md"),
    ("ذكريني بميزانية الشهر", "02_Areas/Finance/Budget.md"),
    ("متى تمرين الجيم الجاي؟", "02_Areas/Health/Fitness.md"),
    ("شو برنامج الرياضة الأسبوعي؟", "02_Areas/Health/Fitness.md"),
    ("وين وصفة المنسف؟", "04_Resources/Recipes/mansaf.md"),
    ("كيف بعمل المنسف البلدي؟", "04_Resources/Recipes/mansaf.md"),
    ("شو وضع المتجر الإلكتروني؟", "03_Projects/Store/plan.md"),
    ("احكيلي عن خطة المشروع", "03_Projects/Store/plan.md"),
    ("وين ملاحظات التطبيق؟", "03_Projects/App/notes.md"),
    ("شو قال كريم عن الشغل؟", "Contacts/Friends/Karim.md"),
    ("راجعيلي قواعد النحو", "Studies/Arabic/grammar.md"),
    ("اشرحيلي الفاعل والمفعول", "Studies/Arabic/grammar.md"),
    ("شو هي التضمينات بالذكاء؟", "Studies/ML/embeddings.md"),
    ("كيف بتقيس التشابه الدلالي؟", "Studies/ML/embeddings.md"),
    ("شو عملت بالجيم اليوم؟", "Daily_Logs/2026-09-13.md"),
    ("لخصيلي المكالمة مع أحمد", "Call_Transcripts/omar-call.md"),
    ("متى موعد التسليم الخميس؟", "Call_Transcripts/omar-call.md"),
    ("احكيلي عن البتراء والسفر", "Studies/History/petra.md"),
    # title/body token hits (no alias crutch)
    ("دواء الضغط مع الفطور", "Contacts/Family/Mother.md"),
    ("راتبي والإيجار والمصاريف", "02_Areas/Finance/Budget.md"),
    ("تمارين الصدر والكتف", "Daily_Logs/2026-09-13.md"),
    ("الدفع عند الاستلام والشحن", "03_Projects/Store/plan.md"),
    ("شاشة الدخول والإشعارات", "03_Projects/App/notes.md"),
    ("اللبن الجميد والرز البسمتي", "04_Resources/Recipes/mansaf.md"),
    ("كرة القدم والمبرمج صاحبي", "Contacts/Friends/Karim.md"),
    ("المدينة الوردية المنحوتة بالصخر", "Studies/History/petra.md"),
    ("حصص الحديد والكارديو", "02_Areas/Health/Fitness.md"),
    ("الكلمات تتحول لأرقام", "Studies/ML/embeddings.md"),
)


def make_vault(root: Path) -> Path:
    import yaml

    for rel, meta, body in NOTES:
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        front = yaml.safe_dump(meta, allow_unicode=True, sort_keys=False) if meta else ""
        head = f"---\n{front}---\n" if meta else ""
        path.write_text(head + body + "\n", encoding="utf-8")
    (root / "State").mkdir(exist_ok=True)
    (root / "State" / "runtime.json").write_text('{"noise": "مصاري مصاري"}', encoding="utf-8")
    return root


def test_recall_at_least_80_percent(tmp_path):
    idx = VaultIndex(make_vault(tmp_path / "vault"))
    assert idx.refresh_if_stale() is True
    assert idx.size == len(NOTES)
    hits = 0
    misses = []
    for query, expected in QUERIES:
        top3 = [s.doc.path for s in idx.query(query)]
        if expected in top3:
            hits += 1
        else:
            misses.append((query, expected, top3))
    recall = hits / len(QUERIES)
    assert recall >= 0.80, f"recall {recall:.2f} ({hits}/{len(QUERIES)}); misses={misses[:5]}"


def test_mtime_invalidation(tmp_path):
    root = make_vault(tmp_path / "vault")
    idx = VaultIndex(root)
    assert idx.refresh_if_stale() is True
    assert idx.refresh_if_stale() is False  # nothing moved
    (root / "02_Areas" / "new_note_for_recall_probe.md").write_text("نص", encoding="utf-8")
    assert idx.refresh_if_stale() is True
    assert idx.size == len(NOTES) + 1


def test_state_dir_excluded(tmp_path):
    idx = VaultIndex(make_vault(tmp_path / "vault"))
    idx.refresh_if_stale()
    assert all("State" not in d.path for d in idx._docs)


def test_inject_block_shape(tmp_path):
    idx = VaultIndex(make_vault(tmp_path / "vault"))
    block = inject("وين صرفنا مصاري هالشهر يا سارة؟", tmp_path / "vault", index=idx)
    assert "02_Areas/Finance/Budget.md" in block
    assert len(block) <= INJECT_MAX_CHARS


def test_inject_degrades_to_empty(tmp_path):
    root = make_vault(tmp_path / "vault")
    assert inject("مرحبا", root) == ""  # greeting: too few tokens
    assert inject("", root) == ""
    assert inject("وين مصاري الشهر؟", tmp_path / "nope") == ""  # missing root


def test_p95_under_40ms_on_500_notes(tmp_path):
    root = tmp_path / "big"
    for i in range(500):
        path = root / f"02_Areas/note_{i:03d}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"---\ntags: [مذكرة{i}]\n---\nنص تجريبي عن الموضوع رقم {i} والمشروع\n", encoding="utf-8"
        )
    idx = VaultIndex(root)
    assert idx.refresh_if_stale() is True
    assert idx.size == 500
    latencies = []
    for i in range(50):
        t0 = time.perf_counter()
        idx.query(f"استفسار عن الموضوع رقم {i} والمشروع")
        latencies.append((time.perf_counter() - t0) * 1000)
    latencies.sort()
    p95 = latencies[int(0.95 * len(latencies)) - 1]
    assert p95 < 40.0, f"p95 {p95:.1f}ms over budget"
