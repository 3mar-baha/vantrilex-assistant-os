"""Voice biometric auth (ADR-17, sprint-2 §2.3): ECAPA-TDNN owner-voice match.

Voice notes carry a second trust factor beyond the Telegram owner-ID gate: the
speaker embedding is matched against the sealed owner voiceprint on CPU
(<50 ms match budget, model loaded once, inference off-loop via executor).
Owner voice -> normal service. Non-owner voice -> Guest Mode: a warm Jordanian
lockdown with zero privileged side effects — no gateway calls carrying personal
context, no whitelist, no PC actions, and no vault writes beyond one staging
note. A guest voice note is DATA: staged for later briefing, never instructions.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from aiogram import Bot
from cryptography.fernet import Fernet, InvalidToken
from loguru import logger

DEFAULT_MODEL_ID: Final[str] = "speechbrain/spkrec-ecapa-voxceleb"
GUEST_LOCKDOWN_AR: Final[str] = "يا هلا، الصوت مش صوت عمر... مين بيحكي معي؟"
GUEST_TRANSCRIPT_PLACEHOLDER: Final[str] = (
    "[رسالة صوتية من متحدث غير معروف — بانتظار التفريغ عند اعتماد المتحدث]"
)
_PCM_SAMPLE_RATE: Final[int] = 16000
# Live round-3 2026-09-03 22:58: the owner's own 2-second note scored 0.388
# against his print (his genuine same-day notes: 0.67-0.72) — ECAPA vectors
# from very short clips are unstable. A note shorter than this is INCONCLUSIVE:
# it can never lock the owner out (the Telegram-ID gate is the security
# boundary); it proceeds on middleware trust with a loud log. Real guests on
# an owner-ID hijacked account remain caught whenever they speak longer.
_MIN_DECISIVE_PCM_BYTES: Final[int] = _PCM_SAMPLE_RATE * 2 * 2  # ≥2 s of 16-bit mono


class VoiceprintError(RuntimeError):
    """Loud config/model failure naming the library + RUNBOOK pointer."""


def _fernet(enc_key: str) -> Fernet:
    if not enc_key:
        raise VoiceprintError(
            "VAULT_ENC_KEY is not set — voiceprints cannot be sealed (docs/04-RUNBOOK.md)"
        )
    try:
        return Fernet(enc_key.encode())
    except ValueError as error:
        raise VoiceprintError(
            "VAULT_ENC_KEY is not a valid Fernet key — regenerate per docs/04-RUNBOOK.md"
        ) from error


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def stage_guest_note(
    vault_root: Path,
    vector: list[float],
    *,
    enc_key: str,
    now: datetime | None = None,
    transcript: str | None = None,
    claimed_name: str | None = None,
) -> Path:
    """One Pending_Speakers staging note per guest voice event (ADR-15: durable
    across Space restarts so the owner can brief it later). Same-minute guests
    keep separate notes — never overwritten."""
    moment = now or datetime.now(UTC)
    directory = Path(vault_root) / "Voice_Memos" / "Pending_Speakers"
    directory.mkdir(parents=True, exist_ok=True)
    stamp = moment.strftime("%Y-%m-%dT%H%M")
    path = directory / f"{stamp}.json"
    suffix = 2
    while path.exists():
        path = directory / f"{stamp}-{suffix}.json"
        suffix += 1
    payload = {
        "received_at": moment.isoformat(timespec="seconds"),
        "transcript": transcript or GUEST_TRANSCRIPT_PLACEHOLDER,
        "voiceprint_enc": (
            _fernet(enc_key).encrypt(json.dumps(vector).encode()).decode() if vector else None
        ),
    }
    if claimed_name is not None:
        payload["claimed_name"] = claimed_name
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


async def verify_or_lockdown(
    *,
    bio: VoiceBiometrics,
    bot: Bot,
    chat_id: int,
    ogg_opus: bytes,
    vault_root: Path,
    enc_key: str,
    registry=None,
) -> bool:
    """True -> continue normal owner handling. False -> non-owner handled: a known
    contact gets the warm CONTACT_MODE_AR reply (message-taking only), anyone else
    gets the Guest Mode lockdown (one staging note + reply) — in both cases NOTHING
    privileged runs (no gateway calls carrying personal context, no whitelist, no
    PC actions, no writes beyond the guest staging note)."""
    if await bio.verify(ogg_opus):
        return True
    if registry is not None and bio.last_vector is not None:
        from src.skills.social_enrollment import CONTACT_MODE_AR  # local: avoids import cycle

        try:
            verdict = await registry.match_vector(bio.last_vector)
        except Exception:  # noqa: BLE001 — registry failure fails closed to Guest Mode
            logger.exception("voiceprint registry match failed — treating as unknown")
            verdict = None
        if verdict is not None and verdict.role == "contact":
            await bot.send_message(chat_id, CONTACT_MODE_AR)
            return False
    try:
        stage_guest_note(vault_root, bio.last_vector or [], enc_key=enc_key)
    except Exception:  # noqa: BLE001 — staging failure never blocks the lockdown reply
        logger.exception("guest staging write failed; lockdown reply still sent")
    await bot.send_message(chat_id, GUEST_LOCKDOWN_AR)
    return False


class VoiceBiometrics:
    """Sealed single-owner voiceprint: enroll once, verify every voice note."""

    def __init__(
        self,
        *,
        embedding_path: Path,
        threshold: float = 0.75,
        executor=None,
        enc_key: str | None = None,
        model_id: str = DEFAULT_MODEL_ID,
    ) -> None:
        self._embedding_path = Path(embedding_path)
        self._threshold = threshold
        self._executor = executor
        self._enc_key = enc_key if enc_key is not None else os.environ.get("VAULT_ENC_KEY", "")
        self._model_id = model_id
        self._model = None
        self._owner_vector: list[float] | None = None
        self._load_attempted = False
        self.last_vector: list[float] | None = None
        self.last_similarity: float = 0.0

    @property
    def enrolled(self) -> bool:
        if not self._load_attempted:
            self._load_attempted = True
            self._owner_vector = self._load_vector()
        return self._owner_vector is not None

    @property
    def owner_vector(self) -> list[float] | None:
        return self._owner_vector

    async def embed(self, ogg_opus: bytes) -> list[float]:
        """Public embedding hook for the multi-speaker registry (§2.3b)."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._executor, self._embed_sync, ogg_opus)

    async def enroll(self, ogg_opus: bytes) -> None:
        """Embed one owner voice note and Fernet-seal it to the vault State.
        Round-3 lesson: re-enrollment BLENDS with the existing print (running
        centroid) when there is one — every genuine note strengthens the
        print instead of replacing it with a single possibly-short clip."""
        loop = asyncio.get_running_loop()
        vector = await loop.run_in_executor(self._executor, self._embed_note_sync, ogg_opus)
        if self._owner_vector is not None and len(self._owner_vector) == len(vector):
            n = getattr(self, "_print_count", 0) + 1
            blended = [
                (a * (n - 1) + b) / n for a, b in zip(self._owner_vector, vector, strict=True)
            ]
            vector, self._print_count = blended, n
            logger.info("owner voiceprint blended ({} notes in the centroid)", n)
        else:
            self._print_count = 1
        sealed = _fernet(self._enc_key).encrypt(
            json.dumps({"model": self._model_id, "vector": vector}).encode()
        )
        path = self._embedding_path
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_bytes(sealed)
        try:
            tmp.chmod(0o600)
        except OSError:  # non-POSIX filesystems: contents stay Fernet-sealed regardless
            pass
        tmp.replace(path)
        self._owner_vector = vector
        self._load_attempted = True
        logger.info("owner voiceprint sealed to {}", path)

    async def verify(self, ogg_opus: bytes) -> bool:
        """True = owner voice (or unenrolled -> middleware-only trust). Fail-closed:
        enrolled + below threshold or any verification error routes Guest Mode —
        EXCEPT an inconclusive clip: shorter than ~2 s cannot decide, so the
        note proceeds on middleware trust (the Telegram-ID gate is the hard
        boundary) with a loud log. Live round-3: the owner's own «اهلا انا
        المستخدم» (~2 s) scored 0.388 and locked him out as a guest."""
        if not self.enrolled:
            logger.info("voiceprint unenrolled — middleware-only trust for voice notes")
            return True
        try:
            loop = asyncio.get_running_loop()
            pcm = await loop.run_in_executor(self._executor, self._decode_pcm, ogg_opus)
            if len(pcm) < _MIN_DECISIVE_PCM_BYTES:
                logger.warning(
                    "voice note too short for a decisive voiceprint ({} bytes) — "
                    "middleware trust; guest lockdown skipped",
                    len(pcm),
                )
                return True
            vector = await loop.run_in_executor(self._executor, self._embed_pcm_sync, pcm)
        except Exception:  # noqa: BLE001 — any verification error fails closed to Guest Mode
            logger.exception("voice verification failed while enrolled — failing closed")
            return False
        self.last_vector = vector
        assert self._owner_vector is not None  # enrolled guarantees the stored vector
        self.last_similarity = _cosine(vector, self._owner_vector)
        return self.last_similarity >= self._threshold

    def _load_vector(self) -> list[float] | None:
        try:
            sealed = self._embedding_path.read_bytes()
        except FileNotFoundError:
            return None
        try:
            payload = json.loads(_fernet(self._enc_key).decrypt(sealed))
            vector = [float(x) for x in payload["vector"]]
        except (InvalidToken, KeyError, TypeError, ValueError):
            logger.warning(
                "corrupt owner voiceprint at {} — treated unenrolled", self._embedding_path
            )
            return None
        return vector or None

    def _embed_sync(self, ogg_opus: bytes) -> list[float]:
        """CPU-bound: ffmpeg decode + ECAPA embedding. Always runs in an executor."""
        return self._embed_pcm_sync(self._decode_pcm(ogg_opus))

    def _embed_note_sync(self, ogg_opus: bytes) -> list[float]:
        """Enrollment hook (round-3): decode + embed with a short-note guard —
        a note shorter than the decisive floor cannot mint a print; the owner
        is told to re-enroll longer (the sealed print stays authoritative)."""
        pcm = self._decode_pcm(ogg_opus)
        if len(pcm) < _MIN_DECISIVE_PCM_BYTES:
            raise VoiceprintError(
                "enrollment note too short (<2 s) — send a note of 8+ seconds "
                "of natural speech (RUNBOOK /enroll-voice)"
            )
        return self._embed_pcm_sync(pcm)

    def _embed_pcm_sync(self, pcm: bytes) -> list[float]:
        """CPU-bound: ECAPA embedding of decoded PCM. Always runs in an executor."""
        import torch

        if self._model is None:
            self._model = self._load_model()
        wav = torch.frombuffer(bytearray(pcm), dtype=torch.int16).float() / 32768.0
        with torch.inference_mode():
            embedding = self._model.encode_batch(wav.unsqueeze(0)).squeeze().tolist()
        return [float(x) for x in embedding]

    def _decode_pcm(self, ogg_opus: bytes) -> bytes:
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
                str(_PCM_SAMPLE_RATE),
                "pipe:1",
            ],
            input=ogg_opus,
            capture_output=True,
            check=False,
        )
        if proc.returncode != 0 or not proc.stdout:
            detail = proc.stderr.decode(errors="replace").strip()[:200]
            raise VoiceprintError(f"ffmpeg could not decode the voice note: {detail}")
        return proc.stdout

    def _load_model(self):
        try:
            from speechbrain.inference.speaker import EncoderClassifier
        except ImportError as error:
            raise VoiceprintError(
                f"speechbrain is not installed (voiceprint_model={self._model_id}) — "
                "pip install speechbrain; see docs/04-RUNBOOK.md voice enrollment"
            ) from error
        try:
            savedir = Path(tempfile.gettempdir()) / "sara-ecapa-voiceprint"
            return EncoderClassifier.from_hparams(
                source=self._model_id, savedir=str(savedir), run_opts={"device": "cpu"}
            )
        except Exception as error:
            raise VoiceprintError(
                f"ECAPA model load failed (speechbrain, {self._model_id}) — "
                "see docs/04-RUNBOOK.md voice enrollment"
            ) from error
