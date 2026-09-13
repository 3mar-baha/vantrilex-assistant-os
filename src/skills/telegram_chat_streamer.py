"""Progressive chat delivery (skill-telegram-chat-streamer, sprint-2 §2.2).

Placeholder lands immediately; the first streamed delta fires one edit (<250 ms
Audio-TTFT KPI); further deltas coalesce onto the interval; the completed text
lands verbatim as the final edit. A cancel event (owner interjection) stops
consumption with the received partial preserved.

Remediation 1.3 (owner 2026-09-03): the first delta — the transient ack — is
DISPOSABLE. With transient_ack=True the bubble shows the ack for instant
reassurance, then the answer REPLACES it: the ack is dropped from the
accumulated text the moment real answer deltas arrive, so memory, the daily
ledger, and voice synthesis only ever see the answer (audit C-4). If the
stream yields nothing beyond the ack (silent tool lane), the returned reply is
EMPTY — never the ack masquerading as a final answer — and the bubble keeps
the ack; `ack_consumed` lets the shell know which is which.
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
        self.ack_consumed: str | None = None  # set when the first delta was the transient ack
        self.message_id: int | None = None  # the streamed bubble (round-3: post-split edits it)

    async def stream_reply(
        self, deltas: AsyncIterator[str], cancel: asyncio.Event, *, transient_ack: bool = False
    ) -> str:
        try:
            message = await self._bot.send_message(self._chat_id, PLACEHOLDER_AR)
        except Exception as error:  # noqa: BLE001 — any send failure -> aggregate fallback (spec error mode)
            # Placeholder failed -> Sprint-1 aggregate behavior: one send, full text.
            logger.warning("streamer placeholder failed -> aggregate fallback: {}", error)
            return await self._aggregate(deltas, transient_ack=transient_ack)
        self.message_id = message.message_id  # round-3: the shell may re-split this bubble

        pending = ""
        answer = ""  # the durable text: ack-free once answer deltas arrive
        last_text = PLACEHOLDER_AR
        last_edit = perf_counter()
        started = False
        ack_shown = False
        async for delta in deltas:
            if cancel.is_set():
                break
            if transient_ack and not ack_shown:
                ack_shown = True
                self.ack_consumed = delta
                await self._edit(delta, message.message_id)  # instant reassurance
                last_edit = perf_counter()
                last_text = delta
                continue
            if transient_ack and not answer:
                answer = delta  # first answer delta: the ack dies here
            else:
                answer += delta
            pending = answer
            if not pending.strip():
                continue
            if not started or perf_counter() - last_edit >= self._interval:
                await self._edit(pending, message.message_id)
                started = True
                last_edit = perf_counter()
                last_text = pending
        if pending.strip() and pending != last_text:
            await self._edit(pending, message.message_id)  # final verbatim edit
        return answer if transient_ack else pending

    async def _edit(self, text: str, message_id: int) -> None:
        # Phase-6 (Leap 4): bubbles never show expressive tags. Partial tags
        # split across deltas survive until the closing bracket lands (the
        # regex needs the pair), then vanish on the next edit. Display-only:
        # accumulators keep raw text for memory/ledger/voice paths.
        from src.voice import strip_tags

        try:
            await self._bot.edit_message_text(
                strip_tags(text), chat_id=self._chat_id, message_id=message_id
            )
        except TelegramRetryAfter as error:
            self._interval *= 2
            logger.warning("streamer rate-limited -> edit interval doubled: {}", error)

    async def _aggregate(self, deltas: AsyncIterator[str], *, transient_ack: bool = False) -> str:
        parts = [part async for part in deltas]
        if transient_ack and parts:
            self.ack_consumed = parts[0]
            parts = parts[1:]  # the ack is disposable here too
        text = "".join(parts)
        if text.strip():
            from src.voice import strip_tags

            await self._bot.send_message(self._chat_id, strip_tags(text))
        return text
