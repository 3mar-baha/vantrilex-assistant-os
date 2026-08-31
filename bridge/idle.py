"""Idle monitor (sprint-3 3.4 AC12): polls Windows last-input time, offers the owner
a sleep/shutdown choice ONCE per idle window; real activity (below half threshold)
re-arms the latch. The monitor only READS input state — it never acts without an
explicit owner choice."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from loguru import logger

IDLE_OFFER_TEXT_AR = "صرت مدة طويلة بدون استخدام، بدهني أفعل وضع النوم أو إطفاء الجهاز؟"


def windows_last_input_seconds() -> float:
    import ctypes

    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return 0.0
    return max(0.0, (ctypes.windll.kernel32.GetTickCount() - info.dwTime) / 1000.0)


class IdleMonitor:
    def __init__(
        self,
        idle_minutes: float,
        on_idle: Callable[[], Awaitable[None]],
        *,
        source: Callable[[], Awaitable[float]] | None = None,
        poll_seconds: float = 30.0,
    ):
        self._threshold_s = idle_minutes * 60
        self._on_idle = on_idle
        self._source = source or windows_last_input_seconds
        self._poll = poll_seconds

    async def run(self, stop: asyncio.Event) -> None:
        offered = False
        rearm_streak = 0
        while not stop.is_set():
            try:
                idle_s = await self._source()
            except OSError:
                logger.exception("idle source failed — treating machine as active")
                idle_s = 0.0
            if idle_s >= self._threshold_s:
                rearm_streak = 0
                if not offered:
                    offered = True  # latch kept even if the callback fails — no spam
                    try:
                        await self._on_idle()
                    except Exception:  # noqa: BLE001 - a failing callback must not kill the monitor
                        logger.exception("idle callback failed — latch kept")
            elif idle_s < self._threshold_s / 2:
                # a momentary input blip must not re-arm; only SUSTAINED sub-half
                # activity does (two consecutive polls)
                rearm_streak += 1
                if rearm_streak >= 2:
                    offered = False
            else:
                rearm_streak = 0
            try:
                await asyncio.wait_for(stop.wait(), timeout=self._poll)
            except TimeoutError:
                pass
