"""Shared hotkey vocabulary (Phase 3.4): the T0 doctrine made machine-usable.

Derived from `04_Resources/Knowledge_Bases/OpenClaw/
Keyboard_Shortcuts_and_Accelerators.md`. SINGLE SOURCE for the safe set:
`bridge.openclaw.breaker` gates exactly this table (imported, not copied).

- SAFE_HOTKEY_SPECS: attention-moving accelerators (auto-execute tier).
- COMMITTING_SPECS: specs that commit owner-visible state (confirmation
  tier) — documented here so planners see the cliff edge; the breaker
  defaults any unknown spec UP (irreversible).
"""

from __future__ import annotations

from typing import Final

# action -> spec (RAG-mapped accelerators the planner may request by name).
ACTION_HOTKEYS: Final[dict[str, str]] = {
    "address_bar": "Ctrl+L",
    "new_tab": "Ctrl+T",
    "close_tab": "Ctrl+W",
    "reopen_tab": "Ctrl+Shift+T",
    "next_tab": "Ctrl+Tab",
    "find": "Ctrl+F",
    "refresh": "Ctrl+R",
    "devtools": "F12",
    "quick_open": "Ctrl+P",
    "command_palette": "Ctrl+Shift+P",
    "terminal": "Ctrl+`",
    "task_manager": "Ctrl+Shift+Esc",
    "run_dialog": "Win+R",
    "lock": "Win+L",
    "snip": "Win+Shift+S",
    "emoji_panel": "Win+.",
    "desktop": "Win+D",
    "explorer": "Win+E",
    "clipboard_history": "Win+V",
    "undo": "Ctrl+Z",
}

SAFE_HOTKEY_SPECS: Final[frozenset[str]] = frozenset(
    {
        "ctrl+l",
        "ctrl+t",
        "ctrl+tab",
        "ctrl+shift+tab",
        "ctrl+f",
        "ctrl+r",
        "f6",
        "f5",
        "alt+tab",
        "alt+left",
        "alt+right",
        "escape",
        "esc",
        "tab",
        "shift+tab",
        "up",
        "down",
        "left",
        "right",
        "pageup",
        "pagedown",
        "home",
        "end",
        "ctrl+home",
        "ctrl+end",
        "win+d",
        "win+e",
        "win+v",
        "win+shift+s",
        "ctrl+w",
        "ctrl+shift+t",
        "ctrl+p",
        "ctrl+shift+p",
        "ctrl+shift+esc",
        "f12",
        "win+r",
        "win+.",
    }
)

# Deliberately NOT safe (default UP to confirmation): win+l (locks the
# owner's live session), ctrl+z (undo destroys forward state).

# Known-committing specs (informational — the breaker treats ANYTHING
# outside SAFE_HOTKEY_SPECS as irreversible, so this set can never excuse).
COMMITTING_SPECS: Final[frozenset[str]] = frozenset({"alt+f4", "ctrl+s", "enter", "ctrl+enter"})
