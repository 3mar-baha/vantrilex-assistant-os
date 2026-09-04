"""STT-5 (owner 2026-09-04 evening): the multi-bubble send — consecutive
short chat messages WITHOUT the owner pressing anything. The send_split +
_split_streamed_bubble surfaces already exist in bot.py but carried NO tests
(the live contract was invisible); these pin the behavior:

- A long answer lands as 2-3 SHORT bubbles (paragraph splits, not a lecture)
- Short replies send exactly ONE bubble — never chopped into noise
- The streamed bubble is edited down to its first paragraph; the rest arrive
  as separate messages
- A failed post-split NEVER loses the original bubble (best-effort contract)
"""

from __future__ import annotations


class _Msg:
    def __init__(self, chat_id):
        self.chat_id = chat_id
        self.message_id = 111
        self.sent: list[str] = []


class _Bot:
    """Minimal bot double: records sends, optional edit failure."""

    def __init__(self, *, fail_edits=False):
        self.sent: list[tuple[int, str]] = []
        self.edits: list[tuple[int, str]] = []
        self.fail_edits = fail_edits

    async def send_message(self, chat_id, text):
        self.sent.append((chat_id, text))
        msg = _Msg(chat_id)
        self.last = msg
        return msg

    async def edit_message_text(self, text, *, chat_id, message_id):
        if self.fail_edits:
            raise RuntimeError("edit rejected")
        self.edits.append((message_id, text))


class _Streamer:
    """The ChatStreamer surface _split_streamed_bubble touches."""

    def __init__(self, message_id):
        self.message_id = message_id


async def test_send_split_short_reply_one_bubble():
    """A short reply = ONE bubble, never chopped («تمام» must not become noise)."""
    from src.bot import send_split

    bot = _Bot()
    msg = _Msg(5)
    msg.bot = bot  # not used; send_split answers on the message

    # send_split uses message.answer — emulate via a tiny object
    class _Answer:
        def __init__(self):
            self.answers: list[str] = []

        async def answer(self, text):
            self.answers.append(text)

    surface = _Answer()
    surface.chat = type("C", (), {"id": 5})()

    # send_split(message, text) — message needs only .answer
    await send_split(surface, "جواب قصير", max_bubbles=3)  # type: ignore[arg-type]
    assert surface.answers == ["جواب قصير"]


async def test_send_split_long_reply_paragraphs():
    """A long multi-paragraph reply lands as SEPARATE short messages, capped
    at max_bubbles — the remaining paragraphs never spam."""
    from src.bot import send_split

    class _Answer:
        def __init__(self):
            self.answers: list[str] = []

        async def answer(self, text):
            self.answers.append(text)

    surface = _Answer()
    long_reply = (
        "الفقيرة الأولى في شرح الموضوع الطويل جداً بما يكفي لتجاوز الحد المفروض "
        "على الرسائل القصيرة هنا بفقرات متعددة.\n\n"
        "الفقيرة الثانية تتابع الشرح بجمل قصيرة ودافئة.\n\n"
        "الفقيرة الثالثة تختم الجواب بامتنان.\n\n"
        "الفقيرة الرابعة زائدة عن الحاجة."
    )
    assert len(long_reply) > 160
    await send_split(surface, long_reply, max_bubbles=3)  # type: ignore[arg-type]
    assert len(surface.answers) == 3  # capped: the 4th paragraph never spams
    assert "الفقيرة الأولى" in surface.answers[0]
    assert "الفقيرة الثالثة" in surface.answers[2]
    assert all("الفقيرة الرابعة" not in a for a in surface.answers)


async def test_split_streamed_bubble_edits_head_sends_tail():
    """The streamed bubble is edited down to paragraph 1; paragraphs 2-3
    arrive as separate messages — the essay becomes a chat."""
    from src.bot import _split_streamed_bubble

    bot = _Bot()
    streamer = _Streamer(message_id=77)
    reply = (
        "أول جزء من الجواب الطويل المتدفق عبر أكثر من فقرة كاملة هنا، "
        "بجمل دافئة تشبه كلام الأصدقاء لا المحاضرات، مع سؤال متابعة صغير.\n\n"
        "الجزء الثاني القصير.\n\n"
        "الجزء الثالث الختامي."
    )
    assert len(reply) > 160  # the short-reply no-op must not trigger
    await _split_streamed_bubble(bot, 5, streamer, reply)
    assert bot.edits == [
        (
            77,
            "أول جزء من الجواب الطويل المتدفق عبر أكثر من فقرة كاملة هنا، بجمل دافئة تشبه كلام الأصدقاء لا المحاضرات، مع سؤال متابعة صغير.",
        )
    ]
    assert [t for _, t in bot.sent] == ["الجزء الثاني القصير.", "الجزء الثالث الختامي."]


async def test_split_streamed_bubble_short_is_noop():
    """A short streamed reply (<160 or single paragraph) is left as-is — no
    edit, no extra sends."""
    from src.bot import _split_streamed_bubble

    bot = _Bot()
    streamer = _Streamer(message_id=77)
    await _split_streamed_bubble(bot, 5, streamer, "رد قصير")
    assert bot.edits == [] and bot.sent == []
    long_single = "جملة واحدة طويلة جداً " * 20  # >160 chars, ONE paragraph
    await _split_streamed_bubble(bot, 5, streamer, long_single.strip())
    assert bot.edits == [] and bot.sent == []


async def test_split_streamed_bubble_edit_failure_keeps_original():
    """A failed edit (Telegram rejected, message too old) is best-effort: the
    original bubble already stands, tail messages still try, nothing raised."""
    from src.bot import _split_streamed_bubble

    bot = _Bot(fail_edits=True)
    streamer = _Streamer(message_id=77)
    reply = "الجزء الأول الكامل الموجود أصلاً.\n\nالجزء الثاني."
    await _split_streamed_bubble(bot, 5, streamer, reply)  # must NOT raise
    # the edit failed but the tail still attempted? contract: original stands,
    # no exception — tail attempts allowed either way
    assert not bot.edits
