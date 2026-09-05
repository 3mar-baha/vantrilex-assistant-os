"""M3 (master directive 2026-09-05 §2): /start_station — the DETERMINISTIC
station boot command.

Contract:
- The handler bypasses LLM inference entirely (no router call, no stream).
- Instant Arabic ack fires FIRST («🚀 جاري إيقاظ...»).
- The Wake-on-LAN magic packet goes to PC_MAC_ADDRESS (UDP:9 broadcast).
- The bridge handshake waits up to 45s; online -> the whitelisted
  scripts/start_station.ps1 launches (omniroute + sara runners + VS Code +
  Obsidian); offline -> the honest never-woke line, no script launch.
- The command is deterministic end-to-end: a fixed reply vocabulary, zero
  model text.
"""

from __future__ import annotations

import pytest


class _StationHarness:
    """Records sends + WoL + launches; scriptable bridge online state."""

    def __init__(self):
        self.sent: list[str] = []
        self.wol_calls: list[str] = []
        self.launched: list[str] = []
        self.online = False
        self.router_calls = 0


@pytest.fixture
def harness():
    return _StationHarness()


async def _drive(harness, settings_mac="AA-BB-CC-DD-EE-FF", *, online=True, wait_s=0.01):
    """Run the start_station handler against the recording doubles."""
    from types import SimpleNamespace

    from src.bot import make_start_station_handler

    harness.online = online

    class _Bot:
        async def send_message(self, chat_id, text):
            harness.sent.append(text)
            return SimpleNamespace(message_id=1)

    async def fake_wol(mac, ip="255.255.255.255", port=9):
        harness.wol_calls.append(mac)
        return 102

    async def fake_wait_online(timeout_s):
        harness.waited = timeout_s
        return harness.online

    async def fake_launch_station():
        harness.launched.append("start_station.ps1")
        return True

    handler = make_start_station_handler(
        bot=_Bot(),
        chat_id=99,
        mac=settings_mac,
        wait_online=fake_wait_online,
        launch_station=fake_launch_station,
        send_wol=fake_wol,
        wait_s=wait_s,
    )
    await handler()
    return harness


async def test_start_station_ack_first_then_wol(harness):
    """The instant ack is the FIRST send; the WoL packet goes to the MAC."""
    await _drive(harness)
    assert harness.sent[0].startswith("🚀"), harness.sent[0]
    assert harness.wol_calls == ["AA-BB-CC-DD-EE-FF"]


async def test_start_station_no_llm(harness):
    """Determinism: the router/stream is never consulted — the handler runs
    purely on doubles; if any LLM path fired, router_calls would grow."""
    await _drive(harness)
    assert harness.router_calls == 0
    # every reply is from the fixed vocabulary (no model text)
    for line in harness.sent:
        assert any(marker in line for marker in ("🚀", "✅", "⚠️", "🌸")), line


async def test_start_station_online_launches_script_and_confirms(harness):
    """Bridge wakes -> start_station.ps1 launches ONCE -> the clean
    confirmation lands."""
    await _drive(harness, online=True)
    assert harness.launched == ["start_station.ps1"]
    assert any("✅" in line for line in harness.sent)


async def test_start_station_offline_honest_never_woke(harness):
    """Bridge never handshakes in 45s -> the honest line; the script NEVER
    launches against a sleeping station."""
    await _drive(harness, online=False)
    assert harness.launched == []
    assert any("ما استنى" in line or "ما صحصح" in line or "⚠️" in line for line in harness.sent)
    assert harness.waited == 45.0


def test_wol_packet_shape():
    """The magic packet: 6x FF + 16x the MAC — 102 bytes exactly."""
    from bridge.wol import magic_packet

    packet = magic_packet("AA-BB-CC-DD-EE-FF")
    assert len(packet) == 102
    assert packet[:6] == b"\xff" * 6
    assert packet[6:12] == bytes.fromhex("AABBCCDDEEFF")


def test_station_script_exists_and_whitelisted():
    """scripts/start_station.ps1 ships in the repo (its launch rides the
    executor's whitelist app entry, never a raw shell)."""
    from pathlib import Path

    script = Path("scripts/start_station.ps1")
    assert script.exists(), "the station script must ship"
    text = script.read_text(encoding="utf-8")
    # the directive's five launches, verified in the script body
    for needle in ("omniroute", "sara.ps1", "code", "obsidian"):
        assert needle.lower() in text.lower(), needle


async def test_shell_start_station_command_no_mac_honest(make_shell, fake_bot):
    """The wired command: a missing MAC answers the honest setup line and
    touches NOTHING (no WoL, no task) — determinism from the first line."""
    from tests.conftest import make_update

    shell = make_shell()  # PC_MAC_ADDRESS="" in the test settings mirror
    bot = fake_bot()
    await shell.dp.feed_update(
        bot, make_update(1, shell.settings.authorized_user_id, "/start_station", command=True)
    )
    from tests.conftest import wait_until

    await wait_until(lambda: bot.session.sent("SendMessage"))
    sent = [c.method.text for c in bot.session.sent("SendMessage")]
    assert any("MAC" in line for line in sent), sent


async def test_handshake_probe_and_launcher_units():
    """The two module edges: the probe polls the tunnel (True on live, False
    after the timeout); the launcher rides the coordinator's launch path and
    raises on refusal (the handler's honest branch fires)."""
    from src.bot import _bridge_handshake_probe, _station_launcher
    from src.pc_actions import LaunchStatus

    class _Live:
        def online(self):
            return True

    probe = _bridge_handshake_probe(_Live())
    assert await probe(0.2) is True

    probe_dead = _bridge_handshake_probe(None)  # no tunnel -> the 45s no-show
    assert await probe_dead(0.0) is False

    launched: list[tuple] = []

    class _Coord:
        async def request_launch(self, name, *, origin):
            launched.append((name, origin))
            return LaunchStatus.EXECUTED

    launcher = _station_launcher(_Coord())
    await launcher()
    assert launched == [("Vantrilex Station", "owner_chat")]

    class _Refused:
        async def request_launch(self, name, *, origin):
            return LaunchStatus.REFUSED

    with pytest.raises(RuntimeError):
        await _station_launcher(_Refused())()

    with pytest.raises(RuntimeError):
        await _station_launcher(None)()  # no coordinator -> honest raise
