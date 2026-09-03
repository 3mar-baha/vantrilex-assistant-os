"""Fish Audio voice engine (remediation 1.9, owner directive 2026-09-03): Fish
`s2.1-pro-free` with the «سمسم-بوس» reference voice via OpenRouter's
`/api/v1/audio/speech` is Sara's PRIMARY voice; Edge-TTS (Salma) stays the
transparent fallback on any Fish failure — $0.00 held (free pool, same
OPENROUTER_API_KEY), the owner never left hanging.

Wire note: the bot calls OpenRouter directly because OmniRoute's speech lane
does not proxy `openrouter/*` slugs (its /v1/audio/speech validates against a
fixed audio-provider list). The OpenRouter key here is the same account key
already in .env — the voice lane borrows it; the brain still routes via OmniRoute.
"""

import httpx
from loguru import logger

from src.dialect import shape_for_tts
from src.voice import transcode_mp3_to_opus

FISH_SPEECH_URL = "https://openrouter.ai/api/v1/audio/speech"
_TIMEOUT = httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0)


class FishVoiceError(RuntimeError):
    """Fish/OpenRouter speech failure — the caller falls back to Edge-TTS."""


class FishVoice:
    """Thin async client over OpenRouter's audio/speech endpoint (Fish s2.1 voices)."""

    def __init__(
        self,
        *,
        model: str,
        voice_ref: str,
        api_key: str,
        speed: float | None = None,
        transport=None,
    ) -> None:
        self.model = model
        self.voice_ref = voice_ref
        self.speed = speed
        self._api_key = api_key
        self._client = httpx.AsyncClient(timeout=_TIMEOUT, transport=transport)

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    @classmethod
    def from_settings(cls, settings, transport=None) -> "FishVoice":
        return cls(
            model=settings.fish_audio_model,
            voice_ref=settings.fish_audio_voice_ref,
            api_key=settings.fish_audio_key,
            speed=settings.fish_audio_speed,
            transport=transport,
        )

    async def synthesize(self, text: str) -> bytes:
        # Owner live-retest 2026-09-03: the Fish lane fed RAW text to the wire —
        # «هههه» became an out-of-context laugh, emoji/tanween mangled the
        # dialect. Shape exactly like the Edge lane; if shaping empties the
        # string (pure emoji), pass the original through — never blank.
        text = (shape_for_tts(text) or text).strip()
        if not text:
            raise ValueError("blank text — nothing to synthesize")
        if not self.available:
            raise FishVoiceError("fish voice unconfigured (no API key)")
        payload = {
            "model": self.model,
            "input": text,
            "voice": self.voice_ref,
            "response_format": "mp3",
        }
        if self.speed is not None:
            # Officially supported multiplier (docs): "Only used by models that
            # support it" — the temperature-0.7 steadiness emulation (owner
            # 2026-09-03); harmless no-op if the provider drops it.
            payload["speed"] = self.speed
        try:
            response = await self._client.post(
                FISH_SPEECH_URL,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=payload,
            )
        except httpx.HTTPError as error:
            raise FishVoiceError(f"fish speech network failure: {error}") from error
        if response.status_code != 200:
            raise FishVoiceError(
                f"fish speech HTTP {response.status_code}: {response.text[:120]!r}"
            )
        content_type = response.headers.get("content-type", "")
        if not response.content or "json" in content_type:
            raise FishVoiceError(
                f"fish speech returned {content_type or 'empty body'} — expected audio bytes"
            )
        return response.content

    async def aclose(self) -> None:
        await self._client.aclose()


class FishFirstVoice:
    """Same synthesize(text) -> Ogg-Opus-bytes interface as VoicePipeline: Fish
    first (MP3 -> the existing ffmpeg 64k chain), Edge-TTS on any Fish failure."""

    def __init__(self, *, fish: FishVoice | None, edge) -> None:
        self._fish = fish
        self._edge = edge

    async def synthesize(self, text: str) -> bytes:
        if self._fish is not None and self._fish.available:
            try:
                mp3 = await self._fish.synthesize(text)
                return await transcode_mp3_to_opus(mp3)
            except FishVoiceError as error:
                logger.warning("fish voice failed, falling back to Edge-TTS: {}", error)
        return await self._edge.synthesize(text)
