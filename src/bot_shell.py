"""Terminal 1 — Sara's clean chat REPL: the front door with no transport around it.

This module owns PRESENTATION ONLY. Every turn is handed to `FrontDoorDispatcher`
(`src/dispatcher.py:744`, `handle` at `:824`) and the dispatcher's deltas are
yielded back verbatim, token by token. There is deliberately no second code path:

  * it binds EXACTLY ONE symbol from `src.persona` — `build_persona_joda`, the
    builder, and nothing else. That is the narrowed contract (owner decision
    2026-09-30). The builder is the single-sourced dialect + gender contract:
    it composes Sara's byte-locked identity core with the JODA ar-JO few-shot
    exemplars, so the terminal speaks the same dialect and the same masculine-
    address rule as Telegram. The raw literals (`SARA_PERSONA_AR`,
    `JODA_EXEMPLARS_AR`, `JODA_EXEMPLARS_HEADER_AR`) and the core-only
    `build_persona` stay out on purpose — a copied literal is a second source
    of truth, and a second source of truth is what drifts;
  * it imports NONE of `src.gender_pipeline`, `src.voice_policy` — the other
    invariant owners. A shell that imported any of them could apply an
    invariant its own way, and the safety floor would depend on discipline
    instead of structure;
  * it imports NONE of `src.tools`, `src.pc_actions`, `bridge.executor`. A turn
    reaches a tool or the PC coordinator only through the dispatcher, which is
    where the confirmation gate lives;
  * it mints no confirmation id and owns no retry policy — the gateway owns both.

`tests/test_bot_shell_dialect.py` and `tests/test_bot_shell_repl.py` both parse
this file with `ast` and assert exactly that, so the constraint is checked
rather than remembered.

Dialect, closed (owner decision 2026-09-30): the terminal used to pass no
`system` prompt at all. `_plain_messages` (`src/dispatcher.py:1076`) emits a
system message only when `system` is truthy, so the FAST conversation call left
the model with a bare user turn and it answered in MSA. The seam already existed
and the Telegram route already used it (`src/bot.py:615`); the terminal never
supplied it. `build_shell` now takes an injected `system` and `Shell.turn`
forwards that exact object on every turn, and `_live_shell` — the sole
production constructor behind `sara.bat -Chat` — supplies
`system=build_persona_joda()`. The default is the same composed prompt, so a
future caller that forgets the keyword gets ar-JO rather than MSA.

Honest failure: a turn that dies lands one Amman-colloquial line — never a
traceback, never an exception class name, never nothing at all. What the shell
already streamed before the failure is NOT retracted (the gateway's own doctrine:
never restart a partially-yielded reply).

Usage:
    .\\sara.bat -Chat
    .venv/Scripts/python.exe -m src.bot_shell
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import AsyncIterator
from typing import Final

from loguru import logger

from src.dispatcher import FrontDoorDispatcher
from src.gateway import OmniRouteClient, Tier
from src.persona import build_persona_joda

# The ONE permitted symbol from src.persona: the builder, never a literal. It
# composes the byte-locked identity core with the JODA ar-JO few-shot exemplars,
# so the terminal and Telegram share one dialect + gender contract. Composed once
# at import and reused as the default so no caller can accidentally ship MSA.
TERMINAL_SYSTEM_PROMPT: Final[str] = build_persona_joda()

# The one honest sentence a failed turn leaves behind. Amman colloquial, because
# the owner reads it in a terminal at 2am. It must never carry the exception: the
# gateway's own log owns the diagnosis, the owner only needs the truth that
# nothing came back.
HONEST_FAILURE_AR: Final[str] = (
    "يا أستاذ، قصفت بشي تقني هلق وما وصل رد — جرب تاني بشوي، وما في شي ضاع."
)

BANNER_AR: Final[str] = "سارة — الطرفية. اكتب سؤالك وسلاّم، وبحكي معك بالعربي الأردني."
PROMPT: Final[str] = "أنت> "

# Rolling window of the conversation, in messages (user + assistant pairs). The
# front door is handed this as `history`; it is bounded so a long session cannot
# grow the prompt without limit. Smaller than src/memory.py's DEFAULT_BUFFER_MESSAGES
# (50): the terminal has no long-term envelope behind it, so a shorter window keeps
# the whole conversation inside the prompt instead of paying to re-send the vault.
HISTORY_MESSAGES: Final[int] = 20

_EXIT_WORDS: Final[frozenset[str]] = frozenset({"/exit", "/quit", "/q", "exit", "quit"})


class Shell:
    """One typed line in, the front door's deltas out.

    Holds no brain of its own: `turn` is the whole contract. Presentation state is
    the conversation window it echoes back to the dispatcher as `history`.
    """

    def __init__(self, front_door: FrontDoorDispatcher, system: str) -> None:
        self._front_door = front_door
        # Held by identity, never rebuilt per turn: a per-turn rebuild would let
        # the dialect drift mid-session while every equality check still passed.
        self._system = system
        self._history: list[dict] = []

    async def turn(self, text: str) -> AsyncIterator[str]:
        """Yield the dispatcher's deltas verbatim, then keep the honest floor.

        Never raises and never yields nothing: whatever the gateway does, the owner
        reads a sentence, not a stack trace. The injected `system` prompt rides
        every call — without it `_plain_messages` sends no system message at all
        and the model answers in MSA instead of ar-JO.
        """
        streamed = False
        spoken = ""
        try:
            async for delta in self._front_door.handle(
                text, system=self._system, history=self._window()
            ):
                streamed = True
                spoken += delta
                yield delta
        except Exception as exc:  # noqa: BLE001 — the terminal floor: a shell never raises at the owner
            # Logged loudly rather than swallowed (CLAUDE.md §3). Named cases this
            # covers: GatewayError (router/gateway exhausted), OSError and
            # asyncio.TimeoutError (transport), anything else the front door raises.
            # Whatever already streamed stays on the owner's screen.
            logger.error("bot_shell turn failed [{}]: {}", type(exc).__name__, exc)
            yield HONEST_FAILURE_AR
        else:
            if not streamed:
                # An empty turn is a dead turn: the owner typed something and is
                # owed a sentence either way.
                yield HONEST_FAILURE_AR
        finally:
            if streamed and spoken.strip():
                # Remember exactly what the owner saw, so turn two's context
                # matches turn one's screen — including a reply that died mid-way.
                self._remember(text, spoken)

    def _window(self) -> list[dict]:
        """A copy — the dispatcher must not be able to mutate our window."""
        return list(self._history)

    def _remember(self, said: str, reply: str) -> None:
        self._history += [
            {"role": "user", "content": said},
            {"role": "assistant", "content": reply},
        ]
        del self._history[:-HISTORY_MESSAGES]


def build_shell(
    gateway: OmniRouteClient, settings, *, system: str = TERMINAL_SYSTEM_PROMPT
) -> Shell:
    """Wrap the ADR-18 front door as a terminal shell.

    The dispatcher is built once and reused for every turn: per-turn construction
    would drop the verdict cache and the reflective friction trace, and the shell
    would silently behave differently on turn two.

    `system` is the injected dialect prompt, keyword-only and named to match
    `FrontDoorDispatcher.handle` so the terminal and Telegram spell the contract
    identically. It defaults to the composed ar-JO prompt rather than to `None`:
    `None` is the silent-MSA failure this decision exists to remove, and a caller
    that forgets the keyword should not inherit it.
    """
    return Shell(FrontDoorDispatcher(gateway, settings), system)


def _live_shell() -> Shell:
    """Build the shell from the owner's real `.env` (no secret is ever written here)."""
    from src.config import Settings

    settings = Settings()
    gateway = OmniRouteClient(
        settings.omniroute_base_url,
        settings.omniroute_api_key,
        chains={
            Tier.FAST: settings.fast_chain,
            Tier.MEDIUM: settings.medium_chain,
            Tier.HEAVY: settings.heavy_chain,
        },
    )
    # The production prompt is passed explicitly, not left to the default: this is
    # the one constructor behind `sara.bat -Chat`, and if the terminal ever loses
    # its dialect this line is where the loss is visible.
    return build_shell(gateway, settings, system=build_persona_joda())


async def _repl(shell: Shell) -> int:
    print(BANNER_AR)
    print("(/exit للنروج)")
    while True:
        try:
            # to_thread so Ctrl-C on Windows stays responsive while a turn streams.
            line = await asyncio.to_thread(input, PROMPT)
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        # lstrip the BOM: PowerShell injects U+FEFF into a piped/redirected stdin, and
        # a scripted smoke test must behave exactly like a typed line.
        said = line.strip().lstrip("﻿")
        if not said:
            continue
        if said.casefold() in _EXIT_WORDS:
            return 0
        async for delta in shell.turn(said):
            print(delta, end="", flush=True)
        print()


async def _session() -> int:
    return await _repl(_live_shell())


def main(argv: list[str] | None = None) -> int:
    """`python -m src.bot_shell` — the Terminal 1 entry point behind `sara.bat -Chat`."""
    argparse.ArgumentParser(
        description="Sara terminal chat REPL (Terminal 1) — Ctrl-D or /exit to leave."
    ).parse_args(argv)
    try:
        return asyncio.run(_session())
    except Exception as exc:  # noqa: BLE001 — a launcher reports its boot failure, never a traceback
        print(f"الت-shell ما قدر يقلع: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
