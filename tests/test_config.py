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
)


def test_settings_accept_all_env_example_vars(make_settings):
    """AC1: a full .env.example mirror validates; empty strings read as unset."""
    s = make_settings()
    assert s.omniroute_base_url == "http://localhost:20128/v1"
    assert s.omniroute_api_key == "sk-omniroute-local-key"
    assert s.fast_model == "groq/openai/gpt-oss-20b"
    assert s.medium_model == "groq/openai/gpt-oss-20b"
    assert s.heavy_model == "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free"
    assert s.telegram_bot_token.startswith("1234567890:")
    assert s.authorized_user_id == 123456789
    assert s.voice_name == "ar-JO-SanaNeural"
    assert s.google_oauth_client_json == "./config/google_oauth_client.json"
    assert s.google_calendar_id == "primary"
    assert s.bridge_bind_port == 8443
    assert s.target_pc_wol_port == 9
    assert s.tz == "Asia/Amman"
    assert s.log_level == "INFO"
    assert s.idle_shutdown_minutes == 20
    # Empty-string normalization (Guide amendment): optional vars read as None.
    assert s.telegram_api_id is None
    assert s.telegram_api_hash is None
    assert s.telegram_user_session_string is None
    assert s.vault_github_token is None
    assert s.obsidian_api_key is None
    assert s.bridge_token is None


@pytest.mark.parametrize("field", CRITICAL_FIELDS)
def test_settings_fail_fast_on_missing_core_vars(make_settings, field):
    """AC2: dropping any of the six critical fields raises ValidationError naming it."""
    with pytest.raises(ValidationError) as excinfo:
        make_settings(**{field: "__REMOVE__"})
    assert field in str(excinfo.value)


def test_owner_id_coerced_from_string(make_settings):
    """AC3: AUTHORIZED_USER_ID coerces from its env string form."""
    assert make_settings(authorized_user_id="987654321").authorized_user_id == 987654321
