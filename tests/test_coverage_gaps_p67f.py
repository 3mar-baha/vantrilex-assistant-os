"""P6 batch 7f — bridge/openclaw/actuator.py uncovered edges: named/F-key/
unknown virtual keys via public send_hotkey, stubbed-Win32 sender line,
pywinauto-absent honest refusal, backend focus/click/type dispatch both
control branches.
"""

from __future__ import annotations

import pytest

from bridge.openclaw.actuator import (
    ActuatorUnavailable,
    DesktopActuator,
    PyWinAutoBackend,
    _ctypes_sender,
    _vk_for,
    send_hotkey,
)
from bridge.openclaw.protocol import Op, OpKind


def test_vk_named_function_and_unknown():
    assert _vk_for("enter") == 0x0D
    assert _vk_for("a") == ord("A")
    assert _vk_for("F6") == 0x6F + 6
    with pytest.raises(ValueError):
        _vk_for("Nope")


def test_send_hotkey_key_shapes():
    events = []
    send_hotkey("Ctrl+Enter", sender=lambda vk, down: events.append((vk, down)))
    assert (0x0D, True) in events
    events.clear()
    send_hotkey("Alt+F6", sender=lambda vk, down: events.append((vk, down)))
    assert (0x6F + 6, True) in events
    with pytest.raises(ValueError):
        send_hotkey("Ctrl+Nope", sender=lambda vk, down: None)


def test_ctypes_sender_line_runs_against_stub_windll(monkeypatch):
    import ctypes

    calls = []

    class _User32:
        def keybd_event(self, vk, scan, flags, extra):
            calls.append((vk, flags))

    monkeypatch.setattr(ctypes, "windll", type("W", (), {"user32": _User32()})(), raising=False)
    _ctypes_sender(0x41, True)
    _ctypes_sender(0x41, False)
    assert calls == [(0x41, 0), (0x41, 2)]  # zero real injection, the line runs


def test_backend_without_pywinauto_refuses_honestly():
    backend = PyWinAutoBackend()
    with pytest.raises(ActuatorUnavailable):
        backend._window("Notepad")


class _Window:
    def __init__(self):
        self.calls = []

    def set_focus(self):
        self.calls.append("focus")

    def click_input(self, *, button="left", double=False):
        self.calls.append(("click", button, double))

    def type_keys(self, text, *, with_spaces=True):
        self.calls.append(("type", text, with_spaces))

    def child_window(self, *, title):
        self.calls.append(("child", title))
        return self


def test_backend_dispatches_control_branches(monkeypatch):
    backend = PyWinAutoBackend()
    window = _Window()
    monkeypatch.setattr(backend, "_window", lambda _title: window)
    backend.focus("Notepad")
    backend.click("Calc", "1")
    backend.click("Desktop", None)
    backend.type_text("Run", "input", "notepad")
    backend.type_text("Run", None, "x")
    assert window.calls[0] == "focus"
    assert ("child", "1") in window.calls and ("click", "left", False) in window.calls
    assert ("type", "notepad", True) in window.calls


async def test_actuator_click_without_control_hits_window():
    seen = []

    class _UIA:
        def click(self, target, control=None, button="left", double=False):
            seen.append((target, control, button, double))

    actuator = DesktopActuator(uia=_UIA(), sender=lambda vk, down: None)
    obs = await actuator.act(Op(op=OpKind.CLICK, target="Desktop"))
    assert obs["ok"] is True and seen == [("Desktop", None, "left", False)]
