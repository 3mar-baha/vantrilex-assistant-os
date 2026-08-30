"""Sprint-2 §2.5 AC9: owner voice note -> LOCAL Whisper transcription -> YAML
frontmatter note filed in Voice_Memos/; zero outbound STT network calls; error
modes (decode chain, empty body, write retry, model warmup)."""

import ast
import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from loguru import logger

from src.skills.voice_to_vault_transcriber import TranscriberError, VoiceToVault

AMMAN = ZoneInfo("Asia/Amman")
RECEIVED_AT = datetime(2026, 8, 30, 18, 5, tzinfo=AMMAN)


class _Seg:
    def __init__(self, text: str) -> None:
        self.text = text


class FakeWhisper:
    """Deterministic faster-whisper double: fixed segments, records the PCM call."""

    def __init__(self, segments=(_Seg(" خلاصة "), _Seg(" الاجتماع بيمشي بعد ساعة"))):
        self.segments = list(segments)
        self.audios: list = []

    def transcribe(self, audio, **kwargs):
        self.audios.append(audio)
        return list(self.segments), object()


def _make(tmp_path, model=None, loader=None) -> VoiceToVault:
    if loader is None:
        loader = (lambda size, compute: model) if model is not None else None
    return VoiceToVault(
        model_size="small",
        compute_type="int8",
        executor=ThreadPoolExecutor(max_workers=1),
        vault_dir=tmp_path / "Voice_Memos",
        model_loader=loader,
        tz=AMMAN,
    )


def _real_ogg(tmp_path: Path) -> bytes:
    ogg = tmp_path / "sine.ogg"
    import subprocess

    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=0.3",
            "-c:a", "libopus", "-b:a", "16k", str(ogg),
        ],
        check=True, capture_output=True,
    )
    return ogg.read_bytes()


async def test_voice_note_transcribed_to_local_whisper_vault_note(tmp_path):
    """AC9: real ffmpeg decode + stubbed-whisper deterministic text -> note lands
    in Voice_Memos/ with correct YAML frontmatter; whisper saw the decoded audio."""
    model = FakeWhisper()
    vv = _make(tmp_path, model)
    ogg = _real_ogg(tmp_path)
    text = await vv.transcribe(ogg)
    assert text == "خلاصة الاجتماع بيمشي بعد ساعة"
    assert len(model.audios) == 1 and len(model.audios[0]) > 0  # float32 samples reached whisper

    path = await vv.file_note(
        text, received_at=RECEIVED_AT, duration_s=12.0, source="telegram-voice"
    )
    assert path == tmp_path / "Voice_Memos" / "2026-08-30-1805.md"
    body = path.read_text(encoding="utf-8")
    assert body.startswith("---\n")
    assert "date: 2026-08-30T18:05:00+03:00" in body
    assert "source: telegram-voice" in body
    assert "duration_s: 12.0" in body
    assert "خلاصة الاجتماع بيمشي بعد ساعة" in body


def test_no_cloud_stt_calls(tmp_path):
    """AC9: AST import-surface scan — no network libraries anywhere in the module."""
    source = (
        Path(__file__).parents[1] / "src" / "skills" / "voice_to_vault_transcriber.py"
    ).read_text(encoding="utf-8")
    banned = {"requests", "urllib", "httpx", "aiohttp", "socket", "ssl", "telnetlib", "ftplib"}
    surface: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            surface.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            surface.add(node.module or "")
    assert not surface & banned


async def test_empty_transcription_files_note_with_empty_body(tmp_path):
    """Error mode: empty transcription still files a note with an (empty) body."""
    vv = _make(tmp_path, model=FakeWhisper(segments=[]))
    path = await vv.file_note("", received_at=RECEIVED_AT, duration_s=3.0)
    body = path.read_text(encoding="utf-8")
    assert "(empty)" in body


async def test_decode_failure_raises_transcriber_error_chained(tmp_path):
    """Error mode: ffmpeg failure -> TranscriberError with the cause chained."""
    vv = _make(tmp_path, model=FakeWhisper())
    with pytest.raises(TranscriberError) as error:
        await vv.transcribe(b"not-an-ogg-file")
    assert isinstance(error.value.__cause__, Exception)


async def test_model_load_failure_names_runbook_warmup(tmp_path):
    """Error mode: model missing -> loud error naming the RUNBOOK warmup step."""
    def boom(size: str, compute: str) -> object:
        raise RuntimeError("model files missing")

    vv = _make(tmp_path, loader=boom)
    with pytest.raises(TranscriberError, match="warmup"):
        await vv.transcribe(_real_ogg(tmp_path))


async def test_vault_write_failure_retried_once_never_blocks(tmp_path, monkeypatch):
    """Error mode: first write failure retried once; persistent failure never raises
    (the reply pipeline is never blocked)."""
    vv = _make(tmp_path, model=FakeWhisper())
    real_replace = os.replace
    calls: list[Path] = []

    def flaky(src, dst):
        calls.append(Path(dst))
        if len(calls) == 1:
            raise OSError("busy")
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", flaky)
    path = await vv.file_note("مذكرة", received_at=RECEIVED_AT, duration_s=2.0)
    assert path.exists() and "مذكرة" in path.read_text(encoding="utf-8")

    monkeypatch.setattr(os, "replace", lambda src, dst: (_ for _ in ()).throw(OSError("down")))
    path2 = await vv.file_note("ثانية", received_at=RECEIVED_AT, duration_s=2.0)
    assert path2 == path  # best-effort path returned; no exception escapes


async def test_same_minute_memo_never_overwritten(tmp_path):
    """Second memo in the same minute gets a numeric suffix, never clobbers."""
    vv = _make(tmp_path, model=FakeWhisper())
    first = await vv.file_note("أول", received_at=RECEIVED_AT, duration_s=1.0)
    second = await vv.file_note("ثاني", received_at=RECEIVED_AT, duration_s=1.0)
    assert first.name == "2026-08-30-1805.md"
    assert second.name == "2026-08-30-1805-2.md"
    assert "أول" in first.read_text(encoding="utf-8")
    assert "ثاني" in second.read_text(encoding="utf-8")
