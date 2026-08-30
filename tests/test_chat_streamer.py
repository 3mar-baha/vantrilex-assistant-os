"""Sprint-2 §2.2 AC5 + error modes: ChatStreamer progressive delivery.

AC5 — first edit <250 ms after stream start, coalesced edits within the interval,
final bubble text exact; owner interjection cancels cleanly with partial text preserved.
Error modes — edit rate-limit doubles the interval; placeholder failure falls back to
the Sprint-1 aggregate reply; stream exception propagates with delivered text intact.
"""

import asyncio
from time import perf_counter

import pytest

from src.skills.telegram_chat_streamer import PLACEHOLDER_AR, ChatStreamer
from tests.conftest import OWNER_ID, wait_until


def _edits(bot) -> list:
    return bot.session.sent("EditMessageText")


async def test_first_edit_within_250ms_ttfb(fake_bot, make_settings):
    """AC5a: placeholder -> immediate edit on first delta (<250 ms TTFT); coalesced
    edits inside the interval; final bubble text exact."""
    bot = fake_bot()

    async def deltas():
        for piece in ("سجّلت", " الموعد", " يوم", " الثلاثاء", " الساعة", " العاشرة"):
            yield piece
            await asyncio.sleep(0.03)

    streamer = ChatStreamer(bot, OWNER_ID, edit_interval_ms=100)
    start = perf_counter()
    final = await streamer.stream_reply(deltas(), asyncio.Event())
    calls = bot.session.calls

    first_edit = next(c for c in calls if c.name == "EditMessageText")
    assert first_edit.at - start < 0.250
    assert calls[0].name == "SendMessage" and calls[0].method.text == PLACEHOLDER_AR

    edits = [c for c in calls if c.name == "EditMessageText"]
    assert 2 <= len(edits) <= 4  # coalesced (never one edit per delta), final included
    assert final == "سجّلت الموعد يوم الثلاثاء الساعة العاشرة"
    assert edits[-1].method.text == final


async def test_owner_interjection_cancels_stream(fake_bot):
    """AC5b: cancel event stops consumption; received text stays in the bubble."""
    bot = fake_bot()
    cancel = asyncio.Event()
    release = asyncio.Event()

    async def deltas():
        yield "أول"
        await release.wait()
        yield "ثاني"

    streamer = ChatStreamer(bot, OWNER_ID, edit_interval_ms=40)
    task = asyncio.create_task(streamer.stream_reply(deltas(), cancel))
    await wait_until(lambda: any(c.method.text == "أول" for c in _edits(bot)))

    cancel.set()
    release.set()
    final = await asyncio.wait_for(task, timeout=2)

    assert final == "أول"
    edit_texts = [c.method.text for c in _edits(bot)]
    assert edit_texts[-1] == "أول"
    assert not any("ثاني" in t for t in edit_texts)


async def test_fast_stream_skips_intermediate_edits(fake_bot):
    """Generation done before the first interval -> first edit then final, nothing between."""
    bot = fake_bot()

    async def deltas():
        for piece in ("جاهز", " تمام"):
            yield piece

    streamer = ChatStreamer(bot, OWNER_ID, edit_interval_ms=750)
    final = await streamer.stream_reply(deltas(), asyncio.Event())

    assert final == "جاهز تمام"
    assert len(_edits(bot)) == 2  # first edit + final edit only


async def test_edit_rate_limit_doubles_interval(fake_bot):
    """Rate-limited edit -> warn + doubled interval for the rest of the stream."""
    bot = fake_bot(rate_limit_edit_indices={2})
    interval_ms = 80

    async def deltas():
        for i in range(8):
            yield f"قلمة{i} "
            await asyncio.sleep(0.04)

    streamer = ChatStreamer(bot, OWNER_ID, edit_interval_ms=interval_ms)
    await streamer.stream_reply(deltas(), asyncio.Event())

    edits = _edits(bot)
    failed = next(c for c in edits if c.error is not None)
    ok_before = [c for c in edits if c.error is None and c.at < failed.at]
    ok_after = [c for c in edits if c.error is None and c.at > failed.at]
    assert ok_before and ok_after
    # the edit that cleared the rate-limit waited at least the doubled interval
    assert ok_after[0].at - ok_before[-1].at >= interval_ms * 2 / 1000 * 0.8


async def test_placeholder_failure_falls_back_to_aggregate(fake_bot):
    """Placeholder send failure -> Sprint-1 aggregate behavior: one message, full text."""
    bot = fake_bot(fail_send_indices={1})

    async def deltas():
        yield "أهلا"
        yield " وسهلا"

    streamer = ChatStreamer(bot, OWNER_ID, edit_interval_ms=40)
    final = await streamer.stream_reply(deltas(), asyncio.Event())

    assert final == "أهلا وسهلا"
    sends = [c for c in bot.session.calls if c.name == "SendMessage"]
    assert len(sends) == 2  # failed placeholder attempt + one aggregate send
    assert sends[-1].method.text == "أهلا وسهلا"
    assert _edits(bot) == []


async def test_stream_exception_propagates_delivered_text_kept(fake_bot):
    """Stream exception propagates (shell maps it to the apology); delivered text stays."""
    bot = fake_bot()

    async def deltas():
        yield "مرئي"
        raise ValueError("upstream blew up")

    streamer = ChatStreamer(bot, OWNER_ID, edit_interval_ms=40)
    with pytest.raises(ValueError):
        await streamer.stream_reply(deltas(), asyncio.Event())

    edit_texts = [c.method.text for c in _edits(bot)]
    assert "مرئي" in edit_texts


async def test_whitespace_only_stream_never_edits_bubble(fake_bot):
    """Whitespace-only deltas never trigger edits; the fallback decision stays with the shell."""
    bot = fake_bot()

    async def deltas():
        yield " "
        yield ""

    final = await ChatStreamer(bot, OWNER_ID, edit_interval_ms=40).stream_reply(
        deltas(), asyncio.Event()
    )

    assert final == " "
    assert _edits(bot) == []


async def test_plain_text_no_parse_mode(fake_bot):
    """Plain-text ruling: neither placeholder nor edits carry a parse_mode."""
    bot = fake_bot()

    async def deltas():
        yield "*not* _markdown_"
        yield " [link](x)"

    final = await ChatStreamer(bot, OWNER_ID, edit_interval_ms=40).stream_reply(
        deltas(), asyncio.Event()
    )

    assert final == "*not* _markdown_ [link](x)"
    for call in bot.session.sent("SendMessage") + bot.session.sent("EditMessageText"):
        assert not isinstance(getattr(call.method, "parse_mode", None), str)
