"""Sprint-3 §3.4 AC11-AC12: WoL magic packet + idle monitor latch/choice roundtrip.

Contract: docs/specs/sprint-3.md §3.4 — the UDP socket edge is spied; the idle monitor
runs against a scripted idle source; the choice roundtrip reuses the §3.4 in-proc rig.
"""

from __future__ import annotations

import asyncio
import socket as socket_mod
from pathlib import Path

import httpx
import pytest
from helpers_vault import FakeGitHub

from bridge.executor import Executor
from bridge.guard import Guard
from bridge.idle import IDLE_OFFER_TEXT_AR, IdleMonitor
from bridge.wol import magic_packet, send_wol
from src.pc_actions import PCActionCoordinator
from src.vault import CONFIRMATIONS_DIR, VaultClient, split_frontmatter

TOKEN = "your-github-test-pat-abcdef0123456789"
WHITELIST = {
    "allowed_apps": [],
    "restricted_actions": [
        {"action": "shutdown", "requires_confirmation": True},
        {"action": "sleep", "requires_confirmation": True},
    ],
}


def test_magic_packet_bytes_and_udp9_send(monkeypatch):
    """AC11 — exact 102-byte frame; malformed MACs raise; single UDP sendto on port 9."""
    packet = magic_packet("AA-BB-CC-DD-EE-FF")
    assert len(packet) == 102
    assert packet[:6] == b"\xff" * 6
    assert packet[6:] == bytes.fromhex("aabbccddeeff") * 16
    for bad in ("ZZ-BB-CC-DD-EE-FF", "AABB", "", "AA:BB:CC:DD:EE:FF:00"):
        with pytest.raises(ValueError):
            magic_packet(bad)

    class FakeSock:
        def __init__(self, recorded):
            self.recorded = recorded

        def setsockopt(self, *a):
            pass

        def sendto(self, data, addr):
            self.recorded.append((data, addr))
            return len(data)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    recorded: list = []

    # patch INSIDE the running loop: loop construction itself dials socket.socket
    # (Windows self-pipe), so the fake must only cover the send path
    async def _patched_send() -> int:
        monkeypatch.setattr(socket_mod, "socket", lambda *args, **kwargs: FakeSock(recorded))
        try:
            return await send_wol("AA-BB-CC-DD-EE-FF", "192.168.1.50", 9)
        finally:
            monkeypatch.undo()

    sent = asyncio.run(_patched_send())
    assert sent == 102
    assert len(recorded) == 1  # exactly ONE sendto
    data, addr = recorded[0]
    assert addr == ("192.168.1.50", 9) and len(data) == 102
    monkeypatch.undo()


class _ScriptedIdle:
    def __init__(self, *values: float):
        self.values = list(values)
        self.calls = 0

    async def __call__(self) -> float:
        self.calls += 1
        if len(self.values) > 1:
            return self.values.pop(0)
        return self.values[0]


async def test_idle_offer_once_rearm_and_choice_roundtrip(tmp_path: Path):
    """AC12 — offer exactly once per window; sub-half activity re-arms; choice -> one
    confirmation + one power command with the same ID."""
    # — latch: one offer despite continued above-threshold polling, re-arm below half —
    offers: list[str] = []

    async def on_idle() -> None:
        offers.append(IDLE_OFFER_TEXT_AR)

    source = _ScriptedIdle(1300.0)  # stays above the 20-min threshold
    monitor = IdleMonitor(20.0, on_idle, source=source, poll_seconds=0.01)
    stop = asyncio.Event()
    runner = asyncio.create_task(monitor.run(stop))
    await asyncio.sleep(0.08)
    stop.set()
    await asyncio.wait_for(runner, timeout=5)
    assert len(offers) == 1  # latched: exactly one offer despite many polls

    async def on_idle2() -> None:
        offers.append("second")

    source2 = _ScriptedIdle(1300.0, 300.0, 1300.0)  # activity below half-threshold re-arms
    monitor2 = IdleMonitor(20.0, on_idle2, source=source2, poll_seconds=0.01)
    stop2 = asyncio.Event()
    runner2 = asyncio.create_task(monitor2.run(stop2))
    await asyncio.sleep(0.08)
    stop2.set()
    await asyncio.wait_for(runner2, timeout=5)
    assert len(offers) == 2  # re-armed and offered again after real activity

    # — choice roundtrip: «نوم» -> one confirmation + one power command, same ID —
    import json as _json

    wl = tmp_path / "whitelist.json"
    wl.write_text(_json.dumps(WHITELIST), encoding="utf-8")
    executor = Executor(Guard(str(wl)))

    class PowerSpy:
        def __init__(self):
            self.calls: list[list[str]] = []

        async def __call__(self, argv: list[str]) -> None:
            self.calls.append(argv)

    power_spy = PowerSpy()
    executor._spawn = power_spy

    class FakeBridge:
        def __init__(self, exec_):
            self.commands = []

        async def send_cmd(self, cmd, args, *, timeout_s=20.0):
            self.commands.append((cmd, dict(args)))
            result = await executor.power(
                args["action"],
                confirmation_id=args["confirmation_id"],
                audit_code=args.get("audit_code"),
            )
            return result.model_dump()

    gh = FakeGitHub()
    session = httpx.AsyncClient(transport=gh.transport, base_url="https://api.github.com")
    vault = VaultClient("owner/vault-repo", TOKEN, session=session)

    sent_notes: list[str] = []

    class Notifier:
        async def notify(self, text: str) -> None:
            sent_notes.append(text)

    bridge = FakeBridge(executor)
    coordinator = PCActionCoordinator(bridge, vault, Notifier())
    action = await coordinator.handle_idle_choice("نوم")
    assert action == "sleep"
    assert len(bridge.commands) == 1 and bridge.commands[0][0] == "power"
    args = bridge.commands[0][1]
    notes = [p for p in gh.objects if p.startswith(CONFIRMATIONS_DIR)]
    assert len(notes) == 1
    meta, _body = split_frontmatter(gh.objects[notes[0]][1])
    assert args["confirmation_id"] == meta["confirmation_id"]
    assert args["audit_code"] == meta["audit_code"]
    assert len(power_spy.calls) == 1  # exactly one power command executed
    # anything else = decline (no writes, no commands)
    action2 = await coordinator.handle_idle_choice("خليها زي ما هي")
    assert action2 is None and len(bridge.commands) == 1
