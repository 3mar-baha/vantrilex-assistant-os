"""Shared fixtures: hermetic Settings factory mirroring .env.example literally.

Sprint-1 §1.1 AC1 validates Settings against exactly these contents — keep
ENV_EXAMPLE in sync with the root .env.example. Values use `your-*` placeholder
shape so the vendored pre-commit secret scanner (which whitelists `your*`)
never trips on test fixtures.
"""

import pytest

from src.config import Settings

REMOVE = "__REMOVE__"  # sentinel: factory deletes this key instead of setting it

ENV_EXAMPLE: dict[str, str] = {
    "OMNIROUTE_BASE_URL": "http://localhost:20128/v1",
    "OMNIROUTE_API_KEY": "sk-omniroute-local-key",
    "FAST_MODEL": "google/gemini-3.5-flash-lite",
    "FAST_MODEL_FALLBACKS": "meta-llama/llama-3.3-70b-instruct,nemotron-3.5-lightning",
    "MEDIUM_MODEL": "google/gemini-3.7-flash",
    "MEDIUM_MODEL_FALLBACKS": "z-ai/glm-5.3-flash",
    "HEAVY_MODEL": "nvidia/nemotron-3-ultra-550b",
    "HEAVY_MODEL_FALLBACKS": "google/gemini-3.7-flash,google/gemini-3.1-pro",
    "TELEGRAM_BOT_TOKEN": "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz",
    "AUTHORIZED_USER_ID": "123456789",
    "TELEGRAM_API_ID": "",
    "TELEGRAM_API_HASH": "",
    "TELEGRAM_USER_SESSION_STRING": "",
    "VOICE_NAME": "ar-JO-SanaNeural",
    "VOICE_RATE": "+0%",
    "VOICE_PITCH": "+0Hz",
    "VAULT_GITHUB_REPO": "owner/vault-repo",
    "VAULT_GITHUB_TOKEN": "",
    "OBSIDIAN_REST_API_URL": "https://127.0.0.1:27124",
    "OBSIDIAN_API_KEY": "",
    "GOOGLE_OAUTH_CLIENT_JSON": "./config/google_oauth_client.json",
    "GOOGLE_CALENDAR_ID": "primary",
    "GOOGLE_CLOUD_PROJECT": "",
    "BRIDGE_TOKEN": "",  # empty on purpose: AC1 proves "" normalizes to None
    "BRIDGE_SERVER_URL": "wss://your-vps-host:8443/bridge",
    "BRIDGE_BIND_PORT": "8443",
    "TARGET_PC_MAC_ADDRESS": "AA:BB:CC:DD:EE:FF",
    "TARGET_PC_IP": "192.168.1.100",
    "TARGET_PC_WOL_PORT": "9",
    "TZ": "Asia/Amman",
    "LOG_LEVEL": "INFO",
    "IDLE_SHUTDOWN_MINUTES": "20",
}


@pytest.fixture
def make_settings():
    """Build a valid Settings from the .env.example mirror; override or drop fields."""

    def _make(**overrides: str) -> Settings:
        # Lowercase keys: init kwargs collide across case under pydantic-settings'
        # case-insensitive matching (AUTHORIZED_USER_ID vs authorized_user_id).
        env = {name.lower(): value for name, value in ENV_EXAMPLE.items()}
        for name, value in overrides.items():
            if value == REMOVE:
                env.pop(name.lower(), None)
            else:
                env[name.lower()] = value
        return Settings(_env_file=None, **env)

    return _make
