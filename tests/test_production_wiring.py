"""Remediation 3.1 (owner-promised loops never launched): the production wiring
must start FOUR background loops — morning brief, evening journaler, gmail
poll, daily summary — and cancel every one on shutdown. The stitch point
`start_background_loops` is testable without polling."""

from __future__ import annotations

import asyncio

from src.bot import start_background_loops


class _LoopSpy:
    """Records run_forever launches; never completes on its own (a real loop)."""

    launched = 0

    async def run_forever(self) -> None:
        _LoopSpy.launched += 1
        while True:
            await asyncio.sleep(3600)

    @classmethod
    def reset(cls) -> None:
        cls.launched = 0


class _PollSpy:
    launched = 0

    async def __call__(self, inbox, dispatcher, classifier, settings) -> None:
        _PollSpy.launched += 1
        while True:
            await asyncio.sleep(3600)

    @classmethod
    def reset(cls) -> None:
        cls.launched = 0


def _rig(make_settings, **env):
    _LoopSpy.reset()
    _PollSpy.reset()
    settings = make_settings(**env)
    return (
        {
            "brief": _LoopSpy(),
            "journaler": _LoopSpy(),
            "summarizer": _LoopSpy(),
        },
        _PollSpy(),
        settings,
    )


async def test_four_loops_created_and_cancelled_on_shutdown(make_settings):
    """Brief + journaler + gmail poll + daily summary: all four tasks live,
    all cancelled in the finally — no orphan loops, no missed owner promises."""
    loops, poll, settings = _rig(make_settings)
    tasks = start_background_loops(
        brief=loops["brief"],
        journaler=loops["journaler"],
        summarizer=loops["summarizer"],
        gmail_poll=poll,
        inbox=object(),
        dispatcher=object(),
        classifier=object(),
        settings=settings,
    )
    try:
        assert len(tasks) == 4  # four loops: brief + journaler + summary + gmail
        assert all(not t.done() for t in tasks)  # all alive
        await asyncio.sleep(0.05)  # let them enter their loops
        assert _LoopSpy.launched == 3  # brief + journaler + summarizer entered
        assert _PollSpy.launched == 1  # gmail poll entered
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    assert all(t.cancelled() or t.done() for t in tasks)  # every loop reaped


async def test_brief_disabled_blocks_only_the_brief(make_settings):
    """BRIEF_ENABLED=false → three loops, the brief never launches; the other
    promises (journaler, summary, gmail) stay live."""
    loops, poll, settings = _rig(make_settings, BRIEF_ENABLED="false")
    tasks = start_background_loops(
        brief=loops["brief"],
        journaler=loops["journaler"],
        summarizer=loops["summarizer"],
        gmail_poll=poll,
        inbox=object(),
        dispatcher=object(),
        classifier=object(),
        settings=settings,
    )
    try:
        await asyncio.sleep(0.05)
        assert _LoopSpy.launched == 2  # journaler + summarizer only
        assert _PollSpy.launched == 1
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def test_no_gmail_stack_degrades_to_three_loops(make_settings):
    """Google stack offline (inbox None) → the gmail poll never starts; the
    chat promises (journaler, summary) + brief still run."""
    loops, poll, settings = _rig(make_settings)
    tasks = start_background_loops(
        brief=loops["brief"],
        journaler=loops["journaler"],
        summarizer=loops["summarizer"],
        gmail_poll=poll,
        inbox=None,  # degraded boot: no Google creds
        dispatcher=object(),
        classifier=object(),
        settings=settings,
    )
    try:
        await asyncio.sleep(0.05)
        assert len(tasks) == 3  # no gmail task
        assert _LoopSpy.launched == 3
        assert _PollSpy.launched == 0  # poll never called
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
