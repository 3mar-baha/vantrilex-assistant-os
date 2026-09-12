"""Shared voice test helpers (not collected by pytest): Fish-only era.

CANNED_MP3 feeds the ffmpeg transcode path; needs_ffmpeg skips opus tests
where no binary exists. The Edge-TTS Communicate doubles were purged with
the engine (2026-09-12) — nothing here synthesizes speech.
"""

import shutil
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
CANNED_MP3: bytes = (FIXTURES / "canned_voice.mp3").read_bytes()

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
