"""P2 turn counter: crash-resilient human-turn tally in vault State.

Only transport-boundary callers (`on_text`/`on_voice` in `src/bot.py`) bump
it — ReAct internals never import this module (pinned by
`tests/test_turn_counter_p21.py`). House idiom throughout: atomic tmp+replace
writes, corrupt-rename recovery to 0, never raises.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Final

from loguru import logger

COUNTER_NAME: Final[str] = "turn_counter.txt"


def _counter_path(vault_local_path: str | Path) -> Path:
    return Path(vault_local_path) / "State" / COUNTER_NAME


def read_turn_count(vault_local_path: str | Path) -> int:
    """Current tally; missing/garbage/empty recovers to 0 (corrupt-rename)."""
    path = _counter_path(vault_local_path)
    try:
        raw = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return 0
    except OSError:
        logger.warning("turn counter unreadable; treating as 0")
        return 0
    try:
        return max(0, int(raw))
    except ValueError:
        try:
            os.replace(path, path.with_name(path.name + ".corrupt"))
        except OSError:
            logger.warning("turn counter corrupt and unrenamable; treating as 0")
        else:
            logger.warning("turn counter corrupt -> renamed, restarting at 0")
        return 0


def bump_turn_counter(vault_local_path: str | Path) -> int:
    """Increment atomically; returns the new tally. Never raises.

    Under pytest the transport hook skips disk entirely (conftest sets
    SARA_TURN_COUNTER_OFF session-wide for suite hermeticity) — production
    turns always persist.
    """
    if os.environ.get("SARA_TURN_COUNTER_OFF"):
        return read_turn_count(vault_local_path)
    path = _counter_path(vault_local_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        current = read_turn_count(vault_local_path)
        tmp = path.with_name(path.name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as handle:
            handle.write(str(current + 1))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
        return current + 1
    except OSError:
        logger.warning("turn counter bump failed; continuing without tally")
        return read_turn_count(vault_local_path)
