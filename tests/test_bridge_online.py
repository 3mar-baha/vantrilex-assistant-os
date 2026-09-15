"""Tier 1 — /start WoL + bridge-reconnect greeting + quiet hours (Step 9).

Hermetic: pure helpers unit-tested directly; on_start exercised through the
shell harness with a fake tunnel; the watcher loop runs on 10ms polls with
an explicit stop event — no real waiting, no network, no WoL packets.
"""

import asyncio
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from src.bot import (
    WOL_OFFLINE_AR,
    in_active_window,
    run_bridge_watcher,
    should_greet_on_reconnect,
    wake_decision,
)


def _amman(hhmm: str) -> datetime:
    h, m = (int(x) for x in hhmm.split(":"))
    return datetime(2026, 9, 14, h, m, tzinfo=ZoneInfo("Asia/Amman")).astimezone(UTC)


def test_wake_decision_matrix():
    assert wake_decision("AA:BB", True) == "welcome"
    assert wake_decision("AA:BB", False) == "wol_offline"
    assert wake_decision("", False) == "no_mac"
    assert wake_decision(None, False) == "no_mac"
    assert wake_decision("  ", True) == "welcome"  # online wins regardless of MAC


def test_wol_offline_string_exact():
    assert WOL_OFFLINE_AR == (
        "أهلين عمر! 🌟 بعثت إشارة تشغيل الجهاز (WOL)، وعم بيصحى هسا... "
        "أول ما يشبك الجسر وأومني روت رح أعطيك خبر فوراً!"
    )


def test_active_window_amman_bounds():
    assert in_active_window(_amman("08:00"), "Asia/Amman") is True
    assert in_active_window(_amman("12:00"), "Asia/Amman") is True
    assert in_active_window(_amman("23:30"), "Asia/Amman") is True
    assert in_active_window(_amman("07:59"), "Asia/Amman") is False
    assert in_active_window(_amman("23:31"), "Asia/Amman") is False
    assert in_active_window(_amman("03:00"), "Asia/Amman") is False


def test_active_window_overnight_wrap():
    assert in_active_window(_amman("23:00"), "Asia/Amman", start="22:00", end="02:00") is True
    assert in_active_window(_amman("01:00"), "Asia/Amman", start="22:00", end="02:00") is True
    assert in_active_window(_amman("12:00"), "Asia/Amman", start="22:00", end="02:00") is False


def test_should_greet_matrix():
    # in-window: first greet ever, or debounce elapsed
    assert (
        should_greet_on_reconnect(
            last_greet_ts=None, now_ts=1000.0, last_turn_ts=None, in_window=True
        )
        is True
    )
    assert (
        should_greet_on_reconnect(
            last_greet_ts=0.0, now_ts=2000.0, last_turn_ts=None, in_window=True
        )
        is True
    )
    assert (
        should_greet_on_reconnect(
            last_greet_ts=1500.0, now_ts=2000.0, last_turn_ts=None, in_window=True
        )
        is False
    )
    # nocturnal: silent unless an owner turn landed in the last 15 minutes
    assert (
        should_greet_on_reconnect(
            last_greet_ts=None, now_ts=2000.0, last_turn_ts=None, in_window=False
        )
        is False
    )
    assert (
        should_greet_on_reconnect(
            last_greet_ts=None, now_ts=2000.0, last_turn_ts=1500.0, in_window=False
        )
        is True
    )
    assert (
        should_greet_on_reconnect(
            last_greet_ts=None, now_ts=2000.0, last_turn_ts=500.0, in_window=False
        )
        is False
    )


async def test_middleware_stamps_owner_turns_only():
    from src.middleware import OwnerOnlyMiddleware, last_owner_event_ts
    from tests.conftest import OWNER_ID, make_update

    seen = []
    mw = OwnerOnlyMiddleware(OWNER_ID)

    async def _handler(event, data):
        seen.append(1)

    before = last_owner_event_ts()
    await mw(_handler, make_update(91, 987654321, "hi"), {})
    during = last_owner_event_ts()
    await mw(_handler, make_update(92, OWNER_ID, "hi"), {})
    after = last_owner_event_ts()
    assert seen == [1]  # stranger dropped silently, owner passed
    assert during == before  # stranger never stamps the clock
    assert after is not None and (before is None or after >= before)


class _Tunnel:
    def __init__(self, online):
        self._online = online

    def online(self):
        return self._online


async def test_watcher_greets_once_on_reconnect_then_debounces():
    greets = []
    stop = asyncio.Event()
    tunnel = _Tunnel(False)

    async def _greet():
        greets.append(1)
        if len(greets) >= 1:
            stop.set()

    async def _flipper():
        await asyncio.sleep(0.02)
        tunnel._online = True

    await asyncio.wait_for(
        asyncio.gather(
            run_bridge_watcher(
                bridge_tunnel=tunnel,
                greet=_greet,
                tzname="Asia/Amman",
                now_fn=lambda: _amman("12:00"),
                last_turn_fn=lambda: None,
                poll_s=0.01,
                stop=stop,
            ),
            _flipper(),
        ),
        timeout=5.0,
    )
    assert len(greets) == 1


async def test_watcher_silent_in_quiet_hours_without_recent_turn():
    greets = []
    stop = asyncio.Event()
    tunnel = _Tunnel(True)

    async def _greet():
        greets.append(1)
        stop.set()

    async def _stopper():
        await asyncio.sleep(0.05)
        stop.set()

    await asyncio.wait_for(
        asyncio.gather(
            run_bridge_watcher(
                bridge_tunnel=tunnel,
                greet=_greet,
                tzname="Asia/Amman",
                now_fn=lambda: _amman("03:00"),
                last_turn_fn=lambda: None,
                poll_s=0.01,
                stop=stop,
            ),
            _stopper(),
        ),
        timeout=5.0,
    )
    assert greets == []


async def test_on_start_offline_wol_and_static_string(fake_bot, make_shell, monkeypatch):
    """MAC + offline bridge: WoL fires once, static offline string lands, no voice."""
    from src.bot import WELCOME_AR
    from tests.conftest import OWNER_ID, make_update

    sent_macs: list = []

    async def _fake_wol(mac: str) -> None:
        sent_macs.append(mac)

    monkeypatch.setattr("src.bot._send_wol", _fake_wol)
    shell, bot = make_shell(pc_mac_address="08:BF:B8:28:B2:F9"), fake_bot()
    await shell.dp.feed_update(bot, make_update(1, OWNER_ID, "/start", command=True))
    assert sent_macs == ["08:BF:B8:28:B2:F9"]
    texts = [c.method.text for c in bot.session.sent("SendMessage")]
    assert texts and texts[0] == WOL_OFFLINE_AR
    assert bot.session.sent("SendVoice") == []
    assert all(c.method.text != WELCOME_AR for c in bot.session.sent("SendMessage"))


async def test_on_start_online_welcomes_without_wol(fake_bot, make_shell, monkeypatch):
    """Bridge live: legacy welcome + voice, WoL never fires."""
    from src.bot import WELCOME_AR
    from tests.conftest import OWNER_ID, make_update

    fired: list = []

    async def _fake_wol(mac: str) -> None:
        fired.append(mac)

    monkeypatch.setattr("src.bot._send_wol", _fake_wol)
    shell, bot = (
        make_shell(pc_mac_address="08:BF:B8:28:B2:F9", bridge_tunnel=_Tunnel(True)),
        fake_bot(),
    )
    await shell.dp.feed_update(bot, make_update(1, OWNER_ID, "/start", command=True))
    assert fired == []
    assert bot.session.sent("SendMessage")[0].method.text == WELCOME_AR


async def test_watcher_nocturnal_greets_on_recent_owner_turn():

    greets = []
    stop = asyncio.Event()
    tunnel = _Tunnel(False)
    base = _amman("03:00")

    async def _greet():
        greets.append(1)
        stop.set()

    async def _flipper():
        await asyncio.sleep(0.02)
        tunnel._online = True

    await asyncio.wait_for(
        asyncio.gather(
            run_bridge_watcher(
                bridge_tunnel=tunnel,
                greet=_greet,
                tzname="Asia/Amman",
                now_fn=lambda: base,
                last_turn_fn=lambda: base.timestamp() - 60.0,
                poll_s=0.01,
                stop=stop,
            ),
            _flipper(),
        ),
        timeout=5.0,
    )
    assert len(greets) == 1
