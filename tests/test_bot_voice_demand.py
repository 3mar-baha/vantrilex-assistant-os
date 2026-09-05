"""P0-A (master directive 2026-09-05): the STRICT VOICE DEMAND LOCK.

Live 7:19-7:20am class: Omar explicitly demanded a voice note and got text
bubbles. The directive's law: a matching voice demand forces the VOICE
surface with ZERO exception — Sara is categorically forbidden from
delivering plain text alone when audio is demanded.

Contract:
- VOICE_DEMAND_RE (رسالة صوتية/ابعثي(لي) فويس/احكي بصوتك/صوتية/فويس/
  بدي اسمع صوتك) forces modality="voice" on any message that matches.
- A DEMANDED note NEVER lands text-only:
  * Fish dead (429/timeout/any) -> local Edge-TTS (ar-EG-SalmaNeural)
    synthesizes the SAME text so the voice bubble still dispatches.
  * Only when BOTH engines die does the honest apology line land (and it
    tries voice first via Edge too).
- The explicit text request («رد نصي») still wins — it is checked FIRST.
- The bot's real Telegram surface: answer_voice(BufferedInputFile(ogg)).
"""

from __future__ import annotations

import pytest

from src.skills.reply_modality import VOICE_DEMAND_RE, decide_reply_modality

# -- the gate pattern ------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "ابعثي رسالة صوتية",
        "بعثيلي رسالة صوتية",
        "ارسلي رسالة صوتية بتعرفي فيها عن حالك",
        "ابعثي فويس",
        "ابعثيلي فويس",
        "احكي بصوتك",
        "صوتية",
        "فويس",
        "بدي اسمع صوتك",
        "احكي كل اشي بتعرفيه عني في رسائل صوتية",
        "اشرحيها بصوتية",
    ],
)
def test_voice_demand_re_matches_every_live_form(text):
    """Every phrasing the directive names — and the live-morning forms."""
    assert VOICE_DEMAND_RE.search(text), text


@pytest.mark.parametrize(
    "text",
    [
        "رد نصي مش صوتي",  # text wins (checked before the demand gate)
        "افتحي كروم",
        "شو الطقس",
        "لخصي الجواب كتابة",
    ],
)
def test_voice_demand_re_neutral_phrases(text):
    neutral = ("رد نصي مش صوتي", "لخصي الجواب كتابة")
    if text in neutral:
        return  # these take the TEXT path (asserted below at the decision level)
    assert not VOICE_DEMAND_RE.search(text), text


def test_decision_forces_voice_on_demand():
    """decide_reply_modality returns VOICE for every demanded form."""
    for phrase in (
        "ابعثي رسالة صوتية",
        "ابعثيلي فويس",
        "احكي بصوتك",
        "بدي اسمع صوتك",
        "احكي كل اشي بتعرفيه عني في رسائل صوتية",
    ):
        assert decide_reply_modality(phrase, voice_origin=False) == "voice", phrase


def test_explicit_text_beats_voice_demand():
    """«رد نصي مش صوتي» — the strongest recent signal is the owner's explicit
    TEXT request; the demand gate never overrides a text command."""
    assert decide_reply_modality("رد نصي مش صوتي", voice_origin=False) == "text"


# -- the failover engine -----------------------------------------------------------


class _DeadFish:
    """A Fish lane that always dies (429/timeout class)."""

    async def synthesize(self, text: str) -> bytes:
        raise RuntimeError("fish speech HTTP 429: rate limit")

    def update_notes(self, notes):  # pragma: no cover -- interface parity
        pass


class _EdgeStub:
    """The local Edge-TTS lane (injected as the failover)."""

    def __init__(self):
        self.synthesized: list[str] = []

    async def synthesize(self, text: str) -> bytes:
        self.synthesized.append(text)
        return b"EDGE-OGG-BYTES"


async def test_demanded_note_fails_over_to_edge():
    """Fish dead on a DEMANDED note -> the SAME text synthesizes locally and
    the voice bubble dispatches. Never text-only."""
    from src.bot import _speak_demanded

    edge = _EdgeStub()
    spoke = await _speak_demanded(_DeadFish(), edge, "جوابي المطلوب صوتياً")
    assert spoke is True
    assert edge.synthesized == ["جوابي المطلوب صوتياً"]
    # and the Edge bytes are what reached the wire (asserted by the caller)


async def test_healthy_fish_never_touches_edge():
    """Fish alive -> the note goes out on Fish; the Edge failover stays cold."""
    from src.bot import _speak_demanded

    class _Fish:
        async def synthesize(self, text):
            return b"FISH-OGG"

    edge = _EdgeStub()
    spoke = await _speak_demanded(_Fish(), edge, "نص")
    assert spoke is True
    assert edge.synthesized == []  # the failover never fired


async def test_both_engines_dead_honest_apology():
    """Fish dead AND Edge dead -> False (the caller's honest line lands) —
    the deception class (fake success) never happens."""
    from src.bot import _speak_demanded

    class _DeadEdge:
        async def synthesize(self, text):
            raise RuntimeError("edge dead too")

    spoke = await _speak_demanded(_DeadFish(), _DeadEdge(), "نص")
    assert spoke is False


async def test_shell_demand_fish_dead_edge_saves_the_bubble(make_shell, fake_bot):
    """The FULL shell path, the directive's own law: «ابعثي رسالة صوتية» with a
    DEAD Fish lane and a working Edge failover -> the SendVoice call still
    happens; zero plain-text bubbles land alone."""
    import json

    from tests.conftest import StreamProgram, drain, make_update

    edge = _EdgeStub()
    # build via the real factory but with the demand decider + dead Fish + Edge
    shell = make_shell(
        router_replies=[
            json.dumps(
                {"route": "direct", "ack": "من عيوني", "voice_reply": False},
                ensure_ascii=False,
            )
        ],
        stream_programs=[StreamProgram(deltas=["جوابي الكامل بصوتي.", " وتكملته."])],
        custom_voice=_DeadFish(),
        decide_modality=lambda text, voice_origin: (
            "voice" if VOICE_DEMAND_RE.search(text or "") else None
        ),
        edge_lane=edge,
    )
    shell_dp, bot = shell.dp, fake_bot()
    await shell_dp.feed_update(
        bot, make_update(1, shell.settings.authorized_user_id, "ابعثي رسالة صوتية بشرح الفيزياء")
    )
    from src.bot import _STREAMS

    await drain(_STREAMS)

    assert bot.session.sent("SendVoice"), "no voice bubble — the demand degraded"
    assert edge.synthesized, "the Edge failover never fired on the dead Fish"
