"""Tier 1 — intent-gated RAG injection (durability 2026-09-14 slice). Hermetic.

Routine device turns spend ZERO memory tokens; advisory turns carry the
Tier-1 digest + top-k; intent=None preserves the legacy path.
"""

from src.associative import (
    DIGEST_HEADER_AR,
    ROUTINE_INTENTS,
    VaultIndex,
    inject,
    intent_for,
    load_digest_block,
)


def _seeded_vault(tmp_path):
    root = tmp_path / "vault"
    digest_dir = root / "02_Areas" / "Profile"
    digest_dir.mkdir(parents=True)
    (digest_dir / "Omar_Master_Digest.md").write_text(
        "---\ntitle: Digest\n---\nنبض اليوم: عمر مشغول بالبناء.",
        encoding="utf-8",
    )
    note_dir = root / "Studies"
    note_dir.mkdir(parents=True)
    (note_dir / "deep.md").write_text("مذكرة عن الشغل العميق والتركيز", encoding="utf-8")
    idx = VaultIndex(root)
    idx.refresh_if_stale()
    return root, idx


def test_routine_intents_spend_zero_tokens(tmp_path):
    root, idx = _seeded_vault(tmp_path)
    assert ROUTINE_INTENTS  # the set is the contract surface
    for intent in sorted(ROUTINE_INTENTS):
        assert inject("شو وضع الجهاز والرام والمعالج هسا؟", root, index=idx, intent=intent) == ""


def test_advisory_carries_digest_plus_topk(tmp_path):
    root, idx = _seeded_vault(tmp_path)
    block = inject("شو أخبار الشغل العميق والتركيز؟", root, index=idx, intent="direct")
    assert DIGEST_HEADER_AR in block
    assert "نبض اليوم" in block
    assert "deep.md" in block


def test_legacy_none_intent_has_no_digest(tmp_path):
    root, idx = _seeded_vault(tmp_path)
    block = inject("شو أخبار الشغل العميق والتركيز؟", root, index=idx)
    assert DIGEST_HEADER_AR not in block
    assert "deep.md" in block


def test_missing_digest_degrades_to_topk_only(tmp_path):
    root = tmp_path / "vault"
    (root / "Studies").mkdir(parents=True)
    (root / "Studies" / "deep.md").write_text("مذكرة عن الشغل العميق", encoding="utf-8")
    idx = VaultIndex(root)
    idx.refresh_if_stale()
    block = inject("شو أخبار الشغل العميق؟", root, index=idx, intent="direct")
    assert DIGEST_HEADER_AR not in block
    assert "deep.md" in block


def test_load_digest_block_shapes_and_misses(tmp_path):
    assert load_digest_block(tmp_path) == ""
    seeded, _idx = _seeded_vault(tmp_path)
    block = load_digest_block(seeded)
    assert block.startswith(DIGEST_HEADER_AR)
    assert "---" not in block  # frontmatter stripped


def test_intent_for_maps_and_falls_back():
    assert intent_for("شو الطقس بعمان؟") in ("weather", "direct")
    assert intent_for("مرحبا") == "direct"
    assert intent_for("") == "direct"


def test_intent_for_survives_deduce_crash(monkeypatch):
    import src.associative as assoc

    def _boom(text, **kw):
        raise RuntimeError("deduce down")

    monkeypatch.setattr("src.cognition.deduce", _boom)
    assert assoc.intent_for("شو الطقس؟") == "direct"
