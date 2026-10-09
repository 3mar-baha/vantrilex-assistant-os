"""Telegram transport shell: long polling, owner gate, handlers, progressive streaming.

The owner text path streams through the front-door dispatcher: placeholder ->
first edit on the ack (<250 ms TTFT) -> coalesced edits -> final verbatim edit.
Owner directive (2026-09-01): every turn carries the dual-tier memory envelope
(50-message rolling history + Obsidian long-term excerpt), background writers
persist exchanges to the vault, tool intents execute real backends, and voice
messages get a voice note back. A pending PC-launch confirmation is answered by
the coordinator before the brain ever sees it. Every handler exception is
mapped to a Jordanian apology — the owner is never left hanging.
"""

import asyncio
import base64
import dataclasses
import io
import re
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final
from zoneinfo import ZoneInfo

import httpx  # M4: the shared external-APIs client
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import BufferedInputFile, ErrorEvent, Message
from loguru import logger

from bridge.guard import Guard
from common.consent import AFFIRMATIVES
from src.config import Settings
from src.decision_loop import react_loop_enabled, run_decision_loop
from src.dispatcher import FrontDoorDispatcher
from src.external_apis import ExternalAPIs
from src.fish_voice import FishFirstVoice, FishVoice
from src.gateway import GatewayError, OmniRouteClient, Tier
from src.memory import (
    LONG_TERM_HEADER_AR,
    AffectiveStateTracker,
    ConversationMemory,
    DailySummarizer,
    VaultMemoryWriter,
    load_long_term,
)
from src.middleware import OwnerOnlyMiddleware
from src.pc_actions import PCActionCoordinator
from src.persona import SARA_PERSONA_AR, build_persona_joda
from src.situational import SituationalState
from src.skills.telegram_chat_streamer import ChatStreamer
from src.skills.voice_biometric_auth import VoiceBiometrics, owner_voice_gate
from src.skills.voice_to_vault_transcriber import _DEFAULT_PROMPT_TERMS, VoiceToVault
from src.telemetry import TelemetryClient
from src.tools import ToolRegistry
from src.turn_counter import bump_turn_counter
from src.vault import (
    VaultClient,
    ensure_master_digest,
    ensure_resources_scaffolding,
    ensure_vault_scaffolding,
)

SYSTEM_PROMPT_AR = SARA_PERSONA_AR  # alias: literal lives in src/persona.py (Phase-1 extraction); external importers keep working
WELCOME_AR: Final[str] = "يا هلا عمر! شغّالة وجاهزة — ابعثلي أي شي."
GREETING_AR: Final[str] = "أهلا فيك، أنا سارة، جاهزة أوامر."
# Step-9 (2026-09-14): the SINGLE allowed static offline string — /start
# while the PC bridge is down. WoL fires first (when PC_MAC_ADDRESS is set);
# everything else Sara says is composed live.
WOL_OFFLINE_AR: Final[str] = (
    "أهلين عمر! 🌟 بعثت إشارة تشغيل الجهاز (WOL)، وعم بيصحى هسا... "
    "أول ما يشبك الجسر وأومني روت رح أعطيك خبر فوراً!"
)
HELP_AR: Final[str] = (
    "أنا سارة — مساعدتك التنفيذية وهسا بذاكر محادثاتنا. بقدر: دردشة بأي موضوع، "
    "أفحص بريدك وتقويمك ومهامك، أطلعلك حالة جهازك من الجسر، وأفتحلك أي برنامج "
    "عالكمبيوتر (بتأكيدك). ابعتلي رسالة صوتية وبجاوبك صوت."
)
EMPTY_VOICE_AR: Final[str] = "ما سمعت شي واضح بالملاحظة — جرب ابعتها مرة ثانية وأنا سامعتك أحسن."
APOLOGY_AR: Final[str] = "سامحني، صار خلل تقني بسيط. جرب مرة ثانية."
EMPTY_REPLY_AR: Final[str] = (
    "رسالتك وصلت بس ما قدرت أركّب رد مضبوط هالمرة — جرّبها بصياغة تانية وبستناها."
)
ENROLL_PROMPT_AR: Final[str] = "تمام، ابعتلي هسا ملاحظة صوتية قصيرة وأسجل بصمتك."
ENROLL_DONE_AR: Final[str] = "سجّلت بصمتك! من هسا بصوتك بتعرفني — أهلا فيك!"
MEDIA_TOO_BIG_AR: Final[str] = "هاد الملف كبير كتير عن اللي بقدر أعالجه — جرّب ملف أصغر."
DEFAULT_MEDIA_PROMPT_AR: Final[str] = "دقّقي فيه وقوليلي شو بتشوفي."
_MEDIA_MAX_BYTES: Final[int] = 10 * 1024 * 1024  # raw bytes; base64 inflates ~4/3 on the wire

_STREAMS: Final[dict[int, tuple[asyncio.Task, asyncio.Event]]] = {}
_ENROLL_PENDING: Final[set[int]] = set()
_PERSIST_TASKS: Final[set[asyncio.Task]] = set()
# Remediation 2.4 (audit C-8): bare refusal markers — a short «لا» left after a
# rejected/failed PC confirmation must not fall through to the brain as an orphan.
_REFUSALS: Final[tuple[str, ...]] = ("لا", "مش هلق", "بعدين", "لأ")
_ORPHAN_MAX_TOKENS: Final[int] = 3


def is_bare_confirmation_token(text: str) -> bool:
    """A bare short consent/refusal reply — the ONLY shape guarded by the 2.4
    orphan net. Real chat («شو رأيك بهالموضوع؟») keeps flowing to the brain."""
    tokens = text.strip().casefold().split()
    if not tokens or len(tokens) > _ORPHAN_MAX_TOKENS:
        return False
    return tokens[0] in AFFIRMATIVES or tokens[0] in _REFUSALS


def _make_photo_sender(bot: Bot, chat_id: int):
    """§4 (owner 2026-09-04): the screenshot tool's REAL-photo surface —
    exactly the directive's answer_photo(BufferedInputFile(jpeg, ...)) with her
    caption. One callable, injected into the registry."""

    async def _send(jpeg_bytes: bytes) -> None:
        await bot.send_photo(
            chat_id,
            BufferedInputFile(jpeg_bytes, filename="screenshot.jpg"),
            caption="تفضل، هاي لقطة شاشتك هسا 🌸",
        )

    return _send


def wake_decision(mac: str | None, bridge_online: bool) -> str:
    """Step-9 /start routing (pure): "welcome" (bridge live — legacy greeting),
    "wol_offline" (MAC set + bridge down — fire WoL, static offline string),
    "no_mac" (bridge down, nothing to wake with — legacy welcome; claiming a
    WoL signal never sent would violate the honesty doctrine)."""
    if bridge_online:
        return "welcome"
    if (mac or "").strip():
        return "wol_offline"
    return "no_mac"


def _tunnel_online(bridge_tunnel) -> bool:
    """Bridge liveness probe that never raises (a crashing probe reads as
    offline-for-welcome — but the caller then takes the welcome path, never
    a spurious WoL)."""
    try:
        return bool(bridge_tunnel is not None and bridge_tunnel.online())
    except Exception:  # noqa: BLE001 — probe failure degrades to welcome
        logger.warning("bridge online probe failed; treating as offline-for-welcome")
        return False


async def _send_wol(mac: str) -> None:
    """Lazy WoL import (monkeypatchable as src.bot._send_wol in tests)."""
    from bridge.wol import send_wol

    await send_wol(mac)


def _hhmm(value: str) -> tuple[int, int]:
    hours, _, minutes = value.strip().partition(":")
    return int(hours), int(minutes or 0)


def in_active_window(
    now: datetime, tzname: str, *, start: str = "08:00", end: str = "23:30"
) -> bool:
    """Quiet-hours guard core (Step 9): True when wall-clock `now` falls in
    [start, end] in `tzname` (overnight wraps supported). Pure + total."""
    local = now.astimezone(ZoneInfo(tzname))
    point = (local.hour, local.minute)
    lower, upper = _hhmm(start), _hhmm(end)
    if lower <= upper:
        return lower <= point <= upper
    return point >= lower or point <= upper


def should_greet_on_reconnect(
    *,
    last_greet_ts: float | None,
    now_ts: float,
    last_turn_ts: float | None,
    in_window: bool,
    debounce_s: float = 1800.0,
    recent_turn_s: float = 900.0,
) -> bool:
    """Reconnect-greeting policy (pure): in-window greets on first sight or
    past debounce; nocturnal stays silent unless an owner turn landed within
    the recent-turn window. All epochs share one clock (time.time)."""
    if in_window:
        return last_greet_ts is None or (now_ts - last_greet_ts) >= debounce_s
    return last_turn_ts is not None and (now_ts - last_turn_ts) <= recent_turn_s


def make_bridge_greeter(*, bot, chat_id: int, gateway, vault=None, tzname: str = "Asia/Amman"):
    """Dynamic reconnect greeting factory (spontaneity doctrine): composes
    persona + best-effort profile excerpt through one FAST call and sends it
    as text. Any failure raises (the watcher logs and does NOT stamp
    last_greet, so the next reconnect retries) — never a canned string."""

    async def _greet() -> None:
        # F-6 follow-up (owner decision 2026-10-01): the greeter is the THIRD
        # owner-visible persona surface and was the LAST one still speaking MSA
        # while Telegram and Terminal 1 spoke ar-JO. Unified on the BUILDER, not
        # on a copied literal — a literal here would be a second source of truth,
        # which is the drift this removes. The identity core is still
        # byte-identical (`build_persona_joda` STARTS with it), so every
        # byte-locked persona law is untouched. ONLY the system prompt changed:
        # the greeting's own words, below, are the owner's and were NOT reworded,
        # and are frozen byte-for-byte by
        # tests/test_greeter_persona_parity.py::test_the_greeting_instruction_bytes_are_unchanged.
        system = build_persona_joda()
        if vault is not None:
            try:
                excerpt = " ".join((await vault.read("02_Areas/Profile/User_Info.md")).split())
                if excerpt:
                    system = f"{system}\n\n[صاحبك باختصار — بيانات مرجعية]\n{excerpt[:500]}"
            except Exception as error:  # noqa: BLE001 — profile is garnish, not load-bearing
                logger.warning("bridge greeting profile excerpt failed: {}", error)
        reply = await gateway.chat(
            [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": "رجع الاتصال مع جهاز عمر هسا بعد انقطاع — حيّيه بجملة أو جملتين "
                    "بعاميتك الدافئة حسب وقت النهار، واذكر إنك رجعت.",
                },
            ],
            tier=Tier.FAST,
            temperature=0.7,
            max_tokens=256,
        )
        text = (reply or "").strip()
        if not text:
            raise ValueError("blank bridge greeting")
        await bot.send_message(chat_id, text)

    return _greet


async def run_bridge_watcher(
    *,
    bridge_tunnel,
    greet,
    tzname: str = "Asia/Amman",
    now_fn=None,
    last_turn_fn=None,
    poll_s: float = 15.0,
    debounce_s: float = 1800.0,
    window_start: str = "08:00",
    window_end: str = "23:30",
    stop=None,
) -> None:
    """Bridge-reconnect monitor (Step 9): polls liveness, greets once per
    reconnect honoring debounce + quiet hours. No greet on boot (initial
    state seeds silently). Any single failure degrades to a skipped poll —
    the loop outlives everything except cancellation or `stop`."""
    import datetime as _datetime

    now_fn = now_fn or (lambda: _datetime.datetime.now(_datetime.UTC))
    last_turn_fn = last_turn_fn or (lambda: None)
    was_online = _tunnel_online(bridge_tunnel)
    last_greet: float | None = None
    while True:
        if stop is not None:
            try:
                await asyncio.wait_for(stop.wait(), timeout=poll_s)
            except TimeoutError:
                pass
            else:
                return
        else:
            await asyncio.sleep(poll_s)
        online = _tunnel_online(bridge_tunnel)
        if not (online and not was_online):
            was_online = online
            continue
        was_online = True
        try:
            now = now_fn()
            if should_greet_on_reconnect(
                last_greet_ts=last_greet,
                now_ts=now.timestamp(),
                last_turn_ts=last_turn_fn(),
                in_window=in_active_window(now, tzname, start=window_start, end=window_end),
                debounce_s=debounce_s,
            ):
                await greet()
                last_greet = now.timestamp()
        except asyncio.CancelledError:
            raise
        except Exception as error:  # noqa: BLE001 — a failed greeting retries next reconnect
            logger.warning("bridge greeting failed (unstamped, will retry): {}", error)


def build_dispatcher(
    gateway,
    voice,
    settings: Settings,
    transcriber=None,
    *,
    vault=None,
    memory=None,
    writer=None,
    tools=None,
    coordinator=None,
    decide_modality=None,
    initial_prompt_terms=None,
    affect=None,
    bridge_tunnel=None,  # M3: the bridge server (start_station handshake probe)
    situational=None,  # Phase-6 (Leap 3): ambient posture state; created when None
) -> Dispatcher:
    """gateway: the OmniRouteClient; wrapped here in the ADR-18 front door.
    transcriber: injectable for tests; production builds the local Whisper one.
    vault/memory/writer/tools/coordinator: dual-tier memory + tool-lane wiring;
    None keeps the legacy bare-chat behavior (tests, degraded boots).
    decide_modality: the reply-surface chooser (owner 2026-09-03: 70/30 mirror
    + explicit request); None falls back to the shipped skill.
    initial_prompt_terms: 2.6 — the Whisper Arabic bias seed (boot pairs)."""
    dp = Dispatcher()
    dp.update.outer_middleware(OwnerOnlyMiddleware(settings.authorized_user_id))
    front = FrontDoorDispatcher(gateway, settings)
    # Phase-6 (Leaps 2+3): ambient context residents — the RAG index (mtime
    # cached, one per dispatcher) and the posture ring (fed by the future
    # heartbeat transport; dp["situational"] is its public handle).
    from src.associative import VaultIndex
    from src.situational import SituationalState

    assoc_index = VaultIndex(settings.vault_local_path)
    if situational is None:
        situational = SituationalState()
    dp["situational"] = situational
    # M6 (owner's mediating-layer design, 2026-09-05): every tool turn's
    # narration carries THAT tool's skill guide — the dispatcher consults the
    # bound vault; run_bot syncs the guides at boot so they stay current.
    if vault is not None:
        front.set_skill_vault(vault)
    decide = decide_modality
    if decide is None:
        from src.skills.reply_modality import decide_reply_modality  # local: lands with its usage

        decide = decide_reply_modality
    if transcriber is None:
        trans_kwargs = {}
        if initial_prompt_terms is not None:
            trans_kwargs["initial_prompt_terms"] = initial_prompt_terms
        transcriber = VoiceToVault(
            model_size=settings.whisper_model_size,
            compute_type=settings.whisper_compute_type,
            executor=ThreadPoolExecutor(max_workers=1, thread_name_prefix="whisper"),
            vault_dir=Path(settings.vault_local_path) / settings.voice_memos_dir,
            tz=ZoneInfo(settings.tz),
            **trans_kwargs,
        )
    bio = VoiceBiometrics(
        embedding_path=Path(settings.vault_local_path) / "State" / "owner_voiceprint.enc",
        threshold=settings.voiceprint_threshold,
        model_id=settings.voiceprint_model,
        enc_key=settings.vault_enc_key,
    )
    # §1 (2026-09-04): the VoiceprintRegistry no longer rides the voice gate —
    # sender-ID is the sole authorization; ECAPA vectors feed diarization only.

    @dp.message(CommandStart())
    async def on_start(message: Message) -> None:
        # Step 9 (2026-09-14): cold-boot WoL — MAC set + bridge down fires
        # one magic packet, then the SINGLE static offline string (mandated
        # wording). Bridge live (or no MAC to wake with) keeps the legacy
        # welcome + voice flow untouched.
        if wake_decision(settings.pc_mac_address, _tunnel_online(bridge_tunnel)) == "wol_offline":
            try:
                await _send_wol((settings.pc_mac_address or "").strip())
            except Exception as error:  # noqa: BLE001 — dead WoL is honest, not fatal
                logger.warning("on_start WoL failed: {}", error)
            await message.answer(WOL_OFFLINE_AR)
            return
        await message.answer(WELCOME_AR)
        try:
            ogg = await voice.synthesize(GREETING_AR)
            await message.answer_voice(BufferedInputFile(ogg, filename="sara.ogg"))
        except Exception:  # noqa: BLE001 — any synthesis/send failure degrades to text-only (spec error mode)
            logger.warning("voice greeting synthesis failed; welcome text already delivered")

    @dp.message(Command("help"))
    async def on_help(message: Message) -> None:
        await message.answer(HELP_AR)

    @dp.message(Command("enroll-voice"))
    async def on_enroll_voice(message: Message) -> None:
        _ENROLL_PENDING.add(message.chat.id)
        await message.answer(ENROLL_PROMPT_AR)

    @dp.message(Command("start_station"))
    async def on_start_station(message: Message, bot: Bot) -> None:
        """M3 (master directive 2026-09-05 §2-B): deterministic station boot —
        strictly out-of-band (zero LLM). The OwnerOnly middleware already
        guarantees this fires for the owner alone."""
        mac = settings.pc_mac_address or ""
        if not mac:
            await message.answer(
                "⚠️ ما ضبطت MAC جهازك بالاعدادات (PC_MAC_ADDRESS) — ضبطها وبشتغل فوراً 🌸"
            )
            return

        handler = make_start_station_handler(
            bot=bot,
            chat_id=message.chat.id,
            mac=mac,
            wait_online=_bridge_handshake_probe(bridge_tunnel),
            launch_station=_station_launcher(coordinator),
        )
        asyncio.create_task(handler())

    @dp.message(F.voice)
    async def on_voice(message: Message, bot: Bot) -> None:
        enrolling = message.chat.id in _ENROLL_PENDING
        ogg = await _download_voice(bot, message)
        if enrolling:
            _ENROLL_PENDING.discard(message.chat.id)
            await bio.enroll(ogg)
            await message.answer(ENROLL_DONE_AR)
            return
        # Directive §1 (owner 2026-09-04): EXECUTION AUTHORIZATION IS 100%
        # SENDER-ID — any voice note from the owner's account has full
        # permissions from ANY device/mic; the biometric NEVER locks his own
        # account (it feeds the diarization/labeling lane only). Non-owner
        # accounts never reach here (OwnerOnlyMiddleware drops them silently);
        # owner_voice_gate keeps the belt under those suspenders.
        allowed = await owner_voice_gate(
            bio=bio,
            ogg_opus=ogg,
            chat_id=message.chat.id,
            authorized_id=int(settings.authorized_user_id),
            vault_root=Path(settings.vault_local_path),
            enc_key=settings.vault_enc_key,
        )
        if not allowed:
            return
        try:
            text = await transcriber.transcribe(ogg)  # LOCAL Whisper only (§2.5)
        except Exception:  # noqa: BLE001 — transcription failure gets the honest voice line
            logger.exception("voice transcription failed")
            await _voice_fail_reply(message, bot, voice)
            return
        await transcriber.file_note(
            text,
            received_at=message.date or datetime.now(UTC),
            duration_s=float(message.voice.duration or 0),
        )  # contract: retried once, never raises into the reply pipeline
        if not text.strip():
            logger.warning(
                "voice transcription empty (silent mic?) duration_s={}",
                float(message.voice.duration or 0),
            )
            await _voice_fail_reply(message, bot, voice)
            return
        # 2.3 (audit C-2, sacred floor): mirror on_text — a pending PC
        # confirmation answered by VOICE «نعم» is consumed by the coordinator,
        # never streamed to the brain.
        # F-6 (audit C-2): `pending_open()`, not `pending_active()`. A
        # confirmation past its TTL is still a DECISION awaiting an answer;
        # gating on `pending_active()` made it invisible the instant the TTL
        # passed, so «نعم» became an ordinary chat message and the owner was
        # never told the request had lapsed. `pending_open()` is True for a
        # live prompt AND for an expired-but-unanswered one, so the reply
        # reaches the coordinator, which refuses it out loud.
        if coordinator is not None and coordinator.pending_open():
            consumed = await coordinator.handle_owner_reply(text)
            if consumed is not None:
                return
            if is_bare_confirmation_token(text):
                return  # 2.4 (C-8): a bare «نعم»/«لا» orphan never reaches the brain
        # Feature 3 (v1.1): the acoustic texture of HOW he spoke rides the
        # envelope — deterministic local DSP, best-effort, never breaks the turn.
        from src.skills.acoustic_nuance import ogg_paralinguistic_block

        acoustic = ogg_paralinguistic_block(ogg)
        bump_turn_counter(Path(settings.vault_local_path))  # P2: human turn tally
        _spawn_stream(message, bot, text, voice_origin=True, acoustic=acoustic)

    @dp.message(F.text)
    async def on_text(message: Message, bot: Bot) -> None:
        # F-6 (audit C-2): `pending_open()`, not `pending_active()`. A
        # confirmation past its TTL is still a DECISION awaiting an answer;
        # gating on `pending_active()` made it invisible the instant the TTL
        # passed, so «نعم» became an ordinary chat message and the owner was
        # never told the request had lapsed. `pending_open()` is True for a
        # live prompt AND for an expired-but-unanswered one, so the reply
        # reaches the coordinator, which refuses it out loud.
        if coordinator is not None and coordinator.pending_open():
            target = await coordinator.handle_owner_reply(message.text)
            if target is not None:
                return  # consumed as the launch confirmation/rejection
            if is_bare_confirmation_token(message.text):
                return  # 2.4 (C-8): a bare «نعم»/«لا» orphan never reaches the brain
        # Reply-awareness (owner 2026-09-03): when the owner replies to a specific
        # message, Sara must KNOW it — the quote reaches the brain as context.
        text = message.text
        quoted = getattr(message, "reply_to_message", None)
        if quoted is not None:
            quoted_text = quoted.text or quoted.caption or ""
            quoted_label = quoted_text.strip()[:120]
            if quoted_label:
                text = f"{text}\n\n[عمر ردّ على رسالة سابقة: «{quoted_label}» — خديها بالحسبان]"
        bump_turn_counter(Path(settings.vault_local_path))  # P2: human turn tally
        _spawn_stream(message, bot, text)

    @dp.message(F.photo)
    async def on_photo(message: Message, bot: Bot) -> None:
        """Media comprehension (owner directive 2026-09-03): a photo the owner
        sends is understood natively — m3's image input describes it. m3 takes
        image_url data-URIs; the caption (or the default ask) is the prompt."""
        await _media_stream(message, bot, media_type="image")

    @dp.message(F.video)
    async def on_video(message: Message, bot: Bot) -> None:
        """A video the owner sends is understood via m3's video input channel."""
        await _media_stream(message, bot, media_type="video")

    async def _media_stream(message: Message, bot: Bot, *, media_type: str) -> None:
        file = message.photo[-1] if media_type == "image" else message.video
        buffer = await bot.download(file, destination=io.BytesIO())
        raw = buffer.getvalue()
        if len(raw) > _MEDIA_MAX_BYTES:
            await message.answer(MEDIA_TOO_BIG_AR)
            return
        prompt = (message.caption or DEFAULT_MEDIA_PROMPT_AR).strip() or DEFAULT_MEDIA_PROMPT_AR
        b64 = base64.b64encode(raw).decode()
        mime = "image/jpeg" if media_type == "image" else "video/mp4"
        block = {
            "type": f"{media_type}_url",
            f"{media_type}_url": {"url": f"data:{mime};base64,{b64}"},
        }
        _spawn_stream(message, bot, prompt, media=[block])

    def _spawn_stream(
        message: Message,
        bot: Bot,
        text: str,
        *,
        voice_origin: bool = False,
        media: list[dict] | None = None,
        acoustic: str = "",
    ) -> None:
        previous = _STREAMS.get(message.chat.id)
        if previous is not None:
            # Owner interjection: signal the in-flight stream AND hard-cancel its
            # task (remediation 1.7 / audit V-3 — the Event only lands between
            # deltas, so a mid-flight block would otherwise live on as a zombie
            # firing late edits/voice from a dead turn).
            previous[1].set()
            previous[0].cancel()
        cancel = asyncio.Event()
        task = asyncio.create_task(
            _stream_answer(
                bot,
                front,
                message,
                settings,
                cancel,
                text,
                decide,
                voice=voice,
                vault=vault,
                memory=memory,
                writer=writer,
                tools=tools,
                voice_origin=voice_origin,
                media=media,
                transcriber=transcriber,
                affect=affect,
                acoustic=acoustic,
                situational=situational,
                assoc_index=assoc_index,
            )
        )
        _STREAMS[message.chat.id] = (task, cancel)

    @dp.errors()
    async def on_error(event: ErrorEvent) -> bool:
        logger.bind(update_id=getattr(event.update, "update_id", None)).error(
            "unhandled handler error: {}", event.exception
        )
        message = getattr(event.update, "message", None)
        if message is not None:
            await message.answer(APOLOGY_AR)
        return True

    return dp


async def _download_voice(bot: Bot, message: Message) -> bytes:
    buffer = io.BytesIO()
    await bot.download(message.voice, destination=buffer)
    return buffer.getvalue()


async def _voice_fail_reply(message: Message, bot: Bot, voice) -> None:
    """Silent/failed transcription: ONE honest surface (remediation 1.4) — a voice
    note begets a voice note; only when synthesis itself dies does the text line
    land. The owner is never left hanging (live 2026-09-01: a 6s silent note got
    two static acks)."""
    if voice is None:
        await message.answer(EMPTY_VOICE_AR)
        return
    try:
        ogg = await voice.synthesize(EMPTY_VOICE_AR)
        await bot.send_voice(message.chat.id, BufferedInputFile(ogg, filename="sara.ogg"))
    except Exception:  # noqa: BLE001 — synthesis dead: the honest text line is the fallback
        logger.warning("voice fail-note synthesis failed; honest text fallback lands")
        await message.answer(EMPTY_VOICE_AR)


async def _stream_answer(
    bot: Bot,
    front: FrontDoorDispatcher,
    message: Message,
    settings: Settings,
    cancel: asyncio.Event,
    text: str,
    decide,
    *,
    voice=None,
    vault=None,
    memory=None,
    writer=None,
    tools=None,
    voice_origin: bool = False,
    media: list[dict] | None = None,
    transcriber=None,
    affect=None,
    acoustic: str = "",
    situational=None,  # Phase-6 (Leap 3): posture ring; None = skip (tests)
    assoc_index=None,  # Phase-6 (Leap 2): RAG index; None = skip (tests)
) -> None:
    chat_id = message.chat.id
    streamer = ChatStreamer(bot, chat_id, edit_interval_ms=settings.stream_edit_interval_ms)
    if vault is not None:
        # 2.5 (dead-loop fix): «تعلمي:» — background, never blocks the reply
        task = asyncio.create_task(
            _learn_dialect(vault, text, voice, ZoneInfo(settings.tz), transcriber)
        )
        _PERSIST_TASKS.add(task)
        task.add_done_callback(_PERSIST_TASKS.discard)
    try:
        await bot.send_chat_action(chat_id, "record_voice" if voice_origin else "typing")
        # F-6 (owner decision 2026-10-01): Telegram and Terminal 1 run
        # the SAME builder. They diverged accidentally — this
        # line said `build_persona([])` (identity core only, no ar-JO
        # exemplars) while `src/bot_shell.py` said
        # `build_persona_joda()`. ar-JO IS Sara's voice, so the split
        # prompt was a split personality: the owner got MSA-with-a-
        # colloquial-preamble from Telegram and real general Arabic from
        # the terminal. Unified on the builder, not on a copied literal:
        # `tests/test_bot_shell_dialect.py` bans the literals in
        # bot_shell, and a literal copied into bot.py would be a second
        # source of truth — the exact drift this removes.
        # The identity core is still byte-identical: `build_persona_joda`
        # STARTS with it (guarded by test_bot_shell_dialect.py:355), so
        # every byte-locked persona law is untouched.
        system = build_persona_joda()
        # V2-COMPOSE: the spoken doctrine rides EVERY composition — any reply
        # may be voiced (modality is decided after generation), and short
        # turns skip the RAG gate, so the guide (not the gate) is the
        # guarantee. The RAG inject below still carries the full voice docs
        # when retrieved (residual tail for unmapped Knowledge/ paths).
        system = f"{system}\n\n{VOICE_STYLE_GUIDE_AR}"
        if vault is not None:
            try:
                long_term = await load_long_term(
                    vault, today=datetime.now(ZoneInfo(settings.tz)).date()
                )
            except Exception:  # noqa: BLE001 — context is best-effort, the reply is not
                logger.warning("long-term context load failed; continuing without it")
                long_term = ""
            if long_term:
                system = f"{system}\n\n{LONG_TERM_HEADER_AR}\n{long_term}"
        history = memory.history(chat_id) if memory is not None else None
        # Feature 2 (v1.1): the affect guide rides the envelope — ONE FAST
        # micro-verdict reading the recent turns + the profile baseline;
        # any failure injects nothing (the chat never blocks on empathy).
        # affect: injectable tracker (tests); run_bot builds the real one.
        if affect is not None and not media:
            try:
                guide = await affect.guide(text)
                if guide:
                    system = f"{system}\n\n{guide}"
            except Exception:  # noqa: BLE001 — empathy is best-effort
                logger.warning("affect guide failed; continuing without it")
        if acoustic:  # f3: the paralinguistic block (voice turns only)
            system = f"{system}\n\n{acoustic}"
        # Phase-6 (Leap 2): associative RAG — local-mirror lookup, "" on miss.
        # Index lives in the dispatcher closure (mtime-cached); never blocks.
        # Intent-gated (durability 2026-09-14): the router tool (or "direct")
        # rides along so routine device turns spend zero memory tokens while
        # advisory turns carry the Tier-1 digest + top-k.
        if assoc_index is not None:
            from src.associative import domains_for_intent, inject, intent_for
            from src.gateway import any_quarantined

            purpose = intent_for(text)
            assoc = inject(
                text,
                settings.vault_local_path,
                index=assoc_index,
                intent=purpose,
                domains=domains_for_intent(purpose),
                quarantined=any_quarantined(),
            )
            if assoc:
                system = f"{system}\n\n{assoc}"
        # Phase-6 (Leap 3): situational posture — NORMAL returns system untouched.
        # Live attention samples ride the future heartbeat transport; until then
        # the state holds no samples and posture() is a proven no-op.
        if situational is not None:
            from src.situational import apply_posture

            system = apply_posture(system, situational.posture())
        # Owner directives 2026-09-03 (round 2): the reply surface — his EXPLICIT
        # request («رد صوتي/نصي») always wins; otherwise the ROUTER's voice_reply
        # (the model picks the channel in the same FAST verdict — zero extra
        # calls); voice-origin defaults voice, text-origin defaults text.
        # Exactly one surface; the no-duplicates contract (1.4) is untouched.
        # Phase-1 (Leap 1): ReAct decision loop behind SARA_REACT_LOOP=off —
        # default path byte-identical to handle().
        if react_loop_enabled() and media is None:

            async def _pulse() -> None:
                await bot.send_chat_action(chat_id, "record_voice" if voice_origin else "typing")

            stream = run_decision_loop(
                gateway=front.gateway,
                tools=tools,
                user_text=text,
                system=system,
                history=history,
                front=front,
                pulse_cb=_pulse,
            )
        else:
            stream = front.handle(text, system=system, history=history, tools=tools, media=media)
        ack = ""
        async for delta in stream:  # the router verdict (voice_hint) is set by now
            ack = delta
            break
        forced = decide(text, voice_origin) if decide is not None else None
        if forced:
            reply_modality = forced
        elif front.voice_hint:
            reply_modality = "voice"
        else:
            reply_modality = "voice" if voice_origin else "text"
        # P0-A: a DEMANDED voice note is the strictest surface — it can never
        # degrade to text (the router's own drift is overruled by the gate)
        from src.skills.reply_modality import VOICE_DEMAND_RE

        demanded = bool(VOICE_DEMAND_RE.search(text or ""))
        if demanded:
            reply_modality = "voice"
        if reply_modality == "voice":
            # Speed pass (owner 2026-09-04): the voice note starts with the
            # FIRST COMPLETE SENTENCE while the brain still streams the rest —
            # no full-buffer wait before the owner hears Sara.
            reply, _spoke = await _deliver_voice_reply(
                bot,
                chat_id,
                message,
                stream,
                cancel,
                voice,
                ack=ack,
                strip=_strip_links_for_voice(),
                demanded=demanded,
            )
            # text fallback (if needed) already landed inside the delivery
        else:
            reply = await streamer.stream_reply(_prepend(ack, stream), cancel, transient_ack=True)
            # Round-3 22:56: a long streamed answer (the climate lecture) must
            # land as 2-3 SHORT chat bubbles, not one formal essay — the first
            # bubble is edited down to the first part, the rest arrive as
            # short follow-up messages the way friends text.
            await _split_streamed_bubble(bot, chat_id, streamer, reply)
    except GatewayError as error:
        logger.error("brain stream failed: {}", error)
        await message.answer(APOLOGY_AR)
        return
    except Exception:  # noqa: BLE001 — last-resort boundary: loud log + apology, owner never hangs
        logger.exception("unexpected brain stream failure")
        await message.answer(APOLOGY_AR)
        return
    if not reply.strip():
        if not voice_origin and streamer.ack_consumed is None:
            await message.answer(EMPTY_REPLY_AR)
        # voice-origin silent turns spoke their ack; text-origin silent tool lanes
        # keep the transient ack bubble — never a fake "empty reply" line after it.
        return
    if memory is not None:
        memory.remember(chat_id, "user", text)
        memory.remember(chat_id, "assistant", reply)
    if writer is not None:
        _persist_exchange(writer, text, reply)


# V2-COMPOSE (voice composition integration): spoken-doctrine guide. Doctrine
# she internalizes at composition time — NOT code bindings: no keyword→tag
# if-statements and no opener list exist anywhere on this path (by absence).
# Distills the RAG doctrine (vault/Knowledge/fish_voice_style.md +
# fish_emotion_control.md Sara addendum); the RAG inject in _stream_answer
# carries the full text when retrieved, while this block guarantees the shape
# on EVERY turn — including short ones the RAG gate (<3 tokens) skips. Any
# reply may be voiced (modality is decided after generation), so it rides all
# turns, text or voice. Placed AFTER _stream_answer (not with the other
# constants) so the `src/bot.py:654` citation pinned by
# tests/test_greeter_persona_parity.py keeps pointing at the composed builder.
VOICE_STYLE_GUIDE_AR: Final[str] = (
    "[صوتك المنطوق — طبع مش تعليمات حرفية] "
    "بتحكي أرقامك كلمات منطوقة متل ما عمر بيحكيها، والكلمات الإنجليزية بنطقها "
    "الطبيعي مش حرف حرف. "
    "بتدخلي بالموضوع نفسه — وأحياناً بدون أي افتتاحية — كل مرة شكل حسب اللحظة، "
    "مش تحية محفوظة. "
    "إيماءاتك الصوتية (مممم، تمام، أكيد، لحظة) مدموجة جوّا الجملة نفسها، نادراً "
    "وبخفّة — تنتين بالكتير على طول المحادثة، وعمرها ما بتنقال لحالها. "
    "الوقفة الطويلة إحساسك باللحظة (خبر تقيل، تصحيح، سؤال صعب) مش مؤقت — "
    "والحكي الخفيف بتمرقي فيه بدون وقفات. "
    "مشاعر كل جملة من معناها: وسم واحد بأول الجملة بأسلوب [bracket]، "
    "واحد بس بدون تكديس — والوسم توجيه لصوتك، مش كلام يُقرأ. "
    "وإذا انقصّ حكيك بنص الكلمة بتعترفي باللحظة بصدق وبكلماتك الخاصة المناسبة "
    "للسياق — نفس واحد خفيف بلهجتك الأردنية، بدون عبارة محفوظة."
)


_SENTENCE_ENDERS: Final = (".", "؟", "!", "?")
_SPEECH_SEGMENT_MIN_CHARS: Final[int] = 12  # a segment must say something real
_SPEECH_SEGMENT_MAX: Final[int] = 4  # an essay is 4 notes + the flush, never spam
_SHORT_ANSWER_CHARS: Final[int] = 120  # below this: ONE note, today's behavior


def _next_speech_segment(buffer: str, cut: int) -> tuple[str | None, int]:
    """The sentence-cutter for streaming voice: return (segment, new_cut) —
    the next SPEECH-COMPLETE slice ending on a sentence ender (skipping
    whitespace), or (None, cut) when nothing speakable has landed yet. A
    region shorter than the minimum waits for more (no word-by-word notes)."""
    search_from = cut
    while search_from < len(buffer):
        idx = min(
            (i for i in (buffer.find(e, search_from) for e in _SENTENCE_ENDERS) if i >= 0),
            default=-1,
        )
        if idx < 0:
            return None, cut
        end = idx + 1
        segment = buffer[cut:end].strip()
        if len(segment) >= _SPEECH_SEGMENT_MIN_CHARS:
            return segment, end
        search_from = end  # a too-short fragment (e.g. «تمام.») waits for more
    return None, cut


def _strip_links_for_voice():
    """The §3 media-link sanitizer, imported lazily (keeps module import light)."""
    from src.voice import strip_external_media_links

    return strip_external_media_links


async def _deliver_voice_reply(
    bot: Bot,
    chat_id: int,
    message: Message,
    stream: AsyncIterator[str],
    cancel: asyncio.Event,
    voice,
    *,
    ack: str,
    strip,
    demanded: bool = False,  # P0-A: the strict surface — never text-only
) -> tuple[str, bool]:
    """Streaming voice delivery (speed pass 2026-09-04): sentence-complete
    segments synthesize + dispatch WHILE the brain still streams. Returns
    (full_answer, spoke_any). Fish-only: any synthesis death lands honest
    text — there is no second voice engine.

    - First segment carries the STT-3 window-aware retry (voice-vs-text verdict)
    - Short answers (<120 chars) stay ONE note with today's exact retry loop
    - Voice dead from the start -> FULL text as chat bubbles
    - Voice dead mid-stream -> the UNSENT remainder as text (nothing lost)
    - P0-A (demanded): the note NEVER lands text-only — the primary lane's
      failure escalates to _speak_demanded (Fish-only retry), and only when
      Fish dies does the honest apology land (as text, with a loud log).
    """
    answer = ""
    spoke = False
    segments_sent = 0
    cut = 0  # how far the buffer has been consumed into sent notes
    voice_dead_midstream = False
    # -- consume the stream, cutting speakable sentences as they land ---------
    async for delta in stream:
        if cancel.is_set():
            break
        answer += delta
        if segments_sent >= _SPEECH_SEGMENT_MAX or voice_dead_midstream:
            continue  # cap/dead: the flush handles the tail
        while segments_sent < _SPEECH_SEGMENT_MAX:
            segment, new_cut = _next_speech_segment(answer, cut)
            if segment is None:
                break
            spoken_seg = strip(segment)
            if not spoken_seg:
                cut = new_cut
                continue
            if segments_sent == 0:
                spoke = await _speak_with_retry(bot, chat_id, voice, spoken_seg, attempts=2)
                if not spoke:
                    break  # full-text fallback happens at the flush (cut=0)
                cut = new_cut
                segments_sent += 1
            else:
                try:
                    ogg = await voice.synthesize(spoken_seg)
                    await bot.send_voice(chat_id, BufferedInputFile(ogg, filename="sara.ogg"))
                except Exception as error:  # noqa: BLE001 — mid-stream: text takes the tail
                    logger.warning("voice segment failed mid-stream: {}", error)
                    voice_dead_midstream = True
                    break  # cut stays BEFORE this segment: the flush owns it as text
                cut = new_cut
                segments_sent += 1
    # -- the flush: whatever the stream held that never became a note ----------
    full_answer = answer
    if cancel.is_set():
        return full_answer, spoke
    remainder = answer[cut:].strip() if (spoke and cut) else ""
    if not spoke:
        # voice never landed: the ACK or the full text reaches the owner
        spoken_all = strip(full_answer.strip() or ack) or "هذي رسالتي الصوتية 🌸"
        if voice is not None and spoken_all and len(spoken_all) <= _SHORT_ANSWER_CHARS:
            if demanded:
                # P0-A: a demanded note NEVER lands text-only — Fish-only retry
                spoke = await _speak_demanded(voice, spoken_all, bot=bot, chat_id=chat_id)
            else:
                spoke = await _speak_with_retry(bot, chat_id, voice, spoken_all, attempts=2)
        if not spoke and spoken_all.strip():
            if demanded:
                # Fish dead: the honest apology (text, loud, named)
                await send_split(
                    message,
                    "صوتي تعطل هالمرة — الرد الكامل بالنص وبتعويضها "
                    "بأول ملاحظة صوتية لما يرجع الصوت 🌷\n\n" + spoken_all,
                )
            else:
                await send_split(message, spoken_all)
    elif remainder and len(remainder) >= _SPEECH_SEGMENT_MIN_CHARS:
        # mid-stream death or cap overflow: the tail lands as text, never lost
        try:
            ogg = await voice.synthesize(strip(remainder))
            await bot.send_voice(chat_id, BufferedInputFile(ogg, filename="sara.ogg"))
        except Exception as error:  # noqa: BLE001 — the text is the last resort
            # Fish-only: a dead tail lands as text, never lost.
            logger.warning("voice tail flush failed: {}", error)
            await send_split(message, strip(remainder))
    return full_answer, spoke


async def _speak_with_retry(bot: Bot, chat_id: int, voice, text: str, *, attempts: int) -> bool:
    """The STT-3 window-aware retry: a 429 announcing its recovery window
    waits a bounded slice of it (never >8s); other failures wait 2s. Returns
    whether the note landed."""
    for attempt in range(1, attempts + 1):
        try:
            ogg = await voice.synthesize(text)
            await bot.send_voice(chat_id, BufferedInputFile(ogg, filename="sara.ogg"))
            return True
        except Exception as error:  # noqa: BLE001 — retry once, then text
            announced = getattr(error, "retry_in_s", None)
            wait_s = min(announced, 8.0) if announced else 2.0
            logger.warning(
                "voice synthesis attempt {} failed; {}",
                attempt,
                f"retrying in {wait_s:.0f}s" if attempt < attempts else "text fallback",
            )
            if attempt < attempts:
                await asyncio.sleep(wait_s)
    return False


async def _speak_demanded(voice, text: str, *, bot=None, chat_id: int | None = None) -> bool:
    """P0-A (master directive 2026-09-05) + owner preference 2026-09-07: a
    DEMANDED voice note lands on Fish (Sara's ONLY voice) OR the honest line —
    there is no second voice engine. A Fish failure returns False so the caller
    sends the honest text (identity purity per the owner)."""
    try:
        ogg = await voice.synthesize(text)
        if bot is not None and chat_id is not None:
            await bot.send_voice(chat_id, BufferedInputFile(ogg, filename="sara.ogg"))
        return True
    except Exception as error:  # noqa: BLE001 — Fish dead: honest text, never a foreign voice
        logger.error("demanded-note Fish lane failed — honest text, no foreign voice: {}", error)
    return False


def _bridge_handshake_probe(bridge_tunnel):
    """M3: poll the live bridge session up to the handler's timeout — the
    natural completion of the wake chain (boot -> auto-logon -> ONLOGON
    daemon -> dial-out). Probe failures keep polling, never abort early."""

    async def _wait_online(timeout_s: float) -> bool:
        import asyncio as _aio

        deadline = _aio.get_running_loop().time() + timeout_s
        while _aio.get_running_loop().time() < deadline:
            try:
                if bridge_tunnel is not None and bridge_tunnel.online():
                    return True
            except Exception:  # noqa: BLE001 — probe failures keep polling
                logger.debug("start_station handshake probe tick failed (polling on)")
            await _aio.sleep(1.5)
        return False

    return _wait_online


def _station_launcher(coordinator):
    """M3: launch scripts/start_station.ps1 through the SAME coordinator path
    as any launch (guard + audit code + ledger) — never a raw shell."""

    async def _launch_station() -> None:
        if coordinator is None:
            raise RuntimeError("coordinator unavailable")
        status = await coordinator.request_launch("Vantrilex Station", origin="owner_chat")
        if status.value not in ("executed", "confirmation_required"):
            raise RuntimeError(f"station launch refused: {status}")

    return _launch_station


def make_start_station_handler(
    *,
    bot,
    chat_id: int,
    mac: str,
    wait_online,
    launch_station,
    send_wol=None,
    wait_s: float = 0.05,
):
    """M3 (master directive 2026-09-05 §2-B): /start_station — the
    DETERMINISTIC station boot. Zero LLM: the ack fires first, the WoL magic
    packet goes to the PC's MAC, the bridge handshake waits up to 45s, and
    the whitelisted scripts/start_station.ps1 launches only on a live
    handshake. All edges are injected (tests); production binds the real
    bridge-online probe + the coordinator's launch path.

    LSA autologon architecture (documented in docs/14-RUNBOOK.md §5b): the
    magic packet wakes the hardware; Windows boots straight into the
    owner's desktop (Sysinternals Autologon, LSA-stored secret); the
    ONLOGON-scheduled VantrilexBridge task starts the daemon inside the
    interactive session — so the handshake THIS handler awaits is the
    natural completion of that chain."""

    from loguru import logger as _log

    async def _handler() -> None:
        async def _send(text: str) -> None:
            try:
                await bot.send_message(chat_id, text)
            except Exception as error:  # noqa: BLE001 — the boot report never hangs
                _log.warning("start_station reply failed: {}", error)

        await _send("🚀 جاري إيقاظ الحاسوب وتخطي القفل وتشغيل منظومة العمل فوراً...")
        try:
            if send_wol is not None:
                await send_wol(mac)
            else:  # pragma: no cover -- production default, never in tests
                from bridge.wol import send_wol as _real_wol

                await _real_wol(mac)
        except Exception as error:  # noqa: BLE001 — a dead WoL is honest, not fatal
            _log.warning("start_station WoL failed: {}", error)
        online = False
        try:
            online = bool(await wait_online(45.0))
        except Exception as error:  # noqa: BLE001
            _log.warning("start_station handshake probe failed: {}", error)
        if not online:
            await _send(
                "⚠️ بعتلك حزمة الإيقاظ بس الجهاز ما صحصح خلال 45 ثانية — "
                "تأكد إنه موصل بالكهرب والشبكة، وبجرب لما تخبرني 🌸"
            )
            return
        try:
            await launch_station()
            await _send(
                "✅ الجهاز صحصح والمنظومة اشتغلت: الأومنيروت والسارة والجسر "
                "وكمان فتحتلك VS Code والأوبسيديان 🌸"
            )
        except Exception:  # noqa: BLE001 — the station half-booted
            _log.exception("start_station script launch failed")
            await _send(
                "⚠️ الجهاز صحصح بس ما قدرت أطلق سكربت التشغيل — افتحه يدوي "
                "بـ sara.ps1 وبتعال أصلحه 🌸"
            )

    return _handler


async def send_split(message: Message, text: str, *, max_bubbles: int = 3) -> None:
    """Round-2 (owner 2026-09-03): a long answer lands as 2-3 SHORT human
    bubbles, not one formal lecture — paragraphs split on blank lines, each a
    chat message the way friends text. Short replies send exactly one bubble."""
    # Phase-6 (Leap 4): fallback bubbles never show expressive tags either.
    from src.voice import strip_tags

    text = strip_tags(text)
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if len(paragraphs) <= 1 or len(text) <= 160:
        await message.answer(text)
        return
    for paragraph in paragraphs[:max_bubbles]:
        await message.answer(paragraph)


async def _split_streamed_bubble(bot: Bot, chat_id: int, streamer, reply: str) -> None:
    """Round-3: re-shape an already-streamed long bubble into 2-3 short ones:
    the bubble is edited down to the first paragraph; the remaining short
    paragraphs arrive as separate chat messages. No-op for short replies."""
    if streamer.message_id is None or not reply.strip() or len(reply) <= 160:
        return
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", reply) if p.strip()]
    if len(paragraphs) <= 1:
        return
    # Phase-6 (Leap 4): text surface never shows expressive tags (links/refs
    # survive — strip_tags is allowlist-narrow by design).
    from src.voice import strip_tags

    head, tail = strip_tags(paragraphs[0]), [strip_tags(p) for p in paragraphs[1:3]]
    try:
        await bot.edit_message_text(head, chat_id=chat_id, message_id=streamer.message_id)
        for part in tail:
            await bot.send_message(chat_id, part)
    except Exception:  # noqa: BLE001 — the full bubble already stands; never lose it
        logger.warning("post-split of a long bubble failed; the original stands")


async def _prepend(first: str, stream) -> AsyncIterator[str]:
    """Re-yield a consumed first delta before the rest of the stream."""
    if first is not None:
        yield first
    async for delta in stream:
        yield delta


def _persist_exchange(writer, user_text: str, reply_text: str) -> None:
    async def _job() -> None:
        now = datetime.now(UTC)
        try:
            await writer.log_exchange(user_text, reply_text, now=now)
        except Exception:  # noqa: BLE001 — the ledger is best-effort
            logger.warning("daily chat log write failed")
        try:
            await writer.maybe_learn(user_text, now=now)
        except Exception:  # noqa: BLE001 — learning is best-effort
            logger.warning("fact learning failed")

    task = asyncio.create_task(_job())
    _PERSIST_TASKS.add(task)
    task.add_done_callback(_PERSIST_TASKS.discard)
    # Step-11 (durability): self-expanding memory — trigger-checked FIRST
    # (routine turns schedule nothing), background-only so TTFT is untouched.
    try:
        from src.memory_ledger import schedule_write_back

        wb_task = schedule_write_back(
            getattr(writer, "_vault", None),
            user_text,
            tz=getattr(writer, "_tz", None),
        )
    except Exception as error:  # noqa: BLE001 — write-back must never break persist
        logger.warning("write-back schedule failed: {}", error)
        wb_task = None
    if wb_task is not None:
        _PERSIST_TASKS.add(wb_task)
        wb_task.add_done_callback(_PERSIST_TASKS.discard)


DIALECT_NOTES_PATH: Final[str] = "02_Areas/Profile/Dialect_Notes.md"


async def _learn_dialect(vault, text: str, voice, tz: ZoneInfo, transcriber=None) -> None:
    """Remediation 2.5 (dead learning loop): «تعلمي: term -> phonetic» —
    read Dialect_Notes → dialect.learn merge → vault upsert → refresh the LIVE
    voice lexicon AND the transcription bias. Best-effort: any failure logs and
    skips, the reply is never blocked (M1 contract)."""
    try:
        from src.dialect import learn, parse_notes

        try:
            notes_md = await vault.read(DIALECT_NOTES_PATH)
        except FileNotFoundError:
            notes_md = "---\nnotes:\n---\n"
        updated = learn(text, notes_md=notes_md, today=datetime.now(tz).date().isoformat())
        if updated is None:
            return
        await vault.upsert(DIALECT_NOTES_PATH, updated, message="sara: dialect learning")
        parsed = parse_notes(updated)
        update = getattr(voice, "update_notes", None)
        if callable(update):
            update(parsed)  # the live Fish lexicon, no reboot
        refresh_prompt = getattr(transcriber, "update_prompt_terms", None)
        if callable(refresh_prompt):  # 2.6: the learned pairs bias transcription too
            refresh_prompt(
                (f"{n.term} -> {n.phonetic}" for n in parsed)
                if parsed
                else tuple(_DEFAULT_PROMPT_TERMS)
            )
        logger.info("dialect learning: vault updated + live lexicon refreshed")
    except Exception:  # noqa: BLE001 — teaching is best-effort, never blocks the reply
        logger.warning("dialect learning failed (non-blocking)")


class _BotNotifier:
    """Delivers PCActionCoordinator outcomes/prompts to the owner's chat."""

    def __init__(self, bot: Bot, chat_id: int) -> None:
        self._bot = bot
        self._chat_id = chat_id

    async def notify(self, text: str) -> None:
        await self._bot.send_message(self._chat_id, text)


def build_voice(settings: Settings, notes: list | None = None):
    """Voice lane factory (Fish-only, 2026-09-12 Edge purge): Fish Audio is
    Sara's ONLY voice — no fallback engine exists. Unconfigured deployments
    get a Fish lane without credentials, whose synthesis raises honestly so
    the caller lands TEXT. Fish failure always lands the caller's honest TEXT
    fallback. 2.5: notes refresh the live dialect lexicon from boot."""
    fish = FishVoice.from_settings(settings) if settings.fish_audio_ready else None
    lane = FishFirstVoice(fish=fish)
    if notes:
        lane.update_notes(notes)
    return lane


def start_background_loops(
    *,
    brief,
    journaler,
    summarizer,
    gmail_poll,
    inbox,
    dispatcher,
    classifier,
    settings: Settings,
    outreach=None,
    evolution=None,
    task_engine=None,
    orchestrator=None,
) -> list[asyncio.Task]:
    """Remediation 3.1: the owner-promised background loops, ONE stitch point
    (testable without polling). Brief suppressed by BRIEF_ENABLED=false; gmail
    poll suppressed by a degraded Google boot (inbox None); outreach (3.2, the
    proactive engine) suppressed by PROACTIVE_ENABLED=false inside its own
    loop; every task is the caller's to cancel (run_bot's finally reaps them).
    pass-2: the scheduled-tasks mirror catch-up rides a ~10-min tick."""
    tasks: list[asyncio.Task] = [asyncio.create_task(summarizer.run_forever())]
    if settings.brief_enabled and brief is not None:
        tasks.append(asyncio.create_task(brief.run_forever()))
    if settings.journaler_enabled and journaler is not None:
        tasks.append(asyncio.create_task(journaler.run_forever()))
    if outreach is not None:
        tasks.append(asyncio.create_task(outreach.run_forever()))
    if evolution is not None:
        # f4 (v1.1): the nightly self-improvement reflection (~23:40 local,
        # after the daily summarizer's window — proposals only, never silent)
        tasks.append(asyncio.create_task(evolution.run_forever()))
    if inbox is not None:
        tasks.append(asyncio.create_task(gmail_poll(inbox, dispatcher, classifier, settings)))
    if task_engine is not None:
        tasks.append(asyncio.create_task(_run_task_sync(task_engine)))
    if orchestrator is not None:
        # §5: the reminder timers — proactive dispatch when a timer fires
        tasks.append(asyncio.create_task(orchestrator.run_forever()))
    return tasks


async def _run_task_sync(engine, *, tick_s: float = 600.0) -> None:
    """pass-2: catch up Scheduled_Tasks notes whose Google mirror failed —
    exception-proof tick loop (journaler pattern)."""
    while True:
        try:
            await engine.sync_pending()
        except Exception:  # noqa: BLE001 — the loop outlives any single failure
            logger.warning("scheduled-tasks sync tick failed (skipped)")
        await asyncio.sleep(tick_s)


@dataclasses.dataclass(frozen=True)
class GoogleStack:
    """What boot decided about Google (F-4 / C-6).

    `healthy` is the flag the tool surface reads. When it is False the
    OAuth-backed surfaces (calendar, tasks, gmail, the daily brief) stay None,
    so `ToolRegistry` answers the honest ar-JO offline line instead of raising
    a Google error in the middle of the owner's turn.

    `cloud` is deliberately NOT gated on `healthy`: Places and Custom Search
    authenticate with API KEYS, so nulling them on an OAuth failure would break
    a feature that was working on a box holding a Places key and never having
    run the OAuth bootstrap.
    """

    healthy: bool
    reason: str
    session: Any = None
    suite: Any = None
    inbox: Any = None
    cloud: Any = None
    composer: Any = None


async def build_google_stack(
    settings: Settings,
    *,
    bot: Bot | None = None,
    gateway: Any = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> GoogleStack:
    """Bind the Google surfaces from ONE probe verdict (F-4 / C-6).

    Replaces the pre-F-4 block that called `GoogleSession(settings)` inside a
    blanket `except`: it constructed a session, proved nothing about whether
    Google actually works, and then swallowed every fault it could have named.

    A BROKEN client secret raises `GoogleAuthError` out of here and stops the
    boot — a misconfigured deployment must fail loudly. An ABSENT one, or a
    probe that cannot reach Google, returns `healthy=False` and every OAuth
    tool degrades to the honest offline line while the rest of Sara boots.

    `transport` is the injection seam production never uses: with no transport
    the probe makes exactly one real authenticated call to Google at boot.
    """
    from src.daily_brief import BriefComposer
    from src.email_triage import TriageClassifier
    from src.gmail import GmailInbox
    from src.google_auth import probe_google
    from src.google_cloud_client import GoogleCloudClient
    from src.google_suite import GoogleSuite

    health = await probe_google(settings, transport=transport)
    cloud = GoogleCloudClient(
        session=health.session,
        custom_search_key=settings.custom_search_key or "",
        custom_search_cx=settings.custom_search_cx or "",
        places_key=settings.google_places_key or "",
    )
    if not health.healthy:
        logger.warning("google boot degraded ({}); google tools answer offline", health.reason)
        return GoogleStack(
            healthy=False,
            reason=health.reason,
            session=health.session,
            cloud=cloud,
        )
    suite = GoogleSuite(health.session, settings.google_calendar_id)
    inbox = GmailInbox(health.session, settings)
    composer = BriefComposer(
        suite,
        inbox,
        TriageClassifier(settings, gateway),
        bot,
        settings.authorized_user_id,
        settings,
    )
    return GoogleStack(
        healthy=True,
        reason=health.reason,
        session=health.session,
        suite=suite,
        inbox=inbox,
        cloud=cloud,
        composer=composer,
    )


async def run_bot(settings: Settings, bridge=None) -> None:
    gateway = OmniRouteClient(
        settings.omniroute_base_url,
        settings.omniroute_api_key,
        chains={
            Tier.FAST: settings.fast_chain,
            Tier.MEDIUM: settings.medium_chain,
            Tier.HEAVY: settings.heavy_chain,
        },
        escalated_heavy_chain=settings.heavy_escalated_chain,
        concurrency_threshold=settings.heavy_concurrency_threshold,
    )
    voice = build_voice(settings)  # 2.5: boot notes load below, once the vault exists
    # Drill fix 2026-09-12: a fresh/disposable local root misses Contacts/,
    # Call_Transcripts/, Studies/ (remote bootstrap never touches disk) —
    # scaffold first so no writer ever meets FileNotFoundError. Never raises.
    ensure_vault_scaffolding(settings.vault_local_path)
    # RAG mirror (audit 2026-09-14): VaultIndex reads the vault, not the
    # repo — 04_Resources/*.md must exist under the vault root to be indexed
    # live. Idempotent one-way copy; never raises.
    ensure_resources_scaffolding(settings.vault_local_path)
    # Tier-1 plant (durability Solution A): seed digest → runtime master
    # copy, copy-if-missing only — Sara's live refreshes are never clobbered.
    ensure_master_digest(settings.vault_local_path)
    vault = VaultClient(
        settings.vault_github_repo,
        settings.vault_github_token.get_secret_value(),
        branch=settings.vault_branch,
    )
    try:  # 2.5: seed the live voice lexicon from the vault at boot (best-effort)
        from src.dialect import parse_notes

        boot_notes = parse_notes(await vault.read(DIALECT_NOTES_PATH))
        voice.update_notes(boot_notes)
    except Exception as error:  # noqa: BLE001 — no notes = no lexicon, the bot still boots
        logger.warning("boot dialect notes load skipped: {}", error)
        boot_notes = []
    # 2.6: the same pairs bias Whisper's Arabic transcription from boot
    boot_terms = tuple(f"{n.term} -> {n.phonetic}" for n in boot_notes) or None
    # M5 (§6): Sara's capabilities manifest — synced into the live vault at
    # boot (one write; the envelope loads it from there on every turn)
    from src.memory import sync_capabilities_manifest

    if not await sync_capabilities_manifest(vault):
        logger.warning("capabilities manifest sync skipped — the envelope degrades honestly")
    # M6 (owner's mediating-layer design): the per-tool skill guides — synced
    # at boot so every tool's narration reads the CURRENT usage guide.
    from src.skills.sara_tool_skills import sync_skill_guides

    synced_guides = await sync_skill_guides(vault)
    logger.info("tool skill guides synced: {}", synced_guides)
    memory = ConversationMemory()
    writer = VaultMemoryWriter(vault, gateway, tz=ZoneInfo(settings.tz))
    bot = Bot(token=settings.telegram_bot_token)
    # F-4 / C-6: one probe verdict decides every Google surface. A broken
    # credential file raises out of here and stops the boot; an absent one, or a
    # probe that cannot reach Google, leaves the OAuth tools unbound so they
    # answer the honest ar-JO offline line instead of raising mid-turn.
    google = await build_google_stack(settings, bot=bot, gateway=gateway)
    suite = google.suite
    inbox = google.inbox
    composer = google.composer
    cloud = google.cloud
    telemetry = TelemetryClient(bridge, gateway) if bridge is not None else None
    # pass-4 (v2.0 §3-هـ): keyless web intelligence — DDG search + page reads.
    # One shared httpx client, bounded lifetime, injected into WebIntel.
    web = None
    try:
        import httpx as _httpx

        from src.skills.web_intel import WebIntel

        web = WebIntel(http=_httpx.AsyncClient(timeout=15.0, follow_redirects=True))
    except Exception as error:  # noqa: BLE001 — web tools degrade honestly without it
        logger.warning("web intel unavailable; web_search degrades: {}", error)
    # pass-4 (v2.0 §3-ب/1): YouTube search — env-gated staging; the tool stays
    # honestly offline until the owner drops YOUTUBE_API_KEY in .env (§7).
    youtube_client = None
    if (settings.youtube_api_key or "").strip():
        try:
            from src.skills.google_extras import YouTubeClient

            youtube_client = YouTubeClient(
                None, api_key=settings.youtube_api_key
            )  # session=None: the real GoogleSession binds at first call in prod
        except Exception as error:  # noqa: BLE001
            logger.warning("youtube client unavailable: {}", error)
    weather_client = None
    if web is not None:
        try:
            from src.skills.weather import WeatherClient

            weather_client = WeatherClient(http=web._http)
        except Exception as error:  # noqa: BLE001
            logger.warning("weather client unavailable; weather degrades: {}", error)
    # pass-2 (v2.0 §3-ج/2): the scheduled-tasks engine — Google suite may be
    # absent (no OAuth yet); the note lane degrades honestly in that case.
    task_engine = None
    if suite is not None and vault is not None:
        from src.skills.scheduled_tasks import ScheduledTasksEngine

        task_engine = ScheduledTasksEngine(vault, suite, tz=ZoneInfo(settings.tz))
    coordinator = (
        PCActionCoordinator(
            bridge,
            vault,
            _BotNotifier(bot, settings.authorized_user_id),
            guard=Guard("config/whitelist.json"),  # 2.2: alias no-hit honesty
            memory=memory,  # 2.4: confirmation exchanges enter the rolling buffer
        )
        if bridge is not None
        else None
    )
    # §5 (2026-09-04): the dual task engine — timed reminders fire PROACTIVELY
    # (the live 3:46pm never-fired lessons); state persists next to the vault.
    from src.task_orchestrator import Orchestrator

    orchestrator = Orchestrator(
        bot=bot,  # send_message(chat_id, text) — proactive dispatch surface
        chat_id=settings.authorized_user_id,
        tz=ZoneInfo(settings.tz),
    )
    orchestrator.bind_state_path(Path(settings.vault_local_path) / "State")
    orchestrator.load_pending()
    tools = ToolRegistry(
        inbox=inbox,
        suite=suite,
        telemetry=telemetry,
        coordinator=coordinator,
        composer=composer,
        tz=ZoneInfo(settings.tz),
        bridge=bridge,  # pass-1: exec.screenshot + telemetry.app_sessions tunnel
        vision=gateway,  # the conversation-lane brain sees the capture natively
        vault=vault,  # pass-2: knowledge-graph snapshots over the vault
        task_engine=task_engine,  # pass-2: schedule tool -> Scheduled_Tasks notes
        web=web,  # pass-4: web_search -> keyless DDG search
        weather=weather_client,  # pass-4: weather -> Open-Meteo current conditions
        youtube=youtube_client,  # pass-4: youtube -> Data API v3 (env-gated)
        cloud=cloud,  # B1-B8 (Phase B): GoogleCloudClient (places/deep/fitness/...)
        externals=ExternalAPIs(
            # B (live 2026-09-05): Aladhan answers /v1/timingsByCity with a 302
            # and _get_json treats non-200 as a miss — without follow_redirects
            # prayer times silently returned None. Every one of the five APIs
            # may redirect; the shared client follows them now.
            http=httpx.AsyncClient(timeout=30.0, follow_redirects=True),
            fx_key=settings.exchangerate_api_key or "",
        ),  # M4 (§4): the five free external APIs, one shared client
        photo_sender=(
            _make_photo_sender(bot, settings.authorized_user_id) if bot is not None else None
        ),  # §4: the screenshot tool dispatches the REAL JPEG as a Telegram photo
        orchestrator=orchestrator,  # §5: timed reminders fire proactively
    )
    # STT-4 (owner 2026-09-04 evening): the agent manager — HEAVY plans
    # multi-task lines, MEDIUM sub-agents map them, the REAL registry executes.
    from src.agent_manager import AgentManager

    tools.bind_agent_manager(AgentManager(gateway=gateway, tools=tools))
    # Live-6 (owner 2026-09-05 7:25am): «شو في تطبيقات عندك في القائمة» —
    # the whitelist_apps tool reads the REAL config/whitelist.json.
    tools.bind_whitelist_path("config/whitelist.json")
    dp = build_dispatcher(
        gateway,
        voice,
        settings,
        vault=vault,
        memory=memory,
        writer=writer,
        tools=tools,
        coordinator=coordinator,
        situational=SituationalState(),  # Phase-6 (Leap 3): owned posture ring
        initial_prompt_terms=boot_terms,  # 2.6: Whisper bias seeded from boot
        affect=AffectiveStateTracker(
            brain=gateway, history=[], baseline=""
        ),  # f2: per-turn tracker reads live history
        bridge_tunnel=bridge,  # Step 9: on_start WoL/offline routing + start_station probe
    )
    summarizer = DailySummarizer(vault, gateway, tz=ZoneInfo(settings.tz))
    # 3.1: the owner-promised loops, all through one testable stitch point —
    # 07:30 brief, evening check-in, real gmail watch, daily summary.
    from src.email_triage import Dispatcher, TriageClassifier
    from src.gmail import run_gmail_poll
    from src.skills.evening_journaler import EveningJournaler
    from src.skills.proactive_outreach import ProactiveOutreach
    from src.skills.self_evolution import SelfEvolutionWorker

    journaler = (
        EveningJournaler(
            suite,
            bot,
            settings.authorized_user_id,
            settings,
            Path(settings.vault_local_path),
            inbox=inbox,
            classifier=TriageClassifier(settings, gateway),
        )
        if suite is not None
        else None
    )
    triage_dispatcher = (
        Dispatcher(bot, settings.authorized_user_id, voice, settings) if inbox is not None else None
    )
    # 3.2: Sara INITIATES — the proactive engine (HEAVY-judged check-ins
    # within the safety window; every gate lives inside its own loop).
    outreach = ProactiveOutreach(
        brain=gateway,
        bot=bot,
        chat_id=settings.authorized_user_id,
        vault=vault,
        suite=suite,
        settings=settings,
        state_path=Path(settings.vault_local_path) / "State" / "proactive.json",
        voice=voice,  # round-2: outreach checks in with her OWN voice
    )
    loop_tasks = start_background_loops(
        brief=composer,
        journaler=journaler,
        summarizer=summarizer,
        gmail_poll=run_gmail_poll,
        inbox=inbox,
        dispatcher=triage_dispatcher,
        classifier=TriageClassifier(settings, gateway),
        settings=settings,
        outreach=outreach,
        evolution=SelfEvolutionWorker(brain=gateway, vault=vault, tz=ZoneInfo(settings.tz)),
        task_engine=task_engine,  # pass-2: mirror catch-up rides the loop set
        orchestrator=orchestrator,  # §5: the reminder timers ride the loop set
    )
    # Step 9 (2026-09-14): bridge-reconnect greeter — same cancel/reap
    # contract as every loop above. Dynamic greeting only (spontaneity
    # doctrine); quiet hours + debounce enforced inside the watcher.
    if bot is not None and bridge is not None:
        from src.middleware import last_owner_event_ts

        loop_tasks.append(
            asyncio.create_task(
                run_bridge_watcher(
                    bridge_tunnel=bridge,
                    greet=make_bridge_greeter(
                        bot=bot,
                        chat_id=settings.authorized_user_id,
                        gateway=gateway,
                        vault=vault,
                        tzname=settings.tz,
                    ),
                    tzname=settings.tz,
                    last_turn_fn=last_owner_event_ts,
                )
            )
        )
    try:
        await dp.start_polling(bot, skip_updates=True)
    finally:
        for task in loop_tasks:
            task.cancel()
        await asyncio.gather(*loop_tasks, return_exceptions=True)
        # pass-1 (V-4): in-flight ledger writes are reaped BEFORE the vault
        # session closes — the last exchanges never die at shutdown.
        if _PERSIST_TASKS:
            await asyncio.gather(*list(_PERSIST_TASKS), return_exceptions=True)
        if web is not None:  # pass-4: the web-intel client dies with the bot
            try:
                await web._http.aclose()
            except Exception as error:  # noqa: BLE001
                logger.warning("web client close failed: {}", error)
        await gateway.aclose()
        await vault.aclose()
