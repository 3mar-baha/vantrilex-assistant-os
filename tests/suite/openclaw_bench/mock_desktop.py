"""Simulated desktop double (Phase 4): window tree, focus states, UIA responses.

Deterministic and CI-safe: no Win32, no cursor, no windows. Faults
(popups, focus loss, missing elements) inject explicitly per scenario —
chaos is scripted, never random.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class UIAElementMissing(Exception):
    """A named window/control does not exist in the simulated tree."""


@dataclass
class MockControl:
    name: str
    role: str = "button"
    value: str = ""


@dataclass
class MockWindow:
    title: str
    controls: dict[str, MockControl] = field(default_factory=dict)
    dirty: bool = False  # unsaved buffer (close-gate scenarios)


class MockDesktop:
    """Window tree + focus state. Every mutation is recorded."""

    def __init__(self, windows: list[MockWindow] | None = None) -> None:
        self.windows: dict[str, MockWindow] = {w.title: w for w in (windows or [])}
        self.focus_title: str | None = next(iter(self.windows), None)
        self.focus_lost = False
        self.calls: list[tuple] = []

    def foreground(self) -> str | None:
        """Foreground probe double: None on simulated focus loss."""
        if self.focus_lost:
            return None
        return self.focus_title

    def resolve_window(self, title: str) -> MockWindow:
        needle = (title or "").strip().casefold()
        for name, window in self.windows.items():
            if needle and needle in name.casefold():
                return window
        raise UIAElementMissing(f"no window matching {title!r}")

    def inject_popup(self, title: str, controls: list[str] | None = None) -> None:
        """Chaos primitive: an unexpected dialog appears AND steals focus."""
        self.windows[title] = MockWindow(
            title=title,
            controls={c: MockControl(name=c, role="button") for c in (controls or ["OK"])},
        )
        self.focus_title = title
        self.calls.append(("popup", title))

    def dismiss_popup(self, title: str) -> None:
        self.windows.pop(title, None)
        self.calls.append(("dismiss", title))
        if self.focus_title == title:
            self.focus_title = next(iter(self.windows), None)


class MockUIA:
    """Actuator-shaped backend over a MockDesktop (focus/click/type_text)."""

    def __init__(self, desktop: MockDesktop) -> None:
        self.desktop = desktop

    def focus(self, target: str) -> None:
        window = self.desktop.resolve_window(target)
        self.desktop.focus_title = window.title
        self.desktop.calls.append(("focus", window.title))

    def click(
        self,
        target: str,
        control: str | None = None,
        button: str = "left",
        double: bool = False,
    ) -> None:
        window = self.desktop.resolve_window(target)
        if control is not None and control not in window.controls:
            raise UIAElementMissing(f"no control {control!r} in {window.title!r}")
        self.desktop.calls.append(("click", window.title, control, button, double))

    def type_text(self, target: str, control: str | None, text: str) -> None:
        window = self.desktop.resolve_window(target)
        if control is None or control not in window.controls:
            raise UIAElementMissing(f"no control {control!r} in {window.title!r}")
        window.controls[control].value = text
        self.desktop.calls.append(("type", window.title, control, text))


def mock_grab_factory(payload: bytes = b"JPEG-BYTES"):
    """Screenshot double: fixed bytes, records invocations."""

    def _grab() -> bytes:
        _grab.calls.append(1)
        return payload

    _grab.calls = []
    return _grab


def mock_ocr_factory(text: str = "Mock dialog text"):
    """OCR double: canned extraction, records (jpeg_len, prompt)."""

    async def _ocr(jpeg: bytes, prompt: str) -> str:
        _ocr.calls.append((len(jpeg), bool(prompt)))
        return text

    _ocr.calls = []
    return _ocr


def notepad_desktop() -> MockDesktop:
    """Standard fixture: Notepad (dirty) + Calculator (clean)."""
    return MockDesktop(
        [
            MockWindow(
                title="Notepad - report.txt",
                controls={"editor": MockControl(name="editor", role="edit")},
                dirty=True,
            ),
            MockWindow(title="Calculator", controls={"1": MockControl(name="1")}),
        ]
    )
