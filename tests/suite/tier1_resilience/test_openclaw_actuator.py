"""Tier 1 — OpenClaw Phase-3.4 desktop actuation arm. Hermetic.

Hotkey injection, UIA routing, and the shared accelerator table are all
exercised through fakes: no keybd_event fires, no pywinauto imports (wheels
absent in dev/CI), no window is ever focused. The non-Windows guard is
pinned by monkeypatching os.name — not by env luck.
"""

import os

import pytest

from bridge.openclaw.actuator import (
    ActuatorUnavailable,
    DesktopActuator,
    parse_hotkey,
    send_hotkey,
)
from bridge.openclaw.hotkeys import COMMITTING_SPECS, SAFE_HOTKEY_SPECS
from bridge.openclaw.protocol import Op, OpKind


def test_parse_hotkey_shapes():
    assert parse_hotkey("Ctrl+L") == (frozenset({"ctrl"}), "L")
    assert parse_hotkey("ctrl+shift+t") == (frozenset({"ctrl", "shift"}), "T")
    assert parse_hotkey("Win+R") == (frozenset({"win"}), "R")
    assert parse_hotkey("F6") == (frozenset(), "F6")
    assert parse_hotkey("  Alt+Tab ") == (frozenset({"alt"}), "TAB")


@pytest.mark.parametrize("spec", ["", "Ctrl+", "+L", "Foo+X", "Ctrl++"])
def test_parse_hotkey_rejects_garbage(spec):
    with pytest.raises(ValueError):
        parse_hotkey(spec)


def test_safe_table_covers_t0_doctrine():
    for spec in ("Ctrl+L", "Ctrl+T", "Ctrl+W", "Ctrl+Tab", "F6", "Win+R", "Escape"):
        assert spec.casefold() in SAFE_HOTKEY_SPECS, spec


def test_committing_specs_never_safe():
    for spec in ("Alt+F4", "Ctrl+S", "Enter", "Ctrl+Enter"):
        assert spec.casefold() not in SAFE_HOTKEY_SPECS
    assert COMMITTING_SPECS & SAFE_HOTKEY_SPECS == set()


def test_breaker_and_hotkeys_share_one_table():
    """Single source: the breaker gates exactly the table this module owns."""
    from bridge.openclaw.breaker import SAFE_HOTKEYS

    assert SAFE_HOTKEYS == SAFE_HOTKEY_SPECS


def test_send_hotkey_event_order():
    events = []
    send_hotkey("Ctrl+L", sender=lambda vk, down: events.append((vk, down)))
    assert events == [(0x11, True), (0x4C, True), (0x4C, False), (0x11, False)]


def test_send_hotkey_modifiers_release_reversed():
    events = []
    send_hotkey("Ctrl+Shift+T", sender=lambda vk, down: events.append((vk, down)))
    assert [vk for vk, down in events if down] == [0x11, 0x10, 0x54]
    assert [vk for vk, down in events if not down] == [0x54, 0x10, 0x11]


def test_send_hotkey_without_sender_off_windows_refuses(monkeypatch):
    monkeypatch.setattr(os, "name", "posix")
    with pytest.raises(ActuatorUnavailable):
        send_hotkey("Ctrl+L")


class _FakeUIA:
    def __init__(self):
        self.calls = []

    def focus(self, target):
        self.calls.append(("focus", target))

    def click(self, target, control=None, button="left", double=False):
        self.calls.append(("click", target, control, button, double))

    def type_text(self, target, control, text):
        self.calls.append(("type", target, control, text))


def _actuator(**kw):
    kw.setdefault("sender", lambda vk, down: None)
    return DesktopActuator(**kw)


async def test_actuator_routes_focus_click_type():
    uia = _FakeUIA()
    actuator = _actuator(uia=uia)
    assert (await actuator.act(Op(op=OpKind.FOCUS, target="Notepad")))["ok"] is True
    assert (await actuator.act(Op(op=OpKind.CLICK, target="Calc>1")))["ok"] is True
    assert (await actuator.act(Op(op=OpKind.RIGHT_CLICK, target="Desktop>View")))["ok"] is True
    assert (await actuator.act(Op(op=OpKind.DOUBLE_CLICK, target="File>Open")))["ok"] is True
    assert (await actuator.act(Op(op=OpKind.TYPE_TEXT, target="Run>input", value="notepad")))[
        "ok"
    ] is True
    kinds = [c[0] for c in uia.calls]
    assert kinds == ["focus", "click", "click", "click", "type"]
    assert uia.calls[1] == ("click", "Calc", "1", "left", False)
    assert uia.calls[2][3] == "right" and uia.calls[3][4] is True
    assert uia.calls[4] == ("type", "Run", "input", "notepad")


async def test_actuator_hotkey_needs_no_uia():
    actuator = _actuator(uia=None)
    obs = await actuator.act(Op(op=OpKind.HOTKEY, value="Ctrl+L"))
    assert obs["ok"] is True and "Ctrl+L" in obs["evidence"]


async def test_actuator_without_uia_is_honest():
    actuator = _actuator(uia=None)
    with pytest.raises(ActuatorUnavailable):
        await actuator.act(Op(op=OpKind.FOCUS, target="Notepad"))
    with pytest.raises(ActuatorUnavailable):
        await actuator.act(Op(op=OpKind.CLICK, target="x"))


async def test_actuator_refuses_non_desktop_ops():
    actuator = _actuator(uia=_FakeUIA())
    with pytest.raises(ActuatorUnavailable):
        await actuator.act(Op(op=OpKind.NAVIGATE, value="https://example.com"))
    with pytest.raises(ActuatorUnavailable):
        await actuator.act(Op(op=OpKind.SCREENSHOT))


async def test_controller_act_end_to_end_with_desktop_actuator():
    from bridge.openclaw.controller import OpenClawController

    uia = _FakeUIA()
    controller = OpenClawController(actuator=_actuator(uia=uia))
    ok = await controller.act({"op": "hotkey", "value": "Ctrl+L"})
    assert ok.status == "ok"
    refused = await controller.act({"op": "hotkey", "value": "Alt+F4"})
    assert refused.status == "error" and "confirmation" in refused.detail
    assert len(uia.calls) == 0  # hotkeys never reach UIA; refused op never ran
