"""Directive §3+§4 (owner 2026-09-04, live 3:41-3:33pm rounds): REAL voice
dispatch + REAL photo dispatch.

§3: «عرفي عن حالك بصوتك» / «بدي اسمع صوتك» must ALWAYS end as ONE synthesized
Ogg-Opus voice note — the model NEVER prints external audio URLs (the live
hallucinated sara-voice.s3.amazonaws.com links), never claims an inability to
send audio on Telegram.

§4: «بتقدري تبعثيلي السكرين شوت؟» must deliver the captured JPEG as a REAL
Telegram photo (answer_photo), not a text description."""

from __future__ import annotations

from src.skills.reply_modality import forced_modality


def test_hearing_her_voice_phrases_force_voice():
    """Every live-failure phrasing forces the voice channel — the router can
    never misroute these as launch/app tools."""
    for phrase in (
        "عرفي عن حالك بصوتك",
        "بدي اسمع صوتك",
        "سمعيني صوتك",
        "ابعتيلي رسالة صوتية عن حالك",
        "بدي اسمع صوتك برسالة صوتية على التيليغرام",
        "احكي عن حالك بصوت",
    ):
        assert forced_modality(phrase) == "voice", phrase


def test_external_audio_url_is_structurally_stripped():
    """Whatever the model emits, synthesized dispatch NEVER carries an external
    audio link into the Telegram message — the sanitizer strips them (defense
    behind the prompt)."""
    from src.voice import strip_external_media_links

    dirty = "هاي رسالتي الصوتية إليك 🌸\n\nhttps://sara-voice.s3.amazonaws.com/clips/voice.mp3"
    clean = strip_external_media_links(dirty)
    assert "s3.amazonaws.com" not in clean
    assert "http" not in clean
    assert "هاي رسالتي" in clean  # the real text survives


def test_screenshot_request_net_routes_to_screenshot():
    """«بعثيلي/ارسلي السكرين شوت» routes to the screenshot tool — the request
    to RECEIVE the capture is a screenshot intent, never a launch."""
    from src.dispatcher import _keyword_net

    for phrase in (
        "بتقدري تبعثيلي السكرين شوت",
        "ابعثيلي السكرين شوت",
        "ارسلي لقطة الشاشة",
        "بعتيلي لقطة شاشة الجهاز",
    ):
        tool, _arg = _keyword_net(phrase)
        assert tool == "screenshot", phrase


async def test_screenshot_tool_sends_real_photo_when_asked_to_receive():
    """§4: a delivery request -> the JPEG is dispatched via answer_photo FIRST,
    then the vision description answers — never a text-only reply."""
    import base64

    from src.tools import ToolRegistry

    JPEG = b"\xff\xd8\xff fake"

    class _Bridge:
        async def send_cmd(self, cmd, args, *, timeout_s=20.0):
            return {
                "status": "ok",
                "detail": base64.b64encode(JPEG).decode(),
            }

    class _Vision:
        async def chat(self, messages, **kw):
            return "شايفها — تيليجرام مفتوح 🌸"

    sent: list[bytes] = []

    async def photo_sender(jpeg_bytes: bytes) -> None:
        sent.append(jpeg_bytes)

    tools = ToolRegistry(bridge=_Bridge(), vision=_Vision(), photo_sender=photo_sender)
    answer = await tools.call("screenshot", "")
    assert sent == [JPEG]  # the REAL photo was dispatched
    assert answer == "شايفها — تيليجرام مفتوح 🌸"


async def test_screenshot_photo_failure_never_kills_description():
    """A dead photo surface degrades to the description — both surfaces tried,
    neither blocks the other."""
    import base64

    from src.tools import ToolRegistry

    class _Bridge:
        async def send_cmd(self, cmd, args, *, timeout_s=20.0):
            return {"status": "ok", "detail": base64.b64encode(b"\xff\xd8").decode()}

    class _Vision:
        async def chat(self, messages, **kw):
            return "وصف الشاشة"

    async def broken_sender(jpeg_bytes):
        raise RuntimeError("telegram photo API down")

    tools = ToolRegistry(bridge=_Bridge(), vision=_Vision(), photo_sender=broken_sender)
    answer = await tools.call("screenshot", "")
    assert answer == "وصف الشاشة"
