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
    MEDIA_TOO_BIG_AR,
    SYSTEM_PROMPT_AR,
    WELCOME_AR,
)
from src.gateway import GatewayError
from src.skills.voice_biometric_auth import GUEST_LOCKDOWN_AR, VoiceBiometrics
from tests.conftest import (
    OWNER_ID,
    StreamProgram,
    drain,
    make_update,
    wait_until,
)
from tests.conftest import FakeVoice as _ConftestFakeVoice


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
    """/start (remediation 1.5): ONE greeting voice note + ONE short caption line —
    no duplicated identity content between the two surfaces (transcript 14:19-14:22
    text-then-voice repeat is impossible now)."""
    shell, bot = make_shell(), fake_bot()
    await shell.dp.feed_update(bot, make_update(1, OWNER_ID, "/start", command=True))
    voices = bot.session.sent("SendVoice")
    assert len(voices) == 1
    assert len(voices[0].method.voice.data) > 0
    sends = bot.session.sent("SendMessage")
    assert len(sends) == 1
    caption, spoken = sends[0].method.text, shell.voice.calls[0]
    assert caption == WELCOME_AR
    assert "سارة" not in caption or "سارة" not in spoken  # identity lives in ONE surface only
    assert shell.voice.calls  # greeting came through the voice pipeline


async def test_help_lists_capabilities(fake_bot, make_shell):
    """AC7: /help replies with capabilities."""
    shell, bot = make_shell(), fake_bot()
    await shell.dp.feed_update(bot, make_update(1, OWNER_ID, "/help", command=True))
    assert bot.session.sent("SendMessage")[0].method.text == HELP_AR


async def test_owner_text_streams_brain_progressively(fake_bot, make_shell):
    """AC8 (2.2 re-map, remediation 1.3): placeholder -> ack first edit (instant
    reassurance) -> the ack is DELETED the moment the answer starts streaming ->
    final bubble carries the answer only; typing issued; the brain stream saw
    the system prompt + owner text ONLY."""
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
    assert edits[0].method.text == "تمام، ببدأ"  # the ack shows instantly...
    assert edits[-1].method.text == "سجّلت الموعد بكره"  # ...then the answer replaces it, ack gone
    assert "تمام" not in edits[-1].method.text
    assert any(c.name == "SendChatAction" for c in bot.session.calls)

    stream_messages, _tier = shell.gateway.stream_calls[0]
    assert [m["content"] for m in stream_messages] == [SYSTEM_PROMPT_AR, "حدّد موعد بكره"]
    assert [m["role"] for m in stream_messages] == ["system", "user"]


async def test_photo_reaches_brain_as_native_image_block(fake_bot, make_shell, monkeypatch):
    """Media comprehension (owner 2026-09-03): a photo the owner sends is seen
    NATIVELY — the stream carries an image_url content block to m3, not a text
    description. The caption is the prompt; no caption -> the default ask."""
    shell = make_shell(
        router_replies=[_router("direct", "دقايق")],
        stream_programs=[StreamProgram(deltas=("هاد كلب صغير حلو",))],
    )
    bot = fake_bot()

    async def fake_download(file, destination=None, **kwargs):
        destination.write(b"PHOTO-BYTES")
        return destination

    monkeypatch.setattr(bot, "download", fake_download)
    update = make_update(1, OWNER_ID, "شو هاد؟", photo=True)
    await _run(shell, bot, update)

    stream_messages, _tier = shell.gateway.stream_calls[0]
    user_msg = stream_messages[-1]
    assert isinstance(user_msg["content"], list)  # multimodal block, not plain text
    types = [b["type"] for b in user_msg["content"]]
    assert types == ["text", "image_url"]
    assert user_msg["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert "شو هاد" in user_msg["content"][0]["text"]


async def test_video_reaches_brain_as_native_video_block(fake_bot, make_shell, monkeypatch):
    """Same contract for video: m3's video input describes what the owner sent."""
    shell = make_shell(
        router_replies=[_router("direct", "دقايق")],
        stream_programs=[StreamProgram(deltas=("مشهد حلو كتير",))],
    )
    bot = fake_bot()

    async def fake_download(file, destination=None, **kwargs):
        destination.write(b"VIDEO-BYTES")
        return destination

    monkeypatch.setattr(bot, "download", fake_download)
    update = make_update(1, OWNER_ID, "وين هاد؟", video=True)
    await _run(shell, bot, update)

    stream_messages, _tier = shell.gateway.stream_calls[0]
    user_msg = stream_messages[-1]
    assert [b["type"] for b in user_msg["content"]] == ["text", "video_url"]


async def test_oversized_media_gets_honest_line_no_brain_call(fake_bot, make_shell, monkeypatch):
    """>10MiB raw -> the honest size line lands; the brain is never called."""
    shell, bot = make_shell(), fake_bot()

    async def fake_download(file, destination=None, **kwargs):
        destination.write(b"X" * (10 * 1024 * 1024 + 1))
        return destination

    monkeypatch.setattr(bot, "download", fake_download)
    await _run(shell, bot, make_update(1, OWNER_ID, "شو هاد؟", photo=True))
    assert bot.session.sent("SendMessage")[-1].method.text == MEDIA_TOO_BIG_AR
    assert shell.gateway.stream_calls == []


async def test_reply_to_message_quote_reaches_brain(fake_bot, make_shell):
    """Reply-awareness (owner 2026-09-03): when the owner replies to a specific
    message, Sara knows WHAT he replied to — the quote rides the prompt."""
    shell = make_shell(
        router_replies=[_router("direct", "من عيوني")],
        stream_programs=[StreamProgram(deltas=("فهمتك تمام",))],
    )
    bot = fake_bot()
    quoted = make_update(7, OWNER_ID, "بكره عندي اجتماع الساعة ١٠")
    reply_update = make_update(8, OWNER_ID, "شو رأيك فيه؟", reply_to=quoted.message)
    await _run(shell, bot, reply_update)

    stream_messages, _ = shell.gateway.stream_calls[0]
    user_content = stream_messages[-1]["content"]
    assert "شو رأيك فيه؟" in user_content
    assert "عمر ردّ على رسالة سابقة" in user_content
    assert "بكره عندي اجتماع" in user_content  # the quoted tail rides along


def test_decide_modality_wired_by_default(make_shell):
    """The deterministic decider is the shell-test default (legacy tests pin the
    old channel contract); production falls back to the shipped 70/30 skill —
    proven by the import fallback test in test_reply_modality.py."""
    shell = make_shell()
    assert shell.decide("نص عادي", False) == "text"  # text origin -> text
    assert shell.decide("نص عادي", True) == "voice"  # voice origin -> voice
    assert (
        shell.decide("رد صوتي", False) == "text"
    )  # the deterministic stub ignores forcing — real forcing is the skill's own suite


async def test_forced_voice_reply_on_text_message(fake_bot, make_shell):
    """Owner directive 2026-09-03 (integration): «رد صوتي» on a TEXT message ->
    the answer arrives as ONE voice note, no text bubble — the skill's forcing
    honored end-to-end through the shell."""
    from src.skills.reply_modality import decide_reply_modality

    shell = make_shell(
        router_replies=[_router("direct", "من عيوني")],
        stream_programs=[StreamProgram(deltas=("جاهزة رح جاوبك بصوتي",))],
        decide_modality=decide_reply_modality,
    )
    bot = fake_bot()
    await _run(shell, bot, make_update(1, OWNER_ID, "رد صوتي كيف حالك"))
    assert len(bot.session.sent("SendVoice")) == 1
    assert bot.session.sent("SendMessage") == []  # no text bubble beside it
    assert shell.voice.calls == ["جاهزة رح جاوبك بصوتي"]


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


async def test_voice_note_acknowledged_without_brain_call(
    fake_bot, make_shell, monkeypatch, tmp_path
):
    """Unenrolled trust level (remediation 1.4): NO static ack lie — the note flows
    to transcription like any owner note; an empty transcript answers with ONE
    honest voice note, and the brain is never consulted."""
    monkeypatch.chdir(tmp_path)
    shell, bot = make_shell(transcriber=_EmptyTranscriber()), fake_bot()

    async def fake_download(file, destination=None, **kwargs):
        destination.write(b"FAKE-OGG")

    monkeypatch.setattr(bot, "download", fake_download)
    await shell.dp.feed_update(bot, make_update(1, OWNER_ID, voice=True))
    texts = [c.method.text for c in bot.session.sent("SendMessage")]
    assert texts == []  # no static ack lie, no duplicate — the voice surface speaks
    voices = bot.session.sent("SendVoice")
    assert len(voices) == 1  # one honest voice note, single modality
    assert shell.gateway.router_calls == []
    assert shell.gateway.stream_calls == []


class _EmptyTranscriber:
    def __init__(self) -> None:
        self.notes: list[dict] = []

    async def transcribe(self, ogg: bytes) -> str:
        return ""

    async def file_note(self, text, *, received_at, duration_s) -> None:
        self.notes.append({"text": text, "duration_s": duration_s})


async def test_silent_voice_note_gets_honest_voice_reply(
    fake_bot, make_shell, monkeypatch, tmp_path
):
    """Live 2026-09-01 22:03 + remediation 1.4: a silent note gets ONE honest
    surface — a VOICE note (no text duplicate). The memo is still filed.
    Hermetic (2026-09-03 power-cut lesson): ./vault in the repo root now holds
    the owner's REAL sealed voiceprint (live /enroll-voice) — without chdir the
    test reads it, FAKE-OGG fails the biometric decode and the turn locks down
    as guest instead of answering. Every on_voice test must own a tmp vault."""
    monkeypatch.chdir(tmp_path)  # never the real ./vault with its live voiceprint
    empty = _EmptyTranscriber()
    shell, bot = make_shell(transcriber=empty), fake_bot()

    async def fake_download(file, destination=None, **kwargs):
        destination.write(b"FAKE-OGG")

    monkeypatch.setattr(bot, "download", fake_download)
    await shell.dp.feed_update(bot, make_update(1, OWNER_ID, voice=True))
    assert empty.notes and empty.notes[0]["text"] == ""  # memo still filed
    voices = bot.session.sent("SendVoice")
    assert len(voices) == 1 and len(voices[0].method.voice.data) > 0  # voice surface...
    assert bot.session.sent("SendMessage") == []  # ...with no text duplicate
    assert shell.voice.calls == [EMPTY_VOICE_AR]  # the spoken line is the honest one
    assert shell.gateway.stream_calls == []


async def test_silent_voice_note_synthesis_dead_falls_back_to_text(
    fake_bot, make_shell, monkeypatch, tmp_path
):
    """Remediation 1.4 fallback: the honest voice note fails to synthesize -> the
    single text line lands — never silence, never double surfaces. Hermetic:
    tmp vault (the repo ./vault carries the owner's real live voiceprint)."""
    monkeypatch.chdir(tmp_path)
    empty = _EmptyTranscriber()
    shell = make_shell(transcriber=empty, voice_error=RuntimeError("engine dead"))
    bot = fake_bot()

    async def fake_download(file, destination=None, **kwargs):
        destination.write(b"FAKE-OGG")

    monkeypatch.setattr(bot, "download", fake_download)
    await shell.dp.feed_update(bot, make_update(1, OWNER_ID, voice=True))
    assert bot.session.sent("SendVoice") == []
    texts = [c.method.text for c in bot.session.sent("SendMessage")]
    assert texts == [EMPTY_VOICE_AR]  # one honest text surface


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
        # Real Whisper rejects FAKE-OGG -> honest EMPTY_VOICE voice note (remediation
        # 1.4: single modality — no text duplicate beside it).
        assert (
            bot.session.sent("SendMessage")[-1].method.text == ENROLL_DONE_AR
        )  # nothing text-new after the enroll line
        assert len(bot.session.sent("SendVoice")) == 1

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
    """Interjection: a newer owner message cancels the in-flight stream; partial kept.
    (Remediation 1.3: the partial is the answer alone — the ack never glues onto it.)"""
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
    await wait_until(lambda: task1.cancelled())  # remediation 1.7: hard-cancelled, not just flagged
    await asyncio.gather(task2)

    final_edits = [c.method.text for c in bot.session.sent("EditMessageText")]
    assert "أول" in final_edits  # partial answer preserved in the bubble
    assert not any("تمأول" in t for t in final_edits)  # the ack was replaced, never glued
    assert not any("تالٍ" in t for t in final_edits)  # never consumed the late delta
    assert any("جواب ثاني" in c.method.text for c in bot.session.sent("EditMessageText"))


async def test_interjection_cancels_a_blocked_midstream_task(fake_bot, make_shell):
    """Remediation 1.7 (audit V-3): the cancel Event only takes effect BETWEEN
    deltas — a stream blocked mid-flight (slow model delta) stayed alive as a
    zombie that could fire late edits/voice from a dead turn. The interjection
    must task.cancel() the abandoned turn at its await point."""
    gate = asyncio.Event()  # never released while turn 1 lives — blocked mid-stream
    shell = make_shell(
        router_replies=[_router("tier2", "تم"), _router("tier2", "جواب")],
        stream_programs=[
            StreamProgram(deltas=("أول", "متأخر جداً"), gate=gate),
            StreamProgram(deltas=("ثاني",)),
        ],
    )
    bot = fake_bot()
    await shell.dp.feed_update(bot, make_update(1, OWNER_ID, "سؤال أول"))
    task1, _ = _STREAMS[OWNER_ID]
    await wait_until(
        lambda: any(c.method.text == "أول" for c in bot.session.sent("EditMessageText"))
    )

    await shell.dp.feed_update(bot, make_update(2, OWNER_ID, "سؤال ثاني"))  # interject
    task2, _ = _STREAMS[OWNER_ID]
    await wait_until(lambda: task1.cancelled())  # the zombie dies NOW, not at the next delta

    gate.set()  # the late delta arrives — but nobody is listening anymore
    await asyncio.gather(task2)
    late = [c for c in bot.session.sent("EditMessageText") if "متأخر" in c.method.text]
    assert late == []  # no edit from the abandoned turn ever lands
    # Remediation 1.7: the abandoned task is CANCELLED, not just signalled — its
    # gateway stream generator is closed, no zombie edits/voice can fire late.
    assert task1.cancelled() or task1.done()


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


class _VaultDouble:
    """2.5: read + upsert double — enough for the dialect-learning loop."""

    def __init__(self, files=None):
        self.files = dict(files or {})
        self.writes: list[tuple[str, str]] = []

    async def read(self, path):
        if path not in self.files:
            raise FileNotFoundError(path)
        return self.files[path]

    async def upsert(self, path, content, *, message):
        self.writes.append((path, content))
        self.files[path] = content


class _WriterDouble:
    def __init__(self):
        self.exchanges = []
        self.learns = []

    async def log_exchange(self, user_text, reply_text, *, now):
        self.exchanges.append((user_text, reply_text))

    async def maybe_learn(self, user_text, *, now):
        self.learns.append(user_text)


class _CoordinatorDouble:
    def __init__(self, target="calc.exe", memory=None):
        self.target = target
        self.replies = []
        self.memory = memory  # 2.4: run_bot wires the shell's memory into the coordinator

    def pending_active(self):
        return True

    async def handle_owner_reply(self, text):
        self.replies.append(text)
        # 2.4 mirror of the real coordinator: the confirmation conversation
        # lands in memory under the owner's chat id
        if self.memory is not None:
            self.memory.remember(OWNER_ID, "user", text)
            self.memory.remember(OWNER_ID, "assistant", f"نفّذت {self.target}")
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


async def test_pending_launch_voice_yes_consumed_by_coordinator(
    fake_bot, make_shell, monkeypatch, tmp_path
):
    """Remediation 2.3 (audit C-2, sacred floor): a pending PC confirmation
    answered with a VOICE note «نعم» is consumed by the coordinator after
    transcription — never streamed to the brain, the launch executes."""
    monkeypatch.chdir(tmp_path)  # hermetic: never the real ./vault voiceprint
    coordinator = _CoordinatorDouble()
    transcriber = FakeTranscriber(text="نعم")
    shell = make_shell(
        VAULT_ENC_KEY=Fernet.generate_key().decode(),
        coordinator=coordinator,
        transcriber=transcriber,
        router_replies=[_router("direct", "ما رح نفذ شي")],
    )
    bot = fake_bot()

    async def fake_download(file, destination=None, **kwargs):
        destination.write(b"FAKE-OGG")

    monkeypatch.setattr(bot, "download", fake_download)
    monkeypatch.setattr(VoiceBiometrics, "_embed_sync", lambda self, ogg: [0.6, 0.8, 0.0])
    try:
        await _run(shell, bot, make_update(1, OWNER_ID, "/enroll-voice", command=True))
        await _run(shell, bot, make_update(2, OWNER_ID, voice=True))
        coordinator.replies.clear()

        await _run(shell, bot, make_update(3, OWNER_ID, voice=True))
        assert coordinator.replies == ["نعم"]  # consumed as the confirmation
        assert shell.gateway.router_calls == []  # brain never consulted
        assert shell.gateway.stream_calls == []  # no stream spawned
    finally:
        _ENROLL_PENDING.clear()


# --- remediation 2.4 (audit C-8): no orphan yes/no; coordinator memory wired --------


class _RejectionCoordinatorDouble:
    """Pending active, but the owner's reply gets REJECTED (bridge failure) —
    handle_owner_reply returns None, the old flow fell through to the brain."""

    def __init__(self) -> None:
        self.replies: list[str] = []

    def pending_active(self) -> bool:
        return True

    async def handle_owner_reply(self, text: str) -> str | None:
        self.replies.append(text)
        return None  # rejected/failed — the orphan-guard must catch this


async def test_orphan_yes_after_rejected_confirmation_never_reaches_brain(fake_bot, make_shell):
    """Remediation 2.4 (audit C-8): the coordinator returns None after a
    rejected/failed confirmation — the bare «نعم» must NOT fall through to the
    brain as an orphan (the blind «أكيد سويتها!» reply). Only a bare short
    consent/refusal token is guarded; real chat keeps flowing."""
    coordinator = _RejectionCoordinatorDouble()
    shell = make_shell(
        coordinator=coordinator,
        router_replies=[_router("direct", "تمام، ببدأ")],
    )
    bot = fake_bot()
    # bare yes — the orphan case
    await _run(shell, bot, make_update(1, OWNER_ID, "نعم"))
    assert coordinator.replies == ["نعم"]
    assert shell.gateway.router_calls == []  # brain NEVER consulted for the orphan
    assert shell.gateway.stream_calls == []

    # bare refusal — guarded too
    await _run(shell, bot, make_update(2, OWNER_ID, "لا"))
    assert coordinator.replies == ["نعم", "لا"]
    assert shell.gateway.stream_calls == []

    # real chat during the pending window — NOT guarded, streams normally
    await _run(shell, bot, make_update(3, OWNER_ID, "شو رأيك بهالموضوع؟"))
    assert coordinator.replies == ["نعم", "لا", "شو رأيك بهالموضوع؟"]
    assert shell.gateway.router_calls  # brain consulted
    assert shell.gateway.router_calls[-1][-1]["content"] == "شو رأيك بهالموضوع؟"


async def test_pending_confirmation_turns_enter_memory(fake_bot, make_shell):
    """Remediation 2.4 (audit C-8): a consumed «افتح X → نعم» turn lands in
    memory — the next turn's history carries the confirmation line and the
    result, so the brain knows what actually happened."""
    from src.memory import ConversationMemory

    memory = ConversationMemory()
    coordinator = _CoordinatorDouble(target="calculator", memory=memory)
    shell = make_shell(
        coordinator=coordinator,
        memory=memory,
        router_replies=[_router("tier2", "تم")],
        stream_programs=[StreamProgram(deltas=("رد",))],
    )
    bot = fake_bot()
    await _run(shell, bot, make_update(1, OWNER_ID, "نعم"))  # consumed confirmation
    await _run(shell, bot, make_update(2, OWNER_ID, "شو فتحتلي؟"))

    history = memory.history(OWNER_ID)
    contents = [m["content"] for m in history]
    assert any("نعم" in c for c in contents)  # the confirmation line entered
    assert any("calculator" in c for c in contents)  # the RESULT entered


# --- remediation 2.5 (dead learning loop): «تعلمي:» writes the vault ----------------


async def test_teach_line_writes_dialect_notes_and_updates_live_lexicon(fake_bot, make_shell):
    """«تعلمي: كفيك -> كفايك» → Dialect_Notes actually UPSERTED in the vault AND
    the live synthesis lexicon updated (the voice pipeline shapes the NEXT reply
    with the owner's pronunciation). The loop: teach → vault → speech + envelope."""
    vault = _VaultDouble(
        {
            "02_Areas/Profile/Dialect_Notes.md": "---\nnotes:\n  - term: هسا\n    phonetic: هسَّا\n---\n"
        }
    )
    shell = make_shell(
        vault=vault,
        router_replies=[_router("tier2", "تم")],
        stream_programs=[StreamProgram(deltas=("كفيك",))],
    )
    bot = fake_bot()
    await _run(shell, bot, make_update(1, OWNER_ID, "تعلمي: كفيك -> كفايك"))

    # the teaching reached the brain turn normally
    assert shell.gateway.stream_calls

    from tests.conftest import wait_until

    await wait_until(lambda: any("Dialect_Notes" in p for p, _ in vault.writes))
    content = next(c for p, c in vault.writes if "Dialect_Notes" in p)
    assert "كفيك" in content and "كفايك" in content  # the pair landed in the vault


async def test_teach_line_refreshes_live_voice_lexicon(fake_bot, make_shell):
    """2.5 live half: after «تعلمي:», the voice pipeline's notes are refreshed
    from the vault — the next synthesis shapes with the learned pair (no reboot)."""
    vault = _VaultDouble(
        {
            "02_Areas/Profile/Dialect_Notes.md": "---\nnotes:\n  - term: هسا\n    phonetic: هسَّا\n---\n"
        }
    )
    updated_notes: list = []

    class _NotedVoice(_ConftestFakeVoice):
        def update_notes(self, notes):
            updated_notes.extend(notes)

    shell = make_shell(
        vault=vault,
        custom_voice=_NotedVoice(),
        router_replies=[_router("tier2", "تم")],
        stream_programs=[StreamProgram(deltas=("رد",))],
    )
    bot = fake_bot()
    await _run(shell, bot, make_update(1, OWNER_ID, "تعلمي: كفيك -> كفايك"))

    from tests.conftest import wait_until

    await wait_until(lambda: updated_notes)
    terms = {n.term for n in updated_notes}
    assert "كفيك" in terms and "هسا" in terms  # learned pair + boot pairs both live


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
    assert second[2] == {
        "role": "assistant",
        "content": "رد1",
    }  # remediation 1.3: answer-only, ack dropped
    assert second[-1] == {"role": "user", "content": "شو رأيك؟"}
    assert memory.history(OWNER_ID)[-1] == {"role": "assistant", "content": "رد2"}


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
    assert writer.exchanges == [
        ("مرحبا", "رد")
    ]  # remediation 1.3: ledger gets the answer without the ack
    assert writer.learns == ["مرحبا"]


async def test_voice_origin_reply_arrives_as_voice_note(
    fake_bot, make_shell, monkeypatch, tmp_path
):
    """Voice in, VOICE out only (remediation 1.4): an enrolled owner voice note gets
    the streamed answer as ONE voice note — zero duplicated answer text bubble
    (audit C-3: the old text+voice double delivery died here)."""
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

        # remediation 1.4: the answer lands ONCE, as the voice note itself — no
        # placeholder bubble, no edits, no answer-text SendMessage (audit C-3).
        answer_text_bubbles = [
            c.method.text
            for c in bot.session.sent("SendMessage")
            if c.method.text not in (ENROLL_PROMPT_AR, ENROLL_DONE_AR, "…")
        ]
        assert answer_text_bubbles == []
        assert bot.session.sent("EditMessageText") == []
        assert shell.voice.calls == ["رتبت لك الموضوع"]  # synthesis input = answer only, ack-free
    finally:
        _ENROLL_PENDING.clear()


async def test_voice_origin_synthesis_failure_falls_back_to_text(
    fake_bot, make_shell, monkeypatch, tmp_path
):
    """Voice origin + synthesis dead -> the answer still arrives as ONE text bubble
    (the honest fallback branch of remediation 1.4) — never silence."""
    monkeypatch.chdir(tmp_path)
    transcriber = FakeTranscriber()
    shell = make_shell(
        VAULT_ENC_KEY=Fernet.generate_key().decode(),
        voice_error=RuntimeError("voice engine down"),
        router_replies=[_router("tier2", "تم")],
        stream_programs=[StreamProgram(deltas=("الجواب الصوتي",))],
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
        await _run(shell, bot, make_update(3, OWNER_ID, voice=True))
        assert bot.session.sent("SendVoice") == []  # synthesis dead -> no voice note
        texts = [
            c.method.text
            for c in bot.session.sent("SendMessage")
            if c.method.text not in (ENROLL_PROMPT_AR, ENROLL_DONE_AR, "…")
        ]
        assert texts[-1] == "الجواب الصوتي"  # ...but the answer text arrives
    finally:
        _ENROLL_PENDING.clear()


# --- Remediation 1.2 (owner directive 2026-09-03): the persona contract ————————
# --- Sara knows her creator; service-register and gateway identity are banned. ——


class _SilentTools:
    """Launch-shaped registry: the coordinator already notified the owner directly."""

    async def call(self, tool, arg):
        return None


async def test_launch_turn_keeps_ack_bubble_no_empty_reply(fake_bot, make_shell):
    """Remediation 1.3 silent tool lane: launch already notified the owner — the
    bubble keeps the transient ack, NO EMPTY_REPLY follows, and nothing fake lands
    in memory (the ack is never remembered as a reply)."""
    from src.memory import ConversationMemory

    memory = ConversationMemory()
    verdict = json.dumps(
        {"route": "tier2", "tool": "launch", "arg": "calc", "ack": "من عيوني"},
        ensure_ascii=False,
    )
    shell = make_shell(
        memory=memory,
        tools=_SilentTools(),
        router_replies=[verdict],
        stream_programs=[],
    )
    bot = fake_bot()
    await _run(shell, bot, make_update(1, OWNER_ID, "افتحي الآلة الحاسبة"))

    edits = bot.session.sent("EditMessageText")
    assert edits[-1].method.text == "من عيوني"  # bubble holds the ack
    send_texts = [c.method.text for c in bot.session.sent("SendMessage")]
    assert send_texts == ["…"]  # placeholder only — no EMPTY_REPLY_AR, no fake answer
    assert memory.history(OWNER_ID) == []  # the ack never masquerades as a reply


def test_persona_contract_recognizes_creator():
    """The system prompt names عمر الفياض as her sole creator/engineer."""
    assert "عمر الفياض" in SYSTEM_PROMPT_AR
    assert "صانعك" in SYSTEM_PROMPT_AR


def test_persona_contract_bans_service_register_explicitly():
    """Customer-service phrasing is forbidden BY NAME in the prompt (so the model
    can never produce it as Sara's voice)."""
    for banned in ("كيف أساعدك", "كيف فيني ساعدك اليوم", "يسرني خدمتك", "أعدك بأن"):
        assert banned in SYSTEM_PROMPT_AR


def test_persona_contract_bans_gateway_identity_explicitly():
    """«أنا بوابة سارة»-class identity leakage is forbidden BY NAME — the audit
    found the third-person gateway framing is the mechanical source of the
    owner-reported robotic identity lines."""
    for banned in ("بوابة", "مساعد آلي", "بوت", "برنامج", "خدمة عملاء"):
        assert banned in SYSTEM_PROMPT_AR


def test_persona_contract_pins_feminine_first_person():
    assert "بصيغة المؤنث" in SYSTEM_PROMPT_AR  # أنا سارة، جاهزة، بقدر، رح أعمل


def test_persona_contract_requires_action_honesty():
    """Sara may claim an action ONLY from a real tool result in the same turn —
    the anti-hallucination clause (audit C-1 defense-in-depth)."""
    assert "ناتج الأداة" in SYSTEM_PROMPT_AR
    assert "عمرك ما تدّعي" in SYSTEM_PROMPT_AR


def test_persona_contract_human_with_real_capabilities():
    """Owner directive 2026-09-03 04:23: Sara is a HUMAN companion with REAL
    tool access — she opens his programs (whitelist), hears his voice notes,
    reads his Gmail/Calendar/Tasks, sees his device telemetry. She must NEVER
    present herself as a limited text-AI or deny her real capabilities; what
    she genuinely cannot do in a turn, she routes internally to the right
    lane and answers naturally — never exposes tier/model/routing internals
    (one entity: it is all Sara)."""
    for clause in (
        "بتفتحيله برامجه",
        "بتسمعين ملاحظاته الصوتية",
        "ما بتنكري قدراتك",
        "كيان واحد",
    ):
        assert clause in SYSTEM_PROMPT_AR


def test_persona_contract_no_service_pushiness():
    """Owner directive 2026-09-03: Sara never pushes offers of help — no
    closing service lines; she flows WITH the conversation, asks natural
    follow-up questions like a friend, not an assistant fishing for tickets."""
    assert "ما بتقدمي نفسك لمساعدات" in SYSTEM_PROMPT_AR
    assert "بتساييرين النقاش" in SYSTEM_PROMPT_AR
