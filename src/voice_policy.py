"""Fish-only voice policy (Edge purged 2026-09-12): no second voice engine
exists anywhere in `src/` or `requirements.txt`. All live execution and every
test under `tests/suite/` MUST resolve voice through `FishFirstVoice`. This
module is the single enforcement seam.
"""

from __future__ import annotations

import sys

FISH_ONLY = True
BANNED_MODULES = ("edge_tts",)


def assert_no_edge() -> None:
    loaded = [m for m in BANNED_MODULES if m in sys.modules]
    if loaded:
        raise AssertionError(f"Edge-TTS footprint detected in active path: {loaded}")


def fish_lane():
    """Resolve Sara's ONLY voice lane from live Settings (Fish, no fallback)."""
    from src.config import get_settings
    from src.fish_voice import FishFirstVoice, FishVoice

    settings = get_settings()
    if not settings.fish_audio_ready:
        raise RuntimeError("Fish voice unconfigured (no OPENROUTER_API_KEY)")
    return FishFirstVoice(fish=FishVoice.from_settings(settings))
