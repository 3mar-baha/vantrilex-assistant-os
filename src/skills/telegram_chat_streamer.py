"""Progressive chat delivery (skill-telegram-chat-streamer, sprint-2 §2.2).

Placeholder lands immediately; the first streamed delta fires one edit (<250 ms
Audio-TTFT KPI); further deltas coalesce onto the interval; the completed text
lands verbatim as the final edit. A cancel event (owner interjection) stops
consumption with the received partial preserved.
"""

import asyncio
from collections.abc import AsyncIterator
from time import perf_counter
from typing import Final

from aiogram.exceptions import TelegramRetryAfter
from loguru import logger

PLACEHOLDER_AR: Final[str] = "…"


class ChatStreamer:
    def __init__(self, bot, chat_id: int, *, edit_interval_ms: int = 750) -> None:
        self._bot = bot
        self._chat_id = chat_id
        self._interval = edit_interval_ms / 1000

    async def stream_reply(self, deltas: AsyncIterator[str], cancel: asyncio.Event) -> str:
        try:
            message = await self._bot.send_message(self._chat_id, PLACEHOLDER_AR)
        except Exception as error:  # noqa: BLE001 — any send failure -> aggregate fallback (spec error mode)
            # Placeholder failed -> Sprint-1 aggregate behavior: one send, full text.
            logger.warning("streamer placeholder failed -> aggregate fallback: {}", error)
            return await self._aggregate(deltas)

        pending = ""
        last_text = PLACEHOLDER_AR
        last_edit = perf_counter()
        started = False
        async for delta in deltas:
            if cancel.is_set():
                break
            pending += delta
            if not pending.strip():
                continue
            if not started or perf_counter() - last_edit >= self._interval:
                await self._edit(pending, message.message_id)
                started = True
                last_edit = perf_counter()
                last_text = pending
        if pending.strip() and pending != last_text:
            await self._edit(pending, message.message_id)  # final verbatim edit
        return pending

    async def _edit(self, text: str, message_id: int) -> None:
        try:
            await self._bot.edit_message_text(text, chat_id=self._chat_id, message_id=message_id)
        except TelegramRetryAfter as error:
            self._interval *= 2
            logger.warning("streamer rate-limited -> edit interval doubled: {}", error)

    async def _aggregate(self, deltas: AsyncIterator[str]) -> str:
        text = "".join([part async for part in deltas])
        if text.strip():
            await self._bot.send_message(self._chat_id, text)
        return text
