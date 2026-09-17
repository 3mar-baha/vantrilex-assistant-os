"""P5.2 OverlayVault gates (master transformation plan, Phase P5.2).

Copy-on-write vault seam for harness runs: writes always land in the shadow
root, reads check shadow first then fall back to the real vault. The diary
stays pristine by construction.
"""

import time
from pathlib import Path

from tests.live_harness.overlay import OverlayVault


def _seed_real(tmp_path: Path) -> Path:
    real = tmp_path / "real"
    note = real / "Daily_Logs" / "2026-09-17.md"
    note.parent.mkdir(parents=True)
    note.write_text("# Real diary\n\nowner content here\n", encoding="utf-8")
    (real / "Studies" / "kb.md").parent.mkdir(parents=True, exist_ok=True)
    (real / "Studies" / "kb.md").write_text("# KB\n\nshared knowledge\n", encoding="utf-8")
    return real


def test_read_falls_back_to_real_vault(tmp_path):
    overlay = OverlayVault(_seed_real(tmp_path), tmp_path / "shadow")
    assert "shared knowledge" in overlay.read_text("Studies/kb.md")


def test_write_lands_in_shadow_real_untouched(tmp_path):
    real = _seed_real(tmp_path)
    overlay = OverlayVault(real, tmp_path / "shadow")
    before = (real / "Studies" / "kb.md").read_text(encoding="utf-8")
    overlay.write_text("Studies/kb.md", "harness overwrite")
    assert overlay.read_text("Studies/kb.md") == "harness overwrite"
    assert (real / "Studies" / "kb.md").read_text(encoding="utf-8") == before


def test_diary_pristine_after_harness_writes(tmp_path):
    real = _seed_real(tmp_path)
    diary = real / "Daily_Logs" / "2026-09-17.md"
    mtime_before = diary.stat().st_mtime_ns
    time.sleep(0.02)
    overlay = OverlayVault(real, tmp_path / "shadow")
    overlay.write_text("Daily_Logs/2026-09-17.md", "harness garbage must not land")
    assert diary.stat().st_mtime_ns == mtime_before
    assert "harness garbage" not in diary.read_text(encoding="utf-8")
    assert "harness garbage" in overlay.read_text("Daily_Logs/2026-09-17.md")


def test_nested_parents_created_in_shadow(tmp_path):
    overlay = OverlayVault(_seed_real(tmp_path), tmp_path / "shadow")
    out = overlay.write_text("a/b/c/note.md", "deep")
    assert out.is_file()
    assert overlay.shadowed() == ["a/b/c/note.md"]


def test_missing_everywhere_raises(tmp_path):
    overlay = OverlayVault(_seed_real(tmp_path), tmp_path / "shadow")
    try:
        overlay.read_text("Nope/missing.md")
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("expected FileNotFoundError")


def test_shadow_shadows_real_on_reread(tmp_path):
    overlay = OverlayVault(_seed_real(tmp_path), tmp_path / "shadow")
    overlay.write_text("Studies/kb.md", "v1")
    overlay.write_text("Studies/kb.md", "v2")
    assert overlay.read_text("Studies/kb.md") == "v2"
