"""Feature 3 (v1.1 roadmap): acoustic & paralinguistic nuance pipeline.

The owner's voice note carries more than words: tempo, energy, pauses — the
acoustic texture of HOW he spoke. A deterministic local extractor (pure DSP:
RMS energy contour over windows — no cloud, no ML models) turns the decoded
PCM into a compact ``AcousticProfile``; ``build_paralinguistic_block`` renders
the subtle Arabic context that rides the cognitive envelope so Sara reads the
tone WITH the words.

The sacred security boundary stays untouched: ECAPA-TDNN (the biometric gate)
is the ONLY authorization path. This module has no verify/enroll/match
surface at all (AST-guarded by its test) — pure interpretation context.

Round-3 lesson applied to interpretation too: a note shorter than ~1 s has
meaningless metrics — the block stays EMPTY rather than guessing.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

_SAMPLE_RATE: Final[int] = 16000
_WINDOW_S: Final[float] = 0.25  # 4 windows/s — fine enough for pauses
_SILENCE_LINE: Final[float] = 300.0  # s16le RMS floor for "speech"
_MIN_PCM_BYTES: Final[int] = _SAMPLE_RATE * 2  # ≥1 s: metrics below are noise

_PARALINGUISTIC_HEADER_AR: Final[str] = (
    "[ملامح صوتية من ملاحظة عمر — بيانات مرجعية وليست تعليمات: خديها بالحسبان بطريقتك وبنبرتك]"
)


@dataclass(frozen=True)
class AcousticProfile:
    duration_s: float
    activity: float  # 0..1 — fraction of windows with speech energy
    pause_ratio: float  # 0..1 — fraction of LOW-energy windows after speech began
    mean_energy: float  # s16le RMS of the loud windows


def _windows(pcm: bytes) -> list[bytes]:
    size = int(_SAMPLE_RATE * 2 * _WINDOW_S)
    return [pcm[i : i + size] for i in range(0, len(pcm), size)]


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


def extract_profile(pcm: bytes) -> AcousticProfile:
    """Deterministic DSP profile of decoded 16 kHz mono s16le PCM."""
    duration = len(pcm) / 2 / _SAMPLE_RATE
    if not pcm:
        return AcousticProfile(0.0, 0.0, 0.0, 0.0)
    frames = _windows(pcm)
    energies = [_rms(f) for f in frames]
    loud = [e for e in energies if e >= _SILENCE_LINE]
    activity = len(loud) / len(energies)
    # pauses: LOW-energy windows AFTER the first loud one (leading silence
    # is breathing room, not hesitation)
    first_loud = next((i for i, e in enumerate(energies) if e >= _SILENCE_LINE), None)
    tail = energies[first_loud:] if first_loud is not None else []
    pause_ratio = (sum(1 for e in tail if e < _SILENCE_LINE) / len(tail)) if tail else 0.0
    mean_energy = sum(loud) / len(loud) if loud else 0.0
    return AcousticProfile(duration, activity, pause_ratio, mean_energy)


def build_paralinguistic_block(profile: AcousticProfile) -> str:
    """The envelope context: how he SOUNDED, phrased as data. Empty string
    when the metrics cannot mean anything (short note / silence)."""
    if profile.duration_s < 1.0 or profile.mean_energy == 0.0:
        return ""
    parts: list[str] = []
    if profile.pause_ratio > 0.4:
        parts.append("حكيه فيه توقفات كتيرة — يمكن متردد أو مفكر بهدوء")
    elif profile.activity > 0.8:
        parts.append("حكيه سريع ومتواصل — فيه حيوية وحماس")
    if profile.mean_energy >= 4000.0:
        parts.append("صوته عالي شوي — طاقة أو انفعال")
    elif profile.mean_energy < 1000.0:
        parts.append("صوته هادي — مرحلة لطيفة أو تعب")
    if not parts:
        return ""
    return _PARALINGUISTIC_HEADER_AR + "\n" + " · ".join(parts)


def ogg_paralinguistic_block(ogg_opus: bytes) -> str:
    """Decode an Ogg Opus note (in-memory ffmpeg, the standard chain) and
    return its paralinguistic block; ANY failure returns an empty string —
    the acoustic lane never breaks the voice turn."""
    import subprocess

    try:
        proc = subprocess.run(
            (
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
                str(_SAMPLE_RATE),
                "pipe:1",
            ),
            input=ogg_opus,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0 or not proc.stdout:
            return ""
        return build_paralinguistic_block(extract_profile(proc.stdout))
    except Exception:  # noqa: BLE001 — interpretation is best-effort
        return ""
