"""Sprint-2 §2.2 bot shell (sprint-1 §1.4 AC6-AC11 carried): handlers + streaming wiring.

The old AC8 "single aggregated reply" is superseded by the 2.2 re-map: the owner text
path streams progressively through the front-door dispatcher (placeholder -> ack edit
-> coalesced edits -> final verbatim edit). Text handlers spawn their stream as a task,
so shell tests drain src.bot._STREAMS before asserting on the recording session.
"""

import asyncio
import json

import pytest
from cryptography.fernet import Fernet
from loguru import logger

from src.bot import (
    _ENROLL_PENDING,
    _STREAMS,
    APOLOGY_AR,
    EMPTY_VOICE_AR,
    ENROLL_DONE_AR,
    ENROLL_PROMPT_AR,
    HELP_AR,
    SYSTEM_PROMPT_AR,
    VOICE_ACK_AR,
    WELCOME_AR,
)
from src.gateway import GatewayError
from src.skills.voice_biometric_auth import GUEST_LOCKDOWN_AR, VoiceBiometrics
from tests.conftest import OWNER_ID, StreamProgram, drain, make_update, wait_until


def _router(route: str, ack: str) -> str:
    return json.dumps({"route": route, "ack": ack}, ensure_ascii=False)


@pytest.fixture
def logs():
    records: list = []
    sink_id = logger.add(records.append, level="DEBUG")
    yield records
    logger.remove(sink_id)


@pytest.fixture(autouse=True)
def _clean_streams():
    _STREAMS.clear()
    yield
    _STREAMS.clear()


async def _run(shell, bot, update):
    await shell.dp.feed_update(bot, update)
    await drain(_STREAMS)


async def test_start_sends_welcome_and_voice_greeting(fake_bot, make_shell):
    """AC6: /start -> welcome text + one answer_voice with non-empty buffered bytes."""
    shell, bot = make_shell(), fake_bot()
    await shell.dp.feed_update(bot, make_update(1, OWNER_ID, "/start", command=True))
    assert bot.session.sent("SendMessage")[0].method.text == WELCOME_AR
    voices = bot.session.sent("SendVoice")
    assert len(voices) == 1
    assert len(voices[0].method.voice.data) > 0
    assert shell.voice.calls  # greeting came through the VoicePipeline


async def test_help_lists_capabilities(fake_bot, make_shell):
    """AC7: /help replies with capabilities."""
    shell, bot = make_shell(), fake_bot()
    await shell.dp.feed_update(bot, make_update(1, OWNER_ID, "/help", command=True))
    assert bot.session.sent("SendMessage")[0].method.text == HELP_AR


async def test_owner_text_streams_brain_progressively(fake_bot, make_shell):
    """AC8 (2.2 re-map): placeholder -> ack first edit -> coalesced edits -> exact final;
    typing issued; the brain stream saw the system prompt + owner text ONLY."""
    shell = make_shell(
        router_replies=[_router("tier2", "تمام، ببدأ")],
        stream_programs=[StreamProgram(deltas=("سجّلت", " الموعد", " بكره"))],
    )
    bot = fake_bot()
    await _run(shell, bot, make_update(1, OWNER_ID, "حدّد موعد بكره"))

    sends = bot.session.sent("SendMessage")
    edits = bot.session.sent("EditMessageText")
    assert sends[0].method.text == "…"
    assert len(edits) >= 2
    assert edits[0].method.text == "تمام، ببدأ"
    assert edits[-1].method.text == "تمام، ببدأسجّلت الموعد بكره"
    assert any(c.name == "SendChatAction" for c in bot.session.calls)

    stream_messages, _tier = shell.gateway.stream_calls[0]
    assert [m["content"] for m in stream_messages] == [SYSTEM_PROMPT_AR, "حدّد موعد بكره"]
    assert [m["role"] for m in stream_messages] == ["system", "user"]

    for call in sends + edits:
        assert not isinstance(getattr(call.method, "parse_mode", None), str)


async def test_brain_failure_sends_apology_and_logs(fake_bot, make_shell, logs):
    """AC10: mid-stream GatewayError -> APOLOGY_AR sent, delivered text stays, logged."""
    shell = make_shell(
        router_replies=[_router("tier2", "بدأت")],
        stream_programs=[StreamProgram(deltas=("جزئي",), error=GatewayError("mid-stream boom"))],
    )
    bot = fake_bot()
    await _run(shell, bot, make_update(1, OWNER_ID, "جهزلي شي"))

    texts = [c.method.text for c in bot.session.sent("SendMessage")]
    assert APOLOGY_AR in texts
    edit_texts = [c.method.text for c in bot.session.sent("EditMessageText")]
    assert any("بدأت" in t for t in edit_texts)
    assert any("brain" in str(record).lower() for record in logs)


async def test_voice_note_acknowledged_without_brain_call(fake_bot, make_shell):
    """AC11: owner voice note -> static ack, zero gateway calls."""
    shell, bot = make_shell(), fake_bot()
    await shell.dp.feed_update(bot, make_update(1, OWNER_ID, voice=True))
    assert bot.session.sent("SendMessage")[0].method.text == VOICE_ACK_AR
    assert shell.gateway.router_calls == []
    assert shell.gateway.stream_calls == []


class _EmptyTranscriber:
    def __init__(self) -> None:
        self.notes: list[dict] = []

    async def transcribe(self, ogg: bytes) -> str:
        return ""

    async def file_note(self, text, *, received_at, duration_s) -> None:
        self.notes.append({"text": text, "duration_s": duration_s})


async def test_silent_voice_note_gets_honest_voice_reply(fake_bot, make_shell):
    """Live 2026-09-01 22:03: a 6-second silent note transcribed empty and the owner
    was left hanging on a static ack. Sara must answer with an honest VOICE note."""
    empty = _EmptyTranscriber()
    shell, bot = make_shell(transcriber=empty), fake_bot()
    await shell.dp.feed_update(bot, make_update(1, OWNER_ID, voice=True))
    assert empty.notes and empty.notes[0]["text"] == ""  # memo still filed
    texts = [c.method.text for c in bot.session.sent("SendMessage")]
    assert EMPTY_VOICE_AR in texts
    voices = bot.session.sent("SendVoice")
    assert len(voices) == 1 and len(voices[0].method.voice.data) > 0
    assert shell.gateway.stream_calls == []


async def test_enroll_voice_flow_and_biometric_gate(fake_bot, make_shell, monkeypatch, tmp_path):
    """2.3 wiring: /enroll-voice -> next voice seals the voiceprint; owner voice
    keeps the static ack; a below-threshold voice triggers Guest Mode lockdown."""
    monkeypatch.chdir(tmp_path)  # ./vault under VAULT_LOCAL_PATH lands inside tmp_path
    shell = make_shell(VAULT_ENC_KEY=Fernet.generate_key().decode())
    bot = fake_bot()

    async def fake_download(file, destination=None, **kwargs):
        destination.write(b"FAKE-OGG")

    monkeypatch.setattr(bot, "download", fake_download)
    monkeypatch.setattr(VoiceBiometrics, "_embed_sync", lambda self, ogg: [0.6, 0.8, 0.0])
    try:
        await _run(shell, bot, make_update(1, OWNER_ID, "/enroll-voice", command=True))
        assert bot.session.sent("SendMessage")[-1].method.text == ENROLL_PROMPT_AR

        await _run(shell, bot, make_update(2, OWNER_ID, voice=True))
        assert bot.session.sent("SendMessage")[-1].method.text == ENROLL_DONE_AR
        assert (tmp_path / "vault" / "State" / "owner_voiceprint.enc").exists()

        await _run(shell, bot, make_update(3, OWNER_ID, voice=True))
        assert bot.session.sent("SendMessage")[-1].method.text == VOICE_ACK_AR

        monkeypatch.setattr(VoiceBiometrics, "_embed_sync", lambda self, ogg: [0.8, -0.6, 0.0])
        await _run(shell, bot, make_update(4, OWNER_ID, voice=True))
        assert bot.session.sent("SendMessage")[-1].method.text == GUEST_LOCKDOWN_AR
        assert shell.gateway.stream_calls == []
    finally:
        _ENROLL_PENDING.clear()


class FakeTranscriber:
    """2.5 double: deterministic transcript, records calls, reports filed notes."""

    def __init__(self, text="رتبلي اجتماع بكرة الصبح") -> None:
        self.text = text
        self.ogg_calls: list[bytes] = []
        self.notes: list[dict] = []

    async def transcribe(self, ogg):
        self.ogg_calls.append(ogg)
        return self.text

    async def file_note(self, text, *, received_at, duration_s, source="telegram-voice"):
        self.notes.append({"text": text, "duration_s": duration_s, "source": source})
        from pathlib import Path

        return Path("note.md")


async def test_owner_voice_transcribed_filed_and_streamed(
    fake_bot, make_shell, monkeypatch, tmp_path
):
    """2.5 wiring: enrolled owner voice -> LOCAL transcriber -> memo filed ->
    transcript enters the standard text pipeline (streamed brain reply)."""
    monkeypatch.chdir(tmp_path)
    transcriber = FakeTranscriber()
    shell = make_shell(
        VAULT_ENC_KEY=Fernet.generate_key().decode(),
        router_replies=[_router("tier2", "تم")],
        stream_programs=[StreamProgram(deltas=("رتبت",))],
        transcriber=transcriber,
    )
    bot = fake_bot()

    async def fake_download(file, destination=None, **kwargs):
        destination.write(b"FAKE-OGG")

    monkeypatch.setattr(bot, "download", fake_download)
    monkeypatch.setattr(VoiceBiometrics, "_embed_sync", lambda self, ogg: [0.6, 0.8, 0.0])
    try:
        await _run(shell, bot, make_update(1, OWNER_ID, "/enroll-voice", command=True))
        await _run(shell, bot, make_update(2, OWNER_ID, voice=True))
        assert bot.session.sent("SendMessage")[-1].method.text == ENROLL_DONE_AR

        await _run(shell, bot, make_update(3, OWNER_ID, voice=True))
        assert transcriber.ogg_calls == [b"FAKE-OGG"]  # only after the biometric gate
        assert len(transcriber.notes) == 1  # memo filed with transcript + duration
        assert transcriber.notes[0]["text"] == transcriber.text
        assert shell.gateway.stream_calls, "transcript entered the text pipeline"
        brain_messages = shell.gateway.stream_calls[0][0]
        assert any(transcriber.text in m["content"] for m in brain_messages)

        # Guest containment: below-threshold voice never reaches the transcriber.
        monkeypatch.setattr(VoiceBiometrics, "_embed_sync", lambda self, ogg: [0.8, -0.6, 0.0])
        await _run(shell, bot, make_update(4, OWNER_ID, voice=True))
        assert bot.session.sent("SendMessage")[-1].method.text == GUEST_LOCKDOWN_AR
        assert len(transcriber.ogg_calls) == 1
    finally:
        _ENROLL_PENDING.clear()


async def test_new_owner_message_cancels_inflight_stream(fake_bot, make_shell):
    """Interjection: a newer owner message cancels the in-flight stream; partial kept."""
    gate = asyncio.Event()
    shell = make_shell(
        router_replies=[_router("tier2", "تم"), _router("tier2", "جواب ثاني")],
        stream_programs=[
            StreamProgram(deltas=("أول", "تالٍ"), gate=gate),
            StreamProgram(deltas=("ثاني",)),
        ],
    )
    bot = fake_bot()
    await shell.dp.feed_update(bot, make_update(1, OWNER_ID, "سؤال أول"))
    task1, _ = _STREAMS[OWNER_ID]
    await wait_until(
        lambda: any(c.method.text == "تم" for c in bot.session.sent("EditMessageText"))
    )

    await shell.dp.feed_update(bot, make_update(2, OWNER_ID, "سؤال ثاني"))
    task2, _ = _STREAMS[OWNER_ID]
    gate.set()
    await asyncio.gather(task1, task2)

    final_edits = [c.method.text for c in bot.session.sent("EditMessageText")]
    assert "تمأول" in final_edits  # partial received text preserved in the bubble
    assert not any("تالٍ" in t for t in final_edits)  # never consumed the late delta
    assert any("جواب ثاني" in c.method.text for c in bot.session.sent("EditMessageText"))


async def test_unhandled_exception_apologizes_and_marks_handled(fake_bot, make_shell):
    """Unexpected stream exception -> one apology, handled — polling never wedges."""
    shell = make_shell(
        router_replies=[_router("tier2", "تم")],
        stream_programs=[StreamProgram(deltas=("بداية",), error=ValueError("bug"))],
    )
    bot = fake_bot()
    await shell.dp.feed_update(bot, make_update(1, OWNER_ID, "شي غريب"))
    await drain(_STREAMS)
    assert any(APOLOGY_AR == c.method.text for c in bot.session.sent("SendMessage"))


async def test_start_voice_synthesis_failure_still_delivers_text(fake_bot, make_shell):
    """Error mode: synthesis failure on /start -> welcome text still delivered."""
    shell, bot = make_shell(voice_error=RuntimeError("edge-tts down")), fake_bot()
    await shell.dp.feed_update(bot, make_update(1, OWNER_ID, "/start", command=True))
    assert bot.session.sent("SendMessage")[0].method.text == WELCOME_AR
    assert bot.session.sent("SendVoice") == []


# --- Owner directive 2026-09-01 wiring: memory envelope, background vault writers,
# --- pending-launch intercept, voice-origin voice replies. --------------------------


class _ReadVault:
    def __init__(self, reads):
        self.reads = reads

    async def read(self, path):
        if path not in self.reads:
            raise FileNotFoundError(path)
        return self.reads[path]


class _WriterDouble:
    def __init__(self):
        self.exchanges = []
        self.learns = []

    async def log_exchange(self, user_text, reply_text, *, now):
        self.exchanges.append((user_text, reply_text))

    async def maybe_learn(self, user_text, *, now):
        self.learns.append(user_text)


class _CoordinatorDouble:
    def __init__(self, target="calc.exe"):
        self.target = target
        self.replies = []

    def pending_active(self):
        return True

    async def handle_owner_reply(self, text):
        self.replies.append(text)
        return self.target


async def test_pending_launch_reply_consumed_by_coordinator(fake_bot, make_shell):
    """A pending PC-launch confirmation is answered to the coordinator directly —
    the message never reaches the brain and no stream spawns."""
    coordinator = _CoordinatorDouble()
    shell = make_shell(
        coordinator=coordinator,
        router_replies=[_router("direct", "ليش حكيت؟")],
    )
    bot = fake_bot()
    await _run(shell, bot, make_update(1, OWNER_ID, "تم"))
    assert coordinator.replies == ["تم"]
    assert shell.gateway.router_calls == []  # brain never consulted


async def test_streams_carry_history_and_long_term_envelope(fake_bot, make_shell):
    """Dual-tier memory: system block carries the vault profile excerpt; the second
    turn streams with the first exchange as rolling history; both turns remembered."""
    from src.memory import ConversationMemory

    memory = ConversationMemory()
    shell = make_shell(
        memory=memory,
        vault=_ReadVault({"02_Areas/Profile/User_Info.md": "---\ntype: profile\n---\nالمالك عمر"}),
        router_replies=[_router("tier2", "إقرار"), _router("tier2", "إقرار2")],
        stream_programs=[StreamProgram(deltas=("رد1",)), StreamProgram(deltas=("رد2",))],
    )
    bot = fake_bot()
    await _run(shell, bot, make_update(1, OWNER_ID, "مرحبا"))
    first = shell.gateway.stream_calls[0][0]
    assert first[0]["role"] == "system"
    assert "المالك عمر" in first[0]["content"]

    await _run(shell, bot, make_update(2, OWNER_ID, "شو رأيك؟"))
    second = shell.gateway.stream_calls[1][0]
    assert [m["role"] for m in second] == ["system", "user", "assistant", "user"]
    assert second[1] == {"role": "user", "content": "مرحبا"}
    assert second[2] == {"role": "assistant", "content": "إقراررد1"}  # ack + deltas = final text
    assert second[-1] == {"role": "user", "content": "شو رأيك؟"}
    assert memory.history(OWNER_ID)[-1] == {"role": "assistant", "content": "إقرار2رد2"}


async def test_exchange_persisted_and_learned_after_stream(fake_bot, make_shell):
    """Background writers: every exchange lands in the daily ledger, and the
    learner gets its shot — both after the reply, never blocking it."""
    writer = _WriterDouble()
    shell = make_shell(
        writer=writer,
        router_replies=[_router("tier2", "تم")],
        stream_programs=[StreamProgram(deltas=("رد",))],
    )
    bot = fake_bot()
    await _run(shell, bot, make_update(1, OWNER_ID, "مرحبا"))
    assert shell.gateway.stream_calls  # reply streamed first
    await wait_until(lambda: writer.exchanges and writer.learns)
    assert writer.exchanges == [("مرحبا", "تمرد")]  # ack + delta = final text
    assert writer.learns == ["مرحبا"]


async def test_voice_origin_reply_arrives_as_voice_note(
    fake_bot, make_shell, monkeypatch, tmp_path
):
    """Voice in, voice out: an enrolled owner voice note gets the streamed text reply
    AND an ar-JO Ogg Opus voice note of the same reply."""
    monkeypatch.chdir(tmp_path)
    transcriber = FakeTranscriber()
    shell = make_shell(
        VAULT_ENC_KEY=Fernet.generate_key().decode(),
        router_replies=[_router("tier2", "تم")],
        stream_programs=[StreamProgram(deltas=("رتبت لك الموضوع",))],
        transcriber=transcriber,
    )
    bot = fake_bot()

    async def fake_download(file, destination=None, **kwargs):
        destination.write(b"FAKE-OGG")

    monkeypatch.setattr(bot, "download", fake_download)
    monkeypatch.setattr(VoiceBiometrics, "_embed_sync", lambda self, ogg: [0.6, 0.8, 0.0])
    try:
        await _run(shell, bot, make_update(1, OWNER_ID, "/enroll-voice", command=True))
        await _run(shell, bot, make_update(2, OWNER_ID, voice=True))
        assert bot.session.sent("SendMessage")[-1].method.text == ENROLL_DONE_AR

        await _run(shell, bot, make_update(3, OWNER_ID, voice=True))
        voices = bot.session.sent("SendVoice")
        assert len(voices) == 1  # enroll path sends no voice reply; the answer does
        assert b"OGGOPUS-FAKE-BYTES" in voices[0].method.voice.data
    finally:
        _ENROLL_PENDING.clear()
