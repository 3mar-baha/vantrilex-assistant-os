"""Tier 1 — vault scaffolding contracts: local boot scaffold never crashes,
never loses data, and leaves no writer facing FileNotFoundError."""

from src.vault import LOCAL_SCAFFOLD_DIRS, ensure_vault_scaffolding


def test_scaffold_creates_missing_mandatory_dirs(tmp_path):
    created = ensure_vault_scaffolding(tmp_path)
    assert "Contacts/" in created
    assert "Call_Transcripts/" in created
    assert "Studies/" in created
    for directory in LOCAL_SCAFFOLD_DIRS:
        assert (tmp_path / directory.rstrip("/")).is_dir()


def test_scaffold_is_idempotent(tmp_path):
    assert ensure_vault_scaffolding(tmp_path)
    assert ensure_vault_scaffolding(tmp_path) == []


def test_scaffold_preserves_existing_content(tmp_path):
    keep = tmp_path / "Contacts" / "keep.md"
    keep.parent.mkdir(parents=True)
    keep.write_text("precious", encoding="utf-8")
    ensure_vault_scaffolding(tmp_path)
    assert keep.read_text(encoding="utf-8") == "precious"


def test_scaffold_never_raises_on_blocked_path(tmp_path):
    (tmp_path / "Contacts").write_text("a file squatting the dir name", encoding="utf-8")
    created = ensure_vault_scaffolding(tmp_path)  # FileExistsError is OSError: skip, don't crash
    assert "Contacts/" not in created
    assert "Studies/" in created
    assert (tmp_path / "Studies").is_dir()
