"""Voice pipeline: Edge-TTS -> ffmpeg -> Ogg Opus, fully in memory (Sprint-1 §1.3).

Every synthesis input passes the dialect TTS shaper first (emoji strip + pronunciation
lexicon + تسكين الأواخر — owner directive 2026-09-02). Opus encodes at 64k in 'audio'
application mode (24k voip choked every voice — live 2026-09-02). First encoded chunk
is yielded the moment ffmpeg emits it; every path reaps the ffmpeg child; no orphans.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Final

import edge_tts
from loguru import logger

from src.dialect import shape_for_tts

FFMPEG_BIN: Final[str] = "ffmpeg"
MAX_TTS_CHARS: Final[int] = 4000
OGG_READ_CHUNK: Final[int] = 4096

_FFMPEG_ARGS: Final[tuple[str, ...]] = (
    "-hide_banner",
    "-loglevel",
    "error",
    # Default probesize gates all output until EOF on piped MP3 — measured 2026-08-29.
    # Tiny probe keeps the first-chunk yield genuinely streaming (~30ms vs ~1s).
    "-analyzeduration",
    "0",
    "-probesize",
    "32",
    "-f",
    "mp3",
    "-i",
    "pipe:0",
    "-map_metadata",
    "-1",
    "-fflags",
    "+nobuffer",
    "-flags",
    "+low_delay",
    "-c:a",
    "libopus",
    "-b:a",
    "64k",
    "-ar",
    "48000",
    "-ac",
    "1",
    "-vbr",
    "on",
    "-frame_duration",
    "20",
    "-application",
    "audio",
    "-f",
    "ogg",
    "-flush_packets",
    "1",
    "pipe:1",
)

_STDERR_TAIL: Final[int] = 500


class VoicePipelineError(RuntimeError):
    pass


async def _spawn_ffmpeg(ffmpeg_bin: str = FFMPEG_BIN):
    """One spawn site for every encode path (streaming + one-shot transcode)."""
    try:
        return await asyncio.create_subprocess_exec(
            ffmpeg_bin,
            *_FFMPEG_ARGS,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise VoicePipelineError(
            "ffmpeg binary not found — install it (docs/04-RUNBOOK.md)"
        ) from exc


async def _drain(proc, producer: asyncio.Task) -> AsyncIterator[bytes]:
    """Shared consume/reap loop: yield opus chunks, surface failures, kill on every path."""
    try:
        try:
            while True:
                chunk = await proc.stdout.read(OGG_READ_CHUNK)
                if not chunk:
                    break
                yield chunk
            await producer  # surface synthesis failure (network etc.)
            code = await proc.wait()
            if code != 0:
                tail = (await proc.stderr.read())[-_STDERR_TAIL:]
                raise VoicePipelineError(f"ffmpeg exited {code}: {tail!r}")
        except (VoicePipelineError, asyncio.CancelledError):
            raise
        except Exception as exc:
            raise VoicePipelineError(f"voice synthesis failed: {exc}") from exc
    finally:
        # Reap on EVERY path — no orphan ffmpeg, no lingering producer task.
        producer.cancel()
        with suppress(BaseException):
            await producer
        with suppress(ProcessLookupError):
            proc.kill()
        with suppress(Exception):
            await proc.wait()
        for pipe in (proc.stdin, proc.stdout, proc.stderr):
            with suppress(Exception):
                pipe.close()


async def _transcode_bytes(mp3: bytes) -> bytes:
    """Encode a COMPLETE in-memory MP3 (e.g. Fish Audio's reply) through the same
    64k/audio-mode chain; one-shot producer, shared consume/reap contract."""
    proc = await _spawn_ffmpeg()

    async def produce() -> None:
        try:
            proc.stdin.write(mp3)
            await proc.stdin.drain()
        finally:
            with suppress(Exception):
                proc.stdin.close()
            with suppress(Exception):
                await proc.stdin.wait_closed()

    chunks = [
        chunk
        async for chunk in _drain(proc, asyncio.create_task(produce(), name="voice-transcode"))
    ]
    return b"".join(chunks)


async def transcode_mp3_to_opus(mp3: bytes) -> bytes:
    """Public one-shot MP3 -> Ogg Opus 64k (Fish Audio replies land here)."""
    return await _transcode_bytes(mp3)


class VoicePipeline:
    def __init__(self, *, voice: str, rate: str, pitch: str, ffmpeg_bin: str = FFMPEG_BIN) -> None:
        self._voice = voice
        self._rate = rate
        self._pitch = pitch
        self._ffmpeg_bin = ffmpeg_bin

    def synthesize_stream(self, text: str) -> AsyncIterator[bytes]:
        shaped = shape_for_tts(text)
        if not shaped.strip():
            raise ValueError("text is blank — nothing to synthesize")
        if len(shaped) > MAX_TTS_CHARS:
            raise ValueError(f"text exceeds MAX_TTS_CHARS ({len(shaped)} > {MAX_TTS_CHARS})")
        return self._stream(shaped)

    async def synthesize(self, text: str) -> bytes:
        return b"".join([chunk async for chunk in self.synthesize_stream(text)])

    async def _stream(self, text: str) -> AsyncIterator[bytes]:
        proc = await _spawn_ffmpeg(self._ffmpeg_bin)
        logger.debug("voice pipeline spawned ffmpeg pid={}", proc.pid)

        async def produce() -> None:
            try:
                com = edge_tts.Communicate(text, self._voice, rate=self._rate, pitch=self._pitch)
                async for event in com.stream():
                    if event.get("type") != "audio":
                        continue  # WordBoundary metadata never forwarded
                    data = event.get("data")
                    if data:
                        proc.stdin.write(data)
                        await proc.stdin.drain()
            finally:
                # Half-close stdin on completion AND on failure — closing is what
                # unblocks ffmpeg's stdout so the consumer can never deadlock.
                with suppress(Exception):
                    proc.stdin.close()
                with suppress(Exception):
                    await proc.stdin.wait_closed()

        async for chunk in _drain(proc, asyncio.create_task(produce(), name="voice-producer")):
            yield chunk
