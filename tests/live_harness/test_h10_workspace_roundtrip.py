"""H10 — Workspace roundtrip: sealed OAuth cache decrypts (skip-soft)."""

from pathlib import Path

from tests.live_harness.conftest import require_env


def test_oauth_cache_decrypts():
    key = require_env("VAULT_ENC_KEY")
    from src.google_auth import load_tokens

    tokens = load_tokens(Path("vault/State/google_token.json.enc"), enc_key=key)
    assert tokens is not None
