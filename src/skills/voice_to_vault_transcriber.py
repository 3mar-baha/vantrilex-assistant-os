"""Sprint-2 §2.5: owner voice note -> LOCAL faster-whisper transcription ->
YAML-frontmattered note filed to `Voice_Memos/` (ADR-21).

Runs only after the 2.3 biometric gate passes — guest voice never reaches this
module. Zero cloud STT: ffmpeg decode to 16 kHz mono s16le PCM fully in memory,
faster-whisper (MIT) inference on the CPU executor, model cached in the
container layer (first-run download is the RUNBOOK warmup step). The transcribed
text enters the standard owner-text pipeline; tier selection is the task-1.5
dispatcher's decision, never this module's.
"""

import asyncio
import os
import subprocess
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Final
from zoneinfo import ZoneInfo

import numpy as np
from loguru import logger

AMMAN: Final[ZoneInfo] = ZoneInfo("Asia/Amman")

# STT-1 (owner 2026-09-04 evening): the transcription prompt REWRITTEN as
# natural Jordanian speech — the live session transcribed «الآلة الحاسبة» as
# «القادر الحاسبي» because a one-line MSA-ish register hint gave the decoder
# nothing to lean on for APP NAMES or command verbs. faster-whisper's
# initial_prompt biases the decoder toward the TEXT's register, so the seed is
# written the way Omar actually talks, carrying his apps and his verbs.
_DEFAULT_PROMPT_TERMS: Final[tuple[str, ...]] = (
    (
        "عمر بيقول لسارة بالعامية الأردنية: افتحي الآلة الحاسبة، سكري كروم، "
        "شغّلي المفكرة، اطفّي المتصفح، افتحي يوتيوب وقفي الفيديو، "
        "افتحي CMD، سجّلي مهمة بكرة، ذكريني بعد عشر دقايق، "
        "افحصي الجيميل والتقويم، شو وضع الجهاز، "
        "كلمني بصوتك، كيفك اليوم، شكراً سارة حبيبتي."
    ),
)

# hotwords: exact-match bias for the app names + Sara + Omar (the decoder
# boosts these tokens directly — the belt under the prompt's suspenders)
_HOTWORDS: Final[tuple[str, ...]] = (
    "سارة",
    "عمر",
    "الآلة الحاسبة",
    "الحاسبة",
    "كروم",
    "المفكرة",
    "يوتيوب",
    "CMD",
    "أوبسيديان",
    "سبوتيفاي",
    "ديسكورد",
    "تيليجرام",
    "الكروم",
    "الديسكورد",
)

_PROMPT_BUDGET: Final[int] = 1100  # chars — the seed (~330) + newest teaches


def build_prompt(taught: tuple[tuple[str, str], ...] = ()) -> str:
    """The full initial_prompt: the Jordanian seed + the owner's taught pairs
    (APPENDED, never replacing the seed — the live bug lost the base register
    the moment one pair was taught). Newest teachings kept; oldest dropped
    first when the budget fills; the seed NEVER drops."""
    seed = " ".join(_DEFAULT_PROMPT_TERMS)
    if not taught:
        return seed
    lines = [f"{term} -> {phon}" for term, phon in taught]
    prompt = f"{seed} {' '.join(lines)}"
    while len(prompt) > _PROMPT_BUDGET and lines:
        lines.pop(0)  # FIFO: the oldest teach drops first
        prompt = f"{seed} {' '.join(lines)}"
    return prompt


def _parse_taught(terms: tuple) -> tuple[tuple[str, str], ...]:
    """One shape for taught pairs everywhere: ("a -> b",) strings OR ((a, b),)
    tuples — both normalize to ((a, b),); anything else drops."""
    parsed: list[tuple[str, str]] = []
    for item in terms:
        if isinstance(item, tuple) and len(item) == 2:
            parsed.append((str(item[0]), str(item[1])))
        elif isinstance(item, str) and "->" in item:
            left, _, right = item.partition("->")
            parsed.append((left.strip(), right.strip()))
    return tuple(parsed)


class TranscriberError(RuntimeError):
    """ffmpeg decode or whisper model failure — callers degrade, never hang."""


def _load_model(model_size: str, compute_type: str):
    from faster_whisper import WhisperModel  # lazy: heavy import only on first use

    return WhisperModel(model_size, device="cpu", compute_type=compute_type)


def decode_pcm16k(ogg_opus: bytes) -> bytes:
    """Ogg Opus -> 16 kHz mono s16le PCM, entirely in memory (zero disk)."""

    proc = subprocess.run(
        [
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
            "16000",
            "pipe:1",
        ],
        input=ogg_opus,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0 or not proc.stdout:
        raise TranscriberError(
            "ffmpeg decode failed (in-memory 16 kHz mono pipe)"
        ) from RuntimeError(proc.stderr.decode(errors="replace")[:200])
    return proc.stdout


class VoiceToVault:
    def __init__(
        self,
        *,
        model_size: str,
        compute_type: str,
        executor: ThreadPoolExecutor,
        vault_dir: Path,
        model_loader: Callable[[str, str], object] | None = None,
        tz: ZoneInfo = AMMAN,
        initial_prompt_terms: tuple[str, ...] = _DEFAULT_PROMPT_TERMS,
    ) -> None:
        self._model_size = model_size
        self._compute_type = compute_type
        self._executor = executor
        self._vault_dir = Path(vault_dir)
        self._load = model_loader or _load_model
        self._tz = tz
        self._taught_pairs = (
            ()
            if initial_prompt_terms == _DEFAULT_PROMPT_TERMS
            else _parse_taught(initial_prompt_terms)
        )
        self._whisper: object | None = None

    def update_prompt_terms(self, terms: tuple[str, ...]) -> None:
        """«تعلمي:» loop (STT-1): taught pairs JOIN the seed — never replace it.
        Accepts either ("term -> phonetic",) strings or ((term, phon),) tuples;
        the Jordanian seed always rides with them."""
        self._taught_pairs = _parse_taught(terms)

    def _model(self) -> object:
        if self._whisper is None:
            try:
                self._whisper = self._load(self._model_size, self._compute_type)
            except Exception as error:
                raise TranscriberError(
                    f"whisper model '{self._model_size}' unavailable — run the RUNBOOK "
                    "warmup once (downloads the model into the local cache)"
                ) from error
        return self._whisper

    def _infer_sync(self, pcm: bytes) -> tuple[list, object]:
        audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        # STT-1: Arabic pinned + beam 5 + the Jordanian seed prompt (app names
        # + command verbs in the owner's register) + hotwords (exact-match
        # app-name bias) + vad_filter (leading silence stops eating decode).
        # The taught pairs JOIN the seed inside build_prompt — never replace.
        segments, info = self._model().transcribe(  # type: ignore[attr-defined]
            audio,
            language="ar",
            beam_size=5,
            initial_prompt=build_prompt(getattr(self, "_taught_pairs", ())),
            hotwords=" ".join(_HOTWORDS),
            vad_filter=True,
        )
        return list(segments), info

    async def transcribe(self, ogg_opus: bytes) -> str:
        loop = asyncio.get_running_loop()
        pcm = await loop.run_in_executor(self._executor, decode_pcm16k, ogg_opus)
        segments, _info = await loop.run_in_executor(self._executor, self._infer_sync, pcm)
        return "".join(seg.text for seg in segments).strip()

    async def file_note(
        self,
        text: str,
        *,
        received_at: datetime,
        duration_s: float,
        source: str = "telegram-voice",
    ) -> Path:
        """Atomically file `Voice_Memos/YYYY-MM-DD-HHMM.md` (same-minute memos get
        numeric suffixes, never clobber). Vault write failure: logged + retried
        once, never raises into the reply pipeline."""
        local = received_at.astimezone(self._tz)
        body = text.strip()
        if not body:
            logger.warning("empty voice transcription — filing (empty) note")
            body = "(empty)"
        note = (
            "---\n"
            f"date: {local.isoformat()}\n"
            f"source: {source}\n"
            f"duration_s: {duration_s:.1f}\n"
            "---\n\n"
            f"{body}\n"
        )
        self._vault_dir.mkdir(parents=True, exist_ok=True)
        path = self._vault_dir / f"{local:%Y-%m-%d-%H%M}.md"
        suffix = 2
        while path.exists():
            path = self._vault_dir / f"{path.stem}-{suffix}.md"
            suffix += 1
        tmp = path.with_name(path.name + ".tmp")
        for attempt in (1, 2):
            try:
                tmp.write_text(note, encoding="utf-8")
                os.replace(tmp, path)  # atomic within the memos dir
                logger.info("voice memo filed: {}", path)
                return path
            except OSError:
                logger.opt(exception=True).warning(
                    "vault write failed (attempt {}): {}", attempt, path
                )
        return path  # best-effort: loud logs carry the failure, reply never blocks
