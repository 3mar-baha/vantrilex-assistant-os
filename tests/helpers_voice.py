"""Shared voice-pipeline test helpers (not collected by pytest)."""

import asyncio
import shutil
import time
from pathlib import Path
from typing import ClassVar

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
CANNED_MP3: bytes = (FIXTURES / "canned_voice.mp3").read_bytes()

needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")


class FakeCommunicate:
    """Mimics edge_tts.Communicate: records init kwargs; stream() scripted via _script()."""

    instances: ClassVar[list["FakeCommunicate"]] = []

    def __init__(self, text: str, voice: str, rate: str = "+0%", pitch: str = "+0Hz") -> None:
        self.text = text
        self.voice = voice
        self.rate = rate
        self.pitch = pitch
        FakeCommunicate.instances.append(self)

    async def stream(self):  # pragma: no cover - scripted by _script()
        raise NotImplementedError


def _script(events: list):
    """Build a Communicate subclass streaming the given events; floats are sleeps.
    Records producer completion time on .done_at (set when the generator finishes)."""

    class _Scripted(FakeCommunicate):
        done_at: float | None = None

        async def stream(self):
            for event in events:
                if isinstance(event, float):
                    await asyncio.sleep(event)
                else:
                    yield event
            self.done_at = time.monotonic()

    return _Scripted
