"""Desktop actuation arm (Phase 3.4): UIA backend + hotkey injection.

- Hotkeys: parsed specs (Ctrl/Alt/Shift/Win + key) driven through an
  injected sender; the default sender is raw Win32 keybd_event (PC only,
  Windows-only guard). The breaker already gated the op — this lane is
  purely mechanical.
- UIA: PyWinAutoBackend resolves windows by title substring and controls
  by accessible name (lazy pywinauto import — wheels are PC-only).
  Target convention: "WindowTitle" or "WindowTitle>ControlName".
- Non-desktop op kinds refuse loudly (ActuatorUnavailable) — lanes never
  bleed into each other.
"""

from __future__ import annotations

import asyncio
import ctypes
import os
from typing import Any, Final, Protocol

from bridge.openclaw.protocol import Op, OpKind


class ActuatorUnavailable(Exception):
    """Honest refusal: backend unbound, wrong lane, or non-Windows host."""


_MOD_VK: Final[dict[str, int]] = {"ctrl": 0x11, "alt": 0x12, "shift": 0x10, "win": 0x5B}

_NAMED_VK: Final[dict[str, int]] = {
    "enter": 0x0D,
    "esc": 0x1B,
    "escape": 0x1B,
    "tab": 0x09,
    "space": 0x20,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pagedown": 0x22,
}


def _vk_for(key: str) -> int:
    lowered = key.casefold()
    if lowered in _NAMED_VK:
        return _NAMED_VK[lowered]
    if len(key) == 1:
        return ord(key.upper())
    if lowered.startswith("f") and lowered[1:].isdigit() and 1 <= int(lowered[1:]) <= 24:
        return 0x6F + int(lowered[1:])
    raise ValueError(f"unknown key {key!r}")


def parse_hotkey(spec: str) -> tuple[frozenset[str], str]:
    """ "Ctrl+Shift+T" -> ({ctrl, shift}, "T"). Rejects empties and unknown
    modifiers — a malformed spec never reaches the wire."""
    parts = [(p or "").strip() for p in (spec or "").split("+")]
    *mods, key = parts
    if not key or any(not m or m.casefold() not in _MOD_VK for m in mods):
        raise ValueError(f"malformed hotkey {spec!r}")
    return frozenset(m.casefold() for m in mods), key.upper()


def _ctypes_sender(vk: int, down: bool) -> None:
    ctypes.windll.user32.keybd_event(vk, 0, 0 if down else 2, 0)  # type: ignore[attr-defined]


def send_hotkey(spec: str, sender=None) -> None:
    """Mechanical key sequence: modifiers down (fixed order), key tap,
    modifiers up reversed. No policy here — the breaker gated upstream."""
    modifiers, key = parse_hotkey(spec)
    if sender is None and os.name != "nt":
        raise ActuatorUnavailable("Win32 hotkey injection needs Windows")
    send = sender or _ctypes_sender
    order = ("ctrl", "alt", "shift", "win")
    held = [m for m in order if m in modifiers]
    code = _vk_for(key)
    for mod in held:
        send(_MOD_VK[mod], True)
    send(code, True)
    send(code, False)
    for mod in reversed(held):
        send(_MOD_VK[mod], False)


class UIAutomation(Protocol):
    """PyWinAuto-shaped backend (methods run in executors — sync is fine)."""

    def focus(self, target: str) -> None: ...
    def click(
        self, target: str, control: str | None = ..., button: str = ..., double: bool = ...
    ) -> None: ...
    def type_text(self, target: str, control: str | None, text: str) -> None: ...


def split_target(target: str | None) -> tuple[str, str | None]:
    """'Window>Control' -> ('Window', 'Control'); bare names -> (name, None)."""
    clean = (target or "").strip()
    if ">" in clean:
        window, _, control = clean.partition(">")
        return window.strip(), control.strip() or None
    return clean, None


class PyWinAutoBackend:
    """Real UIA binding (PC only): windows by title substring, controls by
    accessible name. pywinauto imports lazily per call — missing wheels
    surface as ActuatorUnavailable, never ImportError."""

    def __init__(self, *, backend: str = "uia", timeout: float = 10.0) -> None:
        self._backend = backend
        self._timeout = timeout

    def _window(self, title: str):
        try:
            from pywinauto import Application
        except ImportError as exc:
            raise ActuatorUnavailable(
                "pywinauto wheels not installed (requirements-bridge.txt)"
            ) from exc
        app = Application(backend=self._backend).connect(
            title_re=f".*{title}.*", timeout=self._timeout
        )
        return app.top_window()

    def focus(self, target: str) -> None:
        self._window(target).set_focus()

    def click(
        self, target: str, control: str | None = None, button: str = "left", double: bool = False
    ) -> None:
        window = self._window(target)
        if control:
            window.child_window(title=control).click_input(button=button, double=double)
        else:
            window.click_input(button=button, double=double)

    def type_text(self, target: str, control: str | None, text: str) -> None:
        window = self._window(target)
        if control:
            window.child_window(title=control).type_keys(text, with_spaces=True)
        else:
            window.type_keys(text, with_spaces=True)


class DesktopActuator:
    """Mechanical desktop executor: hotkeys via sender, everything else via
    the injected UIA backend. Returns observation dicts for transcripts."""

    _CLICK_BUTTONS: Final[dict[str, tuple[str, bool]]] = {
        "click": ("left", False),
        "double_click": ("left", True),
        "right_click": ("right", False),
    }

    def __init__(self, *, uia: Any = None, sender=None) -> None:
        self._uia = uia
        self._sender = sender

    async def act(self, op: Op) -> dict[str, Any]:
        kind = op.op
        if kind is OpKind.HOTKEY:
            send_hotkey(op.value or "", sender=self._sender)
            return {"ok": True, "evidence": f"hotkey {op.value}"}
        if self._uia is None:
            raise ActuatorUnavailable("UIA backend not bound (Phase 3.4 binds pywinauto)")
        window, control = split_target(op.target)
        if kind is OpKind.FOCUS:
            await asyncio.to_thread(self._uia.focus, window)
            return {"ok": True, "evidence": f"focused {window}"}
        if kind.value in self._CLICK_BUTTONS:
            button, double = self._CLICK_BUTTONS[kind.value]
            await asyncio.to_thread(self._uia.click, window, control, button, double)
            return {"ok": True, "evidence": f"clicked {window}>{control or 'window'}"}
        if kind is OpKind.TYPE_TEXT:
            await asyncio.to_thread(self._uia.type_text, window, control, op.value or "")
            return {"ok": True, "evidence": f"typed {len(op.value or '')} chars"}
        raise ActuatorUnavailable(f"{kind.value} is not a desktop actuation")


async def _noop() -> None:  # pragma: no cover -- import-time shape guard
    return None
