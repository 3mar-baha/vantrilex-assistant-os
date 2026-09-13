"""Fish-only voice opus chain (2026-09-12 Edge purge): in-memory MP3 -> Ogg Opus.

Sara's ONLY voice is Fish Audio (`src/fish_voice.py`); this module owns the
shared ffmpeg encode (64k mono 48kHz, audio application mode) plus the
hallucinated-media-link sanitizer. There is no synthesis engine here and no
fallback voice — a Fish failure lands the honest TEXT reply upstream.
"""

import asyncio
import re
from collections.abc import AsyncIterator
from contextlib import suppress
from typing import Final

from loguru import logger

FFMPEG_BIN: Final[str] = "ffmpeg"
OGG_READ_CHUNK: Final[int] = 4096

# Directive §3 (owner 2026-09-04, live 3:42pm): the model hallucinated
# sara-voice.s3.amazonaws.com links for her own voice — audio is synthesized
# in-memory and dispatched by US, never linked externally. This sanitizer is
# the structural defense behind the prompt: any media-CDN/file link dies
# before a message surface.
_EXTERNAL_MEDIA_LINK_RE: Final = re.compile(
    r"https?://\S*(?:s3\.amazonaws|soundcloud|cdn|\.mp3|\.wav|\.ogg|storage\.googleapis"
    r"|drive\.google|dropbox)\S*",
    re.IGNORECASE,
)


def strip_external_media_links(text: str) -> str:
    """Remove hallucinated external media URLs from a reply; the rest of the
    text survives untouched. Pure, never raises."""
    try:
        return _EXTERNAL_MEDIA_LINK_RE.sub("", text).strip()
    except Exception:  # noqa: BLE001 — sanitation never blocks the reply
        return text


_TAG_RE: Final = re.compile(r"\[([^\[\]\n]{1,60})\]|\(([^()\n]{1,60})\)")


def strip_tags(text: str) -> str:
    """Remove ALL inline expressive tags (text surface): chat bubbles must
    never show literal tags. Surrounding prose survives; whitespace collapsed.
    Pure, never raises."""
    try:
        cleaned = _TAG_RE.sub("", text or "")
        return re.sub(r"[ \t]{2,}", " ", cleaned).strip()
    except Exception:  # noqa: BLE001 — sanitation never blocks the reply
        return text


def sanitize_tags(text: str, *, mode: str = "routine") -> str:
    """Voice-surface filter (Q3): keep allowlisted tags up to the scarcity cap,
    drop hallucinated/over-cap tags silently. Modes: technical=0, routine≤1,
    extended≤2. Unknown modes degrade to routine. Pure, never raises."""
    from src.skills.expressive_audio import CAPS, is_supported_tag

    try:
        cap = CAPS.get((mode or "routine").strip().lower(), CAPS["routine"])
        if cap <= 0:
            return strip_tags(text)
        kept = 0

        def _filter(match: re.Match[str]) -> str:
            nonlocal kept
            bracket, paren = match.group(1), match.group(2)
            if bracket is not None:
                ok = is_supported_tag(bracket)
            else:
                ok = is_supported_tag(paren or "", parens=True)
            if ok and kept < cap:
                kept += 1
                return match.group(0)
            return ""

        cleaned = _TAG_RE.sub(_filter, text or "")
        return re.sub(r"[ \t]{2,}", " ", cleaned).strip()
    except Exception:  # noqa: BLE001 — sanitation never blocks the reply
        return text


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


class OpusTranscodeError(RuntimeError):
    """ffmpeg MP3->Opus encode failure — the caller falls back to honest text."""


async def _spawn_ffmpeg(ffmpeg_bin: str = FFMPEG_BIN):
    """One spawn site for the Fish MP3 transcode path."""
    try:
        return await asyncio.create_subprocess_exec(
            ffmpeg_bin,
            *_FFMPEG_ARGS,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise OpusTranscodeError(
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
            await producer  # surface transcode failure
            code = await proc.wait()
            if code != 0:
                tail = (await proc.stderr.read())[-_STDERR_TAIL:]
                raise OpusTranscodeError(f"ffmpeg exited {code}: {tail!r}")
        except (OpusTranscodeError, asyncio.CancelledError):
            raise
        except Exception as exc:
            raise OpusTranscodeError(f"opus transcode failed: {exc}") from exc
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
    """Encode a COMPLETE in-memory MP3 (Fish Audio's reply) through the 64k
    audio-mode chain; one-shot producer, shared consume/reap contract."""
    proc = await _spawn_ffmpeg()
    logger.debug("fish opus transcode spawned ffmpeg pid={}", proc.pid)

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
    if not mp3:
        raise ValueError("blank audio — nothing to transcode")
    return await _transcode_bytes(mp3)
