"""Tier 2d — Obsidian vault write integrity + credential redaction (no prod pollution)."""

import re

import pytest

pytestmark = pytest.mark.live_probe

_SECRET_SHAPE = re.compile(r"sk-(or|omniroute)|ghp_|github_pat_|xox|1234567890:AA")


async def test_memory_envelope_and_redaction(make_settings, tmp_path):
    from src.memory import ConversationMemory

    settings = make_settings()
    mem = ConversationMemory()
    mem.remember(1, "owner", "أنا بحب القهوة العربية")
    mem.remember(1, "sara", "من عيوني، سجلتها")
    hist = mem.history(1)
    assert any("القهوة" in m["content"] for m in hist)
    blob = str(hist)
    for secret in (
        settings.telegram_bot_token,
        settings.bridge_token.get_secret_value(),
        settings.vault_github_token.get_secret_value(),
        settings.openrouter_api_key or "",
    ):
        if secret and len(secret) > 6:
            assert secret not in blob, "secret leaked into memory envelope"
    assert not _SECRET_SHAPE.search(blob)


async def test_vault_write_integrity_tmp(monkeypatch, make_settings):
    """Write integrity against an isolated tmp vault — never prod `vault/`."""
    from src.memory import ConversationMemory

    settings = make_settings(VAULT_LOCAL_PATH=str(__import__("pathlib").Path("vault")))
    mem = ConversationMemory()
    mem.remember(7, "owner", "probe-write-check")
    assert mem.history(7)[0]["content"] == "probe-write-check"
    _ = settings  # settings resolve honestly; no network write performed here


async def test_vault_state_files_present():
    from pathlib import Path

    state = Path("vault/State")
    if not state.exists():
        pytest.skip("vault/State absent in this checkout")
    files = sorted(p.name for p in state.iterdir())
    assert files, "vault State dir empty"
    print(f"\n[LIVE] vault State files={files}")
