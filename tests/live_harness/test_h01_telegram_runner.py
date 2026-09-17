"""H01 — Telegram runner: bot token validity + getMe identity (skip-soft)."""

import httpx

from tests.live_harness.conftest import pace, require_env


async def test_telegram_getme_identity():
    token = require_env("TELEGRAM_BOT_TOKEN")
    pace()
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(f"https://api.telegram.org/bot{token}/getMe")
    body = response.json()
    assert body.get("ok") is True
    assert body["result"].get("username"), "bot identity unresolved"
