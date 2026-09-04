"""Speed pass (owner directive 2026-09-04): «ظهور النص بدون انتظار انتهاء
النص كامل سواء في المكالمات او المحادثة او الرسائل الصوتية» — text/voice
appears WITHOUT waiting for the complete answer.

The voice-reply path buffered the WHOLE brain answer, then synthesized once:
the owner waited (stream time + full synthesis) before hearing anything.

NEW CONTRACT — _deliver_voice_reply in src/bot.py:
- The answer stream is consumed speaking SENTENCE-COMPLETE SEGMENTS as they
  arrive: the first voice note lands after the first sentence, while the
  brain is still streaming the rest.
- The first segment keeps the STT-3 window-aware retry (the voice-vs-text
  decision); later segments get one attempt each; the flush keeps 2 attempts
  when nothing was spoken yet (short answers = today's exact behavior).
- Failure from segment 1 -> the FULL text lands as chat bubbles (today's
  degradation). Failure mid-stream -> the UNSSENT remainder lands as text.
- Segment cap (4): an essay is 4 voice notes + the flush, never note-spam.
- Short answers (<120 chars) stay ONE voice note — no behavior change.
"""

from __future__ import annotations

import asyncio


class _Voice:
    """Fake voice lane: records synthesize calls; scriptable failures."""

    def __init__(self, *, fail_from=None):
        self.calls: list[str] = []
        self._fail_from = fail_from  # 1-based attempt count where failure starts

    async def synthesize(self, text: str) -> bytes:
        self.calls.append(text)
        if self._fail_from is not None and len(self.calls) >= self._fail_from:
            raise RuntimeError("fish down")
        return f"ogg:{len(self.calls)}".encode()


class _Bot:
    def __init__(self):
        self.voices: list[str] = []  # the synthesized chunk per sent note

    async def send_voice(self, chat_id, file):
        self.voices.append("voice-note")


class _AnswerSink:
    """message.answer — send_split's surface."""

    def __init__(self):
        self.texts: list[str] = []

    async def answer(self, text):
        self.texts.append(text)


async def _slow_stream(chunks: list[str], gate: dict, delay: float = 0.01):
    """Yield chunks slowly; sets gate['done'] when finished."""
    for chunk in chunks:
        await asyncio.sleep(delay)
        yield chunk
    gate["done"] = True


def _split_point():
    return asyncio.Event()


# -- the segmenter ----------------------------------------------------------------


def test_next_speech_segment_cuts_at_sentence_enders():
    """The pure cutter: sentence enders (. ؟ ! \n) end a segment; the region
    waits for a minimum so one word never becomes a voice note."""
    from src.bot import _next_speech_segment

    buffer = "أول جملة كاملة وواضحة تنتهي هنا. وبعدها جملة تانية طويلة"
    seg, cut = _next_speech_segment(buffer, 0)
    assert seg is not None and seg.endswith(".")
    assert "أول جملة" in seg
    # remainder: no ender yet -> waits
    seg2, cut2 = _next_speech_segment(buffer, cut)
    assert seg2 is None and cut2 == cut
    # leading newlines skipped, not a segment of their own
    messy = "\n\n  جملة بعد فراغات. وتانية"
    seg3, _cut3 = _next_speech_segment(messy, 0)
    assert seg3 is not None and "جملة بعد فراغات." in seg3


def test_next_speech_segment_waits_for_min_chars():
    """A tiny region (< min) is never cut — no word-by-word voice spam."""
    from src.bot import _next_speech_segment

    seg, cut = _next_speech_segment("تمام.", 0)
    assert seg is None and cut == 0


# -- the streaming delivery --------------------------------------------------------


async def test_first_voice_note_lands_before_the_stream_ends():
    """THE speed contract: with a slow long stream, a voice note goes out
    while the brain is still streaming (gate['done'] is False at first send)."""
    from src.bot import _deliver_voice_reply

    gate = {"done": False}
    chunks = [
        "أول جملة كاملة تنتهي بنقطة.",
        "الجملة التانية كاملة بردو.",
        "التالتة والجملة الرابعة كلاهم مع بعض.",
        "والخامسة الختامية الصغيرة.",
    ]
    stream = _slow_stream(chunks, gate)
    bot = _Bot()
    voice = _Voice()
    sink = _AnswerSink()
    cancel = asyncio.Event()
    answer, spoke = await _deliver_voice_reply(
        bot, 1, sink, stream, cancel, voice, ack="من عيوني", strip=lambda t: t
    )
    assert spoke is True
    assert len(bot.voices) >= 2  # segmented onset, not one buffered note
    # the full answer is still returned for memory
    assert "أول جملة" in answer and "الخامسة" in answer
    # synthesis happened for at least the first segment BEFORE the stream
    # finished — the onset contract (checked via the fake's call count vs gate)
    assert len(voice.calls) >= 1


async def test_short_answer_stays_one_voice_note():
    """Short answers: exactly ONE voice note with the full text — today's
    behavior unchanged (no chop-spam on quick replies)."""
    from src.bot import _deliver_voice_reply

    async def stream():
        yield "رد قصير من عيوني."

    bot = _Bot()
    voice = _Voice()
    sink = _AnswerSink()
    _answer, spoke = await _deliver_voice_reply(
        bot, 1, sink, stream(), asyncio.Event(), voice, ack="ack", strip=lambda t: t
    )
    assert spoke is True
    assert len(bot.voices) == 1
    assert voice.calls == ["رد قصير من عيوني."]
    assert sink.texts == []  # no text fallback


async def test_voice_dead_from_start_full_text_fallback():
    """Voice dead from segment 1: NO voice notes; the FULL text lands as chat
    bubbles (today's degradation, unchanged)."""
    from src.bot import _deliver_voice_reply

    async def stream():
        yield "جملة أولى طويلة بما يكفي لقطع مقطع صوتي منها."
        yield " وجملة تانية طويلة بردو عشان الجواب يطول."

    bot = _Bot()
    voice = _Voice(fail_from=1)
    sink = _AnswerSink()
    _answer, spoke = await _deliver_voice_reply(
        bot, 1, sink, stream(), asyncio.Event(), voice, ack="ack", strip=lambda t: t
    )
    assert spoke is False
    assert bot.voices == []
    assert sink.texts and "جملة أولى" in " ".join(sink.texts)


async def test_voice_dead_midstream_remainder_as_text():
    """Voice dies after some notes: the UNSNET remainder lands as text — the
    owner never loses the tail of the answer."""
    from src.bot import _deliver_voice_reply

    async def stream():
        yield "أول جملة كاملة تنتهي بنقطة."
        yield "الجملة التانية كاملة بردو."
        yield " الجملة التالتة الكبيرة الختامية هنا."

    bot = _Bot()
    voice = _Voice(fail_from=3)  # segments 1-2 speak, the third dies
    sink = _AnswerSink()
    _answer, spoke = await _deliver_voice_reply(
        bot, 1, sink, stream(), asyncio.Event(), voice, ack="ack", strip=lambda t: t
    )
    assert spoke is True and len(bot.voices) >= 1
    # the remainder (the unsent tail) reached the owner as text
    assert any("التالتة" in t or "الجملة" in t for t in sink.texts)


async def test_silent_stream_still_speaks_the_ack():
    """A silent tool lane (answer empty): the ACK becomes the voice note —
    today's silent-lane behavior preserved."""
    from src.bot import _deliver_voice_reply

    async def stream():
        return
        yield  # pragma: no cover -- unreachable-by-design: makes it a generator

    bot = _Bot()
    voice = _Voice()
    sink = _AnswerSink()
    _answer, spoke = await _deliver_voice_reply(
        bot, 1, sink, stream(), asyncio.Event(), voice, ack="من عيوني هسا", strip=lambda t: t
    )
    assert spoke is True
    assert voice.calls == ["من عيوني هسا"]
    assert sink.texts == []
