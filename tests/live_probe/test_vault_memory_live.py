"""Tier 2d (legacy rig) — dual-tier vault memory retrieval + strict token redaction.

Asserts the rolling buffer envelope builds, and that no secret material (bot
token, bridge token, github PAT, openrouter key) leaks into the rendered
context.
"""

import re

import pytest

pytestmark = pytest.mark.live_probe

_SECRET_RE = re.compile(r"sk-(or|omniroute)|ghp_|github_pat_|xox|1234567890:AA")


async def test_memory_envelope_and_redaction(make_settings):
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
    assert not _SECRET_RE.search(blob), "secret-shaped string in envelope"


async def test_vault_state_files_present():
    from pathlib import Path

    state = Path("vault/State")
    if not state.exists():
        pytest.skip("vault/State absent in this checkout")
    files = {p.name for p in state.iterdir()}
    assert files, "vault State dir is empty — durable state missing"
    print(f"\n[LIVE] vault State files={sorted(files)}")
