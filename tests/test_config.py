"""Sprint-1 §1.1 AC1-AC3: Settings contract (docs/specs/sprint-1.md)."""

import pytest
from pydantic import ValidationError

CRITICAL_FIELDS = (
    "omniroute_base_url",
    "omniroute_api_key",
    "fast_model",
    "medium_model",
    "heavy_model",
    "telegram_bot_token",
    "authorized_user_id",
    "vault_github_repo",
    "vault_github_token",
    "bridge_token",  # sprint-3 3.4: PC tunnel shared secret
    "bridge_server_url",  # sprint-3 3.4: core WSS endpoint
)


def test_settings_accept_all_env_example_vars(make_settings):
    """AC1: a full .env.example mirror validates; empty strings read as unset."""
    s = make_settings()
    assert s.omniroute_base_url == "http://localhost:20128/v1"
    assert s.omniroute_api_key == "sk-omniroute-local-key"
    assert s.fast_model == "google/gemma-4-31b-it:free"
    assert s.medium_model == "nex-agi/nex-n2.5-mini:free"
    assert s.heavy_model == "nex-agi/nex-n2.5-pro:free"
    assert s.heavy_escalation_model == "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"
    assert s.heavy_concurrency_threshold == 3
    assert s.heavy_escalated_chain[0] == "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"
    assert s.heavy_chain_for(2)[0] == "nex-agi/nex-n2.5-pro:free"
    assert s.heavy_chain_for(4)[0] == "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"
    assert s.heavy_chain_for(1, is_dag_swarm=True)[0] == (
        "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"
    )
    assert s.telegram_bot_token.startswith("1234567890:")
    assert s.authorized_user_id == 123456789
    assert s.voice_name == "ar-EG-SalmaNeural"
    assert s.google_oauth_client_json == "./config/google_oauth_client.json"
    assert s.google_calendar_id == "primary"
    assert s.bridge_lan_port == 8000
    assert s.tz == "Asia/Amman"
    assert s.log_level == "INFO"
    # Empty-string normalization (Guide amendment): optional vars read as None.
    assert s.telegram_api_id is None
    assert s.telegram_api_hash is None
    assert s.telegram_user_session_string is None
    assert s.vault_github_repo == "owner/vault-repo"
    assert s.vault_github_token.get_secret_value() == "your-github-fine-grained-pat"
    assert s.vault_branch == "main"
    assert s.bridge_token.get_secret_value() == "your-bridge-shared-token"


@pytest.mark.parametrize("field", CRITICAL_FIELDS)
def test_settings_fail_fast_on_missing_core_vars(make_settings, monkeypatch, field):
    """AC2: dropping any of the six critical fields raises ValidationError naming it."""
    # Hermetic seal (2026-09-13): the harness exports OMNIROUTE_API_KEY into the
    # ambient process env, which pydantic-settings would backfill past the
    # removal — scrub it so the fail-fast contract is actually exercised.
    monkeypatch.delenv(field.upper(), raising=False)
    with pytest.raises(ValidationError) as excinfo:
        make_settings(**{field: "__REMOVE__"})
    assert field in str(excinfo.value)


def test_owner_id_coerced_from_string(make_settings):
    """AC3: AUTHORIZED_USER_ID coerces from its env string form."""
    assert make_settings(authorized_user_id="987654321").authorized_user_id == 987654321


def test_voiceprint_threshold_calibrated_2026_09_03(make_settings):
    """Live-calibrated threshold (owner retest feedback, 2026-09-03): the sealed
    owner print vs the owner's own notes measures ~0.76 cosine across utterances
    (real ECAPA measurement); the TTS impostor control measures 0.11. The old
    0.75 default sat ABOVE natural intra-speaker variance — genuine owner voice
    notes scored just under it and were locked out as guests. 0.60 keeps every
    measured impostor 0.49 below while leaving the owner's voice room to vary."""
    assert make_settings().voiceprint_threshold == 0.60
