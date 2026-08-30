"""Application settings: pydantic v2 validation over .env + process environment."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Sprint-1 critical: no defaults -> boot fails fast without them.
_REQUIRED_FIELDS = (
    "omniroute_base_url",
    "omniroute_api_key",
    "fast_model",
    "medium_model",
    "heavy_model",
    "telegram_bot_token",
    "authorized_user_id",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    omniroute_base_url: str  # OMNIROUTE_BASE_URL
    omniroute_api_key: str  # OMNIROUTE_API_KEY
    fast_model: str  # FAST_MODEL (tier 1, ADR-16)
    medium_model: str  # MEDIUM_MODEL (tier 2)
    heavy_model: str  # HEAVY_MODEL (tier 3)
    fast_model_fallbacks: str | None = None  # FAST_MODEL_FALLBACKS (comma-separated)
    medium_model_fallbacks: str | None = None  # MEDIUM_MODEL_FALLBACKS
    heavy_model_fallbacks: str | None = None  # HEAVY_MODEL_FALLBACKS
    telegram_bot_token: str  # TELEGRAM_BOT_TOKEN
    authorized_user_id: int  # AUTHORIZED_USER_ID (coerced from string)
    stream_edit_interval_ms: int = 750  # STREAM_EDIT_INTERVAL_MS (§2.2 coalesced edits)

    # Declared now (validates every var in .env.example); consumed by later sprints.
    # Optional fields become required in the commit whose task first consumes them.
    telegram_api_id: int | None = None
    telegram_api_hash: str | None = None
    telegram_user_session_string: str | None = None
    voice_name: str = "ar-JO-SanaNeural"
    voice_rate: str = "+0%"
    voice_pitch: str = "+0Hz"
    vault_github_repo: str | None = None
    vault_github_token: str | None = None
    obsidian_rest_api_url: str | None = None
    obsidian_api_key: str | None = None
    google_oauth_client_json: str = "./config/google_oauth_client.json"
    google_calendar_id: str = "primary"
    bridge_token: str | None = None
    bridge_server_url: str | None = None
    bridge_bind_port: int = 8443
    target_pc_mac_address: str | None = None
    target_pc_ip: str | None = None
    target_pc_wol_port: int = 9
    tz: str = "Asia/Amman"
    log_level: str = "INFO"
    idle_shutdown_minutes: int = 20

    @field_validator("*", mode="before")
    @classmethod
    def _normalize_empty_strings(cls, value, info):
        """Blank env assignments read as unset for optional fields and as missing
        for the critical ones (.env.example ships empty placeholders)."""
        if not (isinstance(value, str) and not value.strip()):
            return value
        if info.field_name in _REQUIRED_FIELDS:
            raise ValueError("must not be empty")
        return None

    @staticmethod
    def _split_fallbacks(raw: str | None) -> list[str]:
        return [model.strip() for model in (raw or "").split(",") if model.strip()]

    @property
    def fast_chain(self) -> list[str]:
        return [self.fast_model, *self._split_fallbacks(self.fast_model_fallbacks)]

    @property
    def medium_chain(self) -> list[str]:
        return [self.medium_model, *self._split_fallbacks(self.medium_model_fallbacks)]

    @property
    def heavy_chain(self) -> list[str]:
        return [self.heavy_model, *self._split_fallbacks(self.heavy_model_fallbacks)]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
