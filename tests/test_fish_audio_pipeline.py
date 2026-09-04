"""Remediation 1.9 (owner directive 2026-09-03): Fish Audio voice engine via
OpenRouter's /api/v1/audio/speech (fish-audio/s2.1-pro-free:free + the «سمسم-بوس»
reference voice). Fish is the primary engine; Edge-TTS Salma stays the transparent
fallback on any Fish failure — $0.00 held, the owner never left hanging."""

import httpx
import pytest

from src.config import Settings
from src.fish_voice import FishFirstVoice, FishVoice, FishVoiceError
from src.voice import VoicePipeline
from tests.helpers_voice import CANNED_MP3, needs_ffmpeg


def _settings(**over) -> Settings:
    base = {
        "omniroute_base_url": "http://gw/v1",
        "omniroute_api_key": "k",
        "fast_model": "f",
        "medium_model": "m",
        "heavy_model": "h",
        "telegram_bot_token": "t",
        "authorized_user_id": 1,
        "vault_enc_key": "your-fernet-key",
        "fish_audio_model": "fish-audio/s2.1-pro-free:free",
        "fish_audio_voice_ref": "56c2f0c23924449781863ff20aceb5fa",
        "fish_audio_speed": "0.9",
        "openrouter_api_key": "sk-or-test",
    }
    base.update(over)
    return Settings(**base)


class _Recorder(httpx.MockTransport):
    """Records the speech request; serves CANNED_MP3 or the scripted error."""

    def __init__(self, *, status: int = 200, body: bytes = b"", content_type: str = "audio/mpeg"):
        self.requests: list[httpx.Request] = []
        self.status = status
        self.body = body
        self.content_type = content_type
        super().__init__(self._handle)

    def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.status != 200:
            return httpx.Response(self.status, json={"error": {"message": "boom"}})
        return httpx.Response(200, content=self.body, headers={"Content-Type": self.content_type})


MP3 = b"ID3\x04fake-mp3-bytes-for-tests"  # any non-empty prefix; ffmpeg not needed here


# --- request shape ----------------------------------------------------------------


async def test_speech_request_shape_and_model():
    """The wire call is OpenRouter /api/v1/audio/speech with the fish model,
    the سمسم reference voice, and the shaped text as input."""
    rec = _Recorder(body=MP3)
    fish = FishVoice(
        model="fish-audio/s2.1-pro-free:free",
        voice_ref="56c2f0c23924449781863ff20aceb5fa",
        api_key="sk-or-test",
        transport=rec,
    )
    out = await fish.synthesize("أهلاً عمر")
    assert out == MP3
    req = rec.requests[0]
    assert req.method == "POST"
    assert req.url.host == "openrouter.ai"
    assert str(req.url.path) == "/api/v1/audio/speech"
    assert req.headers["Authorization"] == "Bearer sk-or-test"
    payload = req.read()
    assert b"fish-audio/s2.1-pro-free:free" in payload
    assert b"56c2f0c23924449781863ff20aceb5fa" in payload
    assert "أهلا عمر".encode() in payload  # shaped like the Edge lane (تسكين strips the tanween)


async def test_speech_input_is_dialect_shaped_like_edge():
    """Owner live-retest 2026-09-03 04:16: Fish received RAW text (emoji, هههه,
    tanween) while the Edge lane shapes — so سمسم laughed out of context and
    mangled dialect words. The Fish lane must feed shape_for_tts output to the
    wire, exactly like the Edge lane does."""
    rec = _Recorder(body=MP3)
    fish = FishVoice(model="m", voice_ref="r", api_key="k", transport=rec)
    await fish.synthesize("هسا بدي أفتح 🐱 كتير")
    payload = rec.requests[0].read()
    assert "أفتح".encode() in payload  # lexicon + emoji strip applied on the Fish lane
    assert "🐱".encode() not in payload


async def test_speech_input_strips_theatrical_laughter():
    """«هههه» in Sara's prose becomes audible laughter out of context (owner
    live-retest 04:16). The TTS shaper must drop laughter tokens entirely —
    the words carry the warmth; a synthesized laugh never fits the context."""
    rec = _Recorder(body=MP3)
    fish = FishVoice(model="m", voice_ref="r", api_key="k", transport=rec)
    await fish.synthesize("هههه من عيوني هسا أجهزها")
    payload = rec.requests[0].read()
    assert "هههه".encode() not in payload
    assert "من عيوني هسَّا".encode() in payload


async def test_empty_text_raises_before_any_request():
    rec = _Recorder(body=MP3)
    fish = FishVoice(
        model="fish-audio/s2.1-pro-free:free",
        voice_ref="ref",
        api_key="k",
        transport=rec,
    )
    with pytest.raises(ValueError):
        await fish.synthesize("   ")
    assert not rec.requests


# --- failure -> fallback contract --------------------------------------------------


async def test_http_error_raises_fishvoiceerror_for_fallback():
    """4xx/5xx/timeout surface as FishVoiceError so the caller falls back to Edge."""
    for status in (402, 429, 500, 503):
        rec = _Recorder(status=status)
        fish = FishVoice(model="m", voice_ref="ref", api_key="k", transport=rec)
        with pytest.raises(FishVoiceError):
            await fish.synthesize("نص")


async def test_429_window_rides_the_error():
    """STT-3 (2026-09-04): a Fish 429 announcing «try again in 12m30s» carries
    retry_in_s — the bot's retry waits a bounded slice of IT, not a blind 2s."""

    class _Body(httpx.MockTransport):
        def __init__(self):
            super().__init__(self._h)

        def _h(self, request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                429,
                content=b"Rate limit reached. Please try again in 12m30s",
                headers={"Content-Type": "text/plain"},
            )

    fish = FishVoice(model="m", voice_ref="ref", api_key="k", transport=_Body())
    with pytest.raises(FishVoiceError) as exc_info:
        await fish.synthesize("نص")
    assert exc_info.value.retry_in_s == 12 * 60 + 30


async def test_plain_429_has_no_window():
    """A window-less 429 keeps retry_in_s None — the caller's default short wait."""
    fish = FishVoice(model="m", voice_ref="ref", api_key="k", transport=_Recorder(status=429))
    with pytest.raises(FishVoiceError) as exc_info:
        await fish.synthesize("نص")
    assert exc_info.value.retry_in_s is None


async def test_network_timeout_raises_fishvoiceerror():
    def _hang(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("net down")

    fish = FishVoice(
        model="m",
        voice_ref="ref",
        api_key="k",
        transport=httpx.MockTransport(_hang),
    )
    with pytest.raises(FishVoiceError):
        await fish.synthesize("نص")


async def test_bad_content_type_raises_fishvoiceerror():
    """A JSON body where audio bytes were expected is a failure, not silence."""
    rec = _Recorder(body=b'{"error":1}', content_type="application/json")
    fish = FishVoice(model="m", voice_ref="ref", api_key="k", transport=rec)
    with pytest.raises(FishVoiceError):
        await fish.synthesize("نص")


# --- disabled / unconfigured -------------------------------------------------------


def test_disabled_when_no_api_key():
    """No OPENROUTER_API_KEY -> available() is False and synthesize never calls the wire."""
    settings = _settings(openrouter_api_key=None)
    assert settings.fish_audio_ready is False
    fish = FishVoice.from_settings(settings, transport=_Recorder(body=MP3))
    assert fish.available is False


def test_enabled_when_key_and_model_present():
    settings = _settings()
    assert settings.fish_audio_ready is True


def test_from_settings_carries_config():
    settings = _settings()
    fish = FishVoice.from_settings(settings, transport=_Recorder(body=MP3))
    assert fish.model == "fish-audio/s2.1-pro-free:free"
    assert fish.voice_ref == "56c2f0c23924449781863ff20aceb5fa"
    assert fish.available is True


# --- calm-tone speed lever (owner 2026-09-03) --------------------------------------


async def test_speed_on_the_wire_when_configured():
    """The officially supported speed multiplier (the temperature-0.7 steadiness
    emulation) rides the payload when configured; default 0.9 from settings."""
    rec = _Recorder(body=MP3)
    fish = FishVoice(model="m", voice_ref="r", api_key="k", speed=0.9, transport=rec)
    await fish.synthesize("من عيوني")
    assert b'"speed":0.9' in rec.requests[0].read()


async def test_speed_absent_when_none():
    """No speed configured -> the payload carries no speed key (provider default)."""
    rec = _Recorder(body=MP3)
    fish = FishVoice(model="m", voice_ref="r", api_key="k", transport=rec)
    await fish.synthesize("من عيوني")
    assert b"speed" not in rec.requests[0].read()


def test_settings_default_speed_09():
    assert _settings().fish_audio_speed == 0.9


# --- FishFirstVoice: Sara's ONLY voice (identity purity, owner 2026-09-03) --------


@needs_ffmpeg
async def test_fishfirst_synthesizes_when_fish_healthy():
    """Fish healthy -> the wire carries fish bytes through the ffmpeg opus chain."""
    rec = _Recorder(body=CANNED_MP3)  # real MPEG frames — the transcode chain must accept them
    pipe = FishFirstVoice(fish=FishVoice(model="m", voice_ref="r", api_key="k", transport=rec))
    out = await pipe.synthesize("أهلاً")
    assert out.startswith(b"OggS")  # same ffmpeg 64k opus chain
    assert len(rec.requests) == 1


async def test_fish_failure_reraises_for_honest_text_fallback():
    """Owner directive 2026-09-03 07:03 (live): Fish is Sara's ONLY voice — a
    Microsoft-Salma voice note after a Fish failure broke identity («الرد عاد
    لمايكروسوفت»). FishFirstVoice never falls back to Edge SYNTHESIS: it
    re-raises so the bot's honest TEXT fallback lands (the owner never hangs;
    the voice identity stays pure Fish)."""
    rec = _Recorder(status=429)
    pipe = FishFirstVoice(fish=FishVoice(model="m", voice_ref="r", api_key="k", transport=rec))
    with pytest.raises(FishVoiceError):
        await pipe.synthesize("أهلاً عمر")


async def test_unconfigured_fish_raises_no_foreign_fallback():
    """No fish config on a FishFirstVoice -> loud failure, never a silent
    Microsoft voice. (Deployments that WANT Edge-TTS simply leave fish
    unconfigured — build_voice returns the pure Edge pipeline.)"""
    pipe = FishFirstVoice(fish=None)
    with pytest.raises(FishVoiceError):
        await pipe.synthesize("أهلاً")


# --- run_bot wiring: fish when ready, pure edge otherwise (remediation 1.9) ------


def test_build_voice_fish_first_when_configured():
    from src.bot import build_voice

    assert isinstance(build_voice(_settings()), FishFirstVoice)


def test_build_voice_pure_edge_when_unconfigured():
    from src.bot import build_voice

    assert isinstance(build_voice(_settings(openrouter_api_key=None)), VoicePipeline)
