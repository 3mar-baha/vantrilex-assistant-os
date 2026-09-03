"""Application settings: pydantic v2 validation over .env + process environment."""

from datetime import time
from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr, field_validator
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
    "vault_enc_key",  # consumed by task 2.1 vault-state encryption (ADR-15)
    "vault_github_repo",  # consumed by task 3.1 vault architect (ADR-21)
    "vault_github_token",  # consumed by task 3.1 vault architect (ADR-21)
    "bridge_token",  # consumed by task 3.4 PC bridge (shared tunnel secret)
    "bridge_server_url",  # consumed by task 3.4 PC bridge (core WSS endpoint)
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
    vault_local_path: Path = Path("./vault")  # VAULT_LOCAL_PATH (ADR-15 durable state root)
    vault_enc_key: str  # VAULT_ENC_KEY (Fernet key, secrets.token_urlsafe)
    gmail_pubsub_topic: str | None = (
        None  # GMAIL_PUBSUB_TOPIC (watch registration; empty -> poll only)
    )
    gmail_poll_seconds: int = 120  # GMAIL_POLL_SECONDS
    gmail_sweep_days: int = 2  # GMAIL_SWEEP_DAYS
    triage_body_max_chars: int = 8000  # TRIAGE_BODY_MAX_CHARS
    google_vip_senders: str | None = None  # GOOGLE_VIP_SENDERS (comma-separated; empty -> none)
    triage_keywords_ar: str | None = None  # TRIAGE_KEYWORDS_AR (empty -> module default)
    triage_keywords_en: str | None = None  # TRIAGE_KEYWORDS_EN (empty -> module default)
    critical_ping_interval_min: int = 5  # CRITICAL_PING_INTERVAL_MIN
    critical_ping_max: int = 6  # CRITICAL_PING_MAX (0 = unlimited)
    tokenjuice_max_chars: int = 4000  # TOKENJUICE_MAX_CHARS (ADR-19 classification budget)
    brief_enabled: bool = True  # BRIEF_ENABLED (daily brief, §2.4)
    brief_local_time: str = "07:30"  # BRIEF_LOCAL_TIME (HH:MM, Amman local)
    journaler_enabled: bool = True  # JOURNALER_ENABLED (evening check-in, §2.6)
    journaler_window_start: str = "18:00"  # JOURNALER_WINDOW_START (HH:MM, Amman)
    journaler_window_end: str = "19:30"  # JOURNALER_WINDOW_END (HH:MM, Amman local)
    daily_logs_dir: str = "Daily_Logs"  # DAILY_LOGS_DIR (ADR-21 mandatory directory)
    voiceprint_threshold: float = 0.60  # VOICEPRINT_THRESHOLD (ADR-17; live-calibrated 2026-09-03: owner-intra 0.76, impostor 0.11)
    voiceprint_model: str = "speechbrain/spkrec-ecapa-voxceleb"  # VOICEPRINT_MODEL (ECAPA-TDNN)
    whisper_model_size: str = "small"  # WHISPER_MODEL_SIZE (local faster-whisper, §2.5)
    whisper_compute_type: str = "int8"  # WHISPER_COMPUTE_TYPE (CPU int8 quantization)
    voice_memos_dir: str = "Voice_Memos"  # VOICE_MEMOS_DIR (ADR-21 mandatory directory)

    # Declared now (validates every var in .env.example); consumed by later sprints.
    # Optional fields become required in the commit whose task first consumes them.
    telegram_api_id: int | None = None
    telegram_api_hash: str | None = None
    telegram_user_session_string: str | None = None
    voice_name: str = "ar-EG-SalmaNeural"
    voice_rate: str = "+0%"
    voice_pitch: str = "+0Hz"
    # Fish Audio primary voice lane (remediation 1.9, owner directive 2026-09-03):
    # fish s2.1-pro-free + the سمسم-بوس reference voice via OpenRouter speech API.
    # Uses the same OPENROUTER_API_KEY already in .env — the voice lane borrows it
    # directly (OmniRoute's speech lane does not proxy openrouter/* slugs).
    openrouter_api_key: str | None = None  # OPENROUTER_API_KEY
    fish_audio_model: str = "fish-audio/s2.1-pro-free:free"  # FISH_AUDIO_MODEL
    fish_audio_voice_ref: str = "56c2f0c23924449781863ff20aceb5fa"  # FISH_AUDIO_VOICE_REF (سمسم)
    # Calm-tone lever (owner 2026-09-03): the /audio/speech schema has NO
    # temperature (chat param) — the official "speed" multiplier emulates the
    # requested 0.7-temperature steadiness as a measured 0.9 pace. Tune via env.
    fish_audio_speed: float = 0.9  # FISH_AUDIO_SPEED
    vault_github_repo: str  # VAULT_GITHUB_REPO (private vault repo, "owner/name")
    vault_github_token: SecretStr  # VAULT_GITHUB_TOKEN (fine-grained PAT, repo scope)
    vault_branch: str = "main"  # VAULT_BRANCH (vault git branch)
    obsidian_rest_api_url: str | None = None
    obsidian_api_key: str | None = None
    google_oauth_client_json: str = "./config/google_oauth_client.json"
    google_calendar_id: str = "primary"
    bridge_token: SecretStr  # BRIDGE_TOKEN (shared core<->bridge secret, sprint-3 3.4)
    bridge_server_url: str  # BRIDGE_SERVER_URL (core WSS endpoint the daemon dials)
    bridge_lan_port: int = 8000  # BRIDGE_LAN_PORT (daemon loopback/LAN health surface)
    target_pc_mac_address: str | None = None
    target_pc_ip: str | None = None
    target_pc_wol_port: int = 9
    space_url: str | None = None  # SPACE_URL (public Space root; deploy smoke + keep-alive target)
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

    @field_validator("brief_local_time")
    @classmethod
    def _brief_time_is_hhmm(cls, value: str) -> str:
        try:
            time.fromisoformat(value)
        except ValueError as error:  # loud settings failure (spec §2.4 error modes)
            raise ValueError("BRIEF_LOCAL_TIME must be HH:MM (24h)") from error
        return value

    @field_validator("journaler_window_start", "journaler_window_end")
    @classmethod
    def _journaler_window_is_hhmm(cls, value: str) -> str:
        try:
            time.fromisoformat(value)
        except ValueError as error:  # loud settings failure (spec §2.6 error modes)
            raise ValueError("journaler window bounds must be HH:MM (24h)") from error
        return value

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

    @property
    def fish_audio_key(self) -> str | None:
        """The voice lane's bearer key: OPENROUTER_API_KEY when present, else none."""
        return self.openrouter_api_key

    @property
    def fish_audio_ready(self) -> bool:
        return bool(self.fish_audio_key and self.fish_audio_model)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
