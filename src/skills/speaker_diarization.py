"""Universal multi-speaker diarization & separation (v1.1 roadmap, feature 1).

A conversation recording (voice note, call, room audio) splits into
per-speaker dialogue turns — CPU-only, zero-cost, zero cloud:

1. ffmpeg decodes the container to 16 kHz mono PCM in memory.
2. Energy windows segment the stream into speech chunks (silence-skipping).
3. Each chunk embeds via ECAPA-TDNN (the same local model the biometric
   gate uses) and clusters by cosine similarity into speaker turns.
4. Every turn is attributed by cross-referencing the sealed owner print and
   the Contacts/ voiceprint registry — a voice in neither stays
   «متحدث غير معروف», never guessed.
5. Local Whisper transcribes each attributed segment (same Whisper lane,
   Jordanian Arabic pinning).

Output: ``[DiarizedTurn(speaker, text, start_s, end_s)]`` +
``render()`` → «المتحدث 1 (عمر): ... | المتحدث 2 (أحمد): ...».

Untrusted-content boundary: transcripts are DATA. This module has no tool,
bridge, or execution surface at all (AST-guarded by its test).
"""

from __future__ import annotations

import subprocess
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from loguru import logger

UNKNOWN_SPEAKER_AR = "متحدث غير معروف"
OWNER_NAME = "عمر"
_SampleRate = 16000
_FFMPEG_ARGS = (
    "ffmpeg",
    "-hide_banner",
    "-loglevel",
    "error",
    "-i",
    "pipe:0",
    "-f",
    "s16le",
    "-ac",
    "1",
    "-ar",
    str(_SampleRate),
    "pipe:1",
)
# segmentation: ~1.2 s analysis windows, split where the RMS energy dips hard
_WINDOW_S = 1.2
_SILENCE_RATIO = 0.35
_CLUSTER_THRESHOLD = 0.60


@dataclass(frozen=True)
class DiarizedTurn:
    speaker: str
    text: str
    start_s: float
    end_s: float


class SpeakerDiarizer:
    def __init__(
        self,
        *,
        embedder,
        transcriber,
        owner_vector: list[float] | None,
        registry=None,
        match_threshold: float = 0.60,
        executor: ThreadPoolExecutor | None = None,
    ) -> None:
        """embedder/transcriber: injectable doubles in tests; production wires
        the ECAPA biometrics model and the local Whisper pipeline."""
        self._embedder = embedder
        self._transcriber = transcriber
        self._owner_vector = owner_vector
        self._registry = registry
        self._threshold = match_threshold
        self._executor = executor

    # --- decode + segment -----------------------------------------------------

    def _decode_pcm(self, container: bytes) -> bytes:
        if not container:
            return b""
        proc = subprocess.run(_FFMPEG_ARGS, input=container, capture_output=True, check=False)
        if proc.returncode != 0 or not proc.stdout:
            logger.warning("diarization: ffmpeg could not decode the container")
            return b""
        return proc.stdout

    @staticmethod
    def _rms(frame: bytes) -> float:
        count = len(frame) // 2
        if not count:
            return 0.0
        acc = 0
        for i in range(0, len(frame), 2):
            sample = frame[i] | (frame[i + 1] << 8)
            if sample >= 32768:
                sample -= 65536
            acc += sample * sample
        return (acc / count) ** 0.5

    def _segments(self, pcm: bytes) -> list[tuple[bytes, float, float]]:
        """Energy windows: contiguous loud windows merge into one speech
        segment; a window under the silence ratio closes the segment."""
        window_bytes = int(_SampleRate * 2 * _WINDOW_S)
        frames: list[tuple[bytes, int]] = []
        peak = 0.0
        for start in range(0, len(pcm), window_bytes):
            frame = pcm[start : start + window_bytes]
            rms = self._rms(frame)
            peak = max(peak, rms)
            frames.append((frame, start))
        if not frames:
            return []
        silence_line = peak * _SILENCE_RATIO
        segments: list[tuple[bytes, float, float]] = []
        current: list[bytes] = []
        seg_start = 0
        for frame, start in frames:
            if self._rms(frame) >= silence_line:
                if not current:
                    seg_start = start
                current.append(frame)
            elif current:
                joined = b"".join(current)
                segments.append((joined, seg_start / 2 / _SampleRate, (start) / 2 / _SampleRate))
                current = []
        if current:
            joined = b"".join(current)
            segments.append((joined, seg_start / 2 / _SampleRate, len(pcm) / 2 / _SampleRate))
        return segments

    # --- attribution ------------------------------------------------------------

    async def _identify(self, vector: list[float]) -> str:
        owner = self._owner_vector
        if owner is not None:
            from src.skills.voice_biometric_auth import _cosine

            if _cosine(vector, owner) >= self._threshold:
                return OWNER_NAME
        if self._registry is not None:
            verdict = await self._registry.match_vector(vector)
            if verdict.role == "owner":
                return OWNER_NAME
            if verdict.role == "contact" and verdict.name:
                return verdict.name
        return UNKNOWN_SPEAKER_AR

    # --- the pipeline ------------------------------------------------------------

    async def diarize(self, container: bytes) -> list[DiarizedTurn]:
        import asyncio

        loop = asyncio.get_running_loop()
        pcm = await loop.run_in_executor(self._executor, self._decode_pcm, container)
        if not pcm:
            return []
        segments = self._segments(pcm)
        if not segments:
            return []
        # cluster: consecutive segments with close embeddings share a speaker
        vectors: list[list[float]] = []
        for seg, _start, _end in segments:
            vectors.append(await loop.run_in_executor(self._executor, self._embedder.embed, seg))
        turns: list[DiarizedTurn] = []
        speaker_cache: dict[int, str] = {}
        for idx, ((seg, start, end), vector) in enumerate(zip(segments, vectors, strict=True)):
            speaker = speaker_cache.get(idx)
            if speaker is None:
                speaker = await self._identify(vector)
                # same voice as a previous turn? reuse its attribution
                for seen_idx, seen_vec in enumerate(vectors[:idx]):
                    if seen_idx in speaker_cache and _close(seen_vec, vector, self._threshold):
                        speaker = speaker_cache[seen_idx]
                        break
                speaker_cache[idx] = speaker
            text = await loop.run_in_executor(self._executor, self._transcriber.transcribe, seg)
            turns.append(DiarizedTurn(speaker=speaker, text=text, start_s=start, end_s=end))
        return turns

    @staticmethod
    def render(turns: list[DiarizedTurn]) -> str:
        """The roadmap's structured attribution line."""
        return " | ".join(f"{t.speaker}: {t.text}" for t in turns)


def _close(a: list[float], b: list[float], threshold: float) -> bool:
    if not a or not b or len(a) != len(b):
        return False
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    return (dot / (na * nb)) >= threshold if na and nb else False
