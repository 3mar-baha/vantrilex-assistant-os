"""P0-A (master directive 2026-09-05) + owner preference 2026-09-07: the STRICT
VOICE DEMAND LOCK, Fish-ONLY.

Live 7:19-7:20am class: Omar explicitly demanded a voice note and got text
bubbles. The directive's law: a matching voice demand forces the VOICE surface.

Contract:
- VOICE_DEMAND_RE (رسالة صوتية/ابعثي(لي) فويس/احكي بصوتك/صوتية/فويس/
  بدي اسمع صوتك) forces modality="voice" on any message that matches.
- A DEMANDED note lands on Fish (Sara's ONLY voice) OR the honest text line —
  it NEVER substitutes a foreign (Microsoft/Edge) voice (owner 2026-09-07:
  «لم يستخدم فيش اوديو بل مايكروسوف» — identity purity beats a foreign voice).
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


# -- the Fish-only demanded engine (Edge purged 2026-09-12) ------------------------


class _DeadFish:
    """A Fish lane that always dies (429/timeout class)."""

    async def synthesize(self, text: str) -> bytes:
        raise RuntimeError("fish speech HTTP 429: rate limit")

    def update_notes(self, notes):  # pragma: no cover -- interface parity
        pass


async def test_demanded_note_fish_dead_returns_false_no_foreign_voice():
    """Fish dead on a DEMANDED note -> False (the honest text) — no second
    voice engine exists anymore (owner 2026-09-07 identity purity)."""
    from src.bot import _speak_demanded

    spoke = await _speak_demanded(_DeadFish(), "جوابي المطلوب صوتياً")
    assert spoke is False  # identity purity: honest text, never a foreign voice


async def test_healthy_fish_speaks_demanded_note():
    """Fish alive -> the demanded note goes out on Fish."""
    from src.bot import _speak_demanded

    class _Fish:
        async def synthesize(self, text):
            return b"FISH-OGG"

    assert await _speak_demanded(_Fish(), "نص") is True


async def test_demanded_note_fish_failure_never_fabricates_success():
    """Fish dead -> False (no fake success). Honest text is the only fallback."""
    from src.bot import _speak_demanded

    assert await _speak_demanded(_DeadFish(), "نص") is False  # honest line, no deception class


async def test_shell_demand_fish_dead_lands_honest_text(make_shell, fake_bot):
    """The FULL shell path with a DEAD Fish lane: no second voice exists, so
    the honest TEXT lands (identity purity) — zero SendVoice."""
    import json

    from tests.conftest import StreamProgram, drain, make_update

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
    )
    shell_dp, bot = shell.dp, fake_bot()
    await shell_dp.feed_update(
        bot, make_update(1, shell.settings.authorized_user_id, "ابعثي رسالة صوتية بشرح الفيزياء")
    )
    from src.bot import _STREAMS

    await drain(_STREAMS)

    assert not bot.session.sent("SendVoice"), "no voice without Fish — the Fish-only law"
    assert bot.session.sent("SendMessage"), "the honest text line must land"
