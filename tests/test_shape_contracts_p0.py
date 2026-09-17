"""P0 shape contracts (master transformation plan, Phase P0).

Additive twins alongside the exact-string originals (which stay frozen this
phase): each `_shape` test asserts the structural contract — script range,
length bounds, required slots, ban-list absence — so P4 directive-driven
wording passes without touching safety semantics. Denylist files
(owner/guest/whitelist/paid-guard) are NOT referenced here by design.
Streamer echo asserts (fixture-in/fixture-out concatenation) are mechanical
plumbing, not presentation contracts, and are explicitly excluded.
"""

import re
from datetime import UTC, datetime

import httpx

from src.bot import EMPTY_VOICE_AR
from src.daily_brief import BriefComposer, BriefData
from src.dispatcher import (
    _ACK_CLAIM_WORDS,
    _ACK_IDENTITY_WORDS,
    DEFAULT_ACK_AR,
    MAX_ACK_CHARS,
    FrontDoorDispatcher,
)
from src.email_triage import EXCERPT_MAX_CHARS, render_semi, render_voice_script
from src.gmail import EmailMessage
from src.skills.evening_journaler import EveningJournaler, LedgerData
from tests.conftest import OWNER_ID, StreamProgram, make_update
from tests.test_bot_shell import _router, _run
from tests.test_dispatcher import _collect, _gateway, _router_json
from tests.test_omniroute_gateway import _chunk, _Scripted, _sse

AR_CONTAINS = re.compile(r"[\u0600-\u06FF]")


def _clean_ack_shape(text: str) -> None:
    assert len(text) <= MAX_ACK_CHARS, f"ack over budget: {text!r}"
    assert AR_CONTAINS.search(text), f"ack carries no Arabic: {text!r}"
    assert not any(w in text for w in _ACK_IDENTITY_WORDS), f"identity leak: {text!r}"
    assert not any(w in text for w in _ACK_CLAIM_WORDS), f"claimed action: {text!r}"


def _msg(**over) -> EmailMessage:
    base = {
        "id": "m1",
        "thread_id": "t1",
        "from_email": "laila@family.jo",
        "from_name": "ليلى",
        "subject": "عزومة عشا",
        "body_text": "تعالي بكرا المسا " * 60,
        "received_at": datetime(2026, 9, 16, 12, 0, tzinfo=UTC),
    }
    base.update(over)
    return EmailMessage(**base)


async def test_ack_clean_shape_p0(make_settings):
    """Scripted clean Jordanian ack surfaces verbatim AND satisfies guard shape."""
    script = _Scripted(
        httpx.Response(200, content=_sse(_router_json("direct", "من عيوني هسا"))),
        httpx.Response(200, content=_sse(_chunk("الجواب"))),
    )
    async with _gateway(script) as client:
        out = await _collect(FrontDoorDispatcher(client, make_settings()).handle("طلب عادي"))
    assert out[0] == "من عيوني هسا"
    _clean_ack_shape(out[0])


async def test_ack_drift_shape_p0(make_settings):
    """A drifted mini-answer ack collapses to the default, which is short."""
    drifted = "أكيد، رح أجهزلك تقرير مفصل عن كل شي طلبته بالتفصيل الممل"
    script = _Scripted(
        httpx.Response(200, content=_sse(_router_json("direct", drifted))),
        httpx.Response(200, content=_sse(_chunk("الجواب"))),
    )
    async with _gateway(script) as client:
        out = await _collect(FrontDoorDispatcher(client, make_settings()).handle("طلب عادي"))
    assert out[0] == DEFAULT_ACK_AR
    _clean_ack_shape(out[0])


async def test_shell_ack_replaced_shape_p0(fake_bot, make_shell):
    """Ack shows first as a short clean line, then vanishes from the final bubble."""
    shell = make_shell(
        router_replies=[_router("tier2", "تمام، ببدأ")],
        stream_programs=[StreamProgram(deltas=("سجّلت", " الموعد", " بكره"))],
    )
    bot = fake_bot()
    await _run(shell, bot, make_update(1, OWNER_ID, "حدّد موعد بكره"))
    edits = bot.session.sent("EditMessageText")
    assert len(edits) >= 2
    _clean_ack_shape(edits[0].method.text)
    assert "تمام" not in edits[-1].method.text
    assert AR_CONTAINS.search(edits[-1].method.text)


async def test_voice_fallback_frozen_shape_p0():
    """EMPTY_VOICE_AR is a frozen contract this phase: document its shape so P4
    directive text must preserve single-surface brevity, not literals."""
    assert AR_CONTAINS.search(EMPTY_VOICE_AR)
    assert 5 <= len(EMPTY_VOICE_AR) <= 120


async def test_triage_card_slots_shape_p0():
    """Semi card carries sender + subject with a capped excerpt, no literals."""
    card = render_semi(_msg())
    assert "ليلى" in card and "عزومة عشا" in card
    assert len(card) <= 800
    body_part = card.split("\n\n", 1)[1]
    assert len(body_part) <= EXCERPT_MAX_CHARS + len("…[مقتطع]")
    assert "triage:ack:" not in card  # callback id rides the button, not the card


async def test_triage_voice_script_slots_shape_p0():
    """Voice scripts name sender + subject in one breath, critical flagged."""
    plain = render_voice_script(_msg(), critical=False)
    urgent = render_voice_script(_msg(), critical=True)
    for script in (plain, urgent):
        assert "ليلى" in script and "عزومة عشا" in script
    assert len(plain.split()) <= 40
    assert len(urgent) <= 300  # 200-char summary cap + fixed framing
    assert "عاجلة" in urgent and "عاجلة" not in plain


async def test_brief_sections_shape_p0(make_settings):
    """Brief render carries all three section markers, degraded or not."""
    composer = BriefComposer(None, None, None, None, 0, make_settings())
    full = composer.render(
        BriefData(events=[], tasks=[], unread_total=0, important_items=[]),
        datetime(2026, 9, 16, 7, 30, tzinfo=UTC),
    )
    assert "📅" in full and "✅" in full and "📥" in full
    assert AR_CONTAINS.search(full)
    empty = composer.render(
        BriefData(events=None, tasks=None, unread_total=None),
        datetime(2026, 9, 16, 7, 30, tzinfo=UTC),
    )
    assert "📅" in empty and "✅" in empty and "📥" in empty


async def test_journaler_sections_shape_p0(make_settings, tmp_path):
    """Ledger note carries frontmatter + all section headers."""
    journaler = EveningJournaler(None, None, 0, make_settings(), tmp_path)
    note = journaler.render_ledger(
        LedgerData(
            date="2026-09-16",
            events=[],
            tasks_done=0,
            critical_mail_count=0,
            memos_filed=0,
        )
    )
    assert note.startswith("---\ndate: 2026-09-16")
    for header in ("## المواعيد", "## البريد", "## المذكرات الصوتية", "## ملاحظات"):
        assert header in note
