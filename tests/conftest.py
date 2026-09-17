"""Shared fixtures: hermetic Settings factory mirroring .env.example literally.

Sprint-1 §1.1 AC1 validates Settings against exactly these contents — keep
ENV_EXAMPLE in sync with the root .env.example. Values use `your-*` placeholder
shape so the vendored pre-commit secret scanner (which whitelists `your*`)
never trips on test fixtures.
"""

import asyncio
import dataclasses
import datetime
import os
from time import perf_counter
from types import SimpleNamespace

import pytest
from aiogram import Bot
from aiogram.client.session.base import BaseSession
from aiogram.exceptions import TelegramRetryAfter
from aiogram.methods import EditMessageText, SendMessage, SendVoice
from aiogram.types import (
    CallbackQuery,
    Chat,
    Message,
    MessageEntity,
    PhotoSize,
    Update,
    User,
    Video,
    Voice,
)

from src.config import Settings

OWNER_ID = 123456789  # mirrors AUTHORIZED_USER_ID in ENV_EXAMPLE

REMOVE = "__REMOVE__"  # sentinel: factory deletes this key instead of setting it

os.environ.setdefault("SARA_TURN_COUNTER_OFF", "1")  # suite hermeticity: the
# P2 transport hook never touches real vault State during tests; unit tests
# opt back into real disk via monkeypatch.delenv.

ENV_EXAMPLE: dict[str, str] = {
    "OMNIROUTE_BASE_URL": "http://localhost:20128/v1",
    "OMNIROUTE_API_KEY": "sk-omniroute-local-key",
    "FAST_MODEL": "groq/openai/gpt-oss-120b",
    "FAST_MODEL_FALLBACKS": "google/gemma-4-31b-it:free",
    "MEDIUM_MODEL": "nex-agi/nex-n2.5-mini:free",
    "MEDIUM_MODEL_FALLBACKS": "groq/openai/gpt-oss-120b",
    "HEAVY_MODEL": "nex-agi/nex-n2.5-pro:free",
    "HEAVY_MODEL_FALLBACKS": "groq/openai/gpt-oss-120b",
    "HEAVY_ESCALATION_MODEL": "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free",
    "HEAVY_ESCALATION_FALLBACKS": "groq/openai/gpt-oss-120b",
    "HEAVY_CONCURRENCY_THRESHOLD": "3",
    "TELEGRAM_BOT_TOKEN": "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz",
    "AUTHORIZED_USER_ID": "123456789",
    "STREAM_EDIT_INTERVAL_MS": "750",
    "VAULT_LOCAL_PATH": "./vault",
    "VAULT_ENC_KEY": "your-fernet-key-vault-state-encryption",  # tests override with a real Fernet key
    "GMAIL_PUBSUB_TOPIC": "",
    "GMAIL_POLL_SECONDS": "120",
    "GMAIL_SWEEP_DAYS": "2",
    "TRIAGE_BODY_MAX_CHARS": "8000",
    "GOOGLE_VIP_SENDERS": "",
    "TRIAGE_KEYWORDS_AR": "عاجل,مستعجل,ضروري,فوراً,حالا",
    "TRIAGE_KEYWORDS_EN": "urgent,asap,critical,immediately,deadline",
    "CRITICAL_PING_INTERVAL_MIN": "5",
    "CRITICAL_PING_MAX": "6",
    "TOKENJUICE_MAX_CHARS": "4000",
    "BRIEF_ENABLED": "true",
    "BRIEF_LOCAL_TIME": "07:30",
    "JOURNALER_ENABLED": "true",
    "JOURNALER_WINDOW_START": "18:00",
    "JOURNALER_WINDOW_END": "19:30",
    "DAILY_LOGS_DIR": "Daily_Logs",
    # Proactive outreach (remediation 3.2) — ENV_EXAMPLE mirror contract
    "PROACTIVE_ENABLED": "true",
    "PROACTIVE_INTERVAL_MIN": "45",
    "PROACTIVE_MAX_PER_DAY": "3",
    "PROACTIVE_WINDOW_START": "08:00",
    "PROACTIVE_WINDOW_END": "22:30",
    "PROACTIVE_COOLDOWN_MIN": "45",
    "VOICEPRINT_THRESHOLD": "0.60",
    "VOICEPRINT_MODEL": "speechbrain/spkrec-ecapa-voxceleb",
    "WHISPER_MODEL_SIZE": "small",
    "WHISPER_COMPUTE_TYPE": "int8",
    "VOICE_MEMOS_DIR": "Voice_Memos",
    "TELEGRAM_API_ID": "",
    "TELEGRAM_API_HASH": "",
    "TELEGRAM_USER_SESSION_STRING": "",
    # Fish Audio primary voice lane (remediation 1.9): borrows the OpenRouter key.
    "OPENROUTER_API_KEY": "your-openrouter-key",
    "FISH_AUDIO_API_KEY": "",
    "FISH_AUDIO_ENDPOINT": "https://openrouter.ai/api/v1/audio/speech",
    "PC_MAC_ADDRESS": "",  # M3: /start_station's WoL target ("" = honest off)
    "FISH_AUDIO_MODEL": "fish-audio/s2.1-pro-free:free",
    "FISH_AUDIO_VOICE_REF": "56c2f0c23924449781863ff20aceb5fa",
    "FISH_AUDIO_SPEED": "0.9",
    "VOICE_NAME": "ar-EG-SalmaNeural",
    "VOICE_RATE": "+0%",
    "VOICE_PITCH": "+0Hz",
    "VAULT_GITHUB_REPO": "owner/vault-repo",
    "VAULT_GITHUB_TOKEN": "your-github-fine-grained-pat",  # sprint-3 3.1: required (SecretStr)
    "VAULT_BRANCH": "main",
    "GOOGLE_OAUTH_CLIENT_JSON": "./config/google_oauth_client.json",
    "GOOGLE_CALENDAR_ID": "primary",
    "BRIDGE_TOKEN": "your-bridge-shared-token",  # sprint-3 3.4: required (SecretStr)
    "BRIDGE_SERVER_URL": "wss://your-space-host/bridge",  # sprint-3 3.4: required
    "BRIDGE_LAN_PORT": "8000",
    "TZ": "Asia/Amman",
    "LOG_LEVEL": "INFO",
}


@pytest.fixture(autouse=True)
def _clear_gateway_registries():
    """Process-wide gateway registries (rate cooldowns, 429 streaks) must not
    leak across tests — live tier-2 probes throttle real pins mid-suite."""
    from src.gateway import _429_STREAK, _MODEL_COOLDOWNS

    _MODEL_COOLDOWNS.clear()
    _429_STREAK.clear()
    yield
    _MODEL_COOLDOWNS.clear()
    _429_STREAK.clear()


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


# --- Sprint-2 §2.2 fakes: recording Telegram session + scripted brain/voice doubles ---


@dataclasses.dataclass
class Call:
    name: str
    method: object
    at: float
    error: Exception | None = None


@dataclasses.dataclass
class StreamProgram:
    deltas: tuple[str, ...] = ()
    error: Exception | None = None
    gate: asyncio.Event | None = None  # when set: block after the first delta


class FakeGateway:
    """Scripted OmniRouteClient double: router replies + stream programs, call order."""

    def __init__(self, *, router_replies=(), stream_programs=()):
        self._routers = list(router_replies)
        self._programs = list(stream_programs)
        self.router_calls: list[list[dict]] = []
        self.stream_calls: list[tuple[list[dict], object]] = []

    async def chat(self, messages, **kwargs):
        self.router_calls.append(messages)
        return self._routers.pop(0)

    def stream_chat(self, messages, *, tier=None, **kwargs):
        self.stream_calls.append((messages, tier))
        prog: StreamProgram = self._programs.pop(0)

        async def gen():
            for i, delta in enumerate(prog.deltas):
                yield delta
                if prog.gate is not None and i == 0:
                    await prog.gate.wait()
            if prog.error is not None:
                raise prog.error

        return gen()


class FakeVoice:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[str] = []
        self.error = error

    async def synthesize(self, text: str) -> bytes:
        self.calls.append(text)
        if self.error is not None:
            raise self.error
        return b"OGGOPUS-FAKE-BYTES" * 4


class RecordingSession(BaseSession):
    """Fake aiogram session: records outbound methods, returns real response models."""

    def __init__(
        self,
        *,
        fail_send_indices: frozenset[int] = frozenset(),
        fail_edit_indices: frozenset[int] = frozenset(),
        rate_limit_edit_indices: frozenset[int] = frozenset(),
    ) -> None:
        super().__init__()
        self.calls: list[Call] = []
        self._send_fails = set(fail_send_indices)
        self._edit_fails = set(fail_edit_indices)
        self._rate_limits = set(rate_limit_edit_indices)
        self._sends = 0
        self._edits = 0

    async def make_request(self, bot, method, timeout=None):
        name = type(method).__name__
        error: Exception | None = None
        if isinstance(method, SendMessage):
            self._sends += 1
            if self._sends in self._send_fails:
                error = RuntimeError("telegram send refused")
        elif isinstance(method, EditMessageText):
            self._edits += 1
            if self._edits in self._rate_limits:
                error = TelegramRetryAfter(method=method, message="retry after 0", retry_after=0)
            elif self._edits in self._edit_fails:
                error = RuntimeError("telegram edit refused")
        self.calls.append(Call(name, method, perf_counter(), error))
        if error is not None:
            raise error
        if isinstance(method, (SendMessage, SendVoice)):
            return Message(
                message_id=self._sends + 100,
                date=datetime.datetime.now(datetime.UTC),
                chat=Chat(id=method.chat_id, type="private"),
            )
        return True

    async def stream_content(self, *args, **kwargs):
        raise NotImplementedError

    async def close(self):
        return None

    def sent(self, name: str) -> list[Call]:
        return [call for call in self.calls if call.name == name]


@pytest.fixture
def fake_bot():
    def _make(**session_kwargs) -> Bot:
        session = RecordingSession(**session_kwargs)
        return Bot(token="1234567890:ABCdefGHIjklMNOpqrsTUVwxyz", session=session)

    return _make


def make_update(
    update_id: int,
    from_id: int | None,
    text: str | None = None,
    *,
    command: bool = False,
    voice: bool = False,
    photo: bool = False,
    video: bool = False,
    reply_to: Message | None = None,
) -> Update:
    kwargs: dict = {
        "message_id": update_id,
        "date": datetime.datetime.now(datetime.UTC),
        "chat": Chat(id=from_id or 0, type="private"),
        "from_user": User(id=from_id or 0, is_bot=False, first_name="O") if from_id else None,
    }
    if text is not None:
        if photo or video:
            # Telegram reality: media rides a CAPTION, never message.text
            kwargs["caption"] = text
        else:
            kwargs["text"] = text
            if command:
                kwargs["entities"] = [MessageEntity(type="bot_command", offset=0, length=len(text))]
    if voice:
        kwargs["voice"] = Voice(file_id="f1", file_unique_id="u1", duration=2)
    if reply_to is not None:
        kwargs["reply_to_message"] = reply_to
    if photo:
        kwargs["photo"] = [PhotoSize(file_id="p1", file_unique_id="pu1", width=64, height=64)]
    if video:
        kwargs["video"] = Video(file_id="v1", file_unique_id="vu1", width=64, height=64, duration=2)
    return Update(update_id=update_id, message=Message(**kwargs))


def make_callback_update(update_id: int, from_id: int) -> Update:
    return Update(
        update_id=update_id,
        callback_query=CallbackQuery(
            id=f"cb{update_id}",
            from_user=User(id=from_id, is_bot=False, first_name="O"),
            chat_instance="ci",
            data="ack",
        ),
    )


@pytest.fixture
def owner_update():
    return make_update(1, OWNER_ID, "مرحبا يا سارة")


@pytest.fixture
def stranger_update():
    return make_update(2, 987654321, "مرحبا")


@pytest.fixture
def make_shell(make_settings):
    """Build a dispatcher wired to scripted brain/voice doubles for shell tests."""

    from src.bot import build_dispatcher

    def _make(
        *,
        router_replies=(),
        stream_programs=(),
        voice_error=None,
        custom_voice=None,
        transcriber=None,
        vault=None,
        memory=None,
        writer=None,
        tools=None,
        coordinator=None,
        decide_modality=None,
        situational=None,
        bridge_tunnel=None,
        **settings_overrides,
    ):
        # Round-2 (2026-09-03): the decider returns ONLY the explicit request
        # (or None) — the router's voice_reply + origin default compose in the
        # shell. Legacy tests pin the channel contract via these doubles:
        # default = follow the origin; explicit tests inject their own.
        if decide_modality is None:
            decide_modality = lambda text, voice_origin: "voice" if voice_origin else "text"
        gateway = FakeGateway(router_replies=router_replies, stream_programs=stream_programs)
        voice = custom_voice if custom_voice is not None else FakeVoice(error=voice_error)
        settings = make_settings(STREAM_EDIT_INTERVAL_MS="40", **settings_overrides)
        dp = build_dispatcher(
            gateway,
            voice,
            settings,
            transcriber=transcriber,
            vault=vault,
            memory=memory,
            writer=writer,
            tools=tools,
            coordinator=coordinator,
            decide_modality=decide_modality,
            situational=situational,
            bridge_tunnel=bridge_tunnel,
        )
        return SimpleNamespace(
            dp=dp,
            gateway=gateway,
            voice=voice,
            settings=settings,
            transcriber=transcriber,
            vault=vault,
            memory=memory,
            writer=writer,
            tools=tools,
            coordinator=coordinator,
            decide=decide_modality,
        )

    return _make


async def wait_until(predicate, *, timeout: float = 2.0) -> None:
    deadline = perf_counter() + timeout
    while not predicate():
        if perf_counter() > deadline:
            raise AssertionError("condition not met in time")
        await asyncio.sleep(0.005)


async def drain(streams: dict) -> None:
    """Await every live stream task registered under the given chat->(task, event) map."""
    tasks = [task for task, _ in list(streams.values())]
    if tasks:
        await asyncio.gather(*tasks)
