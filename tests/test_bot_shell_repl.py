"""Item B (plan §1) — `src/bot_shell.py`, the clean chat REPL (Terminal 1).

FILENAME NOTE (measured, Directive 3): the plan's write-set names
`tests/test_bot_shell.py`, but that path is already occupied by the 47 KB Telegram
shell suite (`tests/test_bot_shell.py`, which drives `src/bot.py` via the
`make_shell` fixture and `tests.conftest`). Overwriting it would delete a live
suite. This file is `test_bot_shell_repl.py`; the module under test is still
`src/bot_shell.py`. Renaming is a one-line owner/implementer decision.

The invariant is preserved STRUCTURALLY, not by discipline (plan §2): bot_shell owns
presentation only, every turn is handed to `FrontDoorDispatcher`
(`src/dispatcher.py:744`, `handle` at `:824`), so there is no second code path for an
invariant to leak through. The guards below:

  1. structural — the shell imports the front door and NOT `src.gender_pipeline` /
     `src.voice_policy`, and cannot reach a tool or the PC coordinator at all;
  2. behavioural — every turn goes through the dispatcher, and every string the shell
     emits is a string the dispatcher produced;
  3. honest failure — a dead gateway or a dead turn lands one Amman-colloquial line,
     never a traceback and never an empty line.

NARROWED 2026-09-30 (owner decision 1, Terminal 1 must answer in ar-JO): guard 1
above no longer bans `src.persona` outright. The terminal was sending no `system`
prompt at all, so it answered in MSA; the persona BUILDER is the only thing that can
give it a dialect. `src/bot_shell.py` now binds exactly `build_persona_joda` and
nothing else from persona. That permit — and the ban on the raw literals and on
core-only `build_persona` — is asserted in `tests/test_bot_shell_dialect.py`. This
file keeps guarding everything else.

The module is unbuilt, so the fixture below fails every test with a message naming
the missing file: that is the intended RED, one failure per guard instead of a single
collection error.

Public seam this file pins (mirrors `src.bot.build_dispatcher`, `:1191`):
    build_shell(gateway, settings) -> shell with `async def turn(text)` yielding the
    dispatcher's deltas verbatim, token by token.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

from src import dispatcher as dispatcher_mod
from src.gateway import GatewayError
from tests.test_omniroute_gateway import _collect

SHELL_PATH = Path(__file__).resolve().parents[1] / "src" / "bot_shell.py"

# The invariant owners the shell must never reach, after the 2026-09-30 narrowing
# that permitted exactly one `src.persona` symbol (`build_persona_joda`) so Terminal 1
# can speak ar-JO. Gender and voice stay banned: a chat shell that imported either has
# a second code path for that invariant, which is the exact failure mode §2 forbids.
INVARIANT_OWNERS = ("src.gender_pipeline", "src.voice_policy")

# The surfaces that can cause a side effect. Presentation-only means none of them.
SIDE_EFFECT_SURFACES = ("src.tools", "src.pc_actions", "bridge.executor")

# Nothing this shell may print, ever.
TRACEBACK_MARKERS = ("Traceback", "Exception:", "Error:")

# The Arabic block, U+0600..U+06FF.
ARABIC_RANGE = ("؀", "ۿ")


def _identifiers(source: str) -> set[str]:
    """Every name the source binds or reads — a comment or docstring cannot pass."""
    return {node.id for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Name)} | {
        node.attr for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Attribute)
    }


def _imported_modules(source: str) -> set[str]:
    """Every module named by an import, normalized to dotted absolute form.

    `from src import persona` yields `src.persona`, so a laundered import cannot
    slip past the check.
    """
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:  # relative import — has no place in this package
                continue
            module = node.module or ""
            names.add(module)
            names.update(f"{module}.{alias.name}" for alias in node.names if module)
    return names


def _shell_mod():
    """Import the unbuilt module from inside the test body, not at module scope.

    A module-scope import reports ONE collection error for all seven guards and hides
    which contract is unmet. Called per test, each guard fails on its own and names
    the file the implementer has to create.
    """
    try:
        return importlib.import_module("src.bot_shell")
    except ModuleNotFoundError as exc:
        pytest.fail(f"src/bot_shell.py does not exist yet (item B, plan §1): {exc}")


def _shell_source() -> str:
    if not SHELL_PATH.exists():
        pytest.fail(f"src/bot_shell.py does not exist yet (item B, plan §1): {SHELL_PATH}")
    return SHELL_PATH.read_text(encoding="utf-8")


class _DispatcherSpy:
    """Stands in for `FrontDoorDispatcher`: records how it was built and how used.

    Doubles as the factory (returns itself) so `build_shell`'s construction call is
    captured with the exact `gateway` / `settings` handles it received.
    """

    def __init__(self, deltas=(), *, boom_before=False, boom_after=False) -> None:
        self.deltas = list(deltas)
        self.boom_before = boom_before
        self.boom_after = boom_after
        self.turns: list[str] = []
        self.constructions: list[dict] = []

    def __call__(self, *args, **kwargs) -> _DispatcherSpy:
        bound = dict(zip(("gateway", "settings"), args))
        bound.update(kwargs)
        self.constructions.append(bound)
        return self

    async def handle(self, user_text: str, **kwargs):
        self.turns.append(user_text)
        if self.boom_before:
            raise GatewayError("router unreachable")
        for delta in self.deltas:
            yield delta
        if self.boom_after:
            raise GatewayError("stream died")


def _front_door(monkeypatch, shell_mod, spy: _DispatcherSpy) -> None:
    """Intercept the class on both import spellings bot_shell might use."""
    monkeypatch.setattr(dispatcher_mod, "FrontDoorDispatcher", spy)
    monkeypatch.setattr(shell_mod, "FrontDoorDispatcher", spy, raising=False)


def _is_amman_line(text: str) -> bool:
    low, high = ARABIC_RANGE
    return bool(text.strip()) and any(low <= char <= high for char in text)


# --- 1. structural: the invariant owners and the side-effect surfaces are absent ---


def test_shell_imports_the_front_door_dispatcher() -> None:
    """The shell must import the front door and actually name its class.

    Red: `src/bot_shell.py` does not exist. Green: the source imports
    `src.dispatcher` and references `FrontDoorDispatcher`.
    """
    source = _shell_source()
    modules = _imported_modules(source)
    assert "src.dispatcher" in modules, f"src.bot_shell must import src.dispatcher; has {modules}"
    assert "FrontDoorDispatcher" in _identifiers(source), (
        "src.bot_shell must build a FrontDoorDispatcher, not import it and ignore it"
    )


def test_shell_does_not_import_the_invariant_owners() -> None:
    """§2: there must be no second persona / gender / voice path to leak through.

    NARROWED 2026-09-30 (owner decision 1): `src.persona` is no longer a blanket
    ban. The terminal must speak ar-JO, the persona builder is the only thing that
    can give it a dialect, and `src/bot_shell.py` now binds EXACTLY
    `build_persona_joda` from it. Relaxing ONE module must not relax the rest, so
    the two remaining invariant owners are still banned here and the side-effect
    surfaces are still banned in the test below — together the two tests assert
    `src.gender_pipeline`, `src.voice_policy`, `src.tools`, `src.pc_actions` and
    `bridge.executor`. The persona permit itself is asserted in
    `tests/test_bot_shell_dialect.py::test_shell_binds_exactly_the_permitted_persona_symbol`,
    which also bans the raw literals and the core-only `build_persona`.

    Red: the module is missing. Green: no import (direct or laundered through
    `from src import ...`) of src.gender_pipeline or src.voice_policy.
    """
    leaked = _imported_modules(_shell_source()) & set(INVARIANT_OWNERS)
    assert not leaked, f"bot_shell owns presentation only; it must not import {sorted(leaked)}"


def test_shell_cannot_reach_a_tool_or_the_pc_coordinator() -> None:
    """Presentation-only also means no side-effect surface in the import graph.

    Red: the module is missing. Green: no import of src.tools (ToolRegistry),
    src.pc_actions (PCActionCoordinator) or bridge.executor.
    """
    reachable = _imported_modules(_shell_source()) & set(SIDE_EFFECT_SURFACES)
    assert not reachable, (
        f"bot_shell must not reach {sorted(reachable)} — a chat turn reaches tools "
        "only through the dispatcher, which is where the confirmation gate lives"
    )


# --- 2. behavioural: every turn goes through the front door, verbatim ---------------


async def test_every_turn_is_handed_to_the_front_door(make_settings, monkeypatch) -> None:
    """Two typed lines, two dispatcher turns — no turn is answered locally.

    Red: the module is missing. Green: `build_shell` constructs exactly one
    FrontDoorDispatcher from the gateway + settings it was handed, and `turn`
    reaches `handle` once per line with the owner's own text.
    """
    shell_mod = _shell_mod()
    spy = _DispatcherSpy(deltas=("أهلاً", " فيك"))
    _front_door(monkeypatch, shell_mod, spy)
    gateway, settings = object(), make_settings()
    shell = shell_mod.build_shell(gateway, settings)
    for line in ("مرحبا يا سارة", "شو عندك اليوم"):
        await _collect(shell.turn(line))
    assert spy.turns == ["مرحبا يا سارة", "شو عندك اليوم"]
    assert len(spy.constructions) == 1, f"front door rebuilt per turn: {spy.constructions}"
    assert spy.constructions[0]["gateway"] is gateway
    assert spy.constructions[0]["settings"] is settings


async def test_shell_emits_exactly_what_the_dispatcher_produced(make_settings, monkeypatch) -> None:
    """§2: it may not emit a string the dispatcher did not produce.

    Red: the module is missing. Green: the ack and every streamed token arrive
    token by token, in the dispatcher's order, with nothing added and nothing
    dropped.
    """
    shell_mod = _shell_mod()
    deltas = ["من عيوني", " هسا ببدأ", " — ثواني"]
    _front_door(monkeypatch, shell_mod, _DispatcherSpy(deltas=deltas))
    shell = shell_mod.build_shell(object(), make_settings())
    assert await _collect(shell.turn("شو رأيك")) == deltas


# --- 3. honest failure: one Amman line, never a traceback, never nothing ----------


@pytest.mark.parametrize(
    ("failure", "booms"),
    [
        ("router never answers", {"boom_before": True}),
        ("stream dies mid-turn", {"boom_after": True}),
    ],
)
async def test_failed_turn_lands_an_honest_amman_line(
    make_settings, monkeypatch, failure: str, booms: dict
) -> None:
    """A failing gateway must leave the owner a sentence, not a stack trace.

    Red: the module is missing. Green: the last thing the turn yields is a
    non-empty ar-JO line, it leaks no Python traceback or exception class, and the
    turn is not silently empty.
    """
    shell_mod = _shell_mod()
    _front_door(monkeypatch, shell_mod, _DispatcherSpy(deltas=("من ع",), **booms))
    shell = shell_mod.build_shell(object(), make_settings())
    out = await _collect(shell.turn("شو رأيك"))
    assert out, f"{failure}: the turn produced nothing at all"
    last = out[-1]
    assert _is_amman_line(last), f"{failure}: last line is not an Amman line: {last!r}"
    leaked = [marker for marker in TRACEBACK_MARKERS if marker in last]
    assert not leaked, f"{failure}: last line leaks {leaked}: {last!r}"
    assert "GatewayError" not in last, f"{failure}: last line names the exception: {last!r}"
