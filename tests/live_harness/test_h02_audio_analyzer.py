"""H02 — Audio analyzer: Fish speech endpoint serves real audio (skip-soft)."""

import httpx

from tests.live_harness.conftest import require_env, require_gateway


async def test_fish_speech_serves_audio():
    require_gateway()
    key = require_env("FISH_AUDIO_API_KEY")
    payload = {
        "model": "fish-audio/s2.1-pro-free:free",
        "input": "مرحبا عمر",
        "voice": "sam",
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/audio/speech",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload,
        )
    assert response.status_code == 200, f"speech HTTP {response.status_code}"
    assert len(response.content) > 1000, "audio payload implausibly small"
