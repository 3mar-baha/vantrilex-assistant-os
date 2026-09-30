"""Item A (plan §1) — `sara.bat` launcher modes, parsed as TEXT, never executed.

Why parse and not run: a batch file is a shell script. Executing it from a test would
launch PowerShell, probe OmniRoute and boot the core. The property under test is a pure
text mapping, so the file is read and its `if /i "%~1"=="<FLAG>" (` blocks are walked line
by line — the same idiom the file already uses at `:6-10` and `:11-14`.

The modes measured in the tree today (re-derived on every run, Directive 6):
    -InstallAutoStart -> scripts/setup_autostart.ps1   (sara.bat:6-10)
    -Trace            -> scripts/live_shadow_tracer.py  (sara.bat:11-14)
    <no flag>         -> sara.ps1 with %*               (sara.bat:15)

Contract pinned here (plan §1 item A):
    - `-Chat` launches `src.bot_shell` (Terminal 1, the clean chat REPL)
    - `--tracer` is accepted as an alias of the existing `-Trace`
    - `-Trace` and `-InstallAutoStart` keep working — no mode is removed or repointed
    - every mode compares case-insensitively (`if /i`) and ends its own flow
    - `sara.ps1` keeps `-Port` / `-StopOnly` / `-Force` (item A's stated non-goal:
      no new PowerShell logic, so the PS side must be untouched)
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

import pytest

ROOT = Path(__file__).resolve().parents[1]
BAT = ROOT / "sara.bat"
PS1 = ROOT / "sara.ps1"

# One match per condition, so a combined line
#   if /i "%~1"=="-Trace" if /i "%~1"=="--tracer" (
# yields two flags off one block.
_COND = re.compile(r'(?:(/i)\s+)?"%~1"\s*==\s*"([^"]+)"')
_BLOCK_OPEN = re.compile(r"^\s*if\b(?P<head>.*?)\(\s*$")
_BLOCK_CLOSE = re.compile(r"^\s*\)\s*$")


class Mode(NamedTuple):
    """One `if "%~1"=="<flag>" (` declaration.

    A file may legitimately declare a flag twice — a combined `-Trace` / `--tracer`
    line does exactly that — so EVERY declaration is kept. Keying by flag and keeping
    only the last would let a repointed mode hide behind a later one, which is how
    this guard was caught being vacuous during the break-run.
    """

    flag: str
    insensitive: bool
    body: str


def _modes(text: str) -> list[Mode]:
    modes: list[Mode] = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        opened = _BLOCK_OPEN.match(lines[index])
        hits = _COND.findall(opened.group("head")) if opened else []
        if not hits:
            index += 1
            continue
        body: list[str] = []
        cursor = index + 1
        while cursor < len(lines) and not _BLOCK_CLOSE.match(lines[cursor]):
            body.append(lines[cursor])
            cursor += 1
        modes += [Mode(flag, bool(insensitive), "\n".join(body)) for insensitive, flag in hits]
        index = cursor + 1
    return modes


def _matches(mode: Mode, typed: str) -> bool:
    """Faithful emulation of one `if [%i] "%~1"=="<flag>" (` comparison.

    `if /i` folds case; a bare `if` does not. Folding unconditionally here would
    make the casing guard pass on a file that is case-sensitive, which is exactly
    the vacuity the break-run caught.
    """
    if mode.insensitive:
        return mode.flag.casefold() == typed.casefold()
    return mode.flag == typed


def _declared(flag: str, text: str | None = None) -> list[Mode]:
    """Every declaration of `flag` the way the batch file itself would match it."""
    source = BAT.read_text(encoding="utf-8") if text is None else text
    return [mode for mode in _modes(source) if _matches(mode, flag)]


def _flags(text: str | None = None) -> list[str]:
    source = BAT.read_text(encoding="utf-8") if text is None else text
    return [mode.flag for mode in _modes(source)]


def _resolve(typed_flag: str) -> Mode | None:
    """What the batch file would do with this exact argument string."""
    found = _declared(typed_flag)
    return found[0] if found else None


def _flat(body: str) -> str:
    """Batch writes backslash paths; normalize so both spellings compare equal."""
    return body.replace("\\", "/")


# The two modes that already exist, with the targets they carry today. A mode that
# silently changes target is as much a regression as a mode that disappears.
EXISTING_MODES = [
    ("-Trace", "scripts/live_shadow_tracer.py"),
    ("-InstallAutoStart", "scripts/setup_autostart.ps1"),
]


def test_chat_mode_exists_and_launches_the_bot_shell() -> None:
    """`sara.bat -Chat` boots Terminal 1 — and nothing else.

    Red: the flag does not exist. Green: an `if /i "%~1"=="-Chat" (` block whose body
    runs the venv interpreter against `src.bot_shell` (module or script form) and
    does not fall into the full-stack `sara.ps1` boot.
    """
    found = _declared("-Chat")
    assert found, f"no -Chat mode in sara.bat; parsed modes: {_flags()}"
    for mode in found:
        body = _flat(mode.body)
        assert "src.bot_shell" in body, f"-Chat must launch src.bot_shell; body was:\n{body}"
        assert "sara.ps1" not in body, f"-Chat is a chat shell, not a full-stack boot:\n{body}"


def test_double_dash_tracer_alias_maps_to_the_same_target() -> None:
    """`--tracer` is an alias, not a second implementation.

    Red: the alias does not exist. Green: every `--tracer` declaration runs byte-for-byte
    the command the `-Trace` declarations run, so the two flags cannot drift apart.
    """
    alias = _declared("--tracer")
    assert alias, f"no --tracer alias in sara.bat; parsed modes: {_flags()}"
    traced = _declared("-Trace")
    assert traced, f"the -Trace mode this aliases is gone; parsed modes: {_flags()}"
    alias_bodies = {_flat(mode.body) for mode in alias}
    trace_bodies = {_flat(mode.body) for mode in traced}
    assert alias_bodies == trace_bodies, (
        f"--tracer must be the same command as -Trace; alias={alias_bodies} -Trace={trace_bodies}"
    )


@pytest.mark.parametrize(("flag", "target"), EXISTING_MODES)
def test_pre_existing_mode_still_maps_to_its_script(flag: str, target: str) -> None:
    """Adding modes must not remove or repoint the two that already ship.

    Checked against EVERY declaration of the flag, so a mode that is declared twice
    and repointed in one of the two blocks cannot pass on the strength of the other.
    """
    found = _declared(flag)
    assert found, f"{flag} was removed from sara.bat; modes: {_flags()}"
    for mode in found:
        assert target in _flat(mode.body), f"{flag} must still launch {target}; body:\n{mode.body}"


def test_every_mode_compares_case_insensitively() -> None:
    """The dispatcher types `-trace` about as often as `-Trace`.

    Red: a new mode written with a bare `if` is case-sensitive. Green: every `%~1`
    comparison in the file carries `/i`, so the batch file matches its own behaviour.
    """
    modes = _modes(BAT.read_text(encoding="utf-8"))
    assert modes, "sara.bat declares no %~1 modes at all"
    case_sensitive = [mode.flag for mode in modes if not mode.insensitive]
    assert not case_sensitive, f"these modes are case-sensitive: {case_sensitive}"


@pytest.mark.parametrize(
    "typed",
    [
        "-trace",
        "-TRACE",
        "-TrAcE",
        "--tracer",
        "--TRACER",
        "--Tracer",
        "-chat",
        "-CHAT",
        "-cHaT",
        "-installautostart",
        "-INSTALLAUTOSTART",
    ],
)
def test_typed_flag_casing_resolves_to_the_mode(typed: str) -> None:
    """What `if /i` buys the owner: any casing of a known flag boots its mode.

    `_declared` folds case ONLY for a declaration that carries `/i`, so this fails
    both when a flag is missing and when its comparison is case-sensitive. Its pair,
    `test_every_mode_compares_case_insensitively`, reports the cause directly.
    """
    assert _resolve(typed) is not None, f"{typed!r} matches no mode; declared: {_flags()}"


def test_every_mode_ends_its_own_flow() -> None:
    """A mode that does not `exit /b` silently continues into the full-stack boot.

    Red: the new `-Chat` block falls through. Green: every mode block terminates
    itself, exactly as both existing blocks do.
    """
    modes = _modes(BAT.read_text(encoding="utf-8"))
    falling_through = [
        mode.flag
        for mode in modes
        if "exit /b" not in mode.body.lower() and "goto" not in mode.body.lower()
    ]
    assert not falling_through, f"these modes fall through to sara.ps1: {falling_through}"


def test_no_flag_fallthrough_still_boots_the_full_stack() -> None:
    """`sara.bat` with no mode is the double-click full-stack boot — unchanged."""
    text = BAT.read_text(encoding="utf-8")
    calls = [
        line
        for line in text.splitlines()
        if "sara.ps1" in line and not line.lstrip().lower().startswith("rem")
    ]
    assert len(calls) == 1, f"expected one sara.ps1 call line, found {calls}"
    assert "%*" in calls[0], f"the fall-through must forward %*: {calls[0]!r}"
    assert not any("sara.ps1" in mode.body for mode in _modes(text)), (
        "sara.ps1 is the default path only — a mode block must not call it"
    )


@pytest.mark.parametrize("param", ["-Port", "-StopOnly", "-Force"])
def test_powershell_launcher_flags_are_untouched(param: str) -> None:
    """Item A's non-goal: no new PowerShell logic. `sara.ps1` keeps its three flags."""
    ps1 = PS1.read_text(encoding="utf-8")
    head = ps1.split(")", 1)[0] if ps1.startswith("param(") else ps1[:400]
    assert param in head, f"sara.ps1 no longer declares {param}; param block:\n{head}"
