"""Owner-only outer gate (ADR-06 / discovery ruling 3): silent drop, no reply.

Registered on ``dp.update.outer_middleware`` so it runs for EVERY update type
before any filter, handler, or outbound call exists — dropped updates never
generate a single Telegram API request.
"""

import time
from typing import Final

from aiogram.dispatcher.middlewares.base import BaseMiddleware
from aiogram.types import TelegramObject, Update
from loguru import logger

_EVENT_FIELDS: Final = (
    "message",
    "edited_message",
    "channel_post",
    "edited_channel_post",
    "callback_query",
    "inline_query",
)


def _extract_user_id(update: Update) -> int | None:
    """First populated update event's ``from_user.id``; None when absent/anonymous."""
    for field in _EVENT_FIELDS:
        event = getattr(update, field, None)
        user = getattr(event, "from_user", None)
        if user is not None:
            return user.id
    return None


class OwnerOnlyMiddleware(BaseMiddleware):
    def __init__(self, owner_id: int) -> None:
        self._owner_id = owner_id

    async def __call__(self, handler, event: TelegramObject, data: dict):
        update = event if isinstance(event, Update) else getattr(event, "update", event)
        user_id = _extract_user_id(update)
        if user_id != self._owner_id:
            logger.bind(update_id=getattr(update, "update_id", None)).debug(
                "owner gate: dropped non-owner update (silent)"
            )
            return None
        note_owner_event()
        return await handler(event, data)


_LAST_OWNER_EVENT_TS: float | None = None


def note_owner_event(*, now_fn=time.time) -> None:
    """Stamp the latest owner ingress (epoch seconds). Single stamp
    point for reconnect-greeting recency, idle monitors, and diagnostics —
    stranger updates never touch it."""
    global _LAST_OWNER_EVENT_TS
    _LAST_OWNER_EVENT_TS = now_fn()


def last_owner_event_ts() -> float | None:
    """Monotonic timestamp of the last owner update, None when never."""
    return _LAST_OWNER_EVENT_TS
